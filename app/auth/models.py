from __future__ import annotations

from dataclasses import dataclass, field

from cryptography.hazmat.primitives.asymmetric import ec


@dataclass
class IdentityRecord:
    uav_id: str
    public_key_bytes: bytes
    role: int
    status: int
    source: str
    extra: dict = field(default_factory=dict)


@dataclass
class SignedAuthRequest:
    body: bytes
    signature: bytes
    certificate_der: bytes | None = None


@dataclass
class Challenge:
    session_id: str
    nonce: bytes
    issued_at: int
    expires_at: int
    uav_id: str
    gcs_id: str
    generation_ns: int = 0


@dataclass
class UAVKeyMaterial:
    uav_id: str
    private_key: ec.EllipticCurvePrivateKey
    public_key: ec.EllipticCurvePublicKey
    public_key_bytes: bytes
    role: int
    tags: list[str] = field(default_factory=list)
