#!/usr/bin/env python3
"""Index all product markdown files into FAISS memory (fact chunks).

Run from S7code/ (gateway V7 must be up for embeddings):
    uv run python scripts/build_shopping_corpus.py
    uv run python scripts/index_shopping_corpus.py
    uv run python scripts/index_shopping_corpus.py --fresh   # wipe memory first
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from gateway import ensure_gateway  # noqa: E402
import memory  # noqa: E402

PRODUCTS_DIR = HERE / "sandbox" / "corpus" / "products"
CHUNK_SIZE = 120  # words — one product sheet ≈ one chunk
OVERLAP = 20


def _chunk_text(text: str, size: int, overlap: int) -> list[str]:
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


def index_file(rel_path: str, *, run_id: str) -> int:
    p = HERE / "sandbox" / rel_path
    if not p.is_file():
        raise FileNotFoundError(p)
    text = p.read_text(encoding="utf-8")
    source = f"sandbox:{rel_path}"
    chunks = _chunk_text(text, CHUNK_SIZE, OVERLAP)
    indexed = 0
    for i, chunk in enumerate(chunks):
        preview = chunk[:120].replace("\n", " ")
        descriptor = f"[{source} chunk {i + 1}/{len(chunks)}] {preview}"
        memory.add_fact(
            descriptor=descriptor,
            value={
                "chunk": chunk,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "source": source,
                "product_slug": p.stem,
            },
            source=source,
            run_id=run_id,
        )
        indexed += 1
    return indexed


def main() -> None:
    parser = argparse.ArgumentParser(description="Index shopping product corpus into FAISS")
    parser.add_argument("--fresh", action="store_true", help="Clear memory.json + FAISS before indexing")
    args = parser.parse_args()

    if not PRODUCTS_DIR.is_dir():
        print(f"Missing {PRODUCTS_DIR}. Run: uv run python scripts/build_shopping_corpus.py")
        sys.exit(1)

    ensure_gateway()
    if args.fresh:
        memory.clear()
        print("[index] cleared existing memory + FAISS")

    files = sorted(PRODUCTS_DIR.glob("*.md"))
    if len(files) < 50:
        print(f"Warning: only {len(files)} product files (expected 50+)")

    run_id = f"shopping-index-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    total_chunks = 0
    for path in files:
        rel = path.relative_to(HERE / "sandbox").as_posix()
        n = index_file(rel, run_id=run_id)
        total_chunks += n
        print(f"  indexed {rel}: {n} chunk(s)")

    print(f"\nDone: {len(files)} products, {total_chunks} chunks (run_id={run_id})")


if __name__ == "__main__":
    main()
