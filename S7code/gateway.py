"""Bridge to llm_gatewayV7.

V7 is V3 plus a single new endpoint, `POST /v1/embed`. The session-version
mapping (V7 for Session 7) lets us evolve the gateway forward without
touching prior versions. V3 remains available for Session 6 agents.

Auto-starts the gateway on port 8107 if it is not already up, then
re-exports the V7 `LLM` client and a module-level `embed()` helper. Every
layer in this agent imports from here so the boot logic lives in one place.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

_S7_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_S7_ROOT / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env")

GATEWAY_V7_DIR = _S7_ROOT / "llm_gatewayV7"
GATEWAY_URL = os.getenv("LLM_GATEWAY_V7_URL", "http://localhost:8107").rstrip("/")
_GATEWAY_LOG = GATEWAY_V7_DIR / "gateway_boot.log"

# Shortcut for llm_gatewayV7 (see router.SHORTCUTS: oai / openai → openai worker).
AGENT_LLM_PROVIDER = os.getenv("AGENT_LLM_PROVIDER", "oai")


def _is_up() -> bool:
    try:
        httpx.get(f"{GATEWAY_URL}/v1/routers", timeout=2.0)
        return True
    except Exception:
        return False


def _uv_cmd() -> list[str]:
    """Resolve a uv invocation that works on Windows and Unix."""
    uv = shutil.which("uv")
    if uv:
        return [uv, "run", "python", "main.py"]
    return [sys.executable, "-m", "uv", "run", "python", "main.py"]


def ensure_gateway() -> None:
    """Start V7 if it is not already running. Idempotent."""
    if _is_up():
        return
    if not GATEWAY_V7_DIR.exists():
        raise RuntimeError(
            f"Gateway V7 directory not found at {GATEWAY_V7_DIR}. "
            "Build llm_gatewayV7 (Session 7 prerequisite) before running S7 code."
        )
    print(f"[gateway] launching llm_gatewayV7 from {GATEWAY_V7_DIR}")
    log = open(_GATEWAY_LOG, "a", encoding="utf-8")
    log.write(f"\n--- boot {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    log.flush()
    subprocess.Popen(
        _uv_cmd(),
        cwd=str(GATEWAY_V7_DIR),
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    for _ in range(45):
        time.sleep(1)
        if _is_up():
            print(f"[gateway] up on {GATEWAY_URL}")
            return
    raise RuntimeError(
        f"Gateway V7 failed to start within 45s. Check {_GATEWAY_LOG} and ../.env"
    )


# Load V7's client.py without polluting sys.path. The gateway dir has its
# own `schemas.py`, which would shadow ours if we put it on the path.
import importlib.util as _importlib_util

_client_path = GATEWAY_V7_DIR / "client.py"
if _client_path.exists():
    _spec = _importlib_util.spec_from_file_location("llm_gatewayV7_client", _client_path)
    _mod = _importlib_util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    LLM = _mod.LLM
else:
    LLM = None  # populated once V7 is built; importers should ensure_gateway() first


def embed(text: str, task_type: str = "retrieval_document") -> dict:
    """Compute an embedding for `text` via the gateway's V7 embed endpoint.

    Returns the full response dict: `{embedding, dim, model, provider,
    latency_ms, ...}`. The chosen embedding model is fixed at the gateway
    level. Changing it invalidates every FAISS index built against the old
    vectors, so callers should treat the model as a project-level constant.
    """
    ensure_gateway()
    if LLM is None:
        raise RuntimeError(
            "Gateway V7 client unavailable. Confirm llm_gatewayV7/client.py exists."
        )
    return LLM().embed(text, task_type=task_type)


__all__ = [
    "ensure_gateway",
    "LLM",
    "GATEWAY_URL",
    "GATEWAY_V7_DIR",
    "AGENT_LLM_PROVIDER",
    "embed",
]
