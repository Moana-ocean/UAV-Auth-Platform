"""Process CPU/memory sampler used during a run."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime

import psutil


class ResourceSampler:
    def __init__(self, interval_s: float, writer: Callable[[dict], None]) -> None:
        self.interval_s = max(0.1, float(interval_s))
        self.writer = writer
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.proc = psutil.Process()
        self.proc.cpu_percent(None)

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="resource-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                mem = psutil.virtual_memory()
                net = psutil.net_io_counters()
                rss = self.proc.memory_info().rss
                row = {
                    "utc_timestamp": datetime.now(UTC).isoformat(),
                    "cpu_percent": float(self.proc.cpu_percent(None)),
                    "rss_bytes": int(rss),
                    "available_memory_bytes": int(mem.available),
                    "net_bytes_sent": int(net.bytes_sent) if net else "",
                    "net_bytes_recv": int(net.bytes_recv) if net else "",
                    "pid": self.proc.pid,
                    "name": self.proc.name(),
                }
                self.writer(row)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(self.interval_s)
