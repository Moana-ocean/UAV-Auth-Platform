"""Generate a comparable UAV population for X.509 and the blockchain registry."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization

from app.auth.models import UAVKeyMaterial
from app.auth.x509.pki import LocalPKI
from app.core.constants import (
    ROLE_DELIVERY,
    ROLE_TELEMETRY,
    TEST_KEY_WARNING,
)
from app.core.crypto import (
    generate_uav_key,
    private_key_from_pem,
    private_key_to_pem,
    public_bytes_uncompressed,
)

SPECIAL_IDS = {
    "UAV-VALID": {"role": ROLE_DELIVERY, "tags": ["valid"]},
    "UAV-REVOKED": {"role": ROLE_DELIVERY, "tags": ["revoked"]},
    "UAV-LIMITED": {"role": ROLE_TELEMETRY, "tags": ["limited"]},
    "UAV-EXPIRED": {"role": ROLE_DELIVERY, "tags": ["expired_cert"]},
    "UAV-UNTRUSTED": {"role": ROLE_DELIVERY, "tags": ["untrusted"]},
}


class IdentityPopulation:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.keys_dir = self.data_dir / "uav_keys"
        self.meta_path = self.data_dir / "identities.json"
        self.roles_path = self.data_dir / "x509_roles.json"
        self.pki = LocalPKI(self.data_dir)

    def generate(self, n_identities: int) -> dict[str, Any]:
        """Create or grow the UAV population without rotating existing keys."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        self.pki.initialise()
        n_identities = max(int(n_identities), len(SPECIAL_IDS))
        existing = self.load_meta().get("identities", [])
        by_id = {r["uav_id"]: r for r in existing}
        records = list(existing)
        roles: dict[str, int] = {}
        if self.roles_path.exists():
            roles = {k: int(v) for k, v in json.loads(self.roles_path.read_text(encoding="utf-8")).items()}
        for rec in existing:
            roles.setdefault(rec["uav_id"], int(rec["role"]))
        special_names = list(SPECIAL_IDS.keys())
        added = 0
        for i in range(n_identities):
            if i < len(special_names):
                uav_id = special_names[i]
                spec = SPECIAL_IDS[uav_id]
            else:
                uav_id = f"UAV-{i:04d}"
                spec = {"role": ROLE_DELIVERY, "tags": ["valid"]}
            if uav_id in by_id:
                continue
            key = generate_uav_key()
            pem_path = self.keys_dir / f"{uav_id}.pem"
            pem_path.write_bytes(private_key_to_pem(key))
            pub = public_bytes_uncompressed(key.public_key())
            now = datetime.now(UTC)
            if "expired_cert" in spec["tags"]:
                cert = self.pki.issue_uav_certificate(
                    uav_id,
                    key.public_key(),
                    not_before=now - timedelta(days=40),
                    not_after=now - timedelta(days=1),
                )
            elif "untrusted" in spec["tags"]:
                cert = self.pki.issue_uav_certificate(uav_id, key.public_key(), untrusted=True)
            else:
                cert = self.pki.issue_uav_certificate(uav_id, key.public_key())
            if "revoked" in spec["tags"]:
                self.pki.revoke(cert.serial_number)
            roles[uav_id] = int(spec["role"])
            rec = {
                "uav_id": uav_id,
                "role": spec["role"],
                "tags": spec["tags"],
                "public_key_hex": pub.hex(),
                "cert_serial": cert.serial_number,
                "cert_pem": str((self.pki.ca_dir / "uavs" / f"{uav_id}.pem").as_posix()),
                "key_pem": str(pem_path.as_posix()),
                "warning": TEST_KEY_WARNING,
            }
            records.append(rec)
            by_id[uav_id] = rec
            added += 1
        payload = {
            "warning": TEST_KEY_WARNING,
            "count": len(records),
            "added": added,
            "reused_existing": len(records) - added,
            "identities": records,
        }
        self.meta_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.roles_path.write_text(json.dumps(roles, indent=2), encoding="utf-8")
        return payload

    def load_meta(self) -> dict[str, Any]:
        if not self.meta_path.exists():
            return {"identities": []}
        return json.loads(self.meta_path.read_text(encoding="utf-8"))

    def load_key(self, uav_id: str) -> UAVKeyMaterial:
        meta = self.load_meta()
        rec = next((r for r in meta["identities"] if r["uav_id"] == uav_id), None)
        if rec is None:
            raise KeyError(uav_id)
        key = private_key_from_pem(Path(rec["key_pem"]).read_bytes())
        # Always derive the public key from the PEM private key so signing and
        # local verification cannot drift from a stale public_key_hex field.
        derived = public_bytes_uncompressed(key.public_key())
        return UAVKeyMaterial(
            uav_id=uav_id,
            private_key=key,
            public_key=key.public_key(),
            public_key_bytes=derived,
            role=int(rec["role"]),
            tags=list(rec.get("tags", [])),
        )

    def certificate_der(self, uav_id: str) -> bytes:
        der = self.pki.ca_dir / "uavs" / f"{uav_id}.der"
        if der.exists():
            return der.read_bytes()
        pem = self.pki.ca_dir / "uavs" / f"{uav_id}.pem"
        from cryptography import x509

        cert = x509.load_pem_x509_certificate(pem.read_bytes())
        return cert.public_bytes(serialization.Encoding.DER)

    def ids_with_tag(self, tag: str) -> list[str]:
        return [
            r["uav_id"] for r in self.load_meta().get("identities", []) if tag in r.get("tags", [])
        ]

    def valid_ids(self) -> list[str]:
        return self.ids_with_tag("valid")

    def comparable_summary(self) -> dict[str, Any]:
        meta = self.load_meta()
        return {
            "count": len(meta.get("identities", [])),
            "valid": len(self.ids_with_tag("valid")),
            "revoked": len(self.ids_with_tag("revoked")),
            "expired_cert": len(self.ids_with_tag("expired_cert")),
            "untrusted": len(self.ids_with_tag("untrusted")),
            "limited": len(self.ids_with_tag("limited")),
        }
