# Submission bundle — Session 7

| Artifact | Path |
|----------|------|
| Corpus manifest (55 products) | [`corpus_manifest.json`](corpus_manifest.json) |
| Eight base traces (RAG on) | [`traces/base/`](traces/base/) |
| Five custom traces (with + no corpus) | [`traces/custom/`](traces/custom/) |
| Video outline | [`VIDEO.md`](VIDEO.md) |

## Regenerate traces

From `S7code/` with gateway on port 8107 and a fresh product index:

```powershell
uv run python scripts/index_shopping_corpus.py --fresh
uv run python scripts/run_submission_traces.py
```

Each trace JSON includes `generated_at`, `catalog_stats`, answers, top retrieved sources, `pass_checks`, and (for custom) `comparison.discriminates`.
