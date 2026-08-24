"""ECDSA P-256 / SHA-256 helpers used by both mechanisms."""

from __future__ import annotations

import hashlib
import os

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed

from app.core.constants import NONCE_BYTES


def new_nonce(n: int = NONCE_BYTES) -> bytes:
    if n < 16:
        raise ValueError("nonce must be at least 128 bits")
    return os.urandom(n)


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate_uav_key() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


def public_bytes_uncompressed(public_key: ec.EllipticCurvePublicKey) -> bytes:
    return public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )


def public_key_from_uncompressed(data: bytes) -> ec.EllipticCurvePublicKey:
    return ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), data)


def private_key_to_pem(key: ec.EllipticCurvePrivateKey) -> bytes:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def private_key_from_pem(data: bytes) -> ec.EllipticCurvePrivateKey:
    key = serialization.load_pem_private_key(data, password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise TypeError("expected EC private key")
    return key


def public_key_to_pem(public_key: ec.EllipticCurvePublicKey) -> bytes:
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def sign_prehashed_sha256(private_key: ec.EllipticCurvePrivateKey, digest: bytes) -> bytes:
    if len(digest) != 32:
        raise ValueError("SHA-256 digest must be 32 bytes")
    return private_key.sign(digest, ec.ECDSA(Prehashed(hashes.SHA256())))


def sign_message(private_key: ec.EllipticCurvePrivateKey, message: bytes) -> bytes:
    digest = sha256(message)
    return sign_prehashed_sha256(private_key, digest)


def verify_message(public_key: ec.EllipticCurvePublicKey, message: bytes, signature: bytes) -> bool:
    digest = sha256(message)
    try:
        public_key.verify(signature, digest, ec.ECDSA(Prehashed(hashes.SHA256())))
        return True
    except InvalidSignature:
        return False
    except ValueError:
        return False
