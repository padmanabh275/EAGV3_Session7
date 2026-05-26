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

## Eval design — five corpus queries

These five queries are the acceptance tests for the shopping RAG stack. Each is designed so that:

| Criterion | With index (`use_index=true`) | Without index (`--no-index` / RAG off) |
|-----------|--------------------------------|----------------------------------------|
| **Pass** | Answer cites the correct product, retailer, and **exact INR** from the indexed chunk | — |
| **Fail** | — | Omits fabricated promo prices, wrong SKU/retailer pairing, or states the catalog is unavailable |
| **Semantic (≥2)** | Retrieval must match by **meaning**, not shared keywords between query and gold chunk | Same — model has no catalog rows to ground on |

Machine-readable spec: [`eval/shopping_queries.json`](../eval/shopping_queries.json) (loaded by the web UI **Eval queries** panel).

Run every query both ways (CLI or **A/B Compare** in the UI):

```powershell
# PASS — RAG on
uv run python scripts/shopping_ask.py "<query>"

# FAIL — control
uv run python scripts/shopping_ask.py --no-index "<query>"
```

---

### Q1 — Semantic (commute / open-plan noise → headphones)

**Query (verbatim):**

> What audio gear cuts vibration from commuter rail and open-plan IT park desks, and what do Flipkart and rivals charge in rupees?

| Field | Value |
|-------|--------|
| **Gold source** | `sandbox/corpus/products/quietwave-pro.md` |
| **Product** | QuietWave Pro (`ELEC-HEAD-8842`) |
| **Pass anchors** | `QuietWave`, `15,999`, `Flipkart` |
| **Why semantic** | Query says *commuter rail*, *IT park desks*, *rivals charge in rupees* — corpus uses *Mumbai suburban local train*, *coworking bays*, *Flipkart: ₹15,999*. None of the query phrases appear verbatim in the gold chunk (`must_not_appear_in_gold_chunk` in JSON). |
| **With index** | Names QuietWave Pro; cites Flipkart **₹15,999** (and may mention Croma / Reliance Digital from the same chunk). |
| **Without index** | Cannot know the synthetic promo row; should refuse exact ₹15,999 or invent a wrong price. |

---

### Q2 — Semantic (multi-day battery phone)

**Query (verbatim):**

> I need a handset that can go about two days on a charge for light use — which listing fits, and who sells it cheapest in India?

| Field | Value |
|-------|--------|
| **Gold source** | `sandbox/corpus/products/voltendure-a54.md` |
| **Product** | VoltEndure A54 (`PHON-AND-5521`) |
| **Pass anchors** | `VoltEndure`, `48`, `36,499` (Vijay Sales lowest listed) |
| **Why semantic** | Query says *two days on a charge*, *cheapest in India*, *light use* — chunk says *48 hours typical mixed use*, *5200 mAh*, *Vijay Sales: ₹36,499*. Query wording does not appear in the chunk. |
| **With index** | Identifies VoltEndure A54; cites **₹36,499** at Vijay Sales (or compares Flipkart ₹36,999). |
| **Without index** | No access to Vijay Sales scrape; should not state ₹36,499 as fact. |

---

### Q3 — Keyword (exact SKU + retailer)

**Query (verbatim):**

> What is Flipkart's exact INR price for SKU ELEC-HEAD-8842?

| Field | Value |
|-------|--------|
| **Gold source** | `sandbox/corpus/products/quietwave-pro.md` |
| **Pass anchors** | `15,999`, `Flipkart`, `ELEC-HEAD-8842` |
| **Why keyword** | Requires literal SKU and retailer row from the sheet — strong lexical overlap with the chunk. |
| **With index** | **₹15,999** on Flipkart for QuietWave Pro. |
| **Without index** | SKU `ELEC-HEAD-8842` is synthetic; model should not guess ₹15,999. |

---

### Q4 — Keyword (product name + doorbuster ₹)

**Query (verbatim):**

> Which Indian retailer lists the PortaCharge Mini 5000 at ₹899?

| Field | Value |
|-------|--------|
| **Gold source** | `sandbox/corpus/products/portacharge-mini.md` |
| **Pass anchors** | `Snapdeal`, `899`, `PortaCharge` |
| **Why keyword** | Exact product name and promo price appear in the corpus line `Snapdeal: ₹899`. |
| **With index** | **Snapdeal** at **₹899**. |
| **Without index** | ₹899 Snapdeal pairing is corpus-specific; control run should not assert it confidently. |

---

### Q5 — Semantic (toddler literacy gift)

**Query (verbatim):**

> Birthday gift for a three-year-old starting to recognise letter shapes — which educational toy listing matches, and at what INR prices?

| Field | Value |
|-------|--------|
| **Gold source** | `sandbox/corpus/products/letterplay-softblocks.md` |
| **Product** | LetterPlay SoftBlocks (`TOY-EDU-7720`) |
| **Pass anchors** | `LetterPlay`, `24–48`, `1,699` (Amazon.in lowest in chunk) |
| **Why semantic** | Query says *birthday*, *three-year-old*, *recognise letter shapes*, *gift* — chunk says *24–48 months*, *pre-literacy*, *embossed … letter forms*. Query phrases are absent from the gold chunk. |
| **With index** | LetterPlay SoftBlocks; **Amazon.in ₹1,699** (or age band 24–48 months). |
| **Without index** | Should not fabricate Amazon.in ₹1,699 for this synthetic SKU. |

---

### Summary table

| ID | Type | Gold file | Decisive INR / retailer |
|----|------|-----------|-------------------------|
| q1 | Semantic | `quietwave-pro.md` | Flipkart **₹15,999** |
| q2 | Semantic | `voltendure-a54.md` | Vijay Sales **₹36,499** |
| q3 | Keyword | `quietwave-pro.md` | Flipkart **₹15,999** + SKU |
| q4 | Keyword | `portacharge-mini.md` | Snapdeal **₹899** |
| q5 | Semantic | `letterplay-softblocks.md` | Amazon.in **₹1,699** |

### Semantic vs keyword (quick reference)

- **Semantic (q1, q2, q5):** Paraphrased intent; `must_not_appear_in_gold_chunk` in JSON lists query phrases that must **not** appear verbatim in the answering chunk — proves recall is not mere keyword match.
- **Keyword (q3, q4):** Exact SKU, product name, or ₹ amount from the index is required; fails without the catalog row.

### Scoring a run

1. Rebuild index after corpus changes: `uv run python scripts/index_shopping_corpus.py --fresh`
2. For each query: **with index** → answer contains all `must_contain` strings from JSON; **without index** → missing those anchors or explicit “cannot verify” / wrong guess.
3. In the web UI: use **Eval queries** chips, then **A/B** — **With RAG** should pass, **Without index** should fail the same anchors.

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

For Tests Queries refer to - Tests Path - [Open file](https://github.com/padmanabh275/EAGV3_Session7/blob/master/llm_gatewayV7/test.md)
