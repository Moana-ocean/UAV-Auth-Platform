"""Smart-contract lifecycle and RBAC integration tests (requires local Besu)."""

from __future__ import annotations

import json
import uuid

import pytest
from eth_account import Account
from web3.exceptions import ContractCustomError, ContractLogicError, Web3RPCError

from app.auth.blockchain.client import is_reachable
from app.auth.blockchain.registry import RegistryAdapter
from app.core.constants import DEFAULT_RPC_URL, ROLE_DELIVERY, ROLE_OBSERVER, ROLE_TELEMETRY
from app.core.crypto import generate_uav_key, public_bytes_uncompressed
from app.experiments.runner import data_dir, deployment_path

pytestmark = pytest.mark.integration


def _ready() -> bool:
    return is_reachable() and deployment_path().exists()


@pytest.fixture
def adapter():
    if not _ready():
        pytest.skip("Besu or deployment.json not available")
    dep = json.loads(deployment_path().read_text(encoding="utf-8"))
    ra = json.loads((data_dir() / "besu" / "ra_key.json").read_text(encoding="utf-8"))
    return RegistryAdapter(DEFAULT_RPC_URL, dep["address"], ra["private_key"], timeout_s=30)


def _expect_revert(fn) -> None:
    with pytest.raises((ContractLogicError, ContractCustomError, Web3RPCError, ValueError)):
        fn()


def _ensure_registered(adapter: RegistryAdapter, uav_id: str, role: int = ROLE_DELIVERY) -> bytes:
    key = generate_uav_key()
    pk = public_bytes_uncompressed(key.public_key())
    rec = adapter.get_record(uav_id)
    status = int(rec["status"])
    if status == 0:
        adapter.register(uav_id, pk, role)
    elif status in {1, 2}:
        chain_pk = bytes(rec["public_key"] or b"")
        if chain_pk != pk:
            adapter.update_key(uav_id, pk)
    elif status == 3:
        raise RuntimeError(f"{uav_id} is revoked; use a fresh test id")
    return pk


def _fresh_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_active_to_suspended_to_active(adapter):
    uav_id = _fresh_id("UAV-LIFE-SUSP")
    _ensure_registered(adapter, uav_id)
    adapter.suspend(uav_id)
    assert adapter.get_record(uav_id)["status"] == 2
    adapter.reinstate(uav_id)
    assert adapter.get_record(uav_id)["status"] == 1


def test_revoked_is_terminal(adapter):
    uav_id = _fresh_id("UAV-LIFE-TERM")
    _ensure_registered(adapter, uav_id)
    if adapter.get_record(uav_id)["status"] != 3:
        adapter.revoke(uav_id)
    assert adapter.get_record(uav_id)["status"] == 3
    _expect_revert(lambda: adapter.reinstate(uav_id))
    _expect_revert(lambda: adapter.update_key(uav_id, b"\x04" + b"\x01" * 64))
    _expect_revert(lambda: adapter.update_role(uav_id, ROLE_TELEMETRY))


def test_revoked_cannot_reregister(adapter):
    uav_id = _fresh_id("UAV-LIFE-REREG")
    pk = _ensure_registered(adapter, uav_id)
    adapter.revoke(uav_id)
    _expect_revert(lambda: adapter.register(uav_id, pk, ROLE_DELIVERY))


@pytest.mark.parametrize("role", [1, 2, 3])
def test_valid_roles_register(adapter, role):
    uav_id = _fresh_id(f"UAV-ROLE-OK-{role}")
    key = generate_uav_key()
    pk = public_bytes_uncompressed(key.public_key())
    rec = adapter.get_record(uav_id)
    if int(rec["status"]) == 0:
        adapter.register(uav_id, pk, role)
    got = adapter.get_record(uav_id)
    assert int(got["role"]) == role
    assert int(got["status"]) == 1


@pytest.mark.parametrize("role", [0, 4, 255])
def test_invalid_roles_rejected(adapter, role):
    uav_id = _fresh_id(f"UAV-ROLE-BAD-{role}")
    key = generate_uav_key()
    pk = public_bytes_uncompressed(key.public_key())
    _expect_revert(lambda: adapter.register(uav_id, pk, role))


def test_empty_public_key_rejected(adapter):
    uav_id = _fresh_id("UAV-PK-EMPTY")
    _expect_revert(lambda: adapter.register(uav_id, b"", ROLE_DELIVERY))


def test_oversized_public_key_rejected(adapter):
    uav_id = _fresh_id("UAV-PK-BIG")
    _expect_revert(lambda: adapter.register(uav_id, b"\x00" * 129, ROLE_DELIVERY))


def test_public_key_hash_matches(adapter):
    uav_id = _fresh_id("UAV-PK-HASH")
    key = generate_uav_key()
    pk = public_bytes_uncompressed(key.public_key())
    rec = adapter.get_record(uav_id)
    if int(rec["status"]) == 0:
        adapter.register(uav_id, pk, ROLE_DELIVERY)
    got = adapter.get_record(uav_id)
    import hashlib

    expected = "0x" + hashlib.sha256(pk).hexdigest()
    assert got["public_key_hash"].lower() == expected.lower()


def test_unauthorised_register(adapter):
    from eth_account import Account

    stranger = Account.create()
    key = generate_uav_key()
    pk = public_bytes_uncompressed(key.public_key())
    with pytest.raises((ContractLogicError, Web3RPCError, ValueError)):
        adapter.contract.functions.register("UAV-STRANGER-LIFE", pk, ROLE_DELIVERY).call(
            {"from": stranger.address}
        )


def test_admin_transfer_zero_rejected(adapter):
    _expect_revert(lambda: adapter.transfer_admin("0x0000000000000000000000000000000000000000"))


def test_audit_does_not_change_status(adapter):
    uav_id = _fresh_id("UAV-AUDIT-STATE")
    _ensure_registered(adapter, uav_id)
    before = adapter.get_record(uav_id)
    adapter.record_audit(uav_id, b"\xab" * 32)
    after = adapter.get_record(uav_id)
    assert int(after["status"]) == int(before["status"])
    assert int(after["role"]) == int(before["role"])
