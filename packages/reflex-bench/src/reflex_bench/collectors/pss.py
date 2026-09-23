"""Proportional set size (PSS) of a process tree, read from ``/proc``.

The fallback for peak memory when no cgroup scope is available. Summing RSS
over a tree counts the pages that forked workers share once per process; PSS
splits each shared page between the processes that map it, so the PSS of a
tree adds up to the memory the tree actually uses. Sampled peaks can miss
spikes between samples, so results record ``method: "pss_sampling"`` and are
never mixed with cgroup peaks. Linux only.
"""

from __future__ import annotations

import math
import operator
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any

import psutil

PROC = Path("/proc")
METHOD = "pss_sampling"
TIMELINE_POINTS = 2000
_KB = 1024


@dataclass(frozen=True)
class PssReading:
    """The memory of a process tree at one moment.

    Attributes:
        pss_bytes: The tree's summed proportional set size.
        pss_anon_bytes: Its anonymous part (heaps, stacks).
        pss_file_bytes: Its file-backed part (code, mapped files).
        uss_bytes: Unique set size (private clean and dirty pages) per command
            name, summed over the processes of that name.
        processes: How many processes were read.
    """

    pss_bytes: int
    pss_anon_bytes: int
    pss_file_bytes: int
    uss_bytes: dict[str, int]
    processes: int


def available(proc_root: Path = PROC) -> str | None:
    """Check that the PSS of processes can be read.

    Args:
        proc_root: The ``/proc`` mount.

    Returns:
        ``None`` when it can, else why not.
    """
    try:
        (proc_root / "self" / "smaps_rollup").read_bytes()
    except OSError as exc:
        return (
            f"cannot read {proc_root}/self/smaps_rollup (PSS needs Linux 4.14+): {exc}"
        )
    return None


def _rollup(text: str) -> dict[str, int]:
    """Parse a ``smaps_rollup`` file.

    Args:
        text: The file content: a header line, then ``Name:  <n> kB`` lines.

    Returns:
        Bytes per field.
    """
    fields: dict[str, int] = {}
    for line in text.splitlines()[1:]:
        name, _, rest = line.partition(":")
        value = rest.split()
        if value and value[0].isdigit():
            fields[name] = int(value[0]) * _KB
    return fields


def tree_pss(root_pid: int, *, proc_root: Path = PROC) -> PssReading:
    """Read the PSS of a process and all its descendants.

    Processes that exit while the tree is read are skipped.

    Args:
        root_pid: The root of the tree.
        proc_root: The ``/proc`` mount.

    Returns:
        The tree's memory; empty when the root is gone.
    """
    try:
        root = psutil.Process(root_pid)
        pids = [root_pid, *(child.pid for child in root.children(recursive=True))]
    except psutil.NoSuchProcess:
        pids = []
    pss = anon = file = processes = 0
    uss: dict[str, int] = {}
    for pid in pids:
        directory = proc_root / str(pid)
        try:
            fields = _rollup((directory / "smaps_rollup").read_text(encoding="utf-8"))
            name = (directory / "comm").read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if "Pss" not in fields:
            # A zombie has no memory left to report.
            continue
        processes += 1
        pss += fields["Pss"]
        anon += fields.get("Pss_Anon", 0)
        file += fields.get("Pss_File", 0)
        uss[name] = (
            uss.get(name, 0)
            + fields.get("Private_Clean", 0)
            + fields.get("Private_Dirty", 0)
        )
    return PssReading(
        pss_bytes=pss,
        pss_anon_bytes=anon,
        pss_file_bytes=file,
        uss_bytes=uss,
        processes=processes,
    )


def _downsample(points: list[tuple[float, int]], limit: int) -> list[tuple[float, int]]:
    """Shorten a timeline, keeping the highest point of each stretch.

    Args:
        points: ``(time, value)`` pairs in time order.
        limit: The most points to keep.

    Returns:
        At most ``limit`` points; the timeline itself when it is short enough.
    """
    if len(points) <= limit:
        return points
    size = math.ceil(len(points) / limit)
    return [
        max(points[start : start + size], key=operator.itemgetter(1))
        for start in range(0, len(points), size)
    ]


@dataclass(frozen=True)
class PssResult:
    """What a :class:`PssSampler` saw.

    Attributes:
        peak_bytes: The highest tree PSS sampled.
        peak: The reading at the peak, with the USS per command name.
        timeline: ``(seconds since the origin, PSS bytes)`` per sample,
            downsampled to at most :data:`TIMELINE_POINTS` points.
        samples: How many samples were taken.
        interval_s: The sampling interval.
        method: Always ``pss_sampling``.
    """

    peak_bytes: int
    peak: PssReading | None
    timeline: list[tuple[float, int]]
    samples: int
    interval_s: float
    method: str = METHOD

    def to_dict(self) -> dict[str, Any]:
        """Describe the result for a sample's extra data.

        Returns:
            The method, peak, USS at the peak, sample count and timeline.
        """
        return {
            "method": self.method,
            "peak_bytes": self.peak_bytes,
            "uss_bytes": dict(self.peak.uss_bytes) if self.peak else {},
            "samples": self.samples,
            "interval_s": self.interval_s,
            "timeline": [[round(t, 3), value] for t, value in self.timeline],
        }


class PssSampler:
    """Sample the PSS of a process tree on a thread until stopped."""

    def __init__(
        self,
        root_pid: int,
        interval: float = 0.05,
        *,
        proc_root: Path = PROC,
        t0: float | None = None,
    ) -> None:
        """Prepare the sampler.

        Args:
            root_pid: The root of the tree.
            interval: Seconds between samples.
            proc_root: The ``/proc`` mount.
            t0: The ``time.perf_counter()`` origin of the timeline; defaults to now.
        """
        self.root_pid = root_pid
        self.interval = interval
        self.proc_root = proc_root
        self.t0 = time.perf_counter() if t0 is None else t0
        self.result: PssResult | None = None
        self._timeline: list[tuple[float, int]] = []
        self._peak: PssReading | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="reflex-bench pss", daemon=True
        )

    def start(self) -> PssSampler:
        """Start sampling.

        Returns:
            The sampler.
        """
        self._thread.start()
        return self

    def stop(self) -> PssResult:
        """Stop sampling.

        Returns:
            The peak and the timeline.
        """
        self._stop.set()
        self._thread.join()
        self.result = PssResult(
            peak_bytes=self._peak.pss_bytes if self._peak else 0,
            peak=self._peak,
            timeline=_downsample(self._timeline, TIMELINE_POINTS),
            samples=len(self._timeline),
            interval_s=self.interval,
        )
        return self.result

    def _run(self) -> None:
        """Sample until stopped."""
        while True:
            reading = tree_pss(self.root_pid, proc_root=self.proc_root)
            self._timeline.append((time.perf_counter() - self.t0, reading.pss_bytes))
            if self._peak is None or reading.pss_bytes > self._peak.pss_bytes:
                self._peak = reading
            if self._stop.wait(self.interval):
                return

    def __enter__(self) -> PssSampler:
        """Start sampling.

        Returns:
            The sampler.
        """
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop sampling; the result is in :attr:`result`.

        Args:
            exc_type: The exception type, if any.
            exc: The exception, if any.
            traceback: Its traceback, if any.
        """
        self.stop()
