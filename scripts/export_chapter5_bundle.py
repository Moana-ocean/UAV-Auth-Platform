"""Export Chapter 5 GPT data bundle from completed matrix runs."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pandas as pd

from scripts.run_chapter5_matrix import planned_runs, project_root

RUN_ID_RE = re.compile(
    r"^n(?P<n>\d+)-identities_c(?P<c>\d+)-conc_mech-(?P<mech>x509|blockchain)-"
    r"(?P<backend>\d)backend_(?P<scenario>.+?)_r(?P<reps>\d+)_audit-(?P<audit>on|off)_"
)


def _parse_run_id(run_id: str) -> dict[str, str | int]:
    m = RUN_ID_RE.match(run_id)
    if not m:
        return {}
    return {
        "n_identities": int(m.group("n")),
        "concurrency": int(m.group("c")),
        "mechanism": m.group("mech"),
        "backend_count": int(m.group("backend")),
        "scenario": m.group("scenario").replace("-", "_"),
        "repetitions": int(m.group("reps")),
        "audit_tx": m.group("audit") == "on",
    }


def _matrix_run_dirs(runs_root: Path) -> list[Path]:
    return sorted(
        p.parent
        for p in runs_root.glob("n*-*/summary.csv")
        if p.parent.is_dir()
    )


def _merge_csv(paths: list[Path], out: Path) -> int:
    if not paths:
        out.write_text("", encoding="utf-8")
        return 0
    frames = [pd.read_csv(p) for p in paths]
    df = pd.concat(frames, ignore_index=True)
    df.to_csv(out, index=False)
    return len(df)


def _build_manifest(export: Path) -> None:
    jobs = planned_runs()
    completed_dirs = {d.name: d for d in _matrix_run_dirs(project_root() / "results" / "runs")}
    steps: list[dict] = []
    for job in jobs:
        folder = job.cfg.descriptive_run_id()
        entry = {
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
            "present_on_disk": folder in completed_dirs,
        }
        if folder in completed_dirs:
            entry["path"] = str(completed_dirs[folder])
            status_path = completed_dirs[folder] / "status.json"
            if status_path.exists():
                entry["status"] = json.loads(status_path.read_text(encoding="utf-8")).get(
                    "status", "unknown"
                )
        steps.append(entry)
    manifest = {
        "n_steps": len(steps),
        "n_present": sum(1 for s in steps if s["present_on_disk"]),
        "steps": steps,
    }
    (export / "00_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _enrich_summaries(export: Path) -> None:
    src = export / "02_all_summaries.csv"
    if not src.exists():
        return
    df = pd.read_csv(src)
    parsed = df["run_id"].map(_parse_run_id)
    for col in ("n_identities", "concurrency", "mechanism", "scenario", "audit_tx"):
        df[col] = parsed.map(lambda x: x.get(col) if x else None)
    df.to_csv(export / "02_all_summaries_enriched.csv", index=False)


def _security_by_scenario(export: Path) -> None:
    src = export / "03_security_observations.csv"
    if not src.exists() or src.stat().st_size == 0:
        return
    df = pd.read_csv(src)
    df = df[df["warmup"].astype(str).str.lower() != "true"]
    rows: list[dict] = []
    for (mech, scenario), grp in df.groupby(["mechanism", "scenario"]):
        n = len(grp)
        malicious = grp[grp["expected_outcome"] != "ACCEPTED"]
        n_mal = len(malicious)
        false_acc = int((malicious["observed_outcome"] == "ACCEPTED").sum())
        false_rej = int(
            (
                (grp["expected_outcome"] == "ACCEPTED")
                & (grp["observed_outcome"] != "ACCEPTED")
            ).sum()
        )
        met = int(grp["expectation_met"].astype(str).str.lower().eq("true").sum())
        attack_rej = (
            round(100.0 * (1 - false_acc / n_mal), 2) if n_mal else None
        )
        lat = grp["decision_latency_ms"].astype(float)
        rows.append(
            {
                "mechanism": mech,
                "scenario": scenario,
                "n_observations": n,
                "n_malicious": n_mal,
                "expectation_met_count": met,
                "expectation_met_rate_pct": round(100.0 * met / n, 2) if n else None,
                "false_acceptances": false_acc,
                "false_rejections": false_rej,
                "attack_rejection_rate_pct": attack_rej,
                "mean_decision_latency_ms": round(lat.mean(), 4) if n else None,
                "p95_decision_latency_ms": round(lat.quantile(0.95), 4) if n else None,
            }
        )
    pd.DataFrame(rows).sort_values(["mechanism", "scenario"]).to_csv(
        export / "03_security_by_scenario.csv", index=False
    )


def _comm_overhead_summary(export: Path) -> None:
    src = export / "04_scale_observations.csv"
    if not src.exists() or src.stat().st_size == 0:
        return
    df = pd.read_csv(src)
    df = df[df["warmup"].astype(str).str.lower() != "true"]
    parsed = df["run_id"].map(_parse_run_id)
    df["n_identities"] = parsed.map(lambda x: x.get("n_identities") if x else None)
    df["concurrency"] = parsed.map(lambda x: x.get("concurrency") if x else None)
    rows: list[dict] = []
    for (mech, n_id, conc), grp in df.groupby(["mechanism", "n_identities", "concurrency"]):
        rows.append(
            {
                "mechanism": mech,
                "n_identities": n_id,
                "concurrency": conc,
                "run_id": grp["run_id"].iloc[0],
                "n_observations": len(grp),
                "mean_request_bytes": round(grp["request_bytes"].astype(float).mean(), 2),
                "mean_response_bytes": round(grp["response_bytes"].astype(float).mean(), 2),
                "mean_contract_call_ms": round(
                    grp["contract_call_ns"].astype(float).mean() / 1e6, 4
                )
                if mech == "blockchain"
                else 0.0,
            }
        )
    pd.DataFrame(rows).sort_values(["n_identities", "concurrency", "mechanism"]).to_csv(
        export / "04_comm_overhead_summary.csv", index=False
    )


def _system_metrics_summary(export: Path) -> None:
    src = export / "05_system_metrics.csv"
    if not src.exists() or src.stat().st_size == 0:
        return
    # system_metrics.csv lacks run_id; aggregate per run directory.
    runs_root = project_root() / "results" / "runs"
    rows: list[dict] = []
    for run_dir in _matrix_run_dirs(runs_root):
        metrics_path = run_dir / "system_metrics.csv"
        if not metrics_path.exists():
            continue
        m = pd.read_csv(metrics_path)
        meta = _parse_run_id(run_dir.name)
        rows.append(
            {
                "run_id": run_dir.name,
                "mechanism": meta.get("mechanism"),
                "n_identities": meta.get("n_identities"),
                "concurrency": meta.get("concurrency"),
                "mean_cpu_percent": round(m["cpu_percent"].astype(float).mean(), 2),
                "max_cpu_percent": round(m["cpu_percent"].astype(float).max(), 2),
                "mean_rss_mb": round(m["rss_bytes"].astype(float).mean() / 1_048_576, 2),
                "max_rss_mb": round(m["rss_bytes"].astype(float).max() / 1_048_576, 2),
            }
        )
    pd.DataFrame(rows).sort_values(["n_identities", "concurrency", "mechanism"]).to_csv(
        export / "05_system_metrics_by_run.csv", index=False
    )


def _quality_report(export: Path) -> None:
    df = pd.read_csv(export / "02_all_summaries.csv")
    df = df[df["latency_set"] == "all_finished"]
    issues: list[str] = []
    for _, row in df.iterrows():
        fa = int(row.get("false_acceptances") or 0)
        fr = int(row.get("false_rejections") or 0)
        nu = int(row.get("n_unexpected") or 0)
        if fa > 0 or fr > 0 or nu > 0:
            issues.append(
                f"- `{row['run_id']}`: false_acceptances={fa}, "
                f"false_rejections={fr}, n_unexpected={nu}"
            )
    blockchain_valid = df[
        df["run_id"].str.contains("blockchain")
        & df["run_id"].str.contains("valid-active")
        & ~df["run_id"].str.contains("security-battery")
    ]
    bc_fr = int(blockchain_valid["false_rejections"].sum())
    decision = (
        "**Decision: report honestly in Chapter 5** — blockchain valid_active runs show "
        "systematic false rejections (likely implementation defect during scale matrix). "
        "Do not use blockchain accepted_only latency for comparative performance claims "
        "until re-run after fix. X.509 and adversarial (non-valid) scenarios remain usable."
    )
    lines = [
        "# Chapter 5 data quality report",
        "",
        f"Generated from `{export.relative_to(project_root())}`",
        "",
        "## Summary",
        "",
        f"- Matrix summary rows analysed: {len(df)}",
        f"- Runs with anomalies (false accept/reject or unexpected): {len(issues)}",
        f"- Total false_rejections on blockchain valid_active scale runs: {bc_fr}",
        "",
        "## Anomalous runs",
        "",
    ]
    lines.extend(issues if issues else ["- None"])
    lines.extend(["", "## Writing guidance", "", decision, ""])
    (export / "07_data_quality_report.md").write_text("\n".join(lines), encoding="utf-8")


def export_bundle() -> Path:
    root = project_root()
    export = root / "results" / "chapter5_export"
    export.mkdir(parents=True, exist_ok=True)
    runs_root = root / "results" / "runs"

    for name in ("CHAPTER5_RUN_ORDER.md",):
        shutil.copy2(root / "docs" / name, export / "00_run_order.md")
    shutil.copy2(root / "docs" / "METRICS.md", export / "00_METRICS.md")
    shutil.copy2(root / "LIMITATIONS.md", export / "00_LIMITATIONS.md")

    env_src = runs_root / (
        "n10-identities_c1-conc_mech-x509-1backend_valid-active_r30_audit-off_"
        "20260820T020457Z/environment.json"
    )
    shutil.copy2(env_src, export / "01_environment.json")

    matrix_dirs = _matrix_run_dirs(runs_root)
    _merge_csv([d / "summary.csv" for d in matrix_dirs], export / "02_all_summaries.csv")
    _merge_csv(
        [d / "observations.csv" for d in matrix_dirs if "security-battery" in d.name],
        export / "03_security_observations.csv",
    )
    _merge_csv(
        [
            d / "observations.csv"
            for d in matrix_dirs
            if "security-battery" not in d.name
        ],
        export / "04_scale_observations.csv",
    )
    _merge_csv([d / "system_metrics.csv" for d in matrix_dirs], export / "05_system_metrics.csv")

    audit_dir = runs_root / (
        "n10-identities_c1-conc_mech-blockchain-1backend_valid-active_r30_audit-on_"
        "20260820T022802Z"
    )
    shutil.copy2(audit_dir / "observations.csv", export / "06_audit_observations.csv")
    shutil.copy2(audit_dir / "config.json", export / "06_audit_config.json")

    _build_manifest(export)
    _enrich_summaries(export)
    _security_by_scenario(export)
    _comm_overhead_summary(export)
    _system_metrics_summary(export)
    _quality_report(export)

    readme = export / "README.md"
    readme.write_text(
        "# Chapter 5 export bundle\n\n"
        "Upload files per batch as described in `docs/CHAPTER5_GPT_BATCHES.md`.\n\n"
        "| File | Description |\n"
        "|------|-------------|\n"
        "| 00_manifest.json | Full 53-step matrix with on-disk status |\n"
        "| 02_all_summaries_enriched.csv | Run aggregates with parsed factors |\n"
        "| 03_security_by_scenario.csv | Adversarial scenario aggregates |\n"
        "| 04_comm_overhead_summary.csv | Request/response size by run |\n"
        "| 05_system_metrics_by_run.csv | CPU/RSS per run |\n"
        "| 07_data_quality_report.md | Anomaly list and writing guidance |\n",
        encoding="utf-8",
    )
    return export


def main() -> None:
    out = export_bundle()
    n_summaries = len(pd.read_csv(out / "02_all_summaries.csv"))
    n_sec = len(pd.read_csv(out / "03_security_observations.csv"))
    print(f"Exported to {out}")
    print(f"  summaries: {n_summaries} rows")
    print(f"  security observations: {n_sec} rows")


if __name__ == "__main__":
    main()
