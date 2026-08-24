"""Unit tests for canonical authentication-object encoding."""

from app.core.canonical import AuthObject
from app.core.crypto import new_nonce


def test_round_trip():
    obj = AuthObject(
        uav_id="UAV-VALID",
        gcs_id="GCS-01",
        nonce=new_nonce(),
        session_id="abc",
        issued_at=1,
        expires_at=2,
        requested_operation="telemetry.submit",
        payload_digest="",
    )
    raw = obj.canonical_bytes()
    parsed = AuthObject.parse(raw)
    assert parsed == obj
    assert AuthObject.parse(raw).canonical_bytes() == raw


def test_field_order_changes_bytes():
    nonce = b"\x01" * 16
    a = AuthObject("A", "GCS-01", nonce, "s", 1, 2, "telemetry.submit", "")
    b = AuthObject("B", "GCS-01", nonce, "s", 1, 2, "telemetry.submit", "")
    assert a.canonical_bytes() != b.canonical_bytes()


def test_malformed_magic():
    try:
        AuthObject.parse(b"nope")
        assert False
    except ValueError:
        pass
