"""Concurrent replay protection tests."""

from __future__ import annotations

import threading
from collections import Counter

import pytest

from app.auth.common.protocol import GCSAuthService
from app.auth.models import IdentityRecord
from app.core.constants import ROLE_DELIVERY, STATUS_ACTIVE
from app.core.crypto import generate_uav_key, public_bytes_uncompressed
from app.core.nonce import NonceStore
from tests.test_protocol import StubBackend, _key


def _auth_once(svc: GCSAuthService, key, uav_id: str) -> str:
    ch = svc.create_challenge(uav_id)
    req = svc.build_signed_request(key, ch, "telemetry.submit")
    return svc.authenticate(req).outcome


def _concurrent_replay_service() -> tuple[GCSAuthService, object]:
    key = _key()
    rec = IdentityRecord(key.uav_id, key.public_key_bytes, key.role, STATUS_ACTIVE, "stub")
    svc = GCSAuthService(StubBackend({key.uav_id: rec}), NonceStore(), challenge_lifetime_s=30)
    ch = svc.create_challenge(key.uav_id)
    req = svc.build_signed_request(key, ch, "telemetry.submit")
    return svc, req


@pytest.mark.parametrize("workers", [2, 10, 50])
def test_concurrent_identical_request_exactly_one_accept(workers: int):
    svc, req = _concurrent_replay_service()
    outcomes: list[str] = []
    lock = threading.Lock()

    def worker() -> None:
        result = svc.authenticate(req).outcome
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(outcomes) == workers
    counts = Counter(outcomes)
    assert counts["ACCEPTED"] == 1
    assert counts["REPLAY_DETECTED"] == workers - 1


def test_nonce_store_concurrent_consume():
    store = NonceStore()
    rec = store.create("UAV-1", 30)
    results: list[str] = []
    lock = threading.Lock()

    def worker() -> None:
        code = store.consume(rec.session_id, rec.nonce)
        with lock:
            results.append(code)

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert Counter(results)["OK"] == 1
    assert Counter(results)["REPLAY_DETECTED"] == 49
