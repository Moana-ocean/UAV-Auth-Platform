"""Nonce single-use and expiry tests."""

import time

from app.core.nonce import NonceStore


def test_consume_once():
    store = NonceStore()
    rec = store.create("UAV-1", 5)
    assert store.consume(rec.session_id, rec.nonce) == "OK"
    assert store.consume(rec.session_id, rec.nonce) == "REPLAY_DETECTED"


def test_expired():
    store = NonceStore()
    rec = store.create("UAV-1", 0.05)
    time.sleep(0.12)
    assert store.consume(rec.session_id, rec.nonce) == "EXPIRED_CHALLENGE"
    assert store.consume(rec.session_id, rec.nonce) == "REPLAY_DETECTED"


def test_unknown_session():
    store = NonceStore()
    assert store.consume("missing", b"\x00" * 16) == "MALFORMED_REQUEST"


def test_nonce_mismatch_still_consumes():
    store = NonceStore()
    rec = store.create("UAV-1", 5)
    assert store.consume(rec.session_id, b"\x00" * 16) == "INVALID_SIGNATURE"
    assert store.consume(rec.session_id, rec.nonce) == "REPLAY_DETECTED"
