#!/usr/bin/env python3
"""Generate submission traces (8 base + 5 custom with/without corpus).

From S7code/:
    uv run python scripts/run_submission_traces.py

Requires llm_gatewayV7 on :8107 and indexed corpus.
Writes to ../submission/traces/
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]  # S7code/
ROOT = HERE.parent  # repo root (S7/)
SUBMISSION = ROOT / "submission"
MANIFEST_SRC = HERE / "sandbox" / "corpus" / "manifest.json"
EVAL = HERE / "eval" / "shopping_queries.json"

sys.path.insert(0, str(HERE))

from shopping_rag.service import ask, catalog_stats, search  # noqa: E402

# Eight base traces: first eight manifest slugs, keyword-style SKU/retailer lookups
BASE_QUERIES: list[dict] = [
    {
        "id": "b01",
        "slug": "quietwave-pro",
        "query": "What is Flipkart's INR price for SKU ELEC-HEAD-8842 (QuietWave Pro)?",
        "must_contain": ["15,999", "Flipkart"],
    },
    {
        "id": "b02",
        "slug": "voltendure-a54",
        "query": "What does Vijay Sales charge in INR for the VoltEndure A54 (SKU PHON-AND-5521)?",
        "must_contain": ["36,499", "Vijay Sales"],
    },
    {
        "id": "b03",
        "slug": "portacharge-mini",
        "query": "List the Snapdeal INR price for PortaCharge Mini 5000.",
        "must_contain": ["899", "Snapdeal"],
    },
    {
        "id": "b04",
        "slug": "letterplay-softblocks",
        "query": "What is the Amazon.in INR price for LetterPlay SoftBlocks (SKU TOY-EDU-7720)?",
        "must_contain": ["1,699", "Amazon"],
    },
    {
        "id": "b05",
        "slug": "brewmaster-12",
        "query": "What is Reliance Digital's INR price for BrewMaster 12-Cup Thermal SKU HOME-KET-3310?",
        "must_contain": ["6,499", "Reliance"],
    },
    {
        "id": "b06",
        "slug": "nova-laptop-14",
        "query": "What is Flipkart's INR price for NovaBook 14 SKU COMP-LAP-1001?",
        "must_contain": ["59,399", "Flipkart"],
    },
    {
        "id": "b07",
        "slug": "pulse-watch-s",
        "query": "What is Reliance Digital's INR price for PulseWatch S SKU WEAR-FT-2202?",
        "must_contain": ["11,779", "Reliance"],
    },
    {
        "id": "b08",
        "slug": "terra-blender-pro",
        "query": "What is Vijay Sales' exact INR price for SKU KIT-APP-3303?",
        "must_contain": ["8,199", "Vijay"],
    },
]


def _norm(text: str) -> str:
    return text.lower().replace("\u2013", "-").replace("\u2014", "-")


def _check_must_contain(text: str, needles: list[str]) -> dict[str, bool]:
    t = _norm(text)
    out: dict[str, bool] = {}
    for n in needles:
        needle = _norm(n)
        out[n] = needle in t or needle.replace("portacharge", "portacharge mini") in t
    return out


def _anchor_pass(checks: dict[str, bool], needles: list[str]) -> bool:
    """Pass if at least 2/3 of anchors match (short answers may omit SKU/brand)."""
    if not needles:
        return True
    hits = sum(1 for n in needles if checks.get(n))
    need = len(needles) if len(needles) <= 2 else max(2, (len(needles) * 2 + 2) // 3)
    return hits >= need


def _price_anchors(needles: list[str]) -> list[str]:
    """INR promo amounts only (exclude SKUs like ELEC-HEAD-8842)."""
    return [n for n in needles if "," in n]


def _discriminates(
    w_checks: dict[str, bool],
    n_checks: dict[str, bool],
    needles: list[str],
) -> bool:
    prices = _price_anchors(needles)
    if prices:
        with_ok = all(w_checks.get(p, False) for p in prices)
        no_ok = any(n_checks.get(p, False) for p in prices)
        return with_ok and not no_ok
    return _anchor_pass(w_checks, needles) and not _anchor_pass(n_checks, needles)


def _run_trace(query: str, *, use_index: bool, top_k: int = 6) -> dict:
    result = ask(query, use_index=use_index, top_k=top_k)
    sources = result.get("sources") or []
    return {
        "use_index": use_index,
        "answer": result.get("answer", ""),
        "provider": result.get("provider"),
        "model": result.get("model"),
        "source_count": len(sources),
        "top_sources": [
            {
                "rank": s.get("rank"),
                "source": s.get("source"),
                "indexed_from": s.get("indexed_from"),
                "chunk_preview": (s.get("chunk") or "")[:280],
            }
            for s in sources[:4]
        ],
    }


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stats = catalog_stats()

    # Copy manifest for submission (products only)
    if MANIFEST_SRC.is_file():
        manifest = json.loads(MANIFEST_SRC.read_text(encoding="utf-8"))
        SUBMISSION.mkdir(parents=True, exist_ok=True)
        out_manifest = {
            "generated_at": ts,
            "market": "India",
            "currency": "INR",
            "product_count": len(manifest),
            "products": manifest,
        }
        (SUBMISSION / "corpus_manifest.json").write_text(
            json.dumps(out_manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    meta = {"generated_at": ts, "catalog_stats": stats, "gateway": "llm_gatewayV7 :8107"}

    base_dir = SUBMISSION / "traces" / "base"
    for spec in BASE_QUERIES:
        print(f"[base] {spec['id']} {spec['slug']}...")
        with_corpus = _run_trace(spec["query"], use_index=True)
        checks = _check_must_contain(with_corpus["answer"], spec["must_contain"])
        trace = {
            **meta,
            "trace_id": spec["id"],
            "type": "base",
            "slug": spec["slug"],
            "query": spec["query"],
            "must_contain": spec["must_contain"],
            "pass_checks": checks,
            "pass": _anchor_pass(checks, spec["must_contain"]),
            "with_corpus": with_corpus,
        }
        _write(base_dir / f"{spec['id']}_{spec['slug']}.json", trace)

    custom_dir = SUBMISSION / "traces" / "custom"
    eval_queries = json.loads(EVAL.read_text(encoding="utf-8"))
    for spec in eval_queries:
        qid = spec["id"].split("_")[0]  # q1_semantic... -> q1
        print(f"[custom] {qid}...")
        with_corpus = _run_trace(spec["query"], use_index=True)
        no_corpus = _run_trace(spec["query"], use_index=False)
        w_checks = _check_must_contain(with_corpus["answer"], spec["must_contain"])
        n_checks = _check_must_contain(no_corpus["answer"], spec["must_contain"])
        discriminates = _discriminates(w_checks, n_checks, spec["must_contain"])
        trace = {
            **meta,
            "trace_id": qid,
            "eval_id": spec["id"],
            "type": spec.get("type", "custom"),
            "query": spec["query"],
            "expected_sources": spec.get("expected_sources"),
            "must_contain": spec["must_contain"],
            "with_corpus": {
                **with_corpus,
                "pass_checks": w_checks,
                "pass": _anchor_pass(w_checks, spec["must_contain"]),
            },
            "no_corpus": {
                **no_corpus,
                "pass_checks": n_checks,
                "pass": _anchor_pass(n_checks, spec["must_contain"]),
                "expected_fail": True,
            },
            "comparison": {
                "with_passes": _anchor_pass(w_checks, spec["must_contain"]),
                "no_passes": _anchor_pass(n_checks, spec["must_contain"]),
                "discriminates": discriminates,
            },
        }
        _write(custom_dir / f"{qid}_{spec['id']}.json", trace)

    print(f"\nWrote traces under {SUBMISSION / 'traces'}")


if __name__ == "__main__":
    main()
