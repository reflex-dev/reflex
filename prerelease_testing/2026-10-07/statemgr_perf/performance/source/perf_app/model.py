"""Dataclass and state workload shared by real browser and isolated probes."""

import importlib.metadata
import os
import time
from dataclasses import dataclass
from pathlib import Path
import reflex as rx

assert str(Path(os.environ["REFLEX_EXPECT_ENV"]) / "lib") in rx.__file__, rx.__file__
CAPTURE = os.environ.get("PERF_QUIET_CONFIRMED") == "1"
SHARED = os.environ.get("PERF_SHARED") == "1"
print(
    "PERF_SOURCE",
    importlib.metadata.version("reflex"),
    rx.__file__,
    "shared",
    SHARED,
    "capture",
    CAPTURE,
    flush=True,
)


@dataclass
class Shipment:
    """A realistic row of the pending shipment list."""

    identifier: int
    units: int
    zone: int


class Workload(rx.State):
    """Read/sort 5,000 dataclass rows, then update 50 independent state vars."""

    rows: list[Shipment] = [Shipment(i, (i * 17) % 1000, i % 7) for i in range(5000)]
    seed: int = 7
    labels: list[int] = list(range(200))
    sequence: int = 0
    checksum: int = 0
    work_ns: int = 0
    work_cpu_ns: int = 0
    order_valid: bool = False
    rank_checksum: int = 0
    value_0: int = 0
    value_1: int = 0
    value_2: int = 0
    value_3: int = 0
    value_4: int = 0
    value_5: int = 0
    value_6: int = 0
    value_7: int = 0
    value_8: int = 0
    value_9: int = 0
    value_10: int = 0
    value_11: int = 0
    value_12: int = 0
    value_13: int = 0
    value_14: int = 0
    value_15: int = 0
    value_16: int = 0
    value_17: int = 0
    value_18: int = 0
    value_19: int = 0
    value_20: int = 0
    value_21: int = 0
    value_22: int = 0
    value_23: int = 0
    value_24: int = 0
    value_25: int = 0
    value_26: int = 0
    value_27: int = 0
    value_28: int = 0
    value_29: int = 0
    value_30: int = 0
    value_31: int = 0
    value_32: int = 0
    value_33: int = 0
    value_34: int = 0
    value_35: int = 0
    value_36: int = 0
    value_37: int = 0
    value_38: int = 0
    value_39: int = 0
    value_40: int = 0
    value_41: int = 0
    value_42: int = 0
    value_43: int = 0
    value_44: int = 0
    value_45: int = 0
    value_46: int = 0
    value_47: int = 0
    value_48: int = 0
    value_49: int = 0

    def _process_shipments(self, validate: bool):
        """Sort and sum dataclass rows and commit 50 independent updates.

        Args:
            validate: Also validate the actual sorted output outside the measured work.
        """
        started = time.perf_counter_ns() if CAPTURE else 0
        cpu_started = time.process_time_ns() if CAPTURE else 0
        ordered = sorted(
            self.rows, key=lambda row: (row.zone, row.units, row.identifier)
        )
        checksum = sum(row.units for row in ordered)
        for index in range(50):
            name = f"value_{index}"
            setattr(self, name, getattr(self, name) + 1)
        elapsed = time.perf_counter_ns() - started if CAPTURE else 0
        cpu_elapsed = time.process_time_ns() - cpu_started if CAPTURE else 0
        self.checksum = checksum
        self.sequence += 1
        self.work_ns = elapsed
        self.work_cpu_ns = cpu_elapsed
        if validate:
            keys = [(row.zone, row.units, row.identifier) for row in ordered]
            self.order_valid = all(left <= right for left, right in zip(keys, keys[1:]))
            self.rank_checksum = sum(
                (rank + 1) * row.identifier for rank, row in enumerate(ordered)
            )

    @rx.event
    def process_shipments(self):
        """Run the common workload without adding payload conversion overhead."""
        self._process_shipments(False)

    @rx.event
    def validate_shipments(self):
        """Check the same sorted workload in the untimed preflight."""
        self._process_shipments(True)


if SHARED:

    class UnusedShared(rx.SharedState):
        """Defined but never referenced by a page or event."""

        shared_value: int = 0
