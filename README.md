# EAG V3 — Session 7: Shopping RAG (India / INR)

**Author:** Padmanabh  
**Repository:** [github.com/padmanabh275/EAGV3_Session7](https://github.com/padmanabh275/EAGV3_Session7)

Session 7 deliverable: **vector memory + FAISS** over a 55-product Indian e-commerce corpus, **llm_gatewayV7** for embed/chat, a **PriceCompare India** web UI, and recorded **evaluation traces** (with vs without corpus).

## Repository layout

| Path | Description |
|------|-------------|
| `llm_gatewayV7/` | Gateway V7 (embed + chat, port **8107**) |
| `S7code/` | Agent, MCP server, shopping RAG, corpus scripts |
| `submission/` | **Submission bundle** — manifest + traces |
| `S7code/docs/SHOPPING_RAG.md` | Full setup, eval design, UI, Add-to-RAG workflow |

## Quick start

```powershell
# 1) Gateway
cd llm_gatewayV7
.\run.ps1

# 2) Corpus + index
cd ..\S7code
uv sync
uv run python scripts/build_shopping_corpus.py
uv run python scripts/index_shopping_corpus.py --fresh

# 3) Web UI → http://127.0.0.1:8765
uv run python scripts/run_shopping_web.py

# 4) Regenerate submission traces (gateway running)
uv run python scripts/run_submission_traces.py
```

Copy `.env.example` → `.env` and set provider API keys (see `llm_gatewayV7/README.md`).

---

## Corpus manifest

**55 products** (INR / India). Submission snapshot:

[`submission/corpus_manifest.json`](submission/corpus_manifest.json)

| # | Slug | SKU | Role |
|---|------|-----|------|
| 1–4 | quietwave-pro … letterplay-softblocks | — | Eval anchors |
| 5–8 | brewmaster-12 … terra-blender-pro | — | Base trace products |
| 9–55 | skydrone-mini … frost-chest-7cu-v5 | — | Extended catalog |

---

## Eight base traces

Keyword lookups with **RAG on** — one per first eight manifest products.

| ID | Product | Expected anchors |
|----|---------|------------------|
| b01 | quietwave-pro | ₹15,999, Flipkart |
| b02 | voltendure-a54 | ₹36,499, Vijay Sales |
| b03 | portacharge-mini | ₹899, Snapdeal |
| b04 | letterplay-softblocks | ₹1,699, Amazon |
| b05 | brewmaster-12 | ₹6,499, Reliance |
| b06 | nova-laptop-14 | ₹59,399, Flipkart |
| b07 | pulse-watch-s | ₹11,779, Reliance |
| b08 | terra-blender-pro | ₹8,199, Vijay |

**Files:** [`submission/traces/base/`](submission/traces/base/)

---

## Five custom traces (with / no-corpus)

From [`S7code/eval/shopping_queries.json`](S7code/eval/shopping_queries.json). Each JSON has `with_corpus`, `no_corpus`, and `comparison.discriminates`.

| ID | Type | With corpus | Without corpus |
|----|------|-------------|----------------|
| q1 | Semantic | QuietWave + Flipkart ₹15,999 | No exact promo |
| q2 | Semantic | VoltEndure + ₹36,499 | No catalog price |
| q3 | Keyword | SKU → ₹15,999 | Cannot verify |
| q4 | Keyword | Snapdeal ₹899 | No Snapdeal pair |
| q5 | Semantic | LetterPlay + ₹1,699 | Generic toys only |

**Files:** [`submission/traces/custom/`](submission/traces/custom/)  
**Design notes:** [`S7code/docs/SHOPPING_RAG.md`](S7code/docs/SHOPPING_RAG.md) (eval section)

---

## Short video

Record **2–4 minutes** and submit the link to your course portal. Outline: [`submission/VIDEO.md`](submission/VIDEO.md)

Suggested demo: gateway dashboard → base SKU query → **A/B Compare** on semantic q1 → optional **Add to RAG**.

---

## Tests

| Suite | Command |
|-------|---------|
| Embed | `cd llm_gatewayV7 && uv run pytest -v tests/test_embed.py` |
| MCP | `cd S7code && uv run pytest -v test_mcp_server.py` |
| Report | `llm_gatewayV7/test.md` |

Synthetic catalog only — verify live prices on retailer sites.
