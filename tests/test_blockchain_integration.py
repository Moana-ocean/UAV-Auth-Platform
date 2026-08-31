"""Integration tests against local Besu. Skipped when the network is down."""

import json
import uuid

import pytest
from app.auth.blockchain.adapter import BlockchainIdentityBackend
from app.auth.blockchain.client import is_reachable
from app.auth.blockchain.compiler import compile_registry
from app.auth.blockchain.registry import RegistryAdapter
from app.auth.common.protocol import GCSAuthService
from app.auth.models import UAVKeyMaterial
from app.core.constants import DEFAULT_RPC_URL, ROLE_DELIVERY
from app.core.crypto import generate_uav_key, public_bytes_uncompressed
from app.core.nonce import NonceStore
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
    return RegistryAdapter(DEFAULT_RPC_URL, dep["address"], ra["private_key"], timeout_s=20)


def test_register_and_lookup(adapter):
    compile_registry()
    key = generate_uav_key()
    uav_id = "UAV-ITEST"
    pk = public_bytes_uncompressed(key.public_key())
    rec = adapter.get_record(uav_id)
    if rec["status"] == 0:
        receipt = adapter.register(uav_id, pk, ROLE_DELIVERY)
        assert receipt["status"] == 1
        assert receipt["gas_used"] > 0
    elif bytes(rec["public_key"] or b"") != pk:
        adapter.update_key(uav_id, pk)
    got = adapter.get_record(uav_id)
    assert got["status"] == 1
    assert got["public_key"] == pk


def test_unauthorised_register_rejected(adapter):
    from eth_account import Account
    from web3.exceptions import ContractCustomError, ContractLogicError, Web3RPCError

    stranger = Account.create()
    key = generate_uav_key()
    with pytest.raises((Web3RPCError, ContractLogicError, ContractCustomError, ValueError)):
        adapter.contract.functions.register(
            "UAV-STRANGER", public_bytes_uncompressed(key.public_key()), ROLE_DELIVERY
        ).call({"from": stranger.address})


def test_blockchain_auth_and_replay(adapter):
    key = generate_uav_key()
    uav_id = "UAV-ITEST-AUTH"
    pk = public_bytes_uncompressed(key.public_key())
    rec = adapter.get_record(uav_id)
    if rec["status"] == 0:
        adapter.register(uav_id, pk, ROLE_DELIVERY)
    elif bytes(rec["public_key"] or b"") != pk:
        adapter.update_key(uav_id, pk)
    km = UAVKeyMaterial(uav_id, key, key.public_key(), pk, ROLE_DELIVERY)
    svc = GCSAuthService(BlockchainIdentityBackend(adapter), NonceStore())
    ch = svc.create_challenge(uav_id)
    req = svc.build_signed_request(km, ch, "telemetry.submit")
    assert svc.authenticate(req).outcome == "ACCEPTED"
    assert svc.authenticate(req).outcome == "REPLAY_DETECTED"


def test_revoked_identity(adapter):
    key = generate_uav_key()
    uav_id = f"UAV-ITEST-REV-{uuid.uuid4().hex[:8]}"
    pk = public_bytes_uncompressed(key.public_key())
    rec = adapter.get_record(uav_id)
    if rec["status"] == 0:
        adapter.register(uav_id, pk, ROLE_DELIVERY)
    elif rec["status"] in {1, 2} and bytes(rec["public_key"] or b"") != pk:
        adapter.update_key(uav_id, pk)
    if adapter.get_record(uav_id)["status"] != 3:
        adapter.revoke(uav_id)
    km = UAVKeyMaterial(uav_id, key, key.public_key(), pk, ROLE_DELIVERY)
    svc = GCSAuthService(BlockchainIdentityBackend(adapter), NonceStore())
    ch = svc.create_challenge(uav_id)
    req = svc.build_signed_request(km, ch, "telemetry.submit")
    assert svc.authenticate(req).outcome == "REVOKED_IDENTITY"
