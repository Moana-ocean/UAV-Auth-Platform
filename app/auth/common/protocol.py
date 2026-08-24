"""Shared GCS challenge-response service.

Mechanism-specific work is limited to identity lookup / status. Signature
verification, nonce consumption, expiry and RBAC use this module for both
X.509 and blockchain so measured differences come from identity-status lookup.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from cryptography.hazmat.primitives.asymmetric import ec

from app.auth.models import Challenge, IdentityRecord, SignedAuthRequest, UAVKeyMaterial
from app.core.canonical import AuthObject
from app.core.clocks import now_ns, timed
from app.core.constants import (
    DEFAULT_GCS_ID,
    DOMAIN_LABEL,
    PROTOCOL_VERSION,
    STATUS_ACTIVE,
    STATUS_REVOKED,
    STATUS_SUSPENDED,
)
from app.core.crypto import public_key_from_uncompressed, sign_message, verify_message
from app.core.nonce import NonceStore
from app.core.roles import authorise
from app.core.schemas import AuthDecision, Timings


class IdentityBackend(Protocol):
    name: str

    def lookup(
        self, uav_id: str, certificate_der: bytes | None = None
    ) -> tuple[IdentityRecord | None, str]:
        """Return (record or None, reason_if_failed_or_empty)."""

    def validate_binding(
        self, record: IdentityRecord, request: SignedAuthRequest, obj: AuthObject
    ) -> tuple[bool, str]:
        """Mechanism-specific binding check. Returns (ok, reason_if_failed)."""


@dataclass
class GCSAuthService:
    backend: IdentityBackend
    nonce_store: NonceStore
    gcs_id: str = DEFAULT_GCS_ID
    challenge_lifetime_s: float = 5.0
    public_key_loader: Callable[[bytes], ec.EllipticCurvePublicKey] | None = None

    def create_challenge(self, uav_id: str, lifetime_s: float | None = None) -> Challenge:
        with timed() as elapsed:
            rec = self.nonce_store.create(uav_id, lifetime_s or self.challenge_lifetime_s)
        return Challenge(
            session_id=rec.session_id,
            nonce=rec.nonce,
            issued_at=int(rec.issued_at),
            expires_at=int(rec.expires_at),
            uav_id=uav_id,
            gcs_id=self.gcs_id,
            generation_ns=elapsed(),
        )

    def build_signed_request(
        self,
        key: UAVKeyMaterial,
        challenge: Challenge,
        operation: str,
        payload_digest: str = "",
        certificate_der: bytes | None = None,
    ) -> SignedAuthRequest:
        obj = AuthObject(
            uav_id=key.uav_id,
            gcs_id=challenge.gcs_id,
            nonce=challenge.nonce,
            session_id=challenge.session_id,
            issued_at=challenge.issued_at,
            expires_at=challenge.expires_at,
            requested_operation=operation,
            payload_digest=payload_digest,
            domain_label=DOMAIN_LABEL,
            protocol_version=PROTOCOL_VERSION,
        )
        body = obj.canonical_bytes()
        signature = sign_message(key.private_key, body)
        return SignedAuthRequest(body=body, signature=signature, certificate_der=certificate_der)

    def authenticate(self, request: SignedAuthRequest) -> AuthDecision:
        timings = Timings()
        t0 = now_ns()
        outcome = "INTERNAL_ERROR"
        detail = ""
        try:
            outcome, detail, timings = self._authenticate_inner(request, timings)
        except Exception as exc:  # noqa: BLE001 — fail closed
            outcome = "INTERNAL_ERROR"
            detail = type(exc).__name__
        timings.decision_latency_ns = now_ns() - t0
        return AuthDecision(
            outcome=outcome,
            reason_detail=detail,
            timings=timings,
            request_bytes=len(request.body) + len(request.signature),
            response_bytes=len(outcome.encode("utf-8")),
        )

    def _authenticate_inner(
        self, request: SignedAuthRequest, timings: Timings
    ) -> tuple[str, str, Timings]:
        try:
            obj = AuthObject.parse(request.body)
        except (ValueError, UnicodeDecodeError) as exc:
            self._consume_best_effort(request)
            return "MALFORMED_REQUEST", str(exc), timings

        if obj.domain_label != DOMAIN_LABEL or obj.protocol_version != PROTOCOL_VERSION:
            self._consume_best_effort(request, obj)
            return "MALFORMED_REQUEST", "domain/version", timings
        if obj.gcs_id != self.gcs_id:
            self._consume_best_effort(request, obj)
            return "MALFORMED_REQUEST", "gcs_id mismatch", timings
        if not request.signature:
            self._consume_best_effort(request, obj)
            return "MALFORMED_REQUEST", "missing signature", timings

        nonce_result = self.nonce_store.consume(obj.session_id, obj.nonce)
        if nonce_result == "REPLAY_DETECTED":
            return "REPLAY_DETECTED", "", timings
        if nonce_result == "EXPIRED_CHALLENGE":
            return "EXPIRED_CHALLENGE", "", timings
        if nonce_result == "MALFORMED_REQUEST":
            return "MALFORMED_REQUEST", "unknown session", timings
        if nonce_result == "INVALID_SIGNATURE":
            return "INVALID_SIGNATURE", "nonce mismatch", timings

        with timed() as elapsed:
            record, reason = self.backend.lookup(obj.uav_id, request.certificate_der)
        timings.identity_lookup_ns = elapsed()
        if reason:
            return reason, "", timings
        if record is None:
            return "UNKNOWN_IDENTITY", "", timings

        with timed() as elapsed:
            bind_ok, bind_reason = self.backend.validate_binding(record, request, obj)
        extra_ns = elapsed()
        if self.backend.name == "x509":
            timings.certificate_validation_ns = extra_ns
        else:
            timings.contract_call_ns = extra_ns
        if not bind_ok and bind_reason:
            return bind_reason, "", timings

        if record.status == STATUS_REVOKED:
            return "REVOKED_IDENTITY", "", timings
        if record.status == STATUS_SUSPENDED:
            return "SUSPENDED_IDENTITY", "", timings
        if record.status != STATUS_ACTIVE:
            return "UNKNOWN_IDENTITY", "inactive", timings

        loader = self.public_key_loader or public_key_from_uncompressed
        try:
            public_key = loader(record.public_key_bytes)
        except Exception as exc:  # noqa: BLE001
            return "INTERNAL_ERROR", f"public-key parse: {type(exc).__name__}", timings

        with timed() as elapsed:
            sig_ok = verify_message(public_key, request.body, request.signature)
        timings.signature_verification_ns = elapsed()
        if not sig_ok:
            return "INVALID_SIGNATURE", "", timings

        with timed() as elapsed:
            allowed = authorise(record.role, obj.requested_operation)
        timings.authorisation_check_ns = elapsed()
        if not allowed:
            return "UNAUTHORISED_OPERATION", "", timings

        return "ACCEPTED", "", timings

    def _consume_best_effort(
        self, request: SignedAuthRequest, obj: AuthObject | None = None
    ) -> None:
        try:
            parsed = obj or AuthObject.parse(request.body)
            self.nonce_store.consume(parsed.session_id, parsed.nonce)
        except Exception:  # noqa: BLE001
            return
