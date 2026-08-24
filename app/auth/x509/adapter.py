"""X.509 identity backend for the shared GCS protocol."""

from __future__ import annotations

import json
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization

from app.auth.common.protocol import IdentityBackend
from app.auth.models import IdentityRecord, SignedAuthRequest
from app.auth.x509.pki import LocalPKI
from app.auth.x509.validator import CertificateValidationError, validate_uav_certificate
from app.core.canonical import AuthObject
from app.core.constants import STATUS_ACTIVE, STATUS_REVOKED
from app.core.crypto import public_bytes_uncompressed


class X509IdentityBackend(IdentityBackend):
    name = "x509"

    def __init__(
        self, pki: LocalPKI, roles: dict[str, int], certs: dict[str, bytes] | None = None
    ) -> None:
        self.pki = pki
        self.roles = roles
        self.certs = certs or {}

    def lookup(
        self, uav_id: str, certificate_der: bytes | None = None
    ) -> tuple[IdentityRecord | None, str]:
        der = certificate_der or self.certs.get(uav_id)
        if der is None:
            der_path = self.pki.ca_dir / "uavs" / f"{uav_id}.der"
            pem_path = self.pki.ca_dir / "uavs" / f"{uav_id}.pem"
            if der_path.exists():
                der = der_path.read_bytes()
            elif pem_path.exists():
                cert = x509.load_pem_x509_certificate(pem_path.read_bytes())
                der = cert.public_bytes(serialization.Encoding.DER)
            else:
                return None, "UNKNOWN_IDENTITY"
        try:
            cert = x509.load_der_x509_certificate(der)
        except ValueError:
            try:
                cert = x509.load_pem_x509_certificate(der)
            except ValueError:
                return None, "MALFORMED_REQUEST"
        pub = public_bytes_uncompressed(cert.public_key())  # type: ignore[arg-type]
        record = IdentityRecord(
            uav_id=uav_id,
            public_key_bytes=pub,
            role=int(self.roles.get(uav_id, 0)),
            status=STATUS_ACTIVE,
            source="x509",
            extra={"serial": cert.serial_number, "certificate": cert},
        )
        return record, ""

    def validate_binding(
        self, record: IdentityRecord, request: SignedAuthRequest, obj: AuthObject
    ) -> tuple[bool, str]:
        cert = record.extra.get("certificate")
        if cert is None:
            return False, "UNKNOWN_IDENTITY"
        try:
            validate_uav_certificate(cert, self.pki, obj.uav_id)
        except CertificateValidationError as exc:
            if exc.reason == "REVOKED_IDENTITY":
                record.status = STATUS_REVOKED
            return False, exc.reason
        return True, ""


def load_roles(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: int(v) for k, v in data.items()}
