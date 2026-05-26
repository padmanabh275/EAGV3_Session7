# Short video script — Session 7 submission

**Target length:** 2–4 minutes  
**Title suggestion:** *EAG S7 — PriceCompare India RAG (55 products, FAISS, gateway V7)*

## Before recording

1. Start gateway: `cd llm_gatewayV7 && .\run.ps1`
2. Index corpus: `cd S7code && uv run python scripts/index_shopping_corpus.py --fresh`
3. Start UI: `uv run python scripts/run_shopping_web.py` → http://127.0.0.1:8765

## Scene 1 — Intro (20 s)

- Show repo README on GitHub: manifest + `submission/traces/`
- One line: *55 INR product sheets, FAISS memory, gateway V7 embed + chat*

## Scene 2 — Gateway (30 s)

- Open `http://localhost:8107` dashboard
- Point at providers + embedders online

## Scene 3 — Base trace (45 s)

- Web UI or terminal:
  ```powershell
  uv run python scripts/shopping_ask.py "What is Flipkart's exact INR price for SKU ELEC-HEAD-8842?"
  ```
- Show answer **₹15,999** and **Sources** tab hitting `quietwave-pro.md`
- Mention: `submission/traces/base/b01_quietwave-pro.json`

## Scene 4 — Custom trace + no-corpus (60 s)

- Load eval query q1 (semantic commute / noise) from sidebar chips
- Click **A/B Compare**
- **With RAG:** QuietWave Pro + Flipkart ₹15,999  
- **Without index:** generic Sony/Bose advice, no catalog price
- Optional: open `submission/traces/custom/q1_*.json` and highlight `comparison.discriminates: true`

## Scene 5 — Wrap (15 s)

- Stats card: 55 products, ~57 indexed chunks
- Link to GitHub repo

## Upload checklist

- [ ] Video link in course submission form
- [ ] Same link added to GitHub README (optional line under **Short video**)
- [ ] Repo public or accessible to instructors
