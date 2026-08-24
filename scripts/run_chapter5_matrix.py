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
from pathlib import Path
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


_CHAIN_SYNCED = False


def _ensure_population(n: int, *, sync_chain: bool) -> dict[str, Any]:
    """Grow local identities; sync the chain only when needed.

    Full-population getRecord/updateKey on every matrix step overwhelms local
    Besu. Sync when new identities were added, or once per process when a
    blockchain job requests chain consistency.
    """
    pop = IdentityPopulation(data_dir())
    payload = pop.generate(n)
    chain_ops: list[Any] = []
    added = int(payload.get("added", 0))
    global _CHAIN_SYNCED  # noqa: PLW0603 — process-local matrix guard
    if sync_chain and is_reachable() and deployment_path().exists():
        if added > 0 or not _CHAIN_SYNCED:
            chain_ops = register_population_on_chain(pop)
            _CHAIN_SYNCED = True
    return {
        "identities": payload["count"],
        "added": added,
        "chain_ops": len(chain_ops),
        "chain_synced": _CHAIN_SYNCED,
    }


def run_matrix(
    *,
    start_step: int = 1,
    dry_run: bool = False,
    output_root: str | None = None,
) -> dict[str, Any]:
    from dataclasses import replace

    global _CHAIN_SYNCED  # noqa: PLW0603
    _CHAIN_SYNCED = False
    jobs = planned_runs()
    root = Path(output_root) if output_root else (project_root() / "results")
    if not root.is_absolute():
        root = project_root() / root
    runs_dir = root / "runs"
    root.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC).isoformat()
    completed: list[dict[str, Any]] = []
    for job in jobs:
        if job.step < start_step:
            continue
        cfg = replace(job.cfg, output_dir=str(runs_dir))
        folder = cfg.descriptive_run_id()
        record = {
            "step": job.step,
            "phase": job.phase,
            "notes": job.notes,
            "run_id": folder,
            "mechanism": cfg.mechanism,
            "n_identities": cfg.n_identities,
            "concurrency": cfg.concurrency_levels,
            "scenarios": cfg.scenarios,
            "repetitions": cfg.repetitions,
            "warmup": cfg.warmup_repetitions,
            "audit_tx": cfg.audit_tx_enabled,
            "estimated_requests": cfg.estimate_total_requests(),
            "output_root": str(root),
        }
        print(
            f"[{job.step}/{jobs[-1].step}] {job.phase} "
            f"n={cfg.n_identities} c={cfg.concurrency_levels} "
            f"mech={cfg.mechanism} -> {folder}",
            flush=True,
        )
        if dry_run:
            completed.append({**record, "status": "planned"})
            continue
        if job.ensure_identities:
            pop_info = _ensure_population(
                job.ensure_identities,
                sync_chain=(cfg.mechanism == "blockchain"),
            )
            record["population"] = pop_info
        runner = ExperimentRunner(cfg, run_id=folder)
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
            "output_root": str(root),
            "completed": completed,
        }
        (root / "chapter5_matrix_progress.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
    summary = {
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
        "dry_run": dry_run,
        "output_root": str(root),
        "n_jobs": len(jobs),
        "completed": completed,
    }
    (root / "chapter5_matrix_progress.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dry = "--dry-run" in argv
    start = 1
    output_root = None
    if "--start-step" in argv:
        start = int(argv[argv.index("--start-step") + 1])
    if "--output-root" in argv:
        output_root = argv[argv.index("--output-root") + 1]
    run_matrix(start_step=start, dry_run=dry, output_root=output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
