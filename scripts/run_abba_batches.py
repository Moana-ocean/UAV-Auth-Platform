"""Independent ABBA batch runs for statistical reliability (E-02).

Design (FINAL_TEST_PLAN E-02):
  configs: (n=10,c=1), (n=500,c=25), (n=500,c=50)
  mechanisms: x509, blockchain
  4 independent batches with ABBA mechanism order per config
  30 measured repetitions + 2 warm-ups per run
  total: 3 × 2 × 4 × 30 = 720 observations
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.auth.blockchain.client import wait_until_ready
from app.core.config import ExperimentConfig
from app.experiments.runner import ExperimentRunner, project_root
from scripts.run_chapter5_matrix import REPETITIONS, WARMUP, _ensure_population

ABBA_CONFIGS: tuple[tuple[int, int], ...] = ((10, 1), (500, 25), (500, 50))
MECHANISMS: tuple[str, ...] = ("x509", "blockchain")
# Batch 1/4: x509 then blockchain (A-B); batches 2/3: blockchain then x509 (B-A).
ABBA_MECH_ORDER: dict[int, tuple[str, ...]] = {
    1: ("x509", "blockchain"),
    2: ("blockchain", "x509"),
    3: ("blockchain", "x509"),
    4: ("x509", "blockchain"),
}


@dataclass(frozen=True)
class AbbaJob:
    batch_id: int
    n_identities: int
    concurrency: int
    mechanism: str

    @property
    def step_label(self) -> str:
        return f"abba-b{self.batch_id}_n{self.n_identities}_c{self.concurrency}_{self.mechanism}"


def planned_jobs() -> list[AbbaJob]:
    jobs: list[AbbaJob] = []
    for batch_id in range(1, 5):
        for n, c in ABBA_CONFIGS:
            for mech in ABBA_MECH_ORDER[batch_id]:
                jobs.append(AbbaJob(batch_id, n, c, mech))
    return jobs


def _run_id(job: AbbaJob) -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return (
        f"abba-b{job.batch_id}_n{job.n_identities}-identities_c{job.concurrency}-conc_"
        f"mech-{job.mechanism}-1backend_valid-active_r{REPETITIONS}_audit-off_{ts}"
    )


def run_abba(
    *,
    output_root: str | Path,
    dry_run: bool = False,
    only_batches: set[int] | None = None,
) -> dict[str, Any]:
    root = Path(output_root)
    if not root.is_absolute():
        root = project_root() / root
    runs_dir = root / "abba_runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    jobs = planned_jobs()
    if only_batches:
        jobs = [j for j in jobs if j.batch_id in only_batches]

    started = datetime.now(UTC).isoformat()
    completed: list[dict[str, Any]] = []

    for idx, job in enumerate(jobs, start=1):
        print(
            f"[{idx}/{len(jobs)}] batch={job.batch_id} n={job.n_identities} "
            f"c={job.concurrency} mech={job.mechanism}",
            flush=True,
        )
        record: dict[str, Any] = {
            "batch_id": job.batch_id,
            "n_identities": job.n_identities,
            "concurrency": job.concurrency,
            "mechanism": job.mechanism,
            "notes": job.step_label,
        }
        if dry_run:
            record["status"] = "planned"
            completed.append(record)
            continue

        if job.mechanism == "blockchain":
            wait_until_ready(timeout_s=30.0)

        max_n = max(n for n, _ in ABBA_CONFIGS)
        pop_info = _ensure_population(max_n, sync_chain=(job.mechanism == "blockchain"))
        record["population"] = pop_info

        cfg = ExperimentConfig(
            mechanism=job.mechanism,
            scenarios=["valid_active"],
            n_identities=job.n_identities,
            repetitions=REPETITIONS,
            warmup_repetitions=WARMUP,
            concurrency_levels=[job.concurrency],
            confirm_large_run=True,
            notes=job.step_label,
            output_dir=str(runs_dir),
        )
        run_id = _run_id(job)
        record["run_id"] = run_id
        runner = ExperimentRunner(cfg, run_id=run_id)
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
            "n_jobs": len(planned_jobs()),
            "completed": completed,
        }
        (root / "abba_progress.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    summary = {
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
        "dry_run": dry_run,
        "output_root": str(root),
        "n_jobs": len(jobs),
        "n_observations": len(jobs) * REPETITIONS,
        "completed": completed,
    }
    (root / "abba_progress.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dry = "--dry-run" in argv
    output_root = "results/dissertation_final_20260831T015600Z"
    only_batches: set[int] | None = None
    if "--output-root" in argv:
        output_root = argv[argv.index("--output-root") + 1]
    if "--only-batches" in argv:
        raw = argv[argv.index("--only-batches") + 1]
        only_batches = {int(s.strip()) for s in raw.split(",") if s.strip()}
    run_abba(output_root=output_root, dry_run=dry, only_batches=only_batches)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
