"""Core RAG logic for the India shopping catalog (shared by CLI and web API)."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from gateway import AGENT_LLM_PROVIDER, LLM, GATEWAY_URL, ensure_gateway
import memory
from vector_index import VectorIndex

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "sandbox" / "corpus" / "manifest.json"
EVAL_QUERIES = ROOT / "eval" / "shopping_queries.json"
STATE_DIR = ROOT / "state"


def catalog_stats() -> dict[str, Any]:
    products = 0
    if MANIFEST.is_file():
        products = len(json.loads(MANIFEST.read_text(encoding="utf-8")))
    idx = VectorIndex(STATE_DIR)
    facts = sum(1 for _ in _iter_facts())
    return {
        "products": products,
        "indexed_chunks": idx.size,
        "fact_records": facts,
        "currency": "INR",
        "market": "India",
    }


def _iter_facts():
    path = STATE_DIR / "memory.json"
    if not path.is_file():
        return
    for row in json.loads(path.read_text(encoding="utf-8")):
        if row.get("kind") == "fact":
            yield row


def sample_queries() -> list[dict[str, str]]:
    if EVAL_QUERIES.is_file():
        return json.loads(EVAL_QUERIES.read_text(encoding="utf-8"))
    return []


def _source_group_key(source: str) -> str:
    """Collapse user-note timestamps and product variant files (slug-v2.md → slug)."""
    if "user-notes/" in source:
        name = source.rsplit("/", 1)[-1]
        return re.sub(r"-\d{8}-\d{6}\.md$", "", name)
    if "products/" in source:
        name = source.rsplit("/", 1)[-1]
        return re.sub(r"-v\d+\.md$", ".md", name).removesuffix(".md")
    return source


def _extract_answer_section(text: str) -> str:
    if "## Answer" in text:
        part = text.split("## Answer", 1)[1]
        return part.split("---", 1)[0].strip()
    if "Answer:\n" in text:
        return text.split("Answer:\n", 1)[1].strip()
    return text.strip()


def _query_note_relevance(query: str, user_query: str | None) -> float:
    if not user_query:
        return 0.0
    qt = set(re.findall(r"\w+", query.lower())) - {"the", "and", "for", "what", "who", "which", "inr"}
    ut = set(re.findall(r"\w+", user_query.lower())) - {"the", "and", "for", "what", "who", "which", "inr"}
    if not qt or not ut:
        return 0.0
    return len(qt & ut) / len(qt)


def _merge_hits(hits: list, *, top_k: int, query: str = "") -> list[dict[str, Any]]:
    """Dedupe by source group; merge multi-chunks; preserve hybrid retrieval order."""
    groups: dict[str, list[tuple[Any, dict, int]]] = {}
    order: list[str] = []
    for rank, item in enumerate(hits):
        val = item.value or {}
        key = _source_group_key(item.source or item.id)
        if key not in groups:
            order.append(key)
            groups[key] = []
        groups[key].append((item, val, rank))

    merged: list[dict[str, Any]] = []
    for key in order:
        items = sorted(groups[key], key=lambda x: (x[1].get("chunk_index") or 0, x[2]))
        item0, val0, best_rank = items[0]
        parts = [v.get("chunk") or "" for _, v, _ in items]
        full = "\n".join(p for p in parts if p).strip() or item0.descriptor
        indexed_from = val0.get("indexed_from")
        user_query = val0.get("user_query")
        if indexed_from == "without_rag":
            body = _extract_answer_section(full)
            full = (
                f"[User-indexed note — general guidance, verify live prices]\n"
                f"Query: {user_query or 'unknown'}\n\n{body}"
            )
        merged.append(
            {
                "id": item0.id,
                "source": item0.source,
                "descriptor": item0.descriptor,
                "chunk": full,
                "product_slug": val0.get("product_slug"),
                "chunk_index": val0.get("chunk_index"),
                "indexed_from": indexed_from,
                "user_query": user_query,
                "retrieval_rank": min(r for _, _, r in items),
            }
        )

    # Keep hybrid retrieval order; push irrelevant user-notes to the tail
    def _sort_key(s: dict[str, Any]) -> tuple:
        rank = s.get("retrieval_rank", 999)
        if s.get("indexed_from") == "without_rag":
            rel = _query_note_relevance(query, s.get("user_query"))
            if rel < 0.25:
                return (1, rank + 10_000)
        return (0, rank)

    merged.sort(key=_sort_key)
    for i, row in enumerate(merged[:top_k], 1):
        row["rank"] = i
    return merged[:top_k]


def search(query: str, *, top_k: int = 6) -> list[dict[str, Any]]:
    """Hybrid retrieval: vector similarity + keyword overlap, then merge/dedupe."""
    ensure_gateway()
    fetch_k = max(top_k * 4, 24)
    vec_hits = memory._vector_search(query, kinds=["fact"], top_k=fetch_k)  # noqa: SLF001
    kw_hits = memory._keyword_search(query, None, kinds=["fact"], top_k=fetch_k)  # noqa: SLF001
    seen: set[str] = set()
    combined = []
    for item in kw_hits + vec_hits:
        if item.id in seen:
            continue
        seen.add(item.id)
        combined.append(item)
    if not combined:
        combined = memory.read(query, kinds=["fact"], top_k=fetch_k)
    return _merge_hits(combined, top_k=top_k, query=query)


def ask(
    query: str,
    *,
    use_index: bool = True,
    top_k: int = 6,
) -> dict[str, Any]:
    ensure_gateway()
    sources = search(query, top_k=top_k) if use_index else []
    llm = LLM()

    if use_index:
        context = _format_hits(sources)
        has_user_notes = any(s.get("indexed_from") == "without_rag" for s in sources)
        if has_user_notes:
            system = (
                "You are a shopping assistant for the Indian market using retrieved excerpts.\n"
                "- For **product catalog** excerpts: cite retailer names and INR (₹) exactly as written.\n"
                "- For **user-indexed notes** (marked general guidance): summarize brands and "
                "recommendations from those notes even when exact ₹ prices are not listed. "
                "Say prices should be verified on Flipkart, Amazon.in, etc.\n"
                "- Do NOT reply 'Not in catalog index' if user-indexed notes answer the question.\n"
                "- Only say 'Not in catalog index' when neither catalog nor user notes cover the topic.\n\n"
                f"--- RETRIEVED EXCERPTS ---\n{context}\n--- END ---"
            )
        else:
            system = (
                "You are a shopping price-comparison assistant for the Indian market. "
                "Answer ONLY using the retrieved product excerpts below. Cite retailer "
                "names and INR amounts (₹) exactly as written. If the excerpts do not "
                "contain the answer, say 'Not in catalog index' and do not guess.\n\n"
                f"--- RETRIEVED CATALOG ---\n{context}\n--- END ---"
            )
    else:
        system = (
            "You are a shopping assistant for India. You do NOT have access to a product "
            "catalog. Answer from general knowledge only. If you are not certain of an "
            "exact SKU price in INR or a store listing, say you cannot verify without "
            "the catalog."
        )

    resp = llm.chat(
        messages=[{"role": "user", "content": query}],
        system=system,
        provider=AGENT_LLM_PROVIDER,
        max_tokens=512,
        temperature=0,
    )
    return {
        "answer": (resp.get("text") or "").strip(),
        "use_index": use_index,
        "sources": sources,
        "provider": resp.get("provider"),
        "model": resp.get("model"),
    }


def health() -> dict[str, Any]:
    gateway_ok = False
    try:
        import httpx

        httpx.get(f"{GATEWAY_URL}/v1/embedders", timeout=2.0)
        gateway_ok = True
    except Exception:
        pass
    stats = catalog_stats()
    return {
        "gateway_url": GATEWAY_URL,
        "gateway_ok": gateway_ok,
        "index_ready": stats["indexed_chunks"] > 0,
        **stats,
    }


def _format_hits(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return "(no retrieved product chunks)"
    blocks = []
    for s in sources:
        blocks.append(f"[{s['rank']}] source={s['source']}\n{s['chunk']}")
    return "\n\n".join(blocks)


def _chunk_text(text: str, size: int = 120, overlap: int = 20) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    stride = max(1, size - overlap)
    i = 0
    while i < len(words):
        chunks.append(" ".join(words[i : i + size]))
        if i + size >= len(words):
            break
        i += stride
    return chunks


def _slugify(text: str, max_len: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:max_len] or "note").strip("-")


def index_qa_pair(
    query: str,
    answer: str,
    *,
    title: str | None = None,
    chunk_size: int = 120,
    overlap: int = 20,
) -> dict[str, Any]:
    """Save a query+answer pair into FAISS (and sandbox markdown) for future RAG retrieval."""
    ensure_gateway()
    query = query.strip()
    answer = answer.strip()
    if not query or not answer:
        raise ValueError("Both query and answer are required to index")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = _slugify(title or query)
    rel_path = f"corpus/user-notes/{slug}-{ts}.md"
    abs_path = ROOT / "sandbox" / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    body = (
        f"# {title or 'User indexed note'}\n\n"
        f"**Original query:** {query}\n\n"
        f"**Source:** General knowledge (indexed by user for RAG)\n"
        f"**Indexed at:** {ts}\n\n"
        f"## Answer\n\n{answer}\n\n"
        f"---\n"
        f"*User-added catalog entry. Verify live prices on Flipkart, Amazon.in, etc.*\n"
    )
    abs_path.write_text(body, encoding="utf-8")
    source = f"sandbox:{rel_path}"

    # Embed query+answer directly so retrieval returns the guidance, not just headers.
    embed_doc = f"Query: {query}\n\nAnswer:\n{answer}"
    words = embed_doc.split()
    if len(words) <= 400:
        chunks = [embed_doc]
    else:
        chunks = _chunk_text(embed_doc, chunk_size=200, overlap=40)

    q_tokens = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2][:12]
    run_id = f"user-index-{ts}"
    indexed = 0
    for i, chunk in enumerate(chunks):
        preview = chunk[:120].replace("\n", " ")
        descriptor = f"[user-note] Q: {query[:80]} | {preview}"
        memory.add_fact(
            descriptor=descriptor,
            keywords=q_tokens,
            value={
                "chunk": chunk,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "source": source,
                "user_query": query,
                "indexed_from": "without_rag",
            },
            source=source,
            run_id=run_id,
        )
        indexed += 1

    return {
        "ok": True,
        "path": rel_path,
        "source": source,
        "chunks_indexed": indexed,
        "slug": slug,
        **catalog_stats(),
    }
