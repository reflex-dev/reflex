"""Where the wall time of a reflex command goes.

reflex logs ``[timing] <label>: <seconds>s`` at debug level for each compile
phase (``console.timing`` in 0.8.23, ``log.timing`` in 0.9), and
:func:`parse_timing` maps the labels of both versions to stable phase names.
:class:`TreePhases` samples the command's process tree and splits the time of its
children between package installs and frontend tools. :func:`attribute`
combines both into a breakdown of the command's wall time.
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Any, TypedDict

import psutil

# The labels of 0.8.23 and 0.9 never collide, so one table serves both versions.
PHASE_LABELS = {
    # Both versions.
    "Evaluate Pages (Backend)": "evaluate",
    "Copy assets": "assets",
    "Install Frontend Packages": "install",
    "Write to Disk": "write",
    # 0.8.23.
    "Evaluate Pages (Frontend)": "evaluate",
    "Collect all imports and app wraps": "imports",
    "Auto-memoize StatefulComponents": "memoize",
    "Compile to Javascript": "compile",
    # 0.9, where one phase evaluates, collects imports and memoizes.
    "Compile pages": "compile",
}
INSTALL = "install"
FRONTEND = "frontend"
CLASSES = (INSTALL, FRONTEND)
# How far the measured parts may exceed the total (sampling jitter) before the
# attribution is flagged as a mismatch.
MISMATCH_TOLERANCE = 0.05

_TIMING = re.compile(r"\[timing\] (?P<label>.+?): (?P<seconds>\d+(?:\.\d+)?)s\s*$")
_PACKAGE_MANAGERS = frozenset({"bun", "npm", "pnpm", "yarn"})
_INSTALL_COMMANDS = frozenset({"install", "add", "i", "ci"})
_FRONTEND_TOOLS = frozenset({"node", "vite", "react-router"})
_SCRIPT_SUFFIX = re.compile(r"\.(?:exe|cmd|[cm]?js)$")


def parse_timing(lines: Iterable[str]) -> dict[str, float]:
    """Sum the ``[timing]`` lines of a reflex log per phase.

    Args:
        lines: Log lines, ANSI escapes stripped.

    Returns:
        Seconds per phase, in order of first appearance: stable names from
        :data:`PHASE_LABELS`, or the raw label when it is unknown. Repeated
        phases (e.g. recompiles) are summed.
    """
    phases: dict[str, float] = {}
    for line in lines:
        if match := _TIMING.search(line):
            phase = PHASE_LABELS.get(match["label"], match["label"])
            phases[phase] = phases.get(phase, 0.0) + float(match["seconds"])
    return phases


def _tool_name(arg: str) -> str:
    """Name the program an argument refers to.

    Args:
        arg: A command line argument, e.g. ``/app/.web/node_modules/vite/bin/vite.js``.

    Returns:
        Its file name without a script or executable suffix, e.g. ``vite``.
    """
    return _SCRIPT_SUFFIX.sub("", PurePath(arg).name)


def classify(cmdline: Sequence[str]) -> str | None:
    """Tell package installs and frontend tools apart by their command line.

    Only the program and, for interpreters and shims, the script it runs are
    considered, so arguments that happen to name a tool do not count.

    Args:
        cmdline: The process's command line.

    Returns:
        ``install`` for ``bun``/``npm``/``pnpm``/``yarn`` ``install``/``add``/``i``/``ci``,
        ``frontend`` for ``node``, ``vite`` and ``react-router``, else ``None``.
    """
    names = [_tool_name(arg) for arg in cmdline[:2]]
    for index, name in enumerate(names):
        if (
            name in _PACKAGE_MANAGERS
            and index + 1 < len(cmdline)
            and cmdline[index + 1] in _INSTALL_COMMANDS
        ):
            return INSTALL
    return FRONTEND if _FRONTEND_TOOLS.intersection(names) else None


def _merge_intervals(
    intervals: Iterable[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Merge overlapping or touching intervals.

    Args:
        intervals: ``(start, end)`` pairs in any order.

    Returns:
        Disjoint intervals, sorted by start.
    """
    merged: list[tuple[float, float]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


@dataclass
class ProcessRecord:
    """One descendant seen by :class:`TreePhases`.

    Attributes:
        pid: The process id.
        ppid: The parent process id when first seen.
        cmdline: The command line.
        first_seen: When a sample first saw it, in seconds since the sampler's origin.
        last_seen: When a sample last saw it.
        cpu_s: Its user and system CPU time at the last sample.
        kind: ``install``, ``frontend`` or ``None``; the class of its topmost
            classified ancestor in the tree, else its own.
    """

    pid: int
    ppid: int
    cmdline: list[str]
    first_seen: float
    last_seen: float
    cpu_s: float
    kind: str | None = None


@dataclass(frozen=True)
class ClassTotals:
    """The time spent in one class of processes.

    Attributes:
        wall_s: The length of the union of the class's process lifetimes.
        cpu_s: The CPU time of the class's processes.
        intervals: The union as disjoint ``(start, end)`` intervals.
    """

    wall_s: float
    cpu_s: float
    intervals: list[tuple[float, float]]


@dataclass(frozen=True)
class TreeReport:
    """What :class:`TreePhases` saw.

    Attributes:
        classes: Totals for ``install`` and ``frontend``, zero when not seen.
        processes: Every descendant seen.
    """

    classes: dict[str, ClassTotals]
    processes: list[ProcessRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Summarize the report for a sample's extra data.

        Returns:
            Wall and CPU seconds and intervals per class, and the process count.
        """
        return {
            "classes": {
                name: {
                    "wall_s": totals.wall_s,
                    "cpu_s": totals.cpu_s,
                    "intervals": [list(interval) for interval in totals.intervals],
                }
                for name, totals in self.classes.items()
            },
            "processes": len(self.processes),
        }


class TreePhases:
    """Sample a process tree on a thread and attribute its children's time.

    Each sample records every descendant's command line, first and last sighting
    and CPU time. Lifetimes are only known to the sampling interval, and a
    process that lives shorter than it can be missed.
    """

    def __init__(
        self, root_pid: int, interval: float = 0.02, *, t0: float | None = None
    ) -> None:
        """Prepare the sampler.

        Args:
            root_pid: The root of the tree; only its descendants are recorded.
            interval: Seconds between samples.
            t0: The ``time.perf_counter()`` origin of the recorded times;
                defaults to now.
        """
        self.root_pid = root_pid
        self.interval = interval
        self.t0 = time.perf_counter() if t0 is None else t0
        self.report: TreeReport | None = None
        self._records: dict[tuple[int, float], ProcessRecord] = {}
        self._root: psutil.Process | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="reflex-bench tree phases", daemon=True
        )

    def start(self) -> TreePhases:
        """Start sampling.

        Returns:
            The sampler.
        """
        try:
            self._root = psutil.Process(self.root_pid)
        except psutil.NoSuchProcess:
            self._root = None
        self._thread.start()
        return self

    def stop(self) -> TreeReport:
        """Stop sampling and attribute the time seen.

        Returns:
            The report.
        """
        self._stop.set()
        self._thread.join()
        self._sample()
        self.report = self._report()
        return self.report

    def _run(self) -> None:
        """Sample until stopped."""
        while True:
            self._sample()
            if self._stop.wait(self.interval):
                return

    def _sample(self) -> None:
        """Record the descendants alive right now."""
        if self._root is None:
            return
        now = time.perf_counter() - self.t0
        try:
            children = self._root.children(recursive=True)
        except psutil.NoSuchProcess:
            return
        for child in children:
            self._observe(child, now)

    def _observe(self, child: psutil.Process, now: float) -> None:
        """Record one sighting of a descendant; one that just exited is skipped.

        Args:
            child: The descendant.
            now: The time of the sample.
        """
        try:
            with child.oneshot():
                key = (child.pid, child.create_time())
                times = child.cpu_times()
                record = self._records.get(key)
                if record is None:
                    self._records[key] = ProcessRecord(
                        pid=child.pid,
                        ppid=child.ppid(),
                        cmdline=child.cmdline(),
                        first_seen=now,
                        last_seen=now,
                        cpu_s=times.user + times.system,
                    )
                else:
                    record.last_seen = now
                    record.cpu_s = times.user + times.system
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return

    def _report(self) -> TreeReport:
        """Classify the recorded processes and total each class.

        Returns:
            The report.
        """
        records = sorted(self._records.values(), key=lambda record: record.first_seen)
        by_pid = {record.pid: record for record in records}
        own = {record.pid: classify(record.cmdline) for record in records}
        for record in records:
            # A child inherits the class of its topmost classified ancestor, so
            # e.g. a postinstall `node` under `bun add` counts as install time.
            kind, pid, seen = None, record.pid, set()
            while pid in by_pid and pid not in seen:
                seen.add(pid)
                kind = own[pid] or kind
                pid = by_pid[pid].ppid
            record.kind = kind
        classes = {}
        for name in CLASSES:
            members = [record for record in records if record.kind == name]
            intervals = _merge_intervals(
                (record.first_seen, record.last_seen) for record in members
            )
            classes[name] = ClassTotals(
                wall_s=sum((end - start for start, end in intervals), 0.0),
                cpu_s=sum((record.cpu_s for record in members), 0.0),
                intervals=intervals,
            )
        return TreeReport(classes=classes, processes=records)


class Attribution(TypedDict):
    """A command's wall time split into its parts, in seconds.

    ``other`` is the rest (interpreter start-up, imports, reflex's own work
    outside the timed phases) and goes negative when the parts overlap.
    ``mismatch`` flags parts that exceed the total by more than
    :data:`MISMATCH_TOLERANCE`.
    """

    total: float
    python: float
    install: float
    frontend: float
    other: float
    mismatch: bool


def attribute(
    total_s: float, timing: Mapping[str, float], tree: TreeReport | None
) -> Attribution:
    """Split a command's wall time into Python phases, installs, frontend tools and the rest.

    Package installs come from the process tree rather than the ``install``
    timing phase, which wraps them, so they are not counted twice.

    Args:
        total_s: The command's wall time.
        timing: Seconds per phase from :func:`parse_timing`.
        tree: The command's process tree, if it was sampled.

    Returns:
        The attribution, flagged when the parts do not fit into the total.
    """
    python = sum(seconds for phase, seconds in timing.items() if phase != INSTALL)
    install = tree.classes[INSTALL].wall_s if tree is not None else 0.0
    frontend = tree.classes[FRONTEND].wall_s if tree is not None else 0.0
    measured = python + install + frontend
    return {
        "total": total_s,
        "python": python,
        "install": install,
        "frontend": frontend,
        "other": total_s - measured,
        "mismatch": measured > total_s * (1 + MISMATCH_TOLERANCE),
    }
