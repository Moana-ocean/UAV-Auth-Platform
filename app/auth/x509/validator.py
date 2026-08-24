"""X.509 chain, expiry, key-usage and CRL checks."""

from __future__ import annotations

from datetime import UTC, datetime

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

from app.auth.x509.pki import LocalPKI


class CertificateValidationError(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail


def _verify_cert_signature(cert: x509.Certificate, issuer: x509.Certificate) -> None:
    pub = issuer.public_key()
    try:
        if isinstance(pub, rsa.RSAPublicKey):
            pub.verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                padding.PKCS1v15(),
                cert.signature_hash_algorithm,
            )
        elif isinstance(pub, ec.EllipticCurvePublicKey):
            from cryptography.hazmat.primitives.asymmetric.ec import ECDSA

            pub.verify(
                cert.signature, cert.tbs_certificate_bytes, ECDSA(cert.signature_hash_algorithm)
            )
        else:
            raise CertificateValidationError("UNTRUSTED_ISSUER", "unsupported issuer key")
    except InvalidSignature as exc:
        raise CertificateValidationError("UNTRUSTED_ISSUER", "bad issuer signature") from exc


def validate_uav_certificate(
    cert: x509.Certificate,
    pki: LocalPKI,
    expected_uav_id: str,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(UTC)
    if cert.not_valid_before_utc > now or cert.not_valid_after_utc < now:
        raise CertificateValidationError("CERTIFICATE_EXPIRED")

    try:
        ku = cert.extensions.get_extension_for_class(x509.KeyUsage).value
        if not ku.digital_signature:
            raise CertificateValidationError("MALFORMED_REQUEST", "keyUsage")
    except x509.ExtensionNotFound as exc:
        raise CertificateValidationError("MALFORMED_REQUEST", "missing keyUsage") from exc

    cn = cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
    if not cn or cn[0].value != expected_uav_id:
        raise CertificateValidationError("UNKNOWN_IDENTITY", "CN binding")

    issuing = pki.issuing_cert()
    root = pki.root_cert()
    if cert.issuer != issuing.subject:
        raise CertificateValidationError("UNTRUSTED_ISSUER")
    _verify_cert_signature(cert, issuing)
    _verify_cert_signature(issuing, root)

    crl = pki.load_crl()
    if crl.issuer != issuing.subject:
        raise CertificateValidationError("INTERNAL_ERROR", "CRL issuer")
    if crl.get_revoked_certificate_by_serial_number(cert.serial_number) is not None:
        raise CertificateValidationError("REVOKED_IDENTITY")
