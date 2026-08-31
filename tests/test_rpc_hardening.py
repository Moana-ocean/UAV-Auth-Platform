"""RPC client fallback and namespace exposure checks."""

from __future__ import annotations

import pytest

from app.auth.blockchain.client import connect, connect_first, first_reachable_url, is_reachable
from app.core.constants import DEFAULT_RPC_URL, RPC_FALLBACK_URLS

pytestmark = pytest.mark.integration


def test_primary_or_fallback_reachable():
    if not is_reachable():
        pytest.skip("Besu not running")
    url = first_reachable_url()
    assert url in RPC_FALLBACK_URLS


def test_connect_first_returns_working_client():
    if not is_reachable():
        pytest.skip("Besu not running")
    w3, url = connect_first(timeout_s=5)
    assert w3.is_connected()
    assert url.startswith("http://127.0.0.1:")


def test_admin_namespace_not_exposed():
    if not is_reachable():
        pytest.skip("Besu not running")
    w3, _ = connect_first(timeout_s=5)
    with pytest.raises(Exception):
        w3.manager.request_blocking("admin_nodeInfo", [])


def test_eth_chain_id_available():
    if not is_reachable():
        pytest.skip("Besu not running")
    w3 = connect(DEFAULT_RPC_URL)
    assert w3.eth.chain_id == 20245
