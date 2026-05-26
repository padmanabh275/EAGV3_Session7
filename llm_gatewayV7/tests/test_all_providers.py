#!/usr/bin/env python3
"""Per-provider matrix test for llm_gatewayV7.

Run as a script (prints matrix, parallel):
    uv run python tests/test_all_providers.py

Run with pytest (one test per provider x capability):
    uv run pytest -v tests/test_all_providers.py

Requires the gateway on http://localhost:8107 (or LLM_GATEWAY_V7_URL).
Only tests providers returned by GET /v1/providers.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx
import pytest
from dotenv import load_dotenv

HERE = Path(__file__).parent.parent
load_dotenv(HERE.parent / ".env")

URL = (
    os.getenv("LLM_GATEWAY_V7_URL")
    or os.getenv("LLM_GATEWAY_V2_URL")
    or "http://localhost:8107"
).rstrip("/")

SHORTCUT_TO_NAME = {
    "oai": "openai",
    "o": "ollama",
    "n": "nvidia",
    "gr": "groq",
    "c": "cerebras",
    "or": "openrouter",
    "gh": "github",
    "g": "gemini",
}
NAME_TO_SHORTCUT = {v: k for k, v in SHORTCUT_TO_NAME.items()}

ADD_TOOL = {
    "name": "add",
    "description": "Return a + b.",
    "input_schema": {
        "type": "object",
        "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
        "required": ["a", "b"],
    },
}

CITY_SCHEMA = {
    "type": "object",
    "properties": {"city": {"type": "string"}, "country": {"type": "string"}},
    "required": ["city", "country"],
}


def discover_providers() -> tuple[list[str], list[str]]:
    """Return (shortcuts, names) for providers registered on the live gateway."""
    r = httpx.get(f"{URL}/v1/providers", timeout=10)
    r.raise_for_status()
    data = r.json()
    names = list(data.get("providers") or [])
    order = list(data.get("order") or names)
    ordered_names = [n for n in order if n in names]
    for n in names:
        if n not in ordered_names:
            ordered_names.append(n)
    shortcuts = [NAME_TO_SHORTCUT[n] for n in ordered_names if n in NAME_TO_SHORTCUT]
    return shortcuts, ordered_names


def post(body, timeout=120, retries=1):
    """POST to /v1/chat with optional retry on transient upstream failure."""
    last_code, last_body = 0, {}
    for attempt in range(retries + 1):
        try:
            r = httpx.post(f"{URL}/v1/chat", json=body, timeout=timeout)
            last_code = r.status_code
            try:
                last_body = r.json()
            except Exception:
                last_body = {"raw": r.text}
        except Exception as e:
            last_code, last_body = 0, {"raw": f"{e}"}
        if last_code == 200:
            return last_code, last_body
        if attempt < retries:
            time.sleep(6)
    return last_code, last_body


def _budget(p: str, default: int) -> int:
    return 1024 if p == "o" else default


def check_basic(p: str) -> tuple[str, str]:
    code, d = post(
        {"prompt": "Say hi in 3 words.", "provider": p, "max_tokens": _budget(p, 256)},
        timeout=120 if p != "o" else 180,
    )
    if code == 200 and d.get("text", "").strip():
        return "OK", d.get("text", "").strip()[:40]
    return "FAIL", f"code={code} {str(d)[:80]}"


def check_tools(p: str) -> tuple[str, str]:
    msgs = [{"role": "user", "content": "What is 7 plus 5? Use the add tool."}]
    code, d = post(
        {
            "messages": msgs,
            "provider": p,
            "tools": [ADD_TOOL],
            "tool_choice": "auto",
            "max_tokens": _budget(p, 512),
            "temperature": 0,
        },
        timeout=180,
    )
    if code != 200:
        return "FAIL", f"first call code={code} {str(d)[:80]}"
    tcs = d.get("tool_calls") or []
    if not tcs:
        return "FAIL", f"no tool_calls; text={d.get('text', '')[:80]}"
    tc = tcs[0]
    args = tc.get("arguments") or {}
    a, b = args.get("a"), args.get("b")
    if {a, b} != {7, 5} and {a, b} != {7.0, 5.0}:
        return "PARTIAL", f"tool_call args={args}"
    msgs2 = msgs + [
        {"role": "assistant", "content": "", "tool_calls": [tc]},
        {
            "role": "tool",
            "tool_call_id": tc["id"],
            "tool_name": tc["name"],
            "content": json.dumps({"result": 12}),
        },
    ]
    code, d2 = post(
        {
            "messages": msgs2,
            "provider": p,
            "tools": [ADD_TOOL],
            "max_tokens": _budget(p, 256),
            "temperature": 0,
        },
        timeout=180,
    )
    if code != 200:
        return "PARTIAL", f"tool_call ok but second call code={code} {str(d2)[:80]}"
    final = (d2.get("text") or "").strip()
    if "12" in final:
        return "OK", f"dialect={d.get('tool_call_dialect')} final='{final[:40]}'"
    return "PARTIAL", f"final='{final[:60]}'"


def check_structured(p: str) -> tuple[str, str]:
    body = {
        "prompt": "Paris is in which country? Respond with JSON {city,country}.",
        "provider": p,
        "max_tokens": _budget(p, 512),
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "schema": CITY_SCHEMA,
            "name": "loc",
            "strict": True,
        },
    }
    code, d = post(body)
    if code != 200:
        return "FAIL", f"code={code} {str(d)[:80]}"
    parsed = d.get("parsed")
    if (
        parsed
        and parsed.get("city", "").lower() == "paris"
        and parsed.get("country", "").lower() == "france"
    ):
        return "OK", f"{parsed}"
    try:
        obj = json.loads(d.get("text") or "{}")
        if obj.get("city", "").lower() == "paris" and obj.get("country", "").lower() == "france":
            return "OK", f"{obj} (text)"
    except Exception:
        pass
    return "PARTIAL", f"parsed={parsed} text='{(d.get('text') or '')[:80]}'"


def check_caching(p: str) -> tuple[str, str]:
    if p == "o":
        return "SKIP", "ollama: local, no upstream cache"
    long_sys = ("You are a meticulous geography tutor. Always answer concisely. " * 200).strip()
    body = {
        "prompt": "Capital of France?",
        "provider": p,
        "system": long_sys,
        "cache_system": True,
        "max_tokens": _budget(p, 80),
        "temperature": 0,
    }
    code1, d1 = post(body)
    if code1 != 200:
        return "FAIL", f"first code={code1} {str(d1)[:80]}"
    time.sleep(0.4)
    code2, d2 = post(body)
    if code2 != 200:
        return "FAIL", f"second code={code2} {str(d2)[:80]}"
    cr1 = d1.get("cache_read_input_tokens", 0) or 0
    cr2 = d2.get("cache_read_input_tokens", 0) or 0
    cw1 = d1.get("cache_creation_input_tokens", 0) or 0
    if cr2 > 0 or cw1 > 0:
        return "OK", f"cw1={cw1} cr2={cr2}"
    return "n/a", f"no cache signal cr1={cr1} cr2={cr2} (provider may not surface)"


def check_reasoning(p: str) -> tuple[str, str]:
    body = {
        "prompt": (
            "If a train leaves Boston at 3pm at 60mph and another leaves NYC "
            "(200mi south) at 4pm at 80mph headed north, when do they meet? Be brief."
        ),
        "provider": p,
        "reasoning": "high",
        "max_tokens": _budget(p, 400),
        "temperature": 0,
    }
    t0 = time.time()
    code, d = post(body, timeout=180)
    dt = time.time() - t0
    if code != 200:
        return "FAIL", f"code={code} {str(d)[:80]}"
    if d.get("reasoning_applied"):
        return "OK", f"applied=True latency={dt:.1f}s"
    return "n/a", f"applied=False (model lacks knob) latency={dt:.1f}s"


# ── pytest integration ───────────────────────────────────────────────────────

_PROVIDER_SHORTCUTS: list[str] = []
_PROVIDER_NAMES: list[str] = []


def pytest_configure(config):
    """Discover providers once before collection parametrization."""
    global _PROVIDER_SHORTCUTS, _PROVIDER_NAMES
    try:
        _PROVIDER_SHORTCUTS, _PROVIDER_NAMES = discover_providers()
    except Exception:
        _PROVIDER_SHORTCUTS, _PROVIDER_NAMES = [], []


def pytest_generate_tests(metafunc):
    if "provider" in metafunc.fixturenames:
        if not _PROVIDER_SHORTCUTS:
            metafunc.parametrize(
                "provider",
                [pytest.param("oai", marks=pytest.mark.skip(reason=f"gateway down: {URL}"))],
            )
        else:
            metafunc.parametrize(
                "provider",
                _PROVIDER_SHORTCUTS,
                ids=_PROVIDER_NAMES,
            )


@pytest.fixture(scope="session", autouse=True)
def _gateway_url():
    if not _PROVIDER_SHORTCUTS:
        pytest.skip(f"Gateway not reachable at {URL}/v1/providers")


def test_basic(provider: str):
    status, info = check_basic(provider)
    assert status == "OK", info


def test_tools(provider: str):
    status, info = check_tools(provider)
    assert status == "OK", info


def test_structured(provider: str):
    status, info = check_structured(provider)
    assert status == "OK", info


def test_caching(provider: str):
    status, info = check_caching(provider)
    assert status in ("OK", "SKIP", "n/a"), info


def test_reasoning(provider: str):
    status, info = check_reasoning(provider)
    assert status in ("OK", "n/a"), info


# ── script entry point (matrix + parallel) ───────────────────────────────────

def run_provider(p: str) -> tuple[str, dict[str, str], dict[str, str]]:
    name = SHORTCUT_TO_NAME[p]
    row: dict[str, str] = {}
    details: dict[str, str] = {}
    for col, fn in [
        ("basic", check_basic),
        ("tools", check_tools),
        ("struct", check_structured),
        ("cache", check_caching),
        ("reasoning", check_reasoning),
    ]:
        try:
            status, info = fn(p)
        except Exception as e:
            status, info = "FAIL", f"exc {e}"
        row[col] = status
        details[col] = info
        print(f"  [{name:10s}] {col:10s} -> {status:7s} {info[:100]}", flush=True)
    return name, row, details


def main():
    import concurrent.futures as cf

    try:
        providers, names = discover_providers()
    except Exception as e:
        print(f"ERROR: cannot reach gateway at {URL}/v1/providers ({e})", file=sys.stderr)
        sys.exit(2)
    if not providers:
        print(f"ERROR: no testable providers at {URL}", file=sys.stderr)
        sys.exit(2)

    matrix: dict[str, dict[str, str]] = {}
    print(f"Gateway: {URL}")
    print(f"Testing {len(providers)} registered providers: {names}\n", flush=True)
    print("Running providers in parallel...\n", flush=True)

    workers = max(1, len(providers))
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(run_provider, p): p for p in providers}
        for fut in cf.as_completed(futs):
            name, row, _det = fut.result()
            matrix[name] = row

    print("\n" + "=" * 78)
    cols = ["basic", "tools", "struct", "cache", "reasoning"]
    print(f"{'provider':12s}" + "  ".join(f"{c:9s}" for c in cols))
    print("-" * 78)
    for name in names:
        row = matrix.get(name, {})
        print(f"{name:12s}" + "  ".join(f"{row.get(c, '?'):9s}" for c in cols))
    print("=" * 78)

    bad = [n for n, r in matrix.items() if r.get("basic") == "FAIL"]
    if bad:
        print(f"\nFAIL: basic test broken on: {bad}")
        sys.exit(1)
    print("\nbasic-test ok across all registered providers.")


if __name__ == "__main__":
    main()
