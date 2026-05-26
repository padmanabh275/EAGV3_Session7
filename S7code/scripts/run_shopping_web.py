#!/usr/bin/env python3
"""Start the Shopping RAG web UI.

From S7code/:
    uv run python scripts/run_shopping_web.py

Requires:
  - llm_gatewayV7 on http://localhost:8107
  - Indexed corpus: uv run python scripts/index_shopping_corpus.py --fresh

Open http://127.0.0.1:8765
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "shopping_rag.api:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
    )
