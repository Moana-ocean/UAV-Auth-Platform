"""Integration: updateKey sync restores blockchain valid_active authentication."""

from __future__ import annotations

import json
import uuid

import pytest
from app.auth.blockchain.adapter import BlockchainIdentityBackend
from app.auth.blockchain.client import is_reachable
from app.auth.blockchain.registry import RegistryAdapter
from app.auth.common.protocol import GCSAuthService
from app.auth.models import UAVKeyMaterial
from app.core.constants import DEFAULT_RPC_URL, ROLE_DELIVERY, ROLE_TELEMETRY
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
    return RegistryAdapter(DEFAULT_RPC_URL, dep["address"], ra["private_key"], timeout_s=30)


def test_stale_key_then_updatekey_accepts(adapter):
    uav_id = f"UAV-SYNC-{uuid.uuid4().hex[:8]}"
    stale = generate_uav_key()
    current = generate_uav_key()
    stale_pk = public_bytes_uncompressed(stale.public_key())
    current_pk = public_bytes_uncompressed(current.public_key())
    assert stale_pk != current_pk

    adapter.register(uav_id, stale_pk, ROLE_DELIVERY)
    km = UAVKeyMaterial(uav_id, current, current.public_key(), current_pk, ROLE_DELIVERY)
    svc = GCSAuthService(BlockchainIdentityBackend(adapter), NonceStore())
    ch = svc.create_challenge(uav_id)
    req = svc.build_signed_request(km, ch, "telemetry.submit")
    assert svc.authenticate(req).outcome == "INVALID_SIGNATURE"

    adapter.update_key(uav_id, current_pk)
    assert bytes(adapter.get_record(uav_id)["public_key"]) == current_pk
    ch2 = svc.create_challenge(uav_id)
    req2 = svc.build_signed_request(km, ch2, "telemetry.submit")
    assert svc.authenticate(req2).outcome == "ACCEPTED"


def test_limited_role_unauthorised_after_sync(adapter):
    uav_id = f"UAV-LIM-{uuid.uuid4().hex[:8]}"
    key = generate_uav_key()
    pk = public_bytes_uncompressed(key.public_key())
    adapter.register(uav_id, pk, ROLE_TELEMETRY)
    km = UAVKeyMaterial(uav_id, key, key.public_key(), pk, ROLE_TELEMETRY)
    svc = GCSAuthService(BlockchainIdentityBackend(adapter), NonceStore())
    ch = svc.create_challenge(uav_id)
    req = svc.build_signed_request(km, ch, "admin.reconfigure")
    assert svc.authenticate(req).outcome == "UNAUTHORISED_OPERATION"
