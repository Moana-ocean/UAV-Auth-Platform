"""Smoke checks for method-B runner instrumentation (no Besu)."""

from __future__ import annotations

from app.core.config import ExperimentConfig
from scripts.run_chapter5_matrix import _measured_reps, planned_runs


def test_measured_reps_saturates_worker_pool():
    assert _measured_reps(1) == 30
    assert _measured_reps(25) == 30
    assert _measured_reps(50) == 50


def test_scale_jobs_request_at_least_concurrency():
    scale = [j for j in planned_runs() if j.phase == "scale-valid"]
    assert len(scale) == 50
    for job in scale:
        c = job.cfg.concurrency_levels[0]
        assert int(job.cfg.requests_per_concurrency or 0) >= c
        assert job.cfg.repetitions >= c


def test_experiment_config_accepts_measured_only_fields():
    cfg = ExperimentConfig(
        mechanism="x509",
        scenarios=["valid_active"],
        n_identities=10,
        repetitions=50,
        requests_per_concurrency=50,
        concurrency_levels=[50],
        warmup_repetitions=2,
        confirm_large_run=True,
    )
    assert cfg.estimate_total_requests() == 52
