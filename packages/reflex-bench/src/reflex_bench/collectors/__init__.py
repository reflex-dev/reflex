"""Measurements of a running reflex process tree: cgroup counters, PSS samples and phases."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

PROC = Path("/proc")


class SamplingLoop:
    """Call a function on a daemon thread every interval until stopped.

    An exception ends the loop and :meth:`stop` raises it: a collector whose
    sampling failed must not pass off what it saw before as a measurement.
    """

    def __init__(self, sample: Callable[[], None], interval: float, what: str) -> None:
        """Prepare the loop.

        Args:
            sample: Takes one sample.
            interval: Seconds between samples.
            what: What is sampled, for the thread's name and the error.
        """
        self.what = what
        self._sample = sample
        self._interval = interval
        self._halt = threading.Event()
        self._error: Exception | None = None
        self._thread = threading.Thread(
            target=self._run, name=f"reflex-bench {what}", daemon=True
        )

    def start(self) -> None:
        """Take the first sample now and the next ones every interval."""
        self._thread.start()

    def stop(self) -> None:
        """Stop sampling and wait for the thread.

        Raises:
            RuntimeError: When a sample raised, with that exception as the cause.
        """
        self._halt.set()
        self._thread.join()
        if self._error is not None:
            msg = f"{self.what} failed: {self._error!r}"
            raise RuntimeError(msg) from self._error

    def _run(self) -> None:
        """Sample until stopped or until a sample raises."""
        try:
            while True:
                self._sample()
                if self._halt.wait(self._interval):
                    return
        except Exception as exc:
            self._error = exc
