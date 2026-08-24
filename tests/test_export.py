from app.core.schemas import AuthDecision, Observation, Timings
from app.metrics.summary import summarise_observations
from app.storage.artifacts import RunStore, zip_run


def test_observation_roundtrip(tmp_path):
    store = RunStore(tmp_path / "run1")
    dec = AuthDecision(outcome="ACCEPTED", timings=Timings(decision_latency_ns=1_000_000))
    obs = Observation.from_decision(
        run_id="r1",
        mechanism="x509",
        scenario="valid_active",
        repetition=0,
        concurrency_level=1,
        uav_id="UAV-VALID",
        expected_outcome="ACCEPTED",
        decision=dec,
        worker_id="w",
        payload_size=0,
        warmup=False,
    )
    store.append_observation(obs)
    store.write_json("config.json", {"mechanism": "x509"})
    store.finalise_checksums()
    text = (tmp_path / "run1" / "checksums.sha256").read_text(encoding="utf-8")
    assert "observations.csv" in text
    z = zip_run(tmp_path / "run1")
    assert z.exists()


def test_summary_excludes_warmup():
    rows = [
        {
            "warmup": "true",
            "decision_latency_ms": "999",
            "observed_outcome": "ACCEPTED",
            "expected_outcome": "ACCEPTED",
            "expectation_met": "true",
            "scenario": "valid_active",
            "mechanism": "x509",
            "timeout_error_class": "none",
        },
        {
            "warmup": "false",
            "decision_latency_ms": "10",
            "observed_outcome": "ACCEPTED",
            "expected_outcome": "ACCEPTED",
            "expectation_met": "true",
            "scenario": "valid_active",
            "mechanism": "x509",
            "timeout_error_class": "none",
        },
    ]
    s = summarise_observations(rows, seed=1)
    assert s["n_warmup_excluded"] == 1
    assert s["latency_all_finished"]["n"] == 1
    assert s["latency_all_finished"]["filter_rule"].startswith("warmup==false")
