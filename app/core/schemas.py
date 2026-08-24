"""Result schemas and reason codes."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.constants import REASON_CODES

OBSERVATION_FIELDS = (
    "run_id",
    "observation_id",
    "utc_timestamp",
    "mechanism",
    "scenario",
    "repetition",
    "concurrency_level",
    "uav_id",
    "expected_outcome",
    "observed_outcome",
    "expectation_met",
    "decision_latency_ns",
    "decision_latency_ms",
    "challenge_generation_ns",
    "identity_lookup_ns",
    "certificate_validation_ns",
    "contract_call_ns",
    "signature_verification_ns",
    "authorisation_check_ns",
    "audit_submission_ns",
    "audit_confirmation_ns",
    "tx_hash",
    "block_number",
    "gas_used",
    "timeout_error_class",
    "worker_id",
    "payload_size",
    "warmup",
    "request_bytes",
    "response_bytes",
    "notes",
)


def new_id(prefix: str = "") -> str:
    uid = uuid.uuid4().hex
    return f"{prefix}{uid}" if prefix else uid


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class Timings:
    decision_latency_ns: int = 0
    challenge_generation_ns: int = 0
    identity_lookup_ns: int = 0
    certificate_validation_ns: int = 0
    contract_call_ns: int = 0
    signature_verification_ns: int = 0
    authorisation_check_ns: int = 0
    audit_submission_ns: int = 0
    audit_confirmation_ns: int = 0


@dataclass
class AuthDecision:
    outcome: str
    reason_detail: str = ""
    timings: Timings = field(default_factory=Timings)
    tx_hash: str = ""
    block_number: str = ""
    gas_used: str = ""
    timeout_error_class: str = "none"
    request_bytes: int = 0
    response_bytes: int = 0

    def __post_init__(self) -> None:
        if self.outcome not in REASON_CODES:
            raise ValueError(f"invalid reason code: {self.outcome}")


@dataclass
class Observation:
    run_id: str
    observation_id: str
    utc_timestamp: str
    mechanism: str
    scenario: str
    repetition: int
    concurrency_level: int
    uav_id: str
    expected_outcome: str
    observed_outcome: str
    expectation_met: bool
    decision_latency_ns: int
    decision_latency_ms: float
    challenge_generation_ns: int = 0
    identity_lookup_ns: int = 0
    certificate_validation_ns: int = 0
    contract_call_ns: int = 0
    signature_verification_ns: int = 0
    authorisation_check_ns: int = 0
    audit_submission_ns: int = 0
    audit_confirmation_ns: int = 0
    tx_hash: str = ""
    block_number: str = ""
    gas_used: str = ""
    timeout_error_class: str = "none"
    worker_id: str = ""
    payload_size: int = 0
    warmup: bool = False
    request_bytes: int = 0
    response_bytes: int = 0
    notes: str = ""

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["expectation_met"] = str(bool(self.expectation_met)).lower()
        row["warmup"] = str(bool(self.warmup)).lower()
        return row

    @classmethod
    def from_decision(
        cls,
        *,
        run_id: str,
        mechanism: str,
        scenario: str,
        repetition: int,
        concurrency_level: int,
        uav_id: str,
        expected_outcome: str,
        decision: AuthDecision,
        worker_id: str,
        payload_size: int,
        warmup: bool,
        notes: str = "",
    ) -> Observation:
        t = decision.timings
        return cls(
            run_id=run_id,
            observation_id=new_id("obs_"),
            utc_timestamp=utc_now_iso(),
            mechanism=mechanism,
            scenario=scenario,
            repetition=repetition,
            concurrency_level=concurrency_level,
            uav_id=uav_id,
            expected_outcome=expected_outcome,
            observed_outcome=decision.outcome,
            expectation_met=decision.outcome == expected_outcome,
            decision_latency_ns=t.decision_latency_ns,
            decision_latency_ms=t.decision_latency_ns / 1_000_000.0,
            challenge_generation_ns=t.challenge_generation_ns,
            identity_lookup_ns=t.identity_lookup_ns,
            certificate_validation_ns=t.certificate_validation_ns,
            contract_call_ns=t.contract_call_ns,
            signature_verification_ns=t.signature_verification_ns,
            authorisation_check_ns=t.authorisation_check_ns,
            audit_submission_ns=t.audit_submission_ns,
            audit_confirmation_ns=t.audit_confirmation_ns,
            tx_hash=decision.tx_hash,
            block_number=decision.block_number,
            gas_used=decision.gas_used,
            timeout_error_class=decision.timeout_error_class,
            worker_id=worker_id,
            payload_size=payload_size,
            warmup=warmup,
            request_bytes=decision.request_bytes,
            response_bytes=decision.response_bytes,
            notes=notes or decision.reason_detail,
        )
