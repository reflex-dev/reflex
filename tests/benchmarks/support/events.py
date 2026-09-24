"""Representative event payloads for performance benchmarks."""

from __future__ import annotations

import dataclasses
import datetime
import decimal
import enum
import uuid
from typing import Any

from pydantic import BaseModel


class PayloadKind(str, enum.Enum):
    """Payload shapes exercised by serialization and event benchmarks."""

    SCALAR = "scalar"
    LIST = "list"
    MAPPING = "mapping"
    DATACLASS = "dataclass"
    MODEL = "model"


@dataclasses.dataclass(frozen=True)
class PayloadRow:
    """Nested dataclass payload row."""

    identifier: int
    label: str
    values: tuple[int, ...]


class PayloadModel(BaseModel):
    """Nested Pydantic payload model."""

    identifier: int
    label: str
    values: list[int]


def make_payload(kind: PayloadKind, rows: int) -> Any:
    """Build a deterministic payload with the requested shape.

    Args:
        kind: Payload representation.
        rows: Number of repeated rows or scalar characters.

    Returns:
        A representative payload.
    """
    if kind is PayloadKind.SCALAR:
        return "x" * rows
    if kind is PayloadKind.LIST:
        return list(range(rows))
    if kind is PayloadKind.MAPPING:
        return {f"key_{index}": index for index in range(rows)}
    if kind is PayloadKind.DATACLASS:
        return [
            PayloadRow(index, f"row-{index}", (index, index + 1))
            for index in range(rows)
        ]
    if kind is PayloadKind.MODEL:
        return [
            PayloadModel(
                identifier=index,
                label=f"row-{index}",
                values=[index, index + 1],
            )
            for index in range(rows)
        ]
    msg = f"Unhandled payload kind: {kind}"
    raise AssertionError(msg)


def wire_edge_cases() -> dict[str, Any]:
    """Return values that exercise the complete socket serialization contract.

    Returns:
        A mapping containing special numeric and structured values.
    """
    return {
        "unicode": "Reflex ⚡",
        "date": datetime.date(2026, 1, 2),
        "datetime": datetime.datetime(2026, 1, 2, 3, 4, 5),
        "decimal": decimal.Decimal("123.45"),
        "uuid": uuid.UUID("12345678-1234-5678-1234-567812345678"),
        "set": {1, 2, 3},
        "large_integer": 2**80,
        "dataclass": PayloadRow(1, "row", (1, 2)),
    }
