"""Portable run artefacts: CSV/JSON/JSONL plus a SQLite index."""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.schemas import OBSERVATION_FIELDS, Observation

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    mechanism TEXT,
    n_observations INTEGER DEFAULT 0,
    path TEXT NOT NULL,
    notes TEXT
);
"""


class RunStore:
    def __init__(self, run_dir: Path, index_db: Path | None = None) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.charts_dir = self.run_dir / "charts"
        self.charts_dir.mkdir(exist_ok=True)
        self.obs_path = self.run_dir / "observations.csv"
        self.events_path = self.run_dir / "events.jsonl"
        self.receipts_path = self.run_dir / "blockchain_receipts.jsonl"
        self.metrics_path = self.run_dir / "system_metrics.csv"
        self.status_path = self.run_dir / "status.json"
        self.cancel_path = self.run_dir / "cancel.flag"
        self._lock = threading.Lock()
        self._index_db = index_db
        self._header_written = self.obs_path.exists() and self.obs_path.stat().st_size > 0
        if not self._header_written:
            with self.obs_path.open("w", newline="", encoding="utf-8") as fh:
                csv.DictWriter(fh, fieldnames=OBSERVATION_FIELDS).writeheader()
            self._header_written = True
        if not self.metrics_path.exists():
            with self.metrics_path.open("w", newline="", encoding="utf-8") as fh:
                csv.DictWriter(
                    fh,
                    fieldnames=(
                        "utc_timestamp",
                        "cpu_percent",
                        "rss_bytes",
                        "available_memory_bytes",
                        "net_bytes_sent",
                        "net_bytes_recv",
                        "pid",
                        "name",
                    ),
                ).writeheader()

    def write_json(self, name: str, payload: Any) -> None:
        path = self.run_dir / name
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def append_observation(self, obs: Observation) -> None:
        with self._lock:
            with self.obs_path.open("a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=OBSERVATION_FIELDS)
                writer.writerow(obs.to_row())

    def append_event(self, event: dict[str, Any]) -> None:
        event = dict(event)
        event.setdefault("utc_timestamp", datetime.now(UTC).isoformat())
        with self._lock:
            with self.events_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, default=str) + "\n")

    def append_receipt(self, receipt: dict[str, Any]) -> None:
        with self._lock:
            with self.receipts_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(receipt, default=str) + "\n")

    def append_metric_row(self, row: dict[str, Any]) -> None:
        with self._lock:
            with self.metrics_path.open("a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=(
                        "utc_timestamp",
                        "cpu_percent",
                        "rss_bytes",
                        "available_memory_bytes",
                        "net_bytes_sent",
                        "net_bytes_recv",
                        "pid",
                        "name",
                    ),
                )
                writer.writerow(row)

    def write_status(self, payload: dict[str, Any]) -> None:
        tmp = self.status_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.status_path)

    def request_cancel(self) -> None:
        self.cancel_path.write_text("1", encoding="utf-8")

    def cancelled(self) -> bool:
        return self.cancel_path.exists()

    def finalise_checksums(self) -> Path:
        digest_path = self.run_dir / "checksums.sha256"
        lines = []
        for path in sorted(self.run_dir.rglob("*")):
            if path.is_dir() or path.name == "checksums.sha256":
                continue
            h = hashlib.sha256(path.read_bytes()).hexdigest()
            rel = path.relative_to(self.run_dir).as_posix()
            lines.append(f"{h}  {rel}")
        digest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return digest_path

    def upsert_index(
        self, run_id: str, status: str, mechanism: str, notes: str, n_obs: int
    ) -> None:
        if not self._index_db:
            return
        self._index_db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._index_db) as conn:
            conn.execute(SCHEMA)
            conn.execute(
                """
                INSERT INTO runs(run_id, created_at, status, mechanism, n_observations, path, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status=excluded.status,
                    n_observations=excluded.n_observations
                """,
                (
                    run_id,
                    datetime.now(UTC).isoformat(),
                    status,
                    mechanism,
                    n_obs,
                    str(self.run_dir),
                    notes,
                ),
            )
            conn.commit()


def list_runs(results_root: Path) -> list[dict[str, Any]]:
    runs = []
    root = Path(results_root)
    if not root.exists():
        return runs
    for d in sorted(root.iterdir()):
        cfg = d / "config.json"
        status = d / "status.json"
        if not cfg.exists():
            continue
        item = {"run_id": d.name, "path": str(d)}
        item["config"] = json.loads(cfg.read_text(encoding="utf-8"))
        if status.exists():
            item["status"] = json.loads(status.read_text(encoding="utf-8"))
        runs.append(item)
    return runs


def read_observations(run_dir: Path) -> list[dict[str, Any]]:
    path = Path(run_dir) / "observations.csv"
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def zip_run(run_dir: Path, dest: Path | None = None) -> Path:
    import zipfile

    run_dir = Path(run_dir)
    dest = dest or run_dir.parent / f"{run_dir.name}.zip"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in run_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(run_dir.parent).as_posix())
    return dest
