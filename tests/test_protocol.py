"""Shared protocol tests with a stub identity backend."""

from app.auth.common.protocol import GCSAuthService
from app.auth.models import IdentityRecord, SignedAuthRequest, UAVKeyMaterial
from app.core.constants import ROLE_DELIVERY, ROLE_TELEMETRY, STATUS_ACTIVE, STATUS_REVOKED
from app.core.crypto import generate_uav_key, public_bytes_uncompressed
from app.core.nonce import NonceStore
from app.core.roles import authorise


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


def _key(uav_id="UAV-VALID", role=ROLE_DELIVERY) -> UAVKeyMaterial:
    k = generate_uav_key()
    return UAVKeyMaterial(
        uav_id=uav_id,
        private_key=k,
        public_key=k.public_key(),
        public_key_bytes=public_bytes_uncompressed(k.public_key()),
        role=role,
    )


def _service(keys: list[UAVKeyMaterial], status=STATUS_ACTIVE) -> tuple[GCSAuthService, dict]:
    records = {
        k.uav_id: IdentityRecord(k.uav_id, k.public_key_bytes, k.role, status, "stub") for k in keys
    }
    svc = GCSAuthService(StubBackend(records), NonceStore(), challenge_lifetime_s=2)
    return svc, records


def test_valid_accept():
    key = _key()
    svc, _ = _service([key])
    ch = svc.create_challenge(key.uav_id)
    req = svc.build_signed_request(key, ch, "telemetry.submit")
    dec = svc.authenticate(req)
    assert dec.outcome == "ACCEPTED"


def test_wrong_key():
    key = _key()
    svc, _ = _service([key])
    ch = svc.create_challenge(key.uav_id)
    attacker = _key()
    attacker.uav_id = key.uav_id
    req = svc.build_signed_request(attacker, ch, "telemetry.submit")
    assert svc.authenticate(req).outcome == "INVALID_SIGNATURE"


def test_replay():
    key = _key()
    svc, _ = _service([key])
    ch = svc.create_challenge(key.uav_id)
    req = svc.build_signed_request(key, ch, "telemetry.submit")
    assert svc.authenticate(req).outcome == "ACCEPTED"
    assert svc.authenticate(req).outcome == "REPLAY_DETECTED"


def test_unknown():
    key = _key()
    svc, _ = _service([key])
    ghost = _key("UAV-NONE")
    ch = svc.create_challenge(ghost.uav_id)
    req = svc.build_signed_request(ghost, ch, "telemetry.submit")
    assert svc.authenticate(req).outcome == "UNKNOWN_IDENTITY"


def test_revoked():
    key = _key()
    svc, recs = _service([key], status=STATUS_REVOKED)
    ch = svc.create_challenge(key.uav_id)
    req = svc.build_signed_request(key, ch, "telemetry.submit")
    assert svc.authenticate(req).outcome == "REVOKED_IDENTITY"


def test_unauthorised():
    key = _key(role=ROLE_TELEMETRY)
    svc, _ = _service([key])
    ch = svc.create_challenge(key.uav_id)
    req = svc.build_signed_request(key, ch, "admin.reconfigure")
    assert svc.authenticate(req).outcome == "UNAUTHORISED_OPERATION"


def test_malformed():
    key = _key()
    svc, _ = _service([key])
    svc.create_challenge(key.uav_id)
    dec = svc.authenticate(SignedAuthRequest(b"bad", b"\x00"))
    assert dec.outcome == "MALFORMED_REQUEST"


def test_tamper_operation():
    key = _key()
    svc, _ = _service([key])
    ch = svc.create_challenge(key.uav_id)
    req = svc.build_signed_request(key, ch, "telemetry.submit")
    from app.core.canonical import AuthObject

    obj = AuthObject.parse(req.body)
    obj = AuthObject(**{**obj.__dict__, "requested_operation": "admin.reconfigure"})
    tampered = SignedAuthRequest(obj.canonical_bytes(), req.signature)
    assert svc.authenticate(tampered).outcome == "INVALID_SIGNATURE"


def test_role_matrix():
    assert authorise(ROLE_DELIVERY, "telemetry.submit")
    assert not authorise(ROLE_TELEMETRY, "admin.reconfigure")
