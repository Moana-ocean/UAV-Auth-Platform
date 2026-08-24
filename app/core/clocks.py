"""Monotonic high-resolution clock helpers."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager


def now_ns() -> int:
    return time.perf_counter_ns()


@contextmanager
def timed() -> Iterator[Callable[[], int]]:
    start = time.perf_counter_ns()
    elapsed = lambda: time.perf_counter_ns() - start  # noqa: E731
    yield elapsed
