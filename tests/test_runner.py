"""Small end-to-end X.509 runner smoke test (no fabricated results)."""

from app.core.config import ExperimentConfig
from app.experiments.identities import IdentityPopulation
from app.experiments.runner import ExperimentRunner
from app.storage.artifacts import read_observations


def test_x509_runner_smoke(tmp_path, monkeypatch):
    monkeypatch.setenv("UAV_AUTH_DATA_DIR", str(tmp_path / "var"))
    monkeypatch.setenv("UAV_AUTH_RESULTS_DIR", str(tmp_path / "runs"))
    pop = IdentityPopulation(tmp_path / "var")
    pop.generate(6)
    cfg = ExperimentConfig(
        mechanism="x509",
        scenarios=["valid_active", "replay", "impersonation_wrong_key", "unknown_uav"],
        repetitions=2,
        warmup_repetitions=1,
        concurrency_levels=[1],
        n_identities=6,
        output_dir=str(tmp_path / "runs"),
        confirm_large_run=True,
        notes="unit-smoke",
    )
    runner = ExperimentRunner(cfg)
    run_dir = runner.run()
    rows = read_observations(run_dir)
    assert rows
    assert (run_dir / "checksums.sha256").exists()
    assert (run_dir / "summary.csv").exists()
    measured = [r for r in rows if r["warmup"] == "false"]
    assert all(r["expectation_met"] == "true" for r in measured)
