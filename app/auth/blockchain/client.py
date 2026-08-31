"""Web3 helpers for the local Besu network."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from app.core.constants import CHAIN_ID, DEFAULT_RPC_URL, RPC_FALLBACK_URLS


def connect(rpc_url: str = DEFAULT_RPC_URL, timeout_s: float = 5.0) -> Web3:
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": timeout_s}))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def first_reachable_url(
    urls: tuple[str, ...] | None = None, timeout_s: float = 2.0
) -> str | None:
    for url in urls or RPC_FALLBACK_URLS:
        if is_reachable(url, timeout_s=timeout_s):
            return url
    return None


def connect_first(timeout_s: float = 5.0) -> tuple[Web3, str]:
    url = first_reachable_url(timeout_s=min(timeout_s, 2.0))
    if url is None:
        raise ConnectionError("no Besu RPC endpoint reachable")
    return connect(url, timeout_s=timeout_s), url


def is_reachable(rpc_url: str = DEFAULT_RPC_URL, timeout_s: float = 2.0) -> bool:
    try:
        w3 = connect(rpc_url, timeout_s=timeout_s)
        return bool(w3.is_connected())
    except Exception:  # noqa: BLE001
        return False


def wait_until_ready(
    urls: tuple[str, ...] | None = None,
    *,
    timeout_s: float = 30.0,
    poll_s: float = 0.5,
) -> str:
    """Block until any Besu RPC endpoint responds or raise TimeoutError."""
    import time

    deadline = time.monotonic() + timeout_s
    candidates = urls or RPC_FALLBACK_URLS
    while time.monotonic() < deadline:
        url = first_reachable_url(candidates, timeout_s=min(2.0, poll_s + 1.0))
        if url is not None:
            return url
        time.sleep(poll_s)
    raise TimeoutError("no Besu RPC endpoint reachable within timeout")


def chain_status(rpc_url: str = DEFAULT_RPC_URL, timeout_s: float = 3.0) -> dict[str, Any]:
    info: dict[str, Any] = {"rpc_url": rpc_url, "reachable": False}
    try:
        w3 = connect(rpc_url, timeout_s=timeout_s)
        info["reachable"] = bool(w3.is_connected())
        if not info["reachable"]:
            return info
        info["chain_id"] = w3.eth.chain_id
        info["latest_block"] = w3.eth.block_number
        info["peer_count"] = w3.net.peer_count
        info["client_version"] = w3.client_version
        info["expected_chain_id"] = CHAIN_ID
        info["chain_id_match"] = info["chain_id"] == CHAIN_ID
    except Exception as exc:  # noqa: BLE001
        info["error"] = type(exc).__name__
    return info


def load_deployment(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
