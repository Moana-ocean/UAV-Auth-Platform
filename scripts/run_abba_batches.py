"""Independent ABBA batch runs for statistical reliability (E-02).

Design (FINAL_TEST_PLAN E-02), method-B instrumentation:
  configs: (n=10,c=1), (n=500,c=25), (n=500,c=50)
  mechanisms: x509, blockchain
  4 independent batches with ABBA mechanism order per config
  measured reps = max(30, concurrency); warm-ups run sequentially first
  Jobs are ordered by ascending n so registry population is honest.
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
from scripts.run_chapter5_matrix import WARMUP, _ensure_population, _measured_reps, reset_local_identities

ABBA_CONFIGS: tuple[tuple[int, int], ...] = ((10, 1), (500, 25), (500, 50))
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
    """Ascending-n order: finish all n=10 jobs before growing to n=500."""
    jobs: list[AbbaJob] = []
    for n, c in ABBA_CONFIGS:
        for batch_id in range(1, 5):
            for mech in ABBA_MECH_ORDER[batch_id]:
                jobs.append(AbbaJob(batch_id, n, c, mech))
    return jobs


def _run_id(job: AbbaJob, reps: int) -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return (
        f"abba-b{job.batch_id}_n{job.n_identities}-identities_c{job.concurrency}-conc_"
        f"mech-{job.mechanism}-1backend_valid-active_r{reps}_audit-off_{ts}"
    )


def run_abba(
    *,
    output_root: str | Path,
    dry_run: bool = False,
    only_batches: set[int] | None = None,
    fresh_identities: bool = False,
    start_index: int = 1,
) -> dict[str, Any]:
    root = Path(output_root)
    if not root.is_absolute():
        root = project_root() / root
    runs_dir = root / "abba_runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    if fresh_identities and not dry_run:
        reset_local_identities()
        print("reset local identities for ABBA ascending-n population", flush=True)

    jobs = planned_jobs()
    if only_batches:
        jobs = [j for j in jobs if j.batch_id in only_batches]
    if start_index > 1:
        jobs = jobs[start_index - 1 :]
        print(f"resuming ABBA from job index {start_index}", flush=True)

    started = datetime.now(UTC).isoformat()
    completed: list[dict[str, Any]] = []
    progress_path = root / "abba_progress.json"
    if start_index > 1 and progress_path.exists():
        try:
            prev = json.loads(progress_path.read_text(encoding="utf-8"))
            completed = list(prev.get("completed") or [])
            started = str(prev.get("started_at") or started)
        except json.JSONDecodeError:
            completed = []
    obs_total = 0

    for offset, job in enumerate(jobs):
        idx = start_index + offset
        reps = _measured_reps(job.concurrency)
        obs_total += reps
        print(
            f"[{idx}/24] batch={job.batch_id} n={job.n_identities} "
            f"c={job.concurrency} mech={job.mechanism} reps={reps}",
            flush=True,
        )
        record: dict[str, Any] = {
            "batch_id": job.batch_id,
            "n_identities": job.n_identities,
            "concurrency": job.concurrency,
            "mechanism": job.mechanism,
            "repetitions": reps,
            "notes": job.step_label,
        }
        if dry_run:
            record["status"] = "planned"
            completed.append(record)
            continue

        if job.mechanism == "blockchain":
            wait_until_ready(timeout_s=30.0)

        pop_info = _ensure_population(
            job.n_identities, sync_chain=(job.mechanism == "blockchain")
        )
        record["population"] = pop_info
        print(
            f"  population count={pop_info['identities']} "
            f"added={pop_info['added']} chain_ops={pop_info['chain_ops']}",
            flush=True,
        )

        cfg = ExperimentConfig(
            mechanism=job.mechanism,
            scenarios=["valid_active"],
            n_identities=job.n_identities,
            repetitions=reps,
            requests_per_concurrency=reps,
            warmup_repetitions=WARMUP,
            concurrency_levels=[job.concurrency],
            confirm_large_run=True,
            notes=job.step_label,
            output_dir=str(runs_dir),
        )
        run_id = _run_id(job, reps)
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
        "n_observations": obs_total,
        "completed": completed,
    }
    (root / "abba_progress.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dry = "--dry-run" in argv
    fresh = "--fresh-identities" in argv
    output_root = "results/method_b_scale_20260903"
    only_batches: set[int] | None = None
    start_index = 1
    if "--output-root" in argv:
        output_root = argv[argv.index("--output-root") + 1]
    if "--only-batches" in argv:
        raw = argv[argv.index("--only-batches") + 1]
        only_batches = {int(s.strip()) for s in raw.split(",") if s.strip()}
    if "--start-index" in argv:
        start_index = int(argv[argv.index("--start-index") + 1])
    run_abba(
        output_root=output_root,
        dry_run=dry,
        only_batches=only_batches,
        fresh_identities=fresh,
        start_index=start_index,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
