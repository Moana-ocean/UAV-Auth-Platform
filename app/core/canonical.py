"""Deterministic length-prefixed canonical encoding of the authentication object."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from app.core.constants import DOMAIN_LABEL, PROTOCOL_VERSION

MAGIC = b"UAV-GCS-AUTH/v1\n"


def _u32(n: int) -> bytes:
    return struct.pack(">I", n)


def encode_field(value: bytes) -> bytes:
    if len(value) > 0xFFFFFFFF:
        raise ValueError("field too large")
    return _u32(len(value)) + value


def encode_text(value: str) -> bytes:
    return encode_field(value.encode("utf-8"))


@dataclass(frozen=True)
class AuthObject:
    uav_id: str
    gcs_id: str
    nonce: bytes
    session_id: str
    issued_at: int
    expires_at: int
    requested_operation: str
    payload_digest: str = ""
    domain_label: str = DOMAIN_LABEL
    protocol_version: str = PROTOCOL_VERSION

    def canonical_bytes(self) -> bytes:
        if self.domain_label != DOMAIN_LABEL:
            raise ValueError("unsupported domain label")
        if self.protocol_version != PROTOCOL_VERSION:
            raise ValueError("unsupported protocol version")
        parts = [
            MAGIC,
            encode_text(self.domain_label),
            encode_text(self.protocol_version),
            encode_text(self.uav_id),
            encode_text(self.gcs_id),
            encode_field(self.nonce),
            encode_text(self.session_id),
            encode_text(str(int(self.issued_at))),
            encode_text(str(int(self.expires_at))),
            encode_text(self.requested_operation),
            encode_text(self.payload_digest or ""),
        ]
        return b"".join(parts)

    @classmethod
    def parse(cls, data: bytes) -> AuthObject:
        if not data.startswith(MAGIC):
            raise ValueError("malformed authentication object: missing magic")
        offset = len(MAGIC)
        fields: list[bytes] = []
        while offset < len(data):
            if offset + 4 > len(data):
                raise ValueError("malformed authentication object: truncated length")
            (length,) = struct.unpack(">I", data[offset : offset + 4])
            offset += 4
            if offset + length > len(data):
                raise ValueError("malformed authentication object: truncated field")
            fields.append(data[offset : offset + length])
            offset += length
        if len(fields) != 10:
            raise ValueError("malformed authentication object: expected 10 fields")
        domain, version, uav_id, gcs_id, nonce, session_id, issued, expires, op, digest = fields
        return cls(
            domain_label=domain.decode("utf-8"),
            protocol_version=version.decode("utf-8"),
            uav_id=uav_id.decode("utf-8"),
            gcs_id=gcs_id.decode("utf-8"),
            nonce=nonce,
            session_id=session_id.decode("utf-8"),
            issued_at=int(issued.decode("utf-8")),
            expires_at=int(expires.decode("utf-8")),
            requested_operation=op.decode("utf-8"),
            payload_digest=digest.decode("utf-8"),
        )


def payload_digest_hex(payload: bytes) -> str:
    import hashlib

    if not payload:
        return ""
    return hashlib.sha256(payload).hexdigest()
