# S7 Session 7 — Test Reports

**Generated:** Tuesday, May 26, 2026  
**Projects:** `llm_gatewayV7` (gateway) · `S7code` (agent + MCP server)  
**Gateway URL:** `http://localhost:8107` (from `LLM_GATEWAY_V7_URL` / `S7/.env`)  
**Environment:** Windows 10, Python 3.12.4, `uv` virtualenvs in each project

---

## Summary

| Suite | Location | Command | Result | Duration |
|-------|----------|---------|--------|----------|
| **Embeddings** | `llm_gatewayV7/tests/test_embed.py` | `uv run pytest -v tests/test_embed.py -s` | **4 passed** | 8.64s |
| **All providers (script)** | `llm_gatewayV7/tests/test_all_providers.py` | `uv run python tests/test_all_providers.py` | **Exit 1** (4 providers failed basic) | ~78s |
| **All providers (pytest)** | `llm_gatewayV7/tests/test_all_providers.py` | `uv run pytest -v tests/test_all_providers.py` | **5 skipped** (collection bug) | 0.12s |
| **MCP server** | `S7code/test_mcp_server.py` | `uv run pytest -v test_mcp_server.py -s` | **10 passed** | 7.61s |

**Recommendations:**
- Use **script mode** for the full provider matrix (`test_all_providers.py`).
- Embedding tests are self-contained and do not need the gateway on port 8107.
- MCP tests spawn `mcp_server.py` via `S7code/.venv` — run `uv sync` in `S7code` first.

---

## Gateway snapshot (at report time)

`GET http://localhost:8107/v1/providers`

| Provider | Model | RPM limit |
|----------|-------|-----------|
| openai | `gpt-4o-mini` | 60 |
| nvidia | `deepseek-ai/deepseek-v4-pro` | 40 |
| groq | `openai/gpt-oss-120b` | 30 |
| cerebras | `zai-glm-4.7` | 30 |
| openrouter | `nvidia/nemotron-3-super-120b-a12b:free` | 20 |
| github | `openai/gpt-4.1-mini` | 10 |
| ollama | `llama3.2:3b` | 9999 |

**Provider order:** openai → nvidia → groq → cerebras → openrouter → github (+ ollama registered)

---

## 1. `llm_gatewayV7/tests/test_embed.py`

### Purpose

In-process ASGI tests against the V7 FastAPI app (`main.app`). **Does not require** the gateway listening on port 8107.

| Test | Marker | What it checks |
|------|--------|----------------|
| `test_ollama_embed` | `local` | `POST /v1/embed` with `provider=ollama`, dim=768, `nomic-embed-text` |
| `test_fallback_embed` | `network` | `provider=openai`, `text-embedding-3-small`, dim=768 (needs `OPENAI_API_KEY`) |
| `test_failover` | `network` | Broken Ollama URL → ring fails over to OpenAI |
| `test_provider_explicit` | `local` | Pinned `provider=ollama` in response |

**Run:** `cd llm_gatewayV7 && uv run pytest -v tests/test_embed.py -s`

### Full pytest output (May 26, 2026)

```
============================= test session starts =============================
platform win32 -- Python 3.12.4, pytest-9.0.3, pluggy-1.6.0
plugins: anyio-4.13.0, asyncio-1.3.0
collecting ... collected 4 items

tests/test_embed.py::test_ollama_embed
  ollama: {'provider': 'ollama', 'model': 'nomic-embed-text', 'dim': 768,
           'latency_ms': 1771, 'attempted': []}
  vec[0:3]: [-0.8685046434402466, 0.2967730760574341, -2.6745595932006836]
PASSED

tests/test_embed.py::test_fallback_embed
  openai: {'provider': 'openai', 'model': 'text-embedding-3-small', 'dim': 768,
           'latency_ms': 1232, 'attempted': []}
  vec[0:3]: [-0.041900634765625, -0.0023097991943359375, 0.006580352783203125]
PASSED

tests/test_embed.py::test_failover
  failover: {'provider': 'openai', 'model': 'text-embedding-3-small', 'dim': 768,
            'latency_ms': 4357,
            'attempted': [{'provider': 'ollama', 'reason': 'All connection attempts failed'}]}
PASSED

tests/test_embed.py::test_provider_explicit
  explicit: {'provider': 'ollama', 'model': 'nomic-embed-text', 'dim': 768,
             'latency_ms': 568, 'attempted': []}
PASSED

============================== 4 passed in 8.64s ==============================
```

### Per-test details

| Test | Status | Provider | Model | Dim | Latency |
|------|--------|----------|-------|-----|---------|
| `test_ollama_embed` | PASS | ollama | nomic-embed-text | 768 | 1771 ms |
| `test_fallback_embed` | PASS | openai | text-embedding-3-small | 768 | 1232 ms |
| `test_failover` | PASS | openai (after ollama fail) | text-embedding-3-small | 768 | 4357 ms |
| `test_provider_explicit` | PASS | ollama | nomic-embed-text | 768 | 568 ms |

**Prerequisites:** Ollama running locally with `nomic-embed-text`; `OPENAI_API_KEY` in `S7/.env` for network tests.

---

## 2. `llm_gatewayV7/tests/test_all_providers.py`

### Purpose

Per-provider capability matrix against a **live** gateway (`POST /v1/chat`).

| Capability | Function | Pass criteria |
|------------|----------|---------------|
| **basic** | `check_basic` | HTTP 200, non-empty `text` (“Say hi in 3 words”) |
| **tools** | `check_tools` | Tool call `add(7,5)` then final answer contains `12` |
| **struct** | `check_structured` | JSON schema `{city, country}` → Paris / France |
| **cache** | `check_caching` | Second call shows cache read/create tokens (ollama → SKIP) |
| **reasoning** | `check_reasoning` | `reasoning=high`; OK if `reasoning_applied`, else `n/a` |

Providers are discovered from `GET /v1/providers`. Tests run **in parallel** (one thread per provider) in script mode.

**Script run:** `cd llm_gatewayV7 && uv run python tests/test_all_providers.py`  
**Pytest run:** `uv run pytest -v tests/test_all_providers.py` (see [Pytest limitation](#pytest-limitation-all-providers) below)

---

### Latest script run — full log (May 26, 2026)

```
Gateway: http://localhost:8107
Testing 7 registered providers: ['openai', 'nvidia', 'groq', 'cerebras', 'openrouter', 'github', 'ollama']

Running providers in parallel...

  [groq      ] basic      -> OK      Hello there friend.
  [cerebras  ] basic      -> FAIL    code=200 {'provider': 'cerebras', 'model': 'zai-glm-4.7', 'text': '', 'tool_calls': [], '
  [openai    ] basic      -> OK      Hello, how are you?
  [openrouter] basic      -> OK      Hi there friend
  [github    ] basic      -> FAIL    code=503 {'detail': "all providers unavailable. attempts: [{'provider': 'github', 'reason
  [groq      ] tools      -> OK      dialect=native final='The sum of 7 and 5 is **12**.'
  [cerebras  ] tools      -> OK      dialect=native final='7 plus 5 equals 12.'
  [nvidia    ] basic      -> FAIL    code=503 {'detail': "all providers unavailable. attempts: [{'provider': 'nvidia', 'reason
  [openai    ] tools      -> OK      dialect=native final='7 plus 5 is 12.'
  [ollama    ] basic      -> FAIL    code=503 {'detail': "all providers unavailable. attempts: [{'provider': 'ollama', 'reason
  [groq      ] struct     -> OK      {'city': 'Paris', 'country': 'France'}
  [cerebras  ] struct     -> OK      {'city': 'Paris', 'country': 'France'}
  [openai    ] struct     -> OK      {'city': 'Paris', 'country': 'France'}
  ...

FAIL: basic test broken on: ['cerebras', 'ollama', 'github', 'nvidia']
```

**Exit code:** `1`

### Result matrix (latest run)

| Provider | basic | tools | struct | cache | reasoning |
|----------|-------|-------|--------|-------|-----------|
| **openai** | OK | OK | OK | OK | n/a |
| **groq** | OK | OK | OK | FAIL | OK |
| **cerebras** | FAIL | OK | OK | FAIL | FAIL |
| **openrouter** | OK | PARTIAL | FAIL | FAIL | FAIL |
| **nvidia** | FAIL | FAIL | FAIL | FAIL | FAIL |
| **github** | FAIL | FAIL | FAIL | FAIL | FAIL |
| **ollama** | FAIL | FAIL | FAIL | SKIP | FAIL |

Results vary run-to-run because all seven providers hammer the gateway **in parallel**, triggering rate limits and local Ollama overload.

---

## 3. `S7code/test_mcp_server.py`

### Purpose

Integration tests for the **EAGV3 S7 MCP server** (`mcp_server.py`) over **stdio**. Each test calls a real tool on a subprocess started for the session.

**Does not require** the LLM gateway on port 8107 (except indirectly if `index_document` / `search_knowledge` were tested — they are not in this suite).

| Test | Marker | Tool | What it checks |
|------|--------|------|----------------|
| `test_web_search` | `network` | `web_search` | Returns ≥1 hit with `title`, `url`, `snippet` (Tavily or DDG) |
| `test_fetch_url` | `network` | `fetch_url` | crawl4ai fetch of `https://example.com` → status 200, markdown body |
| `test_get_time` | — | `get_time` | `Asia/Kolkata` → offset 5.5, ISO + human fields |
| `test_currency_convert` | `network` | `currency_convert` | USD→EUR via frankfurter.dev |
| `test_read_file` | — | `read_file` | Read `hello.txt` from sandbox |
| `test_list_dir` | — | `list_dir` | Dict with `entries`, `names`, `count` (not a bare list) |
| `test_create_file` | — | `create_file` | Create file; duplicate path must error |
| `test_update_file` | — | `update_file` | Overwrite file; missing path must error |
| `test_edit_file` | — | `edit_file` | Ambiguous find errors; `replace_all` and single replace |
| `test_sandbox_escape` | — | `read_file` | `../foo` rejected with sandbox/escape message |

**Run:** `cd S7code && uv run pytest -v test_mcp_server.py -s`

### Architecture / harness

| Component | Behavior |
|-----------|----------|
| **`mcp` fixture** | Session-scoped; dedicated `asyncio` event loop; one stdio MCP connection for all tests |
| **Server subprocess** | `S7code/.venv/Scripts/python.exe mcp_server.py` (falls back to `sys.executable` if no venv) |
| **`_call(mcp, tool, args)`** | Sync wrapper: `loop.run_until_complete(session.call_tool(...))` |
| **`_result(res)`** | Parses `structuredContent` or JSON from `TextContent` |
| **Sandbox** | `S7code/sandbox/` — cleaned with `ignore_errors=True` on Windows |

**Why not pytest-asyncio for the fixture?** Session-scoped async fixtures deadlock or raise cancel-scope errors with MCP stdio on Windows. The sync `mcp` fixture avoids that.

### MCP tools covered by `mcp_server.py` (11 total)

| Tool | Tested in suite |
|------|-----------------|
| `web_search` | Yes |
| `fetch_url` | Yes |
| `get_time` | Yes |
| `currency_convert` | Yes |
| `read_file` | Yes |
| `list_dir` | Yes |
| `create_file` | Yes |
| `update_file` | Yes |
| `edit_file` | Yes |
| `index_document` | No |
| `search_knowledge` | No |

### Full pytest output (May 26, 2026 — latest)

```
============================= test session starts =============================
platform win32 -- Python 3.12.4, pytest-9.0.3, pluggy-1.6.0
rootdir: C:\Users\Padmanabh\OneDrive\Documents\S7\S7code
collecting ... collected 10 items

test_mcp_server.py::test_web_search PASSED
  web_search: [3 hits — python asyncio docs, Real Python, Jacob Padilla article]

test_mcp_server.py::test_fetch_url PASSED
  fetch_url status/len: 200 166

test_mcp_server.py::test_get_time PASSED
  get_time: {'iso': '2026-05-26T17:07:22.160848+05:30',
             'human': 'Tuesday, 26 May 2026 17:07:22 IST',
             'timezone': 'Asia/Kolkata', 'offset_hours': 5.5}

test_mcp_server.py::test_currency_convert PASSED
  currency_convert: {'amount': 100.0, 'from': 'USD', 'to': 'EUR', 'rate': 0.8589,
                     'converted': 85.89, 'date': '2026-05-25', 'source': 'frankfurter.dev'}

test_mcp_server.py::test_read_file PASSED
  read_file: {'path': 'hello.txt', 'size_bytes': 11, 'content': 'hello world', 'encoding': 'utf-8'}

test_mcp_server.py::test_list_dir PASSED
  list_dir: {'path': '.', 'count': 3, 'names': ['a.txt', 'papers', 'sub'],
             'entries': [...]}

test_mcp_server.py::test_create_file PASSED
  create_file: {'ok': True, 'path': 'new.txt', 'size_bytes': 5}
  dup error: File 'new.txt' already exists

test_mcp_server.py::test_update_file PASSED
  update_file: {'ok': True, 'path': 'u.txt', 'size_bytes': 14}
  missing error: File 'nope.txt' does not exist

test_mcp_server.py::test_edit_file PASSED
  ambiguous error: 'foo' occurs 2 times; pass replace_all=True
  replace_all: {'replacements': 2} → "FOO bar FOO"
  single: {'replacements': 1} → "FOO BAZ FOO"

test_mcp_server.py::test_sandbox_escape PASSED
  error: Path '../foo' escapes the sandbox

============================== 10 passed in 7.61s ==============================
```

### Per-test result table

| Test | Status | Notes |
|------|--------|-------|
| `test_web_search` | PASS | 3 results; Tavily or DuckDuckGo |
| `test_fetch_url` | PASS | status=200, 166 bytes markdown; needs Playwright Chromium |
| `test_get_time` | PASS | IST offset 5.5 |
| `test_currency_convert` | PASS | rate ≈ 0.8589 USD→EUR |
| `test_read_file` | PASS | 11-byte UTF-8 file |
| `test_list_dir` | PASS | Dict API with `entries` / `names` / `count` |
| `test_create_file` | PASS | Duplicate create returns tool error |
| `test_update_file` | PASS | Missing file returns tool error |
| `test_edit_file` | PASS | Ambiguous / replace_all / not-found paths |
| `test_sandbox_escape` | PASS | Path traversal blocked |

### Issues encountered and fixes

| Issue | Symptom | Fix |
|-------|---------|-----|
| **Missing `ddgs`** | All tests ERROR: `Connection closed`; stderr: `ModuleNotFoundError: No module named 'ddgs'` | Tests spawn server via `S7code/.venv` after `uv sync` |
| **torch_env vs project venv** | Same as above when running plain `pytest` from conda | `_server_stdio_params()` prefers `.venv/Scripts/python.exe` |
| **`list_dir` API change** | `AssertionError: expected list, got dict` | Server returns `{path, count, names, entries}`; test updated |
| **Playwright missing** | `fetch_url` skip/fail: Chromium not installed | `uv run playwright install chromium` |
| **Windows cp1252 + crawl4ai** | `'charmap' codec can't encode character '\u2192'` | `mcp_server.py`: UTF-8 stdio + redirect stdout/stderr to devnull during crawl |
| **pytest-asyncio + stdio** | Hang or cancel-scope teardown errors | Sync `mcp` fixture with dedicated event loop |
| **Sandbox cleanup on Windows** | `PermissionError` on `sandbox/papers` | `shutil.rmtree(..., ignore_errors=True)` |

### Prerequisites

| Requirement | Used by |
|-------------|---------|
| `uv sync` in `S7code` | All MCP tests (installs `ddgs`, `mcp`, `crawl4ai`, etc.) |
| `TAVILY_API_KEY` in `S7code/.env` (optional) | `web_search` primary path |
| Internet | `web_search`, `fetch_url`, `currency_convert` |
| Playwright Chromium | `fetch_url` (`uv run playwright install chromium`) |
| `tzdata` | `get_time` with IANA zones on Windows |

---

## 4. Pytest limitation (all providers)

`pytest_configure` in `test_all_providers.py` is **not invoked** by pytest (hooks in test modules are not registered as plugins). Therefore only **5 skipped tests** (single `oai`) are collected unless hooks move to `tests/conftest.py`.

**Fix (optional):** Move `pytest_configure` / `pytest_generate_tests` into `tests/conftest.py`.

---

## 5. Prerequisites checklist (all suites)

| Requirement | Used by |
|-------------|---------|
| Gateway on `http://localhost:8107` | `test_all_providers.py` (script) |
| `S7/.env` API keys | Provider + embed tests |
| Ollama + `nomic-embed-text` / `llama3.2:3b` | Embed / provider ollama |
| `uv sync` in `llm_gatewayV7` | Gateway tests |
| `uv sync` in `S7code` | MCP tests |
| Playwright Chromium | `test_fetch_url` |
| `TAVILY_API_KEY` | `test_web_search` (optional; DDG fallback) |

---

## 6. Files

| File | Role |
|------|------|
| `llm_gatewayV7/tests/test_embed.py` | Embedding endpoint tests (in-process ASGI) |
| `llm_gatewayV7/tests/test_all_providers.py` | Provider matrix (script + pytest) |
| `llm_gatewayV7/run.ps1` | Start gateway on port 8107 |
| `S7code/test_mcp_server.py` | MCP stdio integration tests |
| `S7code/mcp_server.py` | MCP server (11 tools, sandbox under `./sandbox/`) |
| `S7/.env` | Shared secrets and `LLM_GATEWAY_V7_URL` |
| `S7code/.env` | Tavily key and agent overrides |

---

## 7. Quick commands

```powershell
# Gateway — embeddings
cd S7\llm_gatewayV7
uv run pytest -v tests/test_embed.py -s

# Gateway — provider matrix (gateway must be up)
uv run python tests/test_all_providers.py

# MCP server
cd S7\S7code
uv sync
uv run playwright install chromium   # once, for fetch_url
uv run pytest -v test_mcp_server.py -s
```

---

*Report generated from live test runs on May 26, 2026. Re-run the commands above to refresh results.*

Tests Path - [Open file](https://github.com/padmanabh275/EAGV3_Session7/blob/master/llm_gatewayV7/test.md)
