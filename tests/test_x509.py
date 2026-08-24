"""X.509 PKI baseline tests."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.auth.common.protocol import GCSAuthService
from app.auth.models import UAVKeyMaterial
from app.auth.x509.adapter import X509IdentityBackend
from app.auth.x509.pki import LocalPKI
from app.core.constants import ROLE_DELIVERY
from app.core.crypto import generate_uav_key, public_bytes_uncompressed
from app.core.nonce import NonceStore
from cryptography.hazmat.primitives import serialization


def _setup(tmp_path: Path):
    pki = LocalPKI(tmp_path)
    pki.initialise()
    key = generate_uav_key()
    cert = pki.issue_uav_certificate("UAV-VALID", key.public_key())
    km = UAVKeyMaterial(
        "UAV-VALID",
        key,
        key.public_key(),
        public_bytes_uncompressed(key.public_key()),
        ROLE_DELIVERY,
    )
    backend = X509IdentityBackend(pki, {"UAV-VALID": ROLE_DELIVERY})
    svc = GCSAuthService(backend, NonceStore(), challenge_lifetime_s=5)
    der = cert.public_bytes(serialization.Encoding.DER)
    return pki, km, svc, der, cert


def test_valid_chain(tmp_path):
    _, km, svc, der, _ = _setup(tmp_path)
    ch = svc.create_challenge(km.uav_id)
    req = svc.build_signed_request(km, ch, "telemetry.submit", certificate_der=der)
    assert svc.authenticate(req).outcome == "ACCEPTED"


def test_expired_cert(tmp_path):
    pki, km, svc, _, _ = _setup(tmp_path)
    now = datetime.now(UTC)
    cert = pki.issue_uav_certificate(
        "UAV-EXPIRED",
        km.public_key,
        not_before=now - timedelta(days=10),
        not_after=now - timedelta(days=1),
    )
    backend = X509IdentityBackend(pki, {"UAV-EXPIRED": ROLE_DELIVERY})
    svc = GCSAuthService(backend, NonceStore())
    km2 = UAVKeyMaterial(
        "UAV-EXPIRED", km.private_key, km.public_key, km.public_key_bytes, ROLE_DELIVERY
    )
    ch = svc.create_challenge("UAV-EXPIRED")
    req = svc.build_signed_request(
        km2, ch, "telemetry.submit", certificate_der=cert.public_bytes(serialization.Encoding.DER)
    )
    assert svc.authenticate(req).outcome == "CERTIFICATE_EXPIRED"


def test_revoked_cert(tmp_path):
    pki, km, svc, der, cert = _setup(tmp_path)
    pki.revoke(cert.serial_number)
    ch = svc.create_challenge(km.uav_id)
    req = svc.build_signed_request(km, ch, "telemetry.submit", certificate_der=der)
    assert svc.authenticate(req).outcome == "REVOKED_IDENTITY"


def test_untrusted_issuer(tmp_path):
    pki, km, svc, _, _ = _setup(tmp_path)
    cert = pki.issue_uav_certificate("UAV-UNTRUSTED", km.public_key, untrusted=True)
    backend = X509IdentityBackend(pki, {"UAV-UNTRUSTED": ROLE_DELIVERY})
    svc = GCSAuthService(backend, NonceStore())
    km2 = UAVKeyMaterial(
        "UAV-UNTRUSTED", km.private_key, km.public_key, km.public_key_bytes, ROLE_DELIVERY
    )
    ch = svc.create_challenge("UAV-UNTRUSTED")
    req = svc.build_signed_request(
        km2, ch, "telemetry.submit", certificate_der=cert.public_bytes(serialization.Encoding.DER)
    )
    assert svc.authenticate(req).outcome == "UNTRUSTED_ISSUER"


def test_wrong_key_x509(tmp_path):
    _, km, svc, der, _ = _setup(tmp_path)
    attacker = generate_uav_key()
    bad = UAVKeyMaterial(
        km.uav_id,
        attacker,
        attacker.public_key(),
        public_bytes_uncompressed(attacker.public_key()),
        ROLE_DELIVERY,
    )
    ch = svc.create_challenge(km.uav_id)
    req = svc.build_signed_request(bad, ch, "telemetry.submit", certificate_der=der)
    assert svc.authenticate(req).outcome == "INVALID_SIGNATURE"
