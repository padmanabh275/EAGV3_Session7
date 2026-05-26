"""Tests for the EAGV3 S7 MCP server.

Run from S7code/ (uses the project .venv so mcp_server deps like ddgs are available):

    uv run pytest -v test_mcp_server.py

Plain `pytest` from torch_env also works: the server subprocess uses `.venv/Scripts/python.exe`.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).parent
SERVER = HERE / "mcp_server.py"
SANDBOX = HERE / "sandbox"


def _server_stdio_params() -> StdioServerParameters:
    """Spawn mcp_server with the uv project venv when present."""
    if sys.platform == "win32":
        venv_py = HERE / ".venv" / "Scripts" / "python.exe"
    else:
        venv_py = HERE / ".venv" / "bin" / "python"
    if venv_py.is_file():
        return StdioServerParameters(command=str(venv_py), args=[str(SERVER)])
    return StdioServerParameters(command=sys.executable, args=[str(SERVER)])


def _result(res) -> object:
    """Extract a structured payload from a CallToolResult."""
    if getattr(res, "structuredContent", None) is not None:
        sc = res.structuredContent
        if isinstance(sc, dict) and set(sc.keys()) == {"result"}:
            return sc["result"]
        return sc
    block = res.content[0]
    text = getattr(block, "text", None)
    if text is None:
        return block
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _clean_sandbox() -> None:
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX, ignore_errors=True)
    SANDBOX.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session")
def mcp():
    """(event_loop, ClientSession) — one stdio MCP connection for all tests."""
    loop = asyncio.new_event_loop()
    stack = AsyncExitStack()

    async def _connect() -> ClientSession:
        read, write = await stack.enter_async_context(stdio_client(_server_stdio_params()))
        s = await stack.enter_async_context(ClientSession(read, write))
        await s.initialize()
        return s

    session = loop.run_until_complete(_connect())
    yield loop, session
    try:
        loop.run_until_complete(stack.aclose())
    except RuntimeError:
        # anyio stdio_client cancel-scope teardown can race on Windows.
        pass
    finally:
        loop.close()


def _call(mcp, tool: str, arguments: dict[str, Any]):
    loop, session = mcp
    return loop.run_until_complete(session.call_tool(tool, arguments))


@pytest.mark.network
def test_web_search(mcp):
    res = _call(mcp, "web_search", {"query": "python asyncio", "max_results": 3})
    data = _result(res)
    print("web_search:", data)
    assert isinstance(data, list)
    assert len(data) >= 1
    for hit in data:
        assert {"title", "url", "snippet"} <= set(hit)


@pytest.mark.network
def test_fetch_url(mcp):
    res = _call(mcp, "fetch_url", {"url": "https://example.com"})
    if res.isError:
        msg = res.content[0].text if res.content else ""
        if "playwright" in msg.lower() or "chromium" in msg.lower():
            pytest.skip("Playwright browser missing; run: playwright install chromium")
        pytest.fail(msg)
    data = _result(res)
    assert isinstance(data, dict), f"expected dict, got {type(data).__name__}: {data!r:.200}"
    print("fetch_url status/len:", data["status"], data["length_bytes"])
    assert data["status"] == 200
    assert "Example Domain" in data["text"]
    assert data["length_bytes"] > 0
    assert "markdown" in data["content_type"].lower() or "html" in data["content_type"].lower()


def test_get_time(mcp):
    res = _call(mcp, "get_time", {"timezone": "Asia/Kolkata"})
    data = _result(res)
    print("get_time:", data)
    assert data["timezone"] == "Asia/Kolkata"
    assert data["offset_hours"] == 5.5
    assert "T" in data["iso"]
    assert data["human"]


@pytest.mark.network
def test_currency_convert(mcp):
    res = _call(
        mcp, "currency_convert", {"amount": 100, "from_currency": "usd", "to_currency": "eur"}
    )
    data = _result(res)
    print("currency_convert:", data)
    assert data["from"] == "USD"
    assert data["to"] == "EUR"
    assert data["amount"] == 100
    assert data["source"] == "frankfurter.dev"
    assert data["converted"] > 0
    assert data["rate"] > 0


def test_read_file(mcp):
    _clean_sandbox()
    (SANDBOX / "hello.txt").write_text("hello world", encoding="utf-8")
    res = _call(mcp, "read_file", {"path": "hello.txt"})
    data = _result(res)
    print("read_file:", data)
    assert data["content"] == "hello world"
    assert data["encoding"] == "utf-8"
    assert data["size_bytes"] == 11
    assert data["path"] == "hello.txt"


def test_list_dir(mcp):
    _clean_sandbox()
    (SANDBOX / "a.txt").write_text("a", encoding="utf-8")
    (SANDBOX / "sub").mkdir()
    res = _call(mcp, "list_dir", {"path": "."})
    data = _result(res)
    print("list_dir:", data)
    assert isinstance(data, dict)
    assert data["path"] == "."
    assert data["count"] == len(data["entries"])
    names = {e["name"]: e for e in data["entries"]}
    assert set(data["names"]) == set(names)
    assert names["a.txt"]["type"] == "file"
    assert names["a.txt"]["size_bytes"] == 1
    assert names["sub"]["type"] == "dir"
    assert names["sub"]["size_bytes"] == 0


def test_create_file(mcp):
    _clean_sandbox()
    res = _call(mcp, "create_file", {"path": "new.txt", "content": "fresh"})
    data = _result(res)
    print("create_file:", data)
    assert data["ok"] is True
    assert data["size_bytes"] == 5
    assert (SANDBOX / "new.txt").read_text(encoding="utf-8") == "fresh"

    dup = _call(mcp, "create_file", {"path": "new.txt", "content": "x"})
    assert dup.isError, "second create on same path must error"
    print("create_file dup error:", dup.content[0].text if dup.content else "")


def test_update_file(mcp):
    _clean_sandbox()
    (SANDBOX / "u.txt").write_text("old", encoding="utf-8")
    res = _call(mcp, "update_file", {"path": "u.txt", "content": "brand new body"})
    data = _result(res)
    print("update_file:", data)
    assert data["ok"] is True
    assert (SANDBOX / "u.txt").read_text(encoding="utf-8") == "brand new body"
    assert data["size_bytes"] == len("brand new body")

    missing = _call(mcp, "update_file", {"path": "nope.txt", "content": "x"})
    assert missing.isError
    print("update_file missing error:", missing.content[0].text if missing.content else "")


def test_edit_file(mcp):
    _clean_sandbox()
    (SANDBOX / "e.txt").write_text("foo bar foo", encoding="utf-8")

    multi = _call(mcp, "edit_file", {"path": "e.txt", "find": "foo", "replace": "FOO"})
    assert multi.isError, "ambiguous find without replace_all must error"
    print("edit_file ambiguous error:", multi.content[0].text if multi.content else "")

    res_all = _call(
        mcp,
        "edit_file",
        {"path": "e.txt", "find": "foo", "replace": "FOO", "replace_all": True},
    )
    data = _result(res_all)
    print("edit_file replace_all:", data)
    assert data["replacements"] == 2
    assert (SANDBOX / "e.txt").read_text(encoding="utf-8") == "FOO bar FOO"

    res_single = _call(mcp, "edit_file", {"path": "e.txt", "find": "bar", "replace": "BAZ"})
    data = _result(res_single)
    print("edit_file single:", data)
    assert data["replacements"] == 1
    assert (SANDBOX / "e.txt").read_text(encoding="utf-8") == "FOO BAZ FOO"

    missing = _call(mcp, "edit_file", {"path": "e.txt", "find": "zzz", "replace": "x"})
    assert missing.isError
    print("edit_file not-found error:", missing.content[0].text if missing.content else "")


def test_sandbox_escape(mcp):
    res = _call(mcp, "read_file", {"path": "../foo"})
    assert res.isError, "sandbox escape must be rejected"
    msg = res.content[0].text if res.content else ""
    print("sandbox_escape error:", msg)
    assert "escape" in msg.lower() or "sandbox" in msg.lower()
