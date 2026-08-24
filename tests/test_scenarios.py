from app.core.config import ExperimentConfig
from app.experiments.identities import IdentityPopulation
from app.experiments.runner import make_x509_service
from app.experiments.scenarios import prepare_attempt


def test_negative_scenarios(tmp_path, monkeypatch):
    monkeypatch.setenv("UAV_AUTH_DATA_DIR", str(tmp_path / "var"))
    pop = IdentityPopulation(tmp_path / "var")
    pop.generate(6)
    cfg = ExperimentConfig(
        mechanism="x509", repetitions=1, warmup_repetitions=0, confirm_large_run=True
    )
    svc = make_x509_service(cfg, pop)
    mapping = {
        "valid_active": "ACCEPTED",
        "unknown_uav": "UNKNOWN_IDENTITY",
        "impersonation_wrong_key": "INVALID_SIGNATURE",
        "replay": "REPLAY_DETECTED",
        "modified_nonce": "INVALID_SIGNATURE",
        "modified_operation": "INVALID_SIGNATURE",
        "revoked_uav": "REVOKED_IDENTITY",
        "unauthorised_operation": "UNAUTHORISED_OPERATION",
        "malformed": "MALFORMED_REQUEST",
        "expired_certificate": "CERTIFICATE_EXPIRED",
        "untrusted_issuer": "UNTRUSTED_ISSUER",
    }
    for scen, expected in mapping.items():
        prep = prepare_attempt(svc, pop, scen, "telemetry.submit", "", "x509", 5)
        out = svc.authenticate(prep.request).outcome
        assert out == expected, (scen, out, expected)
        assert prep.expected == expected
