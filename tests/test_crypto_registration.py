"""Regression tests for signature / registration key consistency."""

from __future__ import annotations

import json
from pathlib import Path

from app.auth.common.protocol import GCSAuthService
from app.auth.models import IdentityRecord, UAVKeyMaterial
from app.core.canonical import AuthObject
from app.core.constants import (
    DOMAIN_LABEL,
    PROTOCOL_VERSION,
    ROLE_DELIVERY,
    ROLE_TELEMETRY,
    STATUS_ACTIVE,
)
from app.core.crypto import (
    generate_uav_key,
    public_bytes_uncompressed,
    public_key_from_uncompressed,
    sha256,
    sign_message,
    verify_message,
)
from app.core.nonce import NonceStore


class StubBackend:
    name = "stub"

    def __init__(self, records: dict[str, IdentityRecord]) -> None:
        self.records = records

    def lookup(self, uav_id, certificate_der=None):
        rec = self.records.get(uav_id)
        if rec is None:
            return None, "UNKNOWN_IDENTITY"
        return rec, ""

    def validate_binding(self, record, request, obj):
        return True, ""


def _km(uav_id: str = "UAV-VALID", role: int = ROLE_DELIVERY) -> UAVKeyMaterial:
    k = generate_uav_key()
    return UAVKeyMaterial(
        uav_id=uav_id,
        private_key=k,
        public_key=k.public_key(),
        public_key_bytes=public_bytes_uncompressed(k.public_key()),
        role=role,
    )


def test_public_key_round_trip():
    k = generate_uav_key()
    raw = public_bytes_uncompressed(k.public_key())
    assert raw[0] == 0x04
    assert len(raw) == 65
    restored = public_key_from_uncompressed(raw)
    msg = b"round-trip-vector"
    sig = sign_message(k, msg)
    assert verify_message(restored, msg, sig)


def test_canonical_vector_file(tmp_path: Path):
    key = _km()
    obj = AuthObject(
        uav_id=key.uav_id,
        gcs_id="GCS-01",
        nonce=b"\x11" * 16,
        session_id="sess-fixed",
        issued_at=1_700_000_000,
        expires_at=1_700_000_005,
        requested_operation="telemetry.submit",
        payload_digest="",
        domain_label=DOMAIN_LABEL,
        protocol_version=PROTOCOL_VERSION,
    )
    body = obj.canonical_bytes()
    digest = sha256(body)
    sig = sign_message(key.private_key, body)
    vector = {
        "warning": "NON-PRODUCTION fixture; not a live experiment key",
        "canonical_bytes_hex": body.hex(),
        "digest_sha256_hex": digest.hex(),
        "public_key_uncompressed_hex": key.public_key_bytes.hex(),
        "signature_der_hex": sig.hex(),
        "note": "private key omitted intentionally",
    }
    path = tmp_path / "auth_vector.json"
    path.write_text(json.dumps(vector, indent=2), encoding="utf-8")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert verify_message(
        public_key_from_uncompressed(bytes.fromhex(loaded["public_key_uncompressed_hex"])),
        bytes.fromhex(loaded["canonical_bytes_hex"]),
        bytes.fromhex(loaded["signature_der_hex"]),
    )


def test_registered_key_verifies_and_wrong_key_fails():
    key = _km()
    msg = b"auth-body"
    sig = sign_message(key.private_key, msg)
    assert verify_message(public_key_from_uncompressed(key.public_key_bytes), msg, sig)
    other = public_bytes_uncompressed(generate_uav_key().public_key())
    assert not verify_message(public_key_from_uncompressed(other), msg, sig)


def test_stale_on_chain_key_causes_invalid_signature_then_sync_accepts():
    """Minimal reproducer of the Chapter 5 matrix defect."""
    signer = _km()
    stale = public_bytes_uncompressed(generate_uav_key().public_key())
    assert stale != signer.public_key_bytes
    records = {
        signer.uav_id: IdentityRecord(
            signer.uav_id, stale, signer.role, STATUS_ACTIVE, "stub"
        )
    }
    svc = GCSAuthService(StubBackend(records), NonceStore())
    ch = svc.create_challenge(signer.uav_id)
    req = svc.build_signed_request(signer, ch, "telemetry.submit")
    assert svc.authenticate(req).outcome == "INVALID_SIGNATURE"

    # After syncing the registry to the signing public key, the same protocol accepts.
    records[signer.uav_id] = IdentityRecord(
        signer.uav_id, signer.public_key_bytes, signer.role, STATUS_ACTIVE, "stub"
    )
    ch2 = svc.create_challenge(signer.uav_id)
    req2 = svc.build_signed_request(signer, ch2, "telemetry.submit")
    assert svc.authenticate(req2).outcome == "ACCEPTED"


def test_tamper_nonce_uav_id_operation_fail():
    key = _km()
    records = {
        key.uav_id: IdentityRecord(
            key.uav_id, key.public_key_bytes, key.role, STATUS_ACTIVE, "stub"
        )
    }
    svc = GCSAuthService(StubBackend(records), NonceStore())
    ch = svc.create_challenge(key.uav_id)
    req = svc.build_signed_request(key, ch, "telemetry.submit")
    obj = AuthObject.parse(req.body)
    for field, value in (
        ("nonce", b"\x00" * 16),
        ("uav_id", "UAV-OTHER"),
        ("requested_operation", "admin.reconfigure"),
    ):
        tampered_obj = AuthObject(**{**obj.__dict__, field: value})
        from app.auth.models import SignedAuthRequest

        bad = SignedAuthRequest(tampered_obj.canonical_bytes(), req.signature)
        # Unknown UAV ID may return UNKNOWN_IDENTITY if lookup fails first.
        if field == "uav_id":
            assert svc.authenticate(bad).outcome in {"INVALID_SIGNATURE", "UNKNOWN_IDENTITY"}
        else:
            # Need a fresh challenge/signature path: nonce already consumed on first parse path.
            # Re-issue for each tamper using a new signed request then mutate.
            ch_i = svc.create_challenge(key.uav_id)
            base = svc.build_signed_request(key, ch_i, "telemetry.submit")
            base_obj = AuthObject.parse(base.body)
            mut = AuthObject(**{**base_obj.__dict__, field: value})
            bad2 = SignedAuthRequest(mut.canonical_bytes(), base.signature)
            assert svc.authenticate(bad2).outcome == "INVALID_SIGNATURE"


def test_unauthorised_reaches_authorisation_reason():
    key = _km(role=ROLE_TELEMETRY)
    records = {
        key.uav_id: IdentityRecord(
            key.uav_id, key.public_key_bytes, key.role, STATUS_ACTIVE, "stub"
        )
    }
    svc = GCSAuthService(StubBackend(records), NonceStore())
    ch = svc.create_challenge(key.uav_id)
    req = svc.build_signed_request(key, ch, "admin.reconfigure")
    assert svc.authenticate(req).outcome == "UNAUTHORISED_OPERATION"
