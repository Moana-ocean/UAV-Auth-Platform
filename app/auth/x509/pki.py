"""X.509 test PKI: root CA, issuing CA, UAV certificates, CRL revocation."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from app.core.constants import TEST_KEY_WARNING
from app.core.crypto import generate_uav_key, private_key_from_pem, private_key_to_pem

ORG = "UAV-Auth-Experiment"


def _now() -> datetime:
    return datetime.now(UTC)


def _name(common_name: str) -> x509.Name:
    return x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, ORG),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )


def _save_pem(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    readme = path.parent / "README.txt"
    if not readme.exists():
        readme.write_text(TEST_KEY_WARNING + "\n", encoding="utf-8")


class LocalPKI:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.ca_dir = self.root / "pki"
        self._lock = threading.Lock()
        self._serial = 1
        self._revoked: dict[int, datetime] = {}

    @property
    def root_key_path(self) -> Path:
        return self.ca_dir / "root_ca_key.pem"

    @property
    def root_cert_path(self) -> Path:
        return self.ca_dir / "root_ca.pem"

    @property
    def issuing_key_path(self) -> Path:
        return self.ca_dir / "issuing_ca_key.pem"

    @property
    def issuing_cert_path(self) -> Path:
        return self.ca_dir / "issuing_ca.pem"

    @property
    def crl_path(self) -> Path:
        return self.ca_dir / "issuing.crl"

    @property
    def untrusted_key_path(self) -> Path:
        return self.ca_dir / "untrusted_ca_key.pem"

    @property
    def untrusted_cert_path(self) -> Path:
        return self.ca_dir / "untrusted_ca.pem"

    @property
    def state_path(self) -> Path:
        return self.ca_dir / "serial_state.json"

    def initialise(self) -> None:
        self.ca_dir.mkdir(parents=True, exist_ok=True)
        if self.root_cert_path.exists() and self.issuing_cert_path.exists():
            self._load_serial()
            return
        root_key = generate_uav_key()
        root_cert = (
            x509.CertificateBuilder()
            .subject_name(_name("Experiment Root CA"))
            .issuer_name(_name("Experiment Root CA"))
            .public_key(root_key.public_key())
            .serial_number(1)
            .not_valid_before(_now() - timedelta(minutes=1))
            .not_valid_after(_now() + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(root_key, hashes.SHA256())
        )
        issuing_key = generate_uav_key()
        issuing_cert = (
            x509.CertificateBuilder()
            .subject_name(_name("Experiment Issuing CA"))
            .issuer_name(root_cert.subject)
            .public_key(issuing_key.public_key())
            .serial_number(2)
            .not_valid_before(_now() - timedelta(minutes=1))
            .not_valid_after(_now() + timedelta(days=1825))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()),
                critical=False,
            )
            .sign(root_key, hashes.SHA256())
        )
        untrusted_key = generate_uav_key()
        untrusted_cert = (
            x509.CertificateBuilder()
            .subject_name(_name("Untrusted Experiment CA"))
            .issuer_name(_name("Untrusted Experiment CA"))
            .public_key(untrusted_key.public_key())
            .serial_number(1)
            .not_valid_before(_now() - timedelta(minutes=1))
            .not_valid_after(_now() + timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(untrusted_key, hashes.SHA256())
        )
        _save_pem(self.root_key_path, private_key_to_pem(root_key))
        _save_pem(self.root_cert_path, root_cert.public_bytes(serialization.Encoding.PEM))
        _save_pem(self.issuing_key_path, private_key_to_pem(issuing_key))
        _save_pem(self.issuing_cert_path, issuing_cert.public_bytes(serialization.Encoding.PEM))
        _save_pem(self.untrusted_key_path, private_key_to_pem(untrusted_key))
        _save_pem(self.untrusted_cert_path, untrusted_cert.public_bytes(serialization.Encoding.PEM))
        self._serial = 100
        self._revoked = {}
        self._persist_serial()
        self.write_crl()

    def _load_serial(self) -> None:
        if self.state_path.exists():
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            self._serial = int(data.get("serial", 100))
            self._revoked = {
                int(k): datetime.fromisoformat(v) for k, v in data.get("revoked", {}).items()
            }
        else:
            self._serial = 100

    def _persist_serial(self) -> None:
        payload = {
            "serial": self._serial,
            "revoked": {str(k): v.isoformat() for k, v in self._revoked.items()},
            "warning": TEST_KEY_WARNING,
        }
        self.state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _next_serial(self) -> int:
        with self._lock:
            n = self._serial
            self._serial += 1
            self._persist_serial()
            return n

    def issuing_cert(self) -> x509.Certificate:
        return x509.load_pem_x509_certificate(self.issuing_cert_path.read_bytes())

    def root_cert(self) -> x509.Certificate:
        return x509.load_pem_x509_certificate(self.root_cert_path.read_bytes())

    def issuing_key(self) -> ec.EllipticCurvePrivateKey:
        return private_key_from_pem(self.issuing_key_path.read_bytes())

    def untrusted_key(self) -> ec.EllipticCurvePrivateKey:
        return private_key_from_pem(self.untrusted_key_path.read_bytes())

    def untrusted_cert(self) -> x509.Certificate:
        return x509.load_pem_x509_certificate(self.untrusted_cert_path.read_bytes())

    def issue_uav_certificate(
        self,
        uav_id: str,
        public_key: ec.EllipticCurvePublicKey,
        *,
        not_before: datetime | None = None,
        not_after: datetime | None = None,
        untrusted: bool = False,
    ) -> x509.Certificate:
        self.initialise()
        serial = self._next_serial()
        nb = not_before or (_now() - timedelta(minutes=1))
        na = not_after or (_now() + timedelta(days=365))
        if untrusted:
            issuer_cert = self.untrusted_cert()
            issuer_key = self.untrusted_key()
        else:
            issuer_cert = self.issuing_cert()
            issuer_key = self.issuing_key()
        cert = (
            x509.CertificateBuilder()
            .subject_name(_name(uav_id))
            .issuer_name(issuer_cert.subject)
            .public_key(public_key)
            .serial_number(serial)
            .not_valid_before(nb)
            .not_valid_after(na)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]),
                critical=False,
            )
            .add_extension(
                x509.SubjectAlternativeName([x509.UniformResourceIdentifier(f"uav:{uav_id}")]),
                critical=False,
            )
            .sign(issuer_key, hashes.SHA256())
        )
        out = self.ca_dir / "uavs" / f"{uav_id}.pem"
        _save_pem(out, cert.public_bytes(serialization.Encoding.PEM))
        der = self.ca_dir / "uavs" / f"{uav_id}.der"
        der.write_bytes(cert.public_bytes(serialization.Encoding.DER))
        return cert

    def revoke(self, serial: int) -> None:
        self._revoked[int(serial)] = _now()
        self._persist_serial()
        self.write_crl()

    def write_crl(self) -> x509.CertificateRevocationList:
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(self.issuing_cert().subject)
            .last_update(_now())
            .next_update(_now() + timedelta(days=7))
        )
        for serial, when in self._revoked.items():
            revoked = (
                x509.RevokedCertificateBuilder().serial_number(serial).revocation_date(when).build()
            )
            builder = builder.add_revoked_certificate(revoked)
        crl = builder.sign(self.issuing_key(), hashes.SHA256())
        self.crl_path.write_bytes(crl.public_bytes(serialization.Encoding.PEM))
        return crl

    def load_crl(self) -> x509.CertificateRevocationList:
        if not self.crl_path.exists():
            return self.write_crl()
        return x509.load_pem_x509_crl(self.crl_path.read_bytes())

    def status(self) -> dict:
        self.initialise()
        uav_dir = self.ca_dir / "uavs"
        n_certs = len(list(uav_dir.glob("*.pem"))) if uav_dir.exists() else 0
        return {
            "root_ca": str(self.root_cert_path),
            "issuing_ca": str(self.issuing_cert_path),
            "crl": str(self.crl_path),
            "issued_certificates": n_certs,
            "revoked_serials": len(self._revoked),
            "next_serial": self._serial,
            "revocation_method": "local_crl",
        }
