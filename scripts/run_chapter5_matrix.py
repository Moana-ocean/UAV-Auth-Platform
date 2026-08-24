"""Chapter 3 workload-matrix runner with descriptive result folder names.

Folder pattern:
  n{identities}-identities_c{conc}-conc_mech-{x509|blockchain|both}-{1|2}backend_{scenario}_r{reps}_audit-{on|off}_{timestamp}

Example:
  n10-identities_c5-conc_mech-x509-1backend_valid-active_r30_audit-off_20260820T094500Z
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.auth.blockchain.client import is_reachable
from app.core.config import ExperimentConfig
from app.experiments.identities import IdentityPopulation
from app.experiments.runner import (
    ExperimentRunner,
    data_dir,
    deployment_path,
    project_root,
    register_population_on_chain,
)

IDENTITY_LEVELS = (10, 50, 100, 250, 500)
CONCURRENCY_LEVELS = (1, 5, 10, 25, 50)
REPETITIONS = 30
WARMUP = 2

SECURITY_SCENARIOS = [
    "valid_active",
    "unknown_uav",
    "impersonation_wrong_key",
    "replay",
    "modified_nonce",
    "modified_uav_id",
    "modified_operation",
    "expired_challenge",
    "revoked_uav",
    "unauthorised_operation",
    "malformed",
    "expired_certificate",
    "untrusted_issuer",
    "rpc_unavailable",
]


@dataclass
class PlannedRun:
    step: int
    phase: str
    notes: str
    cfg: ExperimentConfig
    ensure_identities: int | None = None


def planned_runs() -> list[PlannedRun]:
    """Ordered Chapter 3 matrix: security, then n × concurrency × mechanism, then audit."""
    jobs: list[PlannedRun] = []
    step = 1
    x509_security = [s for s in SECURITY_SCENARIOS if s != "rpc_unavailable"]
    bc_security = [
        s for s in SECURITY_SCENARIOS if s not in {"expired_certificate", "untrusted_issuer"}
    ]
    jobs.append(
        PlannedRun(
            step=step,
            phase="security",
            notes="ch3-rq1-security-x509-n10-c1",
            ensure_identities=10,
            cfg=ExperimentConfig(
                mechanism="x509",
                scenarios=x509_security,
                n_identities=10,
                repetitions=REPETITIONS,
                warmup_repetitions=WARMUP,
                concurrency_levels=[1],
                confirm_large_run=True,
                notes="ch3-rq1-security-x509-n10-c1",
            ),
        )
    )
    step += 1
    jobs.append(
        PlannedRun(
            step=step,
            phase="security",
            notes="ch3-rq1-security-blockchain-n10-c1",
            ensure_identities=10,
            cfg=ExperimentConfig(
                mechanism="blockchain",
                scenarios=bc_security,
                n_identities=10,
                repetitions=REPETITIONS,
                warmup_repetitions=WARMUP,
                concurrency_levels=[1],
                confirm_large_run=True,
                notes="ch3-rq1-security-blockchain-n10-c1",
            ),
        )
    )
    for n in IDENTITY_LEVELS:
        for conc in CONCURRENCY_LEVELS:
            for mech in ("x509", "blockchain"):
                step += 1
                jobs.append(
                    PlannedRun(
                        step=step,
                        phase="scale-valid",
                        notes=f"ch3-rq2-rq3-n{n}-c{conc}-{mech}",
                        ensure_identities=n,
                        cfg=ExperimentConfig(
                            mechanism=mech,
                            scenarios=["valid_active"],
                            n_identities=n,
                            repetitions=REPETITIONS,
                            warmup_repetitions=WARMUP,
                            concurrency_levels=[conc],
                            confirm_large_run=True,
                            notes=f"ch3-rq2-rq3-n{n}-c{conc}-{mech}",
                        ),
                    )
                )
    step += 1
    jobs.append(
        PlannedRun(
            step=step,
            phase="audit-commit",
            notes="ch3-logging-blockchain-audit-n10-c1",
            ensure_identities=10,
            cfg=ExperimentConfig(
                mechanism="blockchain",
                scenarios=["valid_active"],
                n_identities=10,
                repetitions=REPETITIONS,
                warmup_repetitions=WARMUP,
                concurrency_levels=[1],
                audit_tx_enabled=True,
                confirm_large_run=True,
                notes="ch3-logging-blockchain-audit-n10-c1",
            ),
        )
    )
    return jobs


def _ensure_population(n: int) -> dict[str, Any]:
    pop = IdentityPopulation(data_dir())
    payload = pop.generate(n)
    chain_ops = []
    if is_reachable() and deployment_path().exists():
        chain_ops = register_population_on_chain(pop)
    return {"identities": payload["count"], "added": payload.get("added", 0), "chain_ops": len(chain_ops)}


def run_matrix(*, start_step: int = 1, dry_run: bool = False) -> dict[str, Any]:
    jobs = planned_runs()
    root = project_root() / "results"
    root.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC).isoformat()
    completed: list[dict[str, Any]] = []
    for job in jobs:
        if job.step < start_step:
            continue
        folder = job.cfg.descriptive_run_id()
        record = {
            "step": job.step,
            "phase": job.phase,
            "notes": job.notes,
            "run_id": folder,
            "mechanism": job.cfg.mechanism,
            "n_identities": job.cfg.n_identities,
            "concurrency": job.cfg.concurrency_levels,
            "scenarios": job.cfg.scenarios,
            "repetitions": job.cfg.repetitions,
            "warmup": job.cfg.warmup_repetitions,
            "audit_tx": job.cfg.audit_tx_enabled,
            "estimated_requests": job.cfg.estimate_total_requests(),
        }
        print(
            f"[{job.step}/{jobs[-1].step}] {job.phase} "
            f"n={job.cfg.n_identities} c={job.cfg.concurrency_levels} "
            f"mech={job.cfg.mechanism} -> {folder}",
            flush=True,
        )
        if dry_run:
            completed.append({**record, "status": "planned"})
            continue
        if job.ensure_identities:
            pop_info = _ensure_population(job.ensure_identities)
            record["population"] = pop_info
        runner = ExperimentRunner(job.cfg, run_id=folder)
        path = runner.run()
        record["path"] = str(path)
        record["status"] = json.loads((path / "status.json").read_text(encoding="utf-8")).get(
            "status", "unknown"
        )
        completed.append(record)
        manifest = {
            "started_at": started,
            "updated_at": datetime.now(UTC).isoformat(),
            "dry_run": dry_run,
            "completed": completed,
        }
        (root / "chapter5_matrix_progress.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
    summary = {
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
        "dry_run": dry_run,
        "n_jobs": len(jobs),
        "completed": completed,
    }
    (root / "chapter5_matrix_progress.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dry = "--dry-run" in argv
    start = 1
    if "--start-step" in argv:
        start = int(argv[argv.index("--start-step") + 1])
    run_matrix(start_step=start, dry_run=dry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
