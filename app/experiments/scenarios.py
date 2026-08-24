"""Repeatable attack and negative-test request builders."""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.auth.common.protocol import GCSAuthService
from app.auth.models import SignedAuthRequest, UAVKeyMaterial
from app.core.canonical import AuthObject
from app.core.constants import OPERATION_ADMIN_RECONFIGURE
from app.core.crypto import generate_uav_key, public_bytes_uncompressed
from app.experiments.identities import IdentityPopulation


@dataclass
class PreparedAttempt:
    request: SignedAuthRequest
    expected: str
    uav_id: str
    challenge_generation_ns: int = 0
    notes: str = ""


def _valid_key(pop: IdentityPopulation) -> UAVKeyMaterial:
    ids = pop.valid_ids()
    if not ids:
        raise RuntimeError("no valid UAV identities; run init-identities")
    return pop.load_key(ids[0])


def prepare_attempt(
    service: GCSAuthService,
    pop: IdentityPopulation,
    scenario: str,
    operation: str,
    payload_digest: str,
    mechanism: str,
    challenge_lifetime_s: float,
) -> PreparedAttempt:
    if scenario in {"valid_active", "concurrent_valid"}:
        key = _valid_key(pop)
        ch = service.create_challenge(key.uav_id)
        cert = pop.certificate_der(key.uav_id) if mechanism == "x509" else None
        req = service.build_signed_request(key, ch, operation, payload_digest, cert)
        return PreparedAttempt(req, "ACCEPTED", key.uav_id, ch.generation_ns)

    if scenario == "unknown_uav":
        key = _valid_key(pop)
        ghost = UAVKeyMaterial(
            uav_id="UAV-NOT-REGISTERED",
            private_key=key.private_key,
            public_key=key.public_key,
            public_key_bytes=key.public_key_bytes,
            role=key.role,
        )
        ch = service.create_challenge(ghost.uav_id)
        req = service.build_signed_request(ghost, ch, operation, payload_digest, None)
        return PreparedAttempt(req, "UNKNOWN_IDENTITY", ghost.uav_id, ch.generation_ns)

    if scenario == "impersonation_wrong_key":
        key = _valid_key(pop)
        ch = service.create_challenge(key.uav_id)
        attacker = generate_uav_key()
        fake = UAVKeyMaterial(
            uav_id=key.uav_id,
            private_key=attacker,
            public_key=attacker.public_key(),
            public_key_bytes=public_bytes_uncompressed(attacker.public_key()),
            role=key.role,
        )
        cert = pop.certificate_der(key.uav_id) if mechanism == "x509" else None
        req = service.build_signed_request(fake, ch, operation, payload_digest, cert)
        return PreparedAttempt(req, "INVALID_SIGNATURE", key.uav_id, ch.generation_ns)

    if scenario == "replay":
        key = _valid_key(pop)
        ch = service.create_challenge(key.uav_id)
        cert = pop.certificate_der(key.uav_id) if mechanism == "x509" else None
        req = service.build_signed_request(key, ch, operation, payload_digest, cert)
        first = service.authenticate(req)
        if first.outcome != "ACCEPTED":
            return PreparedAttempt(
                req, "REPLAY_DETECTED", key.uav_id, ch.generation_ns, "setup-not-accepted"
            )
        return PreparedAttempt(req, "REPLAY_DETECTED", key.uav_id, ch.generation_ns)

    if scenario in {"modified_nonce", "modified_uav_id", "modified_operation"}:
        key = _valid_key(pop)
        ch = service.create_challenge(key.uav_id)
        cert = pop.certificate_der(key.uav_id) if mechanism == "x509" else None
        req = service.build_signed_request(key, ch, operation, payload_digest, cert)
        obj = AuthObject.parse(req.body)
        if scenario == "modified_nonce":
            obj = AuthObject(**{**obj.__dict__, "nonce": b"\x00" * 16})
            cert_out = cert
        elif scenario == "modified_uav_id":
            others = [i for i in pop.valid_ids() if i != key.uav_id]
            new_id = others[0] if others else "UAV-0007"
            obj = AuthObject(**{**obj.__dict__, "uav_id": new_id})
            cert_out = None
        else:
            obj = AuthObject(**{**obj.__dict__, "requested_operation": OPERATION_ADMIN_RECONFIGURE})
            cert_out = cert
        tampered = SignedAuthRequest(
            body=obj.canonical_bytes(), signature=req.signature, certificate_der=cert_out
        )
        return PreparedAttempt(tampered, "INVALID_SIGNATURE", obj.uav_id, ch.generation_ns)

    if scenario == "expired_challenge":
        key = _valid_key(pop)
        ch = service.create_challenge(key.uav_id, lifetime_s=0.05)
        time.sleep(0.12)
        cert = pop.certificate_der(key.uav_id) if mechanism == "x509" else None
        req = service.build_signed_request(key, ch, operation, payload_digest, cert)
        return PreparedAttempt(req, "EXPIRED_CHALLENGE", key.uav_id, ch.generation_ns)

    if scenario == "revoked_uav":
        ids = pop.ids_with_tag("revoked")
        if not ids:
            raise RuntimeError("revoked UAV missing from population")
        key = pop.load_key(ids[0])
        ch = service.create_challenge(key.uav_id)
        cert = pop.certificate_der(key.uav_id) if mechanism == "x509" else None
        req = service.build_signed_request(key, ch, operation, payload_digest, cert)
        return PreparedAttempt(req, "REVOKED_IDENTITY", key.uav_id, ch.generation_ns)

    if scenario == "unauthorised_operation":
        ids = pop.ids_with_tag("limited")
        key = pop.load_key(ids[0]) if ids else _valid_key(pop)
        ch = service.create_challenge(key.uav_id)
        cert = pop.certificate_der(key.uav_id) if mechanism == "x509" else None
        req = service.build_signed_request(
            key, ch, OPERATION_ADMIN_RECONFIGURE, payload_digest, cert
        )
        return PreparedAttempt(req, "UNAUTHORISED_OPERATION", key.uav_id, ch.generation_ns)

    if scenario == "malformed":
        key = _valid_key(pop)
        ch = service.create_challenge(key.uav_id)
        req = SignedAuthRequest(
            body=b"not-an-auth-object", signature=b"\x00" * 8, certificate_der=None
        )
        return PreparedAttempt(req, "MALFORMED_REQUEST", key.uav_id, ch.generation_ns)

    if scenario == "expired_certificate":
        ids = pop.ids_with_tag("expired_cert")
        if not ids:
            raise RuntimeError("expired-cert UAV missing")
        key = pop.load_key(ids[0])
        ch = service.create_challenge(key.uav_id)
        req = service.build_signed_request(
            key, ch, operation, payload_digest, pop.certificate_der(key.uav_id)
        )
        return PreparedAttempt(req, "CERTIFICATE_EXPIRED", key.uav_id, ch.generation_ns)

    if scenario == "untrusted_issuer":
        ids = pop.ids_with_tag("untrusted")
        if not ids:
            raise RuntimeError("untrusted UAV missing")
        key = pop.load_key(ids[0])
        ch = service.create_challenge(key.uav_id)
        req = service.build_signed_request(
            key, ch, operation, payload_digest, pop.certificate_der(key.uav_id)
        )
        return PreparedAttempt(req, "UNTRUSTED_ISSUER", key.uav_id, ch.generation_ns)

    if scenario == "rpc_unavailable":
        key = _valid_key(pop)
        ch = service.create_challenge(key.uav_id)
        req = service.build_signed_request(key, ch, operation, payload_digest, None)
        return PreparedAttempt(req, "IDENTITY_SERVICE_UNAVAILABLE", key.uav_id, ch.generation_ns)

    if scenario == "concurrent_mixed":
        # Caller uses this as a valid request; mixed batches are assembled in the runner.
        return prepare_attempt(
            service, pop, "valid_active", operation, payload_digest, mechanism, challenge_lifetime_s
        )

    raise ValueError(f"unknown scenario {scenario}")


def mixed_kind(index: int) -> str:
    kinds = ["valid_active", "impersonation_wrong_key", "unknown_uav", "malformed"]
    return kinds[index % len(kinds)]
