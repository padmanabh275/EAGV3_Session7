#!/usr/bin/env python3
"""Shopping price-comparison RAG: retrieve product chunks, then answer via gateway.

Examples:
    uv run python scripts/shopping_ask.py "What is TechMart's price for SKU ELEC-HEAD-8842?"
    uv run python scripts/shopping_ask.py --no-index "What is TechMart's price for SKU ELEC-HEAD-8842?"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from shopping_rag.service import ask as _ask  # noqa: E402


def ask(query: str, *, use_index: bool, top_k: int = 6) -> str:
    return _ask(query, use_index=use_index, top_k=top_k)["answer"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Shopping RAG Q&A")
    parser.add_argument("query", help="Natural-language shopping question")
    parser.add_argument("--no-index", action="store_true", help="Control: answer without retrieval")
    parser.add_argument("-k", type=int, default=6, help="Top-k chunks when retrieving")
    args = parser.parse_args()

    mode = "NO INDEX (control)" if args.no_index else "WITH INDEX (RAG)"
    print(f"\n=== {mode} ===\n")
    answer = ask(args.query, use_index=not args.no_index, top_k=args.k)
    print(answer)
    print()


if __name__ == "__main__":
    main()
