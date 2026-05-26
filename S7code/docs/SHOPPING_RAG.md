# Shopping Price Comparison RAG — India (INR)

A retrieval-grounded **Indian e-commerce catalog assistant**: 55 synthetic SKU sheets with **INR (₹)** prices and retailers (Flipkart, Amazon.in, Croma, etc.), FAISS index via `memory.add_fact`, answers through **gateway V7** chat with retrieved chunks only.

## Architecture

```text
sandbox/corpus/products/*.md   (55 items, Market: India)
        │
        ▼  scripts/index_shopping_corpus.py  (embed via POST /v1/embed)
state/memory.json + state/index.faiss
        │
        ▼  memory.read(query)  — vector search over fact chunks
scripts/shopping_ask.py  — build prompt + LLM().chat()
        │
        ▼
llm_gatewayV7  (port 8107)
```

## Setup

```powershell
cd S7\llm_gatewayV7
.\run.ps1

cd ..\S7code
uv sync
uv run python scripts/build_shopping_corpus.py
uv run python scripts/index_shopping_corpus.py --fresh
```

## Web frontend

```powershell
# Terminal 1 — gateway
cd S7\llm_gatewayV7
.\run.ps1

# Terminal 2 — web UI (after index)
cd S7\S7code
uv sync
uv run python scripts/run_shopping_web.py
```

Open **http://127.0.0.1:8765** — refresh the page if the server was already running.

**UI features:** saffron/green/navy theme · light/dark toggle · stats cards · tabbed Answer / Sources / A/B Compare · expandable source cards · ₹ price highlighting · query history · copy answer · eval query badges (semantic/keyword) · toast notifications · skeleton loading · **Add to RAG** (index without-catalog answers) · **Retry with RAG** after indexing.

### Grow the catalog from answers

When RAG returns **“Not in catalog index”** (or you run **A/B Compare**), the **Without index** side has useful general knowledge. You can save it into FAISS:

1. Run **A/B** or **Get answer** with RAG off (plain mode).
2. Click **Add to RAG** on the Answer tab, or **+ Index** on the compare column.
3. Chunk count in the header updates; files land in `sandbox/corpus/user-notes/`.
4. After indexing, **With RAG** refreshes automatically (or use **↻ Refresh** / **Retry with RAG**).

**Tip:** Run **A/B Compare** before **+ Index** — indexing only saves the *Without index* column text; the compare panels stay empty until A/B has run at least once.

```http
POST /api/index-answer
{ "query": "...", "answer": "...", "title": "optional" }
```

User-added notes are tagged `indexed_from: without_rag` in memory metadata. Verify live INR prices on retailer sites before trusting indexed text.

**Why “Not in catalog index” after indexing?** Older indexes stored mostly metadata headers; the app now merges user-note chunks and uses a relaxed prompt for user-indexed guidance (brands/recommendations without exact ₹). Restart the web server after pulling updates, hard-refresh the browser, then click **↻ Refresh** on With RAG.

| Component | Path |
|-----------|------|
| API | `shopping_rag/api.py` |
| Service | `shopping_rag/service.py` |
| UI | `shopping_rag/static/` |

## CLI (with vs without index)

```powershell
# PASS: uses retrieved INR prices from catalog
uv run python scripts/shopping_ask.py "What is Flipkart's exact INR price for SKU ELEC-HEAD-8842?"

# FAIL (control): model must guess or refuse
uv run python scripts/shopping_ask.py --no-index "What is Flipkart's exact INR price for SKU ELEC-HEAD-8842?"
```

## Eval queries (5) — India / INR

| ID | Type | Query (short) | Gold source | Expected answer (with index) |
|----|------|---------------|-------------|----------------------------|
| q1 | **Semantic** | Commuter rail + IT park noise + Flipkart INR | `quietwave-pro.md` | QuietWave Pro; **Flipkart ₹15,999** |
| q2 | **Semantic** | ~2-day battery phone, cheapest in India | `voltendure-a54.md` | VoltEndure A54; **Vijay Sales ₹36,499** |
| q3 | Keyword | Flipkart INR for `ELEC-HEAD-8842` | `quietwave-pro.md` | **₹15,999** on Flipkart |
| q4 | Keyword | Who sells PortaCharge Mini at **₹899** | `portacharge-mini.md` | **Snapdeal ₹899** |
| q5 | **Semantic** | Toddler letter-shape gift + INR | `letterplay-softblocks.md` | LetterPlay; **Amazon.in ₹1,699** |

Full spec: `eval/shopping_queries.json`

### Semantic vs keyword

- **q1, q2, q5:** Query wording must not appear verbatim in gold chunks (`must_not_appear_in_gold_chunk`).
- **q3, q4:** Require exact **SKU / ₹ / retailer** from the index.

### Without index (control)

Runs should omit exact promo prices (₹899, ₹15,999), confuse SKUs, or say the catalog is unavailable.

## Indian retailers in corpus

Flipkart, Amazon.in, Croma, Reliance Digital, Vijay Sales, Tata Cliq, Snapdeal, JioMart, FirstCry, Hamleys India, Reliance Smart Bazaar.

## Corpus stats

| Metric | Value |
|--------|-------|
| Product files | 55 |
| Currency | **INR (₹)** only |
| Locale | India (230V, BIS, metro/commuter context) |

## Files

| Path | Role |
|------|------|
| `scripts/build_shopping_corpus.py` | Generate 55 India/INR product sheets |
| `scripts/index_shopping_corpus.py` | Embed + FAISS index |
| `scripts/shopping_ask.py` | RAG Q&A CLI |
| `eval/shopping_queries.json` | Five eval queries |

---

*After editing corpus: `uv run python scripts/build_shopping_corpus.py` then `uv run python scripts/index_shopping_corpus.py --fresh`*
