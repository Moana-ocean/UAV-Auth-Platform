"""Publication-quality charts written from stored observations only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def _ms(rows: list[dict[str, Any]]) -> list[float]:
    out = []
    for r in rows:
        if str(r.get("warmup", "")).lower() == "true":
            continue
        try:
            out.append(float(r["decision_latency_ms"]))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def write_charts(rows: list[dict[str, Any]], charts_dir: Path) -> list[str]:
    charts_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    by_mech: dict[str, list[float]] = {}
    for r in rows:
        if str(r.get("warmup", "")).lower() == "true":
            continue
        by_mech.setdefault(r.get("mechanism", "?"), []).append(
            float(r.get("decision_latency_ms") or 0)
        )

    if by_mech:
        labels = sorted(by_mech)
        data = [by_mech[k] for k in labels]
        ymax = max((max(v) if v else 0) for v in data) * 1.05 or 1
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.boxplot(data, tick_labels=labels, showfliers=True)
        ax.set_ylabel("decision_latency_ms")
        ax.set_title("Decision latency by mechanism (warm-ups excluded)")
        ax.set_ylim(0, ymax)
        ax.grid(True, axis="y", alpha=0.3)
        path = charts_dir / "latency_boxplot.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        fig.savefig(charts_dir / "latency_boxplot.svg", bbox_inches="tight")
        plt.close(fig)
        written.append(str(path))

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.violinplot(data, showmeans=True, showmedians=True)
        ax.set_xticks(np.arange(1, len(labels) + 1), labels)
        ax.set_ylabel("decision_latency_ms")
        ax.set_title("Decision latency violin plot (warm-ups excluded)")
        ax.set_ylim(0, ymax)
        path = charts_dir / "latency_violin.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        fig.savefig(charts_dir / "latency_violin.svg", bbox_inches="tight")
        plt.close(fig)
        written.append(str(path))

        if "x509" in by_mech and "blockchain" in by_mech:
            fig, ax = plt.subplots(figsize=(8, 5))
            ax.boxplot([by_mech["x509"], by_mech["blockchain"]], tick_labels=["x509", "blockchain"])
            ax.set_ylabel("decision_latency_ms")
            ax.set_title("Comparable axes: X.509 vs blockchain decision latency")
            ax.set_ylim(0, ymax)
            ax.grid(True, axis="y", alpha=0.3)
            path = charts_dir / "x509_vs_blockchain.png"
            fig.savefig(path, dpi=150, bbox_inches="tight")
            fig.savefig(charts_dir / "x509_vs_blockchain.svg", bbox_inches="tight")
            plt.close(fig)
            written.append(str(path))
    return written
