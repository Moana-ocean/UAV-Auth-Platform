"""Local Streamlit operator UI. Protocol logic lives in app.auth / app.experiments."""

from __future__ import annotations

import json
import threading

import pandas as pd
import streamlit as st

from app.core.config import ConfigError, ExperimentConfig
from app.core.constants import LARGE_RUN_THRESHOLD, SCENARIOS
from app.experiments.runner import ExperimentRunner, project_root
from app.metrics.summary import summarise_observations
from app.ui.services import (
    comparable_population,
    export_zip,
    full_environment_status,
    generate_identities,
    observations_for,
    run_history,
)

st.set_page_config(page_title="UAV Auth Evaluation", layout="wide")
st.title("UAV-to-GCS authentication evaluation platform")
st.caption("Chapter 5 local experiment console. Results are shown only from stored run files.")

tabs = st.tabs(
    [
        "A. Environment",
        "B. Identities",
        "C. Configure",
        "D. Execute",
        "E. Results",
        "F. Export",
    ]
)


def _start_run(cfg: ExperimentConfig) -> str:
    runner = ExperimentRunner(cfg)

    def _go() -> None:
        try:
            runner.run()
        except Exception as exc:  # noqa: BLE001
            run_dir = project_root() / cfg.output_dir / runner.run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "status.json").write_text(
                json.dumps({"status": "failed", "error": type(exc).__name__, "detail": str(exc)}),
                encoding="utf-8",
            )

    thread = threading.Thread(target=_go, name="experiment-runner", daemon=True)
    thread.start()
    st.session_state["active_run_id"] = runner.run_id
    st.session_state["runner"] = runner
    return runner.run_id


with tabs[0]:
    st.subheader("Environment status")
    env = full_environment_status()
    c1, c2, c3 = st.columns(3)
    c1.metric("Python", env["python"])
    c2.metric("CPUs", env["cpu_count"])
    c3.metric("Memory GiB", f"{env['total_memory_bytes'] / (1024 ** 3):.1f}")
    st.json(
        {k: env[k] for k in ("os", "cpu", "packages", "docker", "besu_image", "chain_id_expected")}
    )
    st.markdown("**Validator nodes**")
    st.json(env["besu_nodes"])
    st.markdown("**Contract / PKI / identities**")
    st.json(
        {
            "deployment": env["deployment"],
            "artifact": env["artifact"],
            "pki": env["pki"],
            "identities": env["identities"],
        }
    )
    for w in env["warnings"]:
        st.warning(w)
    st.info(env["topology_note"])

with tabs[1]:
    st.subheader("Test-data and identity setup")
    n = st.number_input("Number of UAV identities", min_value=5, max_value=500, value=10)
    register = st.checkbox(
        "Register the same population on-chain (requires deployed contract)", value=True
    )
    if st.button("Generate identities"):
        st.session_state["id_result"] = generate_identities(int(n), register)
    if "id_result" in st.session_state:
        st.success(st.session_state["id_result"])
    st.markdown("**Comparable population check**")
    st.json(comparable_population())
    st.markdown(
        "Destructive reset is available from the CLI: `python -m app.cli reset-local --confirm`"
    )

with tabs[2]:
    st.subheader("Experiment configuration")
    mechanism = st.selectbox("Mechanism", ["x509", "blockchain", "both"])
    scenarios = st.multiselect("Scenarios", list(SCENARIOS), default=["valid_active"])
    repetitions = st.number_input("Repetitions per scenario/concurrency", 1, 10000, 30)
    warmup = st.number_input("Warm-up repetitions (excluded from default summary)", 0, 1000, 2)
    conc_text = st.text_input("Concurrency levels", "1")
    n_ids = st.number_input("Registered UAV identities (setup size)", 1, 10000, 10)
    lifetime = st.number_input("Challenge lifetime (s)", 0.1, 3600.0, 5.0)
    payload = st.number_input("Payload size (bytes)", 0, 1_000_000, 0)
    rpc_t = st.number_input("RPC timeout (s)", 0.1, 60.0, 5.0)
    auth_t = st.number_input("Auth timeout (s)", 0.1, 120.0, 10.0)
    audit = st.checkbox("Blockchain write-audit transaction (measured separately)", value=False)
    confs = st.number_input("Required confirmations", 0, 64, 1)
    sample = st.number_input("Resource sample interval (s)", 0.1, 10.0, 0.5)
    seed = st.number_input("Random seed", 0, 2**31 - 1, 42)
    notes = st.text_area("Run notes")
    confirm_large = st.checkbox("Confirm large run (>1000 requests)", value=False)
    try:
        cfg = ExperimentConfig(
            mechanism=mechanism,
            scenarios=scenarios or ["valid_active"],
            repetitions=int(repetitions),
            warmup_repetitions=int(warmup),
            concurrency_levels=conc_text,
            n_identities=int(n_ids),
            challenge_lifetime_s=float(lifetime),
            payload_size=int(payload),
            rpc_timeout_s=float(rpc_t),
            auth_timeout_s=float(auth_t),
            audit_tx_enabled=bool(audit),
            confirmation_blocks=int(confs),
            resource_sample_interval_s=float(sample),
            random_seed=int(seed),
            notes=notes,
            confirm_large_run=bool(confirm_large),
        )
        st.markdown(f"Estimated total requests: **{cfg.estimate_total_requests()}**")
        if cfg.estimate_total_requests() > LARGE_RUN_THRESHOLD and not confirm_large:
            st.warning("Large run: tick the confirmation box.")
        if not cfg.comparable:
            st.error("Non-comparable algorithm settings.")
        st.code(cfg.to_json(), language="json")
        st.session_state["draft_config"] = cfg.to_dict()
    except ConfigError as exc:
        st.error(str(exc))

with tabs[3]:
    st.subheader("Live execution")
    if st.button("Start run", type="primary"):
        data = st.session_state.get("draft_config")
        if not data:
            st.error("Fix the configuration tab first.")
        else:
            cfg = ExperimentConfig.from_dict(data)
            rid = _start_run(cfg)
            st.success(f"Started {rid}")
    runner: ExperimentRunner | None = st.session_state.get("runner")
    if st.button("Cancel run") and runner:
        runner.cancel()
        st.warning(
            "Cancel requested: no new work will be scheduled; completed observations are kept."
        )
    run_id = st.session_state.get("active_run_id")
    if run_id:
        status_path = project_root() / "results" / "runs" / run_id / "status.json"
        if status_path.exists():
            status = json.loads(status_path.read_text(encoding="utf-8"))
            st.json(status)
            total = max(int(status.get("total") or 1), 1)
            done = int(status.get("completed") or 0)
            st.progress(min(done / total, 1.0))
            counts = status.get("counts") or {}
            a, b, c, d, e = st.columns(5)
            a.metric("Accepted", counts.get("accepted", 0))
            b.metric("Expected reject", counts.get("expected_rejection", 0))
            c.metric("Unexpected", counts.get("unexpected", 0))
            d.metric("Timeout", counts.get("timeout", 0))
            e.metric("Internal error", counts.get("internal", 0))
            eta = status.get("eta_s")
            st.caption(
                f"Elapsed {status.get('elapsed_s', 0):.1f}s  ETA {eta:.1f}s"
                if eta
                else f"Elapsed {status.get('elapsed_s', 0):.1f}s"
            )
        events = project_root() / "results" / "runs" / run_id / "events.jsonl"
        if events.exists():
            lines = events.read_text(encoding="utf-8").splitlines()[-20:]
            st.markdown("**Recent events**")
            st.text("\n".join(lines))
        st.info("The page does not auto-refresh: rerun or switch tabs to poll status.json.")

with tabs[4]:
    st.subheader("Results and run history")
    history = run_history()
    if not history:
        st.write("No stored runs yet.")
    else:
        labels = [h["run_id"] for h in history]
        selected = st.multiselect("Select runs to view/compare", labels, default=labels[-1:])
        comparable_ok = True
        cfgs = []
        for rid in selected:
            item = next(h for h in history if h["run_id"] == rid)
            cfgs.append(item.get("config") or {})
            st.markdown(f"### {rid}")
            st.json({"config": item.get("config"), "status": item.get("status")})
            rows = observations_for(rid)
            if not rows:
                st.write("No observations.")
                continue
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True)
            summary = summarise_observations(
                rows, seed=int((item.get("config") or {}).get("random_seed") or 42)
            )
            st.json(summary)
            charts = project_root() / "results" / "runs" / rid / "charts"
            for img in sorted(charts.glob("*.png")):
                st.image(str(img), caption=img.name)
        if len(cfgs) >= 2:
            keys = ("signature_algorithm", "hash_function", "payload_size", "challenge_lifetime_s")
            for k in keys:
                vals = {json.dumps(c.get(k), sort_keys=True) for c in cfgs}
                if len(vals) > 1:
                    comparable_ok = False
            if not comparable_ok:
                st.error(
                    "Selected runs are not directly comparable (algorithm, payload, topology or timing differs)."
                )
            else:
                st.success("Selected runs share the core comparison controls.")

with tabs[5]:
    st.subheader("Export")
    history = run_history()
    if history:
        rid = st.selectbox("Run", [h["run_id"] for h in history])
        run_dir = project_root() / "results" / "runs" / rid
        mapping = {
            "observations.csv": run_dir / "observations.csv",
            "summary.csv": run_dir / "summary.csv",
            "config.json": run_dir / "config.json",
            "environment.json": run_dir / "environment.json",
            "events.jsonl": run_dir / "events.jsonl",
            "system_metrics.csv": run_dir / "system_metrics.csv",
        }
        for label, path in mapping.items():
            if path.exists():
                st.download_button(label, path.read_bytes(), file_name=f"{rid}_{label}")
        if st.button("Build ZIP of run directory"):
            z = export_zip(rid)
            st.success(str(z))
            st.download_button("Download ZIP", z.read_bytes(), file_name=z.name)
        charts = run_dir / "charts"
        for img in sorted(charts.glob("*")):
            st.download_button(img.name, img.read_bytes(), file_name=img.name)
