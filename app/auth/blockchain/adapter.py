"""Blockchain identity backend: read-only registry lookup plus optional audit tx."""

from __future__ import annotations

from app.auth.blockchain.registry import RegistryAdapter
from app.auth.common.protocol import IdentityBackend
from app.auth.models import IdentityRecord, SignedAuthRequest
from app.core.canonical import AuthObject
from app.core.constants import STATUS_NONE
from app.core.crypto import sha256


class BlockchainUnavailable(RuntimeError):
    """RPC endpoint missing, timed out or returned an error."""


class BlockchainIdentityBackend(IdentityBackend):
    name = "blockchain"

    def __init__(self, adapter: RegistryAdapter, audit_tx: bool = False) -> None:
        self.adapter = adapter
        self.audit_tx = audit_tx

    def lookup(
        self, uav_id: str, certificate_der: bytes | None = None
    ) -> tuple[IdentityRecord | None, str]:
        try:
            rec = self.adapter.get_record(uav_id)
        except Exception as exc:  # noqa: BLE001
            name = type(exc).__name__
            if "timeout" in name.lower() or "Time" in name:
                return None, "IDENTITY_SERVICE_UNAVAILABLE"
            if "Connection" in name or "timeout" in str(exc).lower():
                return None, "IDENTITY_SERVICE_UNAVAILABLE"
            return None, "IDENTITY_SERVICE_UNAVAILABLE"
        if rec["status"] == STATUS_NONE or not rec["public_key"]:
            return None, "UNKNOWN_IDENTITY"
        record = IdentityRecord(
            uav_id=uav_id,
            public_key_bytes=rec["public_key"],
            role=int(rec["role"]),
            status=int(rec["status"]),
            source="blockchain",
            extra=rec,
        )
        return record, ""

    def validate_binding(
        self, record: IdentityRecord, request: SignedAuthRequest, obj: AuthObject
    ) -> tuple[bool, str]:
        if record.uav_id != obj.uav_id:
            return False, "UNKNOWN_IDENTITY"
        if not record.public_key_bytes:
            return False, "UNKNOWN_IDENTITY"
        return True, ""

    def maybe_audit(self, uav_id: str, outcome: str) -> dict:
        if not self.audit_tx:
            return {}
        try:
            return self.adapter.record_audit(uav_id, sha256(outcome.encode("utf-8")))
        except Exception as exc:  # noqa: BLE001
            return {"error": type(exc).__name__}
