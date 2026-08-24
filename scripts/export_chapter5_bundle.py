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
    return sorted(p.parent for p in runs_root.glob("n*-*/summary.csv") if p.parent.is_dir())


def _merge_csv(paths: list[Path], out: Path) -> int:
    if not paths:
        out.write_text("", encoding="utf-8")
        return 0
    frames = [pd.read_csv(p) for p in paths]
    df = pd.concat(frames, ignore_index=True)
    df.to_csv(out, index=False)
    return len(df)


def _factor_key(mechanism: str, n: int, concurrency: list[int] | int, scenarios: list[str], audit: bool) -> str:
    c = concurrency[0] if isinstance(concurrency, list) else concurrency
    if scenarios == ["valid_active"]:
        scen = "valid_active"
    else:
        scen = "security_battery"
    return f"{mechanism}|n={n}|c={c}|{scen}|audit={'on' if audit else 'off'}"


def _build_manifest(export: Path, runs_root: Path) -> None:
    """Match planned steps to real on-disk run directories by factors (not regenerated timestamps)."""
    jobs = planned_runs()
    dirs = _matrix_run_dirs(runs_root)
    by_factor: dict[str, list[Path]] = {}
    for d in dirs:
        meta = _parse_run_id(d.name)
        if not meta:
            continue
        scen = "security_battery" if "security" in str(meta.get("scenario", "")) else "valid_active"
        key = (
            f"{meta['mechanism']}|n={meta['n_identities']}|c={meta['concurrency']}|"
            f"{scen}|audit={'on' if meta['audit_tx'] else 'off'}"
        )
        by_factor.setdefault(key, []).append(d)

    steps: list[dict] = []
    for job in jobs:
        key = _factor_key(
            job.cfg.mechanism,
            job.cfg.n_identities,
            job.cfg.concurrency_levels,
            job.cfg.scenarios,
            job.cfg.audit_tx_enabled,
        )
        matches = by_factor.get(key, [])
        # Prefer the newest directory if multiple exist for the same cell.
        chosen = sorted(matches, key=lambda p: p.name)[-1] if matches else None
        entry = {
            "step": job.step,
            "phase": job.phase,
            "notes": job.notes,
            "planned_factor_key": key,
            "mechanism": job.cfg.mechanism,
            "n_identities": job.cfg.n_identities,
            "concurrency": job.cfg.concurrency_levels,
            "scenarios": job.cfg.scenarios,
            "repetitions": job.cfg.repetitions,
            "warmup": job.cfg.warmup_repetitions,
            "audit_tx": job.cfg.audit_tx_enabled,
            "present_on_disk": chosen is not None,
            "run_id": chosen.name if chosen else None,
            "path": str(chosen) if chosen else None,
        }
        if chosen and (chosen / "status.json").exists():
            entry["status"] = json.loads((chosen / "status.json").read_text(encoding="utf-8")).get(
                "status", "unknown"
            )
        steps.append(entry)

    n_present = sum(1 for s in steps if s["present_on_disk"])
    manifest = {
        "n_steps": len(steps),
        "n_present": n_present,
        "n_missing": len(steps) - n_present,
        "runs_root": str(runs_root),
        "match_method": "factor_key_latest_timestamp",
        "steps": steps,
    }
    (export / "00_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _enrich_summaries(export: Path) -> None:
    src = export / "02_all_summaries.csv"
    if not src.exists() or src.stat().st_size == 0:
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
        attack_rej = round(100.0 * (1 - false_acc / n_mal), 2) if n_mal else None
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


def _system_metrics_summary(export: Path, run_dirs: list[Path]) -> None:
    rows: list[dict] = []
    for run_dir in run_dirs:
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
    if rows:
        pd.DataFrame(rows).sort_values(["n_identities", "concurrency", "mechanism"]).to_csv(
            export / "05_system_metrics_by_run.csv", index=False
        )


def _quality_report(export: Path) -> None:
    src = export / "02_all_summaries.csv"
    if not src.exists() or src.stat().st_size == 0:
        (export / "07_data_quality_report.md").write_text(
            "# Chapter 5 data quality report\n\nNo summaries found.\n", encoding="utf-8"
        )
        return
    df = pd.read_csv(src)
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
    bc_fr = int(blockchain_valid["false_rejections"].sum()) if len(blockchain_valid) else 0
    if issues:
        decision = (
            "**NOT clean for unrestricted Chapter 5 comparison** — resolve anomalies "
            "listed below before treating blockchain accepted_only latency as comparable."
        )
    else:
        decision = (
            "**Clean for Chapter 5 analysis** — no false acceptances/rejections or unexpected "
            "outcomes in all_finished summaries for this export package."
        )
    try:
        rel = str(export.relative_to(project_root()))
    except ValueError:
        rel = str(export)
    lines = [
        "# Chapter 5 data quality report",
        "",
        f"Generated from `{rel}`",
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


def export_bundle(
    *,
    runs_root: str | Path | None = None,
    export_dir: str | Path | None = None,
) -> Path:
    root = project_root()
    runs = Path(runs_root) if runs_root else (root / "results" / "runs")
    if not runs.is_absolute():
        runs = root / runs
    export = Path(export_dir) if export_dir else (root / "results" / "chapter5_export")
    if not export.is_absolute():
        export = root / export
    export.mkdir(parents=True, exist_ok=True)

    shutil.copy2(root / "docs" / "CHAPTER5_RUN_ORDER.md", export / "00_run_order.md")
    shutil.copy2(root / "docs" / "METRICS.md", export / "00_METRICS.md")
    shutil.copy2(root / "LIMITATIONS.md", export / "00_LIMITATIONS.md")

    _build_manifest(export, runs)
    manifest = json.loads((export / "00_manifest.json").read_text(encoding="utf-8"))
    # Only use the factor-matched latest run per planned step — ignore superseded retries.
    matrix_dirs = [
        Path(s["path"])
        for s in manifest["steps"]
        if s.get("present_on_disk") and s.get("path")
    ]
    (export / "00_selected_run_ids.txt").write_text(
        "\n".join(d.name for d in matrix_dirs) + "\n", encoding="utf-8"
    )

    env_candidates = [d / "environment.json" for d in matrix_dirs if (d / "environment.json").exists()]
    if env_candidates:
        shutil.copy2(env_candidates[0], export / "01_environment.json")

    _merge_csv([d / "summary.csv" for d in matrix_dirs], export / "02_all_summaries.csv")
    _merge_csv(
        [d / "observations.csv" for d in matrix_dirs if "security-battery" in d.name],
        export / "03_security_observations.csv",
    )
    _merge_csv(
        [d / "observations.csv" for d in matrix_dirs if "security-battery" not in d.name],
        export / "04_scale_observations.csv",
    )
    _merge_csv([d / "system_metrics.csv" for d in matrix_dirs], export / "05_system_metrics.csv")

    audit_dirs = [
        d
        for d in matrix_dirs
        if "blockchain" in d.name and "audit-on" in d.name and "valid-active" in d.name
    ]
    if audit_dirs:
        audit_dir = sorted(audit_dirs, key=lambda p: p.name)[-1]
        shutil.copy2(audit_dir / "observations.csv", export / "06_audit_observations.csv")
        shutil.copy2(audit_dir / "config.json", export / "06_audit_config.json")

    _enrich_summaries(export)
    _security_by_scenario(export)
    _comm_overhead_summary(export)
    _system_metrics_summary(export, matrix_dirs)
    _quality_report(export)

    for name in (
        "BASELINE_INVENTORY.md",
        "ROOT_CAUSE_AND_FIX_REPORT.md",
        "RERUN_PLAN.md",
        "CHANGE_IMPACT_ASSESSMENT.md",
        "BEFORE_AFTER_VALIDATION.md",
        "REGRESSION_TEST_REPORT.md",
    ):
        src = root / name
        if src.exists():
            shutil.copy2(src, export / name)

    (export / "README.md").write_text(
        "# Chapter 5 export bundle\n\n"
        f"runs_root: `{runs}`\n\n"
        "Manifest matches planned steps to real directories by factor key "
        "(mechanism, n, concurrency, scenario group, audit), using the latest timestamp "
        "when duplicates exist. Summaries include only those selected run IDs.\n",
        encoding="utf-8",
    )
    return export


def main() -> None:
    import sys

    runs_root = None
    export_dir = None
    argv = sys.argv[1:]
    if "--runs-root" in argv:
        runs_root = argv[argv.index("--runs-root") + 1]
    if "--export-dir" in argv:
        export_dir = argv[argv.index("--export-dir") + 1]
    out = export_bundle(runs_root=runs_root, export_dir=export_dir)
    n_summaries = len(pd.read_csv(out / "02_all_summaries.csv")) if (out / "02_all_summaries.csv").stat().st_size else 0
    print(f"Exported to {out}")
    print(f"  summaries: {n_summaries} rows")
    man = json.loads((out / "00_manifest.json").read_text(encoding="utf-8"))
    print(f"  manifest present={man['n_present']}/{man['n_steps']} missing={man['n_missing']}")


if __name__ == "__main__":
    main()
