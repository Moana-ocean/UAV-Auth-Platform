"""Summaries derived only from stored raw observations."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
from scipy.stats import bootstrap

from app.core.constants import ADVERSARIAL_SCENARIOS


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _latency_ms(rows: list[dict[str, Any]]) -> np.ndarray:
    vals = []
    for row in rows:
        try:
            vals.append(float(row["decision_latency_ms"]))
        except (KeyError, TypeError, ValueError):
            continue
    return np.asarray(vals, dtype=float)


def _percentile(arr: np.ndarray, q: float) -> float | None:
    if arr.size == 0:
        return None
    return float(np.percentile(arr, q))


def _bootstrap_ci(arr: np.ndarray, seed: int) -> tuple[float | None, float | None, str]:
    if arr.size < 2:
        return None, None, "n<2; CI omitted"
    rng = np.random.default_rng(seed)

    def stat(x: np.ndarray) -> float:
        return float(np.mean(x))

    try:
        result = bootstrap(
            (arr,),
            stat,
            n_resamples=10_000,
            confidence_level=0.95,
            method="percentile",
            random_state=rng,
        )
        low = float(result.confidence_interval.low)
        high = float(result.confidence_interval.high)
        return low, high, "scipy.stats.bootstrap percentile 10000 resamples 95%"
    except Exception as exc:  # noqa: BLE001
        return None, None, f"bootstrap failed: {type(exc).__name__}"


def _latency_block(rows: list[dict[str, Any]], seed: int, filter_rule: str) -> dict[str, Any]:
    arr = _latency_ms(rows)
    mean = float(np.mean(arr)) if arr.size else None
    std = float(np.std(arr, ddof=1)) if arr.size > 1 else None
    ci_low, ci_high, ci_method = _bootstrap_ci(arr, seed)
    return {
        "n": int(arr.size),
        "filter_rule": filter_rule,
        "mean_ms": mean,
        "median_ms": _percentile(arr, 50) if arr.size else None,
        "std_ms": std,
        "min_ms": float(np.min(arr)) if arr.size else None,
        "max_ms": float(np.max(arr)) if arr.size else None,
        "p95_ms": _percentile(arr, 95) if arr.size else None,
        "p99_ms": _percentile(arr, 99) if arr.size else None,
        "ci95_low_ms": ci_low,
        "ci95_high_ms": ci_high,
        "ci_method": ci_method,
    }


def summarise_observations(
    rows: list[dict[str, Any]],
    *,
    seed: int = 42,
    batch_seconds: float | None = None,
    offered_load: float | None = None,
) -> dict[str, Any]:
    n_submitted = len(rows)
    warm = [r for r in rows if _as_bool(r.get("warmup"))]
    measured = [r for r in rows if not _as_bool(r.get("warmup"))]
    accepted = [r for r in measured if r.get("observed_outcome") == "ACCEPTED"]
    expected_rej = [
        r
        for r in measured
        if r.get("observed_outcome") != "ACCEPTED" and _as_bool(r.get("expectation_met"))
    ]
    unexpected = [r for r in measured if not _as_bool(r.get("expectation_met"))]
    timeouts = [
        r
        for r in measured
        if r.get("timeout_error_class") in {"auth_timeout", "rpc_timeout", "rpc_unavailable"}
    ]
    internal = [
        r
        for r in measured
        if r.get("observed_outcome") == "INTERNAL_ERROR"
        or r.get("timeout_error_class") == "internal"
    ]
    malicious = [r for r in measured if r.get("scenario") in ADVERSARIAL_SCENARIOS]
    malicious_rejected = [r for r in malicious if r.get("observed_outcome") != "ACCEPTED"]
    false_accept = [r for r in malicious if r.get("observed_outcome") == "ACCEPTED"]
    valid_rows = [r for r in measured if r.get("scenario") in {"valid_active", "concurrent_valid"}]
    false_reject = [r for r in valid_rows if r.get("observed_outcome") != "ACCEPTED"]

    by_cell: dict[str, int] = defaultdict(int)
    for r in measured:
        key = f"{r.get('mechanism')}|{r.get('scenario')}|{r.get('observed_outcome')}"
        by_cell[key] += 1

    n_meas = max(len(measured), 1)
    completed_throughput = None
    if batch_seconds and batch_seconds > 0:
        completed_throughput = len(measured) / batch_seconds

    gas_vals = []
    for r in measured:
        g = r.get("gas_used") or ""
        if str(g).strip():
            try:
                gas_vals.append(float(g))
            except ValueError:
                pass

    return {
        "n_submitted": n_submitted,
        "n_warmup_excluded": len(warm),
        "n_measured": len(measured),
        "n_accepted": len(accepted),
        "n_expected_rejection": len(expected_rej),
        "n_unexpected": len(unexpected),
        "n_timeout": len(timeouts),
        "n_internal_error": len(internal),
        "failure_rate_pct": 100.0 * (len(timeouts) + len(internal)) / n_meas if measured else 0.0,
        "attack_rejection_rate_pct": (
            100.0 * len(malicious_rejected) / len(malicious) if malicious else None
        ),
        "false_acceptances": len(false_accept),
        "false_rejections": len(false_reject),
        "completed_throughput_rps": completed_throughput,
        "offered_load_rps": offered_load,
        "counts_by_mechanism_scenario_outcome": dict(by_cell),
        "latency_all_finished": _latency_block(
            measured, seed, "warmup==false; include all finished decisions"
        ),
        "latency_accepted_only": _latency_block(
            accepted, seed, "warmup==false AND observed_outcome==ACCEPTED"
        ),
        "gas_used": {
            "n": len(gas_vals),
            "mean": float(np.mean(gas_vals)) if gas_vals else None,
            "note": "EVM gas units; not a monetary cost",
        },
    }


def summary_csv_rows(summary: dict[str, Any], run_id: str) -> list[dict[str, Any]]:
    rows = []
    for name, block in (
        ("all_finished", summary["latency_all_finished"]),
        ("accepted_only", summary["latency_accepted_only"]),
    ):
        row = {
            "run_id": run_id,
            "latency_set": name,
            "n_submitted": summary["n_submitted"],
            "n_warmup_excluded": summary["n_warmup_excluded"],
            "n_measured": summary["n_measured"],
            "n_accepted": summary["n_accepted"],
            "n_expected_rejection": summary["n_expected_rejection"],
            "n_unexpected": summary["n_unexpected"],
            "n_timeout": summary["n_timeout"],
            "n_internal_error": summary["n_internal_error"],
            "failure_rate_pct": summary["failure_rate_pct"],
            "attack_rejection_rate_pct": summary["attack_rejection_rate_pct"],
            "false_acceptances": summary["false_acceptances"],
            "false_rejections": summary["false_rejections"],
            "completed_throughput_rps": summary["completed_throughput_rps"],
            "offered_load_rps": summary["offered_load_rps"],
        }
        row.update(block)
        rows.append(row)
    return rows
