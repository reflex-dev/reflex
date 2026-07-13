"""Benchmark-only event pipeline tracing."""

from __future__ import annotations

import dataclasses
import json
import time
from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any


@dataclasses.dataclass(frozen=True)
class StageEvent:
    """One monotonic pipeline stage observation."""

    token: str
    stage: str
    timestamp_ns: int


@dataclasses.dataclass
class PipelineTrace:
    """Collect per-token pipeline stages without changing runtime code."""

    events: list[StageEvent] = dataclasses.field(default_factory=list)

    def record(self, token: str, stage: str) -> None:
        """Record a pipeline stage using a monotonic clock.

        Args:
            token: Event token or transaction identifier.
            stage: Stable stage name.
        """
        self.events.append(
            StageEvent(token=token, stage=stage, timestamp_ns=time.perf_counter_ns())
        )

    def durations_ms(self, stages: Sequence[tuple[str, str]]) -> dict[str, list[float]]:
        """Calculate named adjacent or non-adjacent stage durations.

        Args:
            stages: Start/end stage pairs.

        Returns:
            Durations grouped under ``start_to_end`` keys.
        """
        grouped: dict[str, list[StageEvent]] = defaultdict(list)
        for event in self.events:
            grouped[event.token].append(event)

        durations: dict[str, list[float]] = {
            f"{start}_to_{end}": [] for start, end in stages
        }
        for token_events in grouped.values():
            timestamps = {event.stage: event.timestamp_ns for event in token_events}
            for start, end in stages:
                if start in timestamps and end in timestamps:
                    durations[f"{start}_to_{end}"].append(
                        (timestamps[end] - timestamps[start]) / 1_000_000
                    )
        return durations

    def chrome_trace(self) -> dict[str, Any]:
        """Convert observations to Chrome instant trace events.

        Returns:
            A Chrome trace JSON mapping.
        """
        return {
            "traceEvents": [
                {
                    "name": event.stage,
                    "cat": "reflex.event_pipeline",
                    "ph": "i",
                    "s": "t",
                    "pid": 1,
                    "tid": event.token,
                    "ts": event.timestamp_ns / 1000,
                }
                for event in self.events
            ]
        }

    def write_chrome_trace(self, path: str | Path) -> Path:
        """Write Chrome trace JSON.

        Args:
            path: Destination path.

        Returns:
            The resolved destination path.
        """
        destination = Path(path).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.chrome_trace(), indent=2) + "\n",
            encoding="utf-8",
        )
        return destination

    def extend(self, events: Iterable[StageEvent]) -> None:
        """Append existing observations.

        Args:
            events: Observations to append.
        """
        self.events.extend(events)
