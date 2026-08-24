"""Web3 helpers for the local Besu network."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from app.core.constants import CHAIN_ID, DEFAULT_RPC_URL


def connect(rpc_url: str = DEFAULT_RPC_URL, timeout_s: float = 5.0) -> Web3:
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": timeout_s}))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def is_reachable(rpc_url: str = DEFAULT_RPC_URL, timeout_s: float = 2.0) -> bool:
    try:
        w3 = connect(rpc_url, timeout_s=timeout_s)
        return bool(w3.is_connected())
    except Exception:  # noqa: BLE001
        return False


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
