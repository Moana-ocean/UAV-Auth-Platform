"""Typed experiment configuration with range checks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.core.constants import (
    BLOCKCHAIN_ONLY_SCENARIOS,
    HASH_FUNCTION,
    LARGE_RUN_THRESHOLD,
    MAX_REPETITIONS,
    MECHANISMS,
    OPERATION_TELEMETRY_SUBMIT,
    SCENARIOS,
    SIGNATURE_ALGORITHM,
    X509_ONLY_SCENARIOS,
)


class ConfigError(ValueError):
    """Raised when an experiment configuration is invalid."""


def _parse_int_list(value: str | list[int]) -> list[int]:
    if isinstance(value, list):
        return [int(v) for v in value]
    parts = [p.strip() for p in str(value).replace(";", ",").split(",") if p.strip()]
    return [int(p) for p in parts]


@dataclass
class ExperimentConfig:
    mechanism: str = "both"
    scenarios: list[str] = field(default_factory=lambda: ["valid_active"])
    n_identities: int = 10
    repetitions: int = 30
    warmup_repetitions: int = 2
    concurrency_levels: list[int] = field(default_factory=lambda: [1])
    requests_per_concurrency: int | None = None
    random_seed: int = 42
    challenge_lifetime_s: float = 5.0
    requested_operation: str = OPERATION_TELEMETRY_SUBMIT
    payload_size: int = 0
    rpc_timeout_s: float = 5.0
    auth_timeout_s: float = 10.0
    audit_tx_enabled: bool = False
    confirmation_blocks: int = 1
    resource_sample_interval_s: float = 0.5
    output_dir: str = "results/runs"
    notes: str = ""
    signature_algorithm: str = SIGNATURE_ALGORITHM
    hash_function: str = HASH_FUNCTION
    gcs_id: str = "GCS-01"
    comparable: bool = True
    confirm_large_run: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.scenarios, str):
            self.scenarios = [s.strip() for s in self.scenarios.split(",") if s.strip()]
        self.concurrency_levels = _parse_int_list(self.concurrency_levels)
        if self.requests_per_concurrency is None:
            self.requests_per_concurrency = int(self.repetitions)
        self.validate()

    def validate(self) -> None:
        if self.mechanism not in (*MECHANISMS, "both"):
            raise ConfigError(f"mechanism must be x509, blockchain or both, got {self.mechanism}")
        unknown = [s for s in self.scenarios if s not in SCENARIOS]
        if unknown:
            raise ConfigError(f"unknown scenarios: {unknown}")
        if not self.scenarios:
            raise ConfigError("at least one scenario is required")
        if not (1 <= self.n_identities <= 10_000):
            raise ConfigError("n_identities must be in 1..10000")
        if not (1 <= self.repetitions <= MAX_REPETITIONS):
            raise ConfigError(f"repetitions must be in 1..{MAX_REPETITIONS}")
        if not (0 <= self.warmup_repetitions <= 1000):
            raise ConfigError("warmup_repetitions must be in 0..1000")
        if any(c < 1 or c > 200 for c in self.concurrency_levels):
            raise ConfigError("concurrency levels must be in 1..200")
        if not self.concurrency_levels:
            raise ConfigError("at least one concurrency level is required")
        if self.challenge_lifetime_s <= 0 or self.challenge_lifetime_s > 3600:
            raise ConfigError("challenge_lifetime_s must be in (0, 3600]")
        if self.payload_size < 0 or self.payload_size > 1_000_000:
            raise ConfigError("payload_size must be in 0..1_000_000")
        if self.rpc_timeout_s <= 0 or self.auth_timeout_s <= 0:
            raise ConfigError("timeouts must be positive")
        if self.confirmation_blocks < 0 or self.confirmation_blocks > 64:
            raise ConfigError("confirmation_blocks must be in 0..64")
        if self.signature_algorithm != SIGNATURE_ALGORITHM or self.hash_function != HASH_FUNCTION:
            self.comparable = False
        if self.mechanism == "x509" and any(s in BLOCKCHAIN_ONLY_SCENARIOS for s in self.scenarios):
            raise ConfigError("rpc_unavailable is blockchain-only")
        if self.mechanism == "blockchain" and any(s in X509_ONLY_SCENARIOS for s in self.scenarios):
            raise ConfigError("expired_certificate/untrusted_issuer are X.509-only")
        total = self.estimate_total_requests()
        if total > LARGE_RUN_THRESHOLD and not self.confirm_large_run:
            raise ConfigError(
                f"estimated {total} requests exceeds {LARGE_RUN_THRESHOLD}; "
                "set confirm_large_run=true to proceed"
            )

    def mechanisms(self) -> list[str]:
        if self.mechanism == "both":
            return ["x509", "blockchain"]
        return [self.mechanism]

    def applicable_scenarios(self, mechanism: str) -> list[str]:
        out = []
        for s in self.scenarios:
            if mechanism == "x509" and s in BLOCKCHAIN_ONLY_SCENARIOS:
                continue
            if mechanism == "blockchain" and s in X509_ONLY_SCENARIOS:
                continue
            out.append(s)
        return out

    def estimate_total_requests(self) -> int:
        total = 0
        for mech in self.mechanisms():
            n_scen = len(self.applicable_scenarios(mech))
            for conc in self.concurrency_levels:
                per = int(self.requests_per_concurrency or self.repetitions)
                warmup = self.warmup_repetitions if conc == self.concurrency_levels[0] else 0
                total += n_scen * (per + warmup)
        return total

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["estimated_total_requests"] = self.estimate_total_requests()
        data["comparable"] = self.comparable
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def descriptive_run_id(self, *, timestamp: str | None = None) -> str:
        """Folder name encoding n, concurrency, mechanism, scenario group, reps."""
        from datetime import UTC, datetime

        conc = "-".join(str(c) for c in self.concurrency_levels)
        n_mech = len(self.mechanisms())
        mech = f"mech-{self.mechanism}-{n_mech}backend"
        scenarios = list(self.scenarios)
        if scenarios == ["valid_active"]:
            scen = "valid-active"
        elif set(scenarios) >= {
            "valid_active",
            "unknown_uav",
            "impersonation_wrong_key",
            "replay",
            "revoked_uav",
            "unauthorised_operation",
        }:
            scen = "security-battery"
        elif len(scenarios) == 1:
            scen = scenarios[0].replace("_", "-")
        else:
            scen = f"{len(scenarios)}scenarios"
        audit = "audit-on" if self.audit_tx_enabled else "audit-off"
        ts = timestamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        name = (
            f"n{self.n_identities}-identities_"
            f"c{conc}-conc_"
            f"{mech}_"
            f"{scen}_"
            f"r{self.repetitions}_"
            f"{audit}_"
            f"{ts}"
        )
        return "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in name)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentConfig:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    @classmethod
    def from_json_path(cls, path: Path) -> ExperimentConfig:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
