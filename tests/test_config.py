from app.core.config import ConfigError, ExperimentConfig
from app.experiments.identities import IdentityPopulation


def test_defaults_ok():
    cfg = ExperimentConfig(repetitions=5, warmup_repetitions=1)
    assert cfg.estimate_total_requests() > 0


def test_rejects_unknown_scenario():
    try:
        ExperimentConfig(scenarios=["nope"], confirm_large_run=True)
        assert False
    except ConfigError:
        pass


def test_large_run_requires_confirm():
    try:
        ExperimentConfig(repetitions=2000, warmup_repetitions=0, confirm_large_run=False)
        assert False
    except ConfigError:
        pass
    cfg = ExperimentConfig(repetitions=2000, warmup_repetitions=0, confirm_large_run=True)
    assert cfg.estimate_total_requests() >= 2000


def test_descriptive_run_id():
    cfg = ExperimentConfig(
        mechanism="x509",
        scenarios=["valid_active"],
        n_identities=10,
        repetitions=30,
        warmup_repetitions=2,
        concurrency_levels=[5],
        confirm_large_run=True,
    )
    name = cfg.descriptive_run_id(timestamp="20260820T000000Z")
    assert name.startswith("n10-identities_c5-conc_mech-x509-1backend_valid-active_r30_audit-off_")


def test_grow_identities_keeps_existing(tmp_path):
    pop = IdentityPopulation(tmp_path / "var")
    first = pop.generate(6)
    uav = first["identities"][0]["uav_id"]
    pk = first["identities"][0]["public_key_hex"]
    second = pop.generate(8)
    kept = next(r for r in second["identities"] if r["uav_id"] == uav)
    assert kept["public_key_hex"] == pk
    assert second["count"] == 8
    assert second["added"] == 2
