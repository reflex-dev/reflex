"""Strict serialization for durable run data.

Run state and event payloads must round-trip through JSON. The regular Reflex
serializer silently encodes unknown objects as ``null``, which would corrupt a
durable snapshot (e.g. a connector client or socket stored on run state), so
the workflow runtime uses this strict variant that raises instead.
"""

from __future__ import annotations

import json
from typing import Any

from reflex_base.utils import serializers


def _strict_default(value: Any) -> Any:
    """Serialize a non-JSON-native value or raise.

    Args:
        value: The value encountered by the JSON encoder.

    Returns:
        The serialized representation from the Reflex serializer registry.

    Raises:
        TypeError: If no serializer is registered for the value's type.
    """
    serialized = serializers.serialize(value)
    if serialized is None:
        msg = (
            f"{type(value).__name__} is not valid run data; durable values must "
            "be serializable through the Reflex/pydantic serializer layer."
        )
        raise TypeError(msg)
    return serialized


def to_run_data(value: Any) -> Any:
    """Normalize a value to JSON-compatible run data.

    Args:
        value: The value to normalize.

    Returns:
        The JSON-compatible representation.

    Raises:
        TypeError: If the value contains something no serializer handles.
        ValueError: If the value cannot be encoded -- a circular reference, or
            a float that JSON has no representation for (NaN, infinity).
    """
    # allow_nan=False is the whole point: NaN and Infinity are not JSON, and
    # Python emitting them anyway is how a workflow that works on SQLite and
    # in memory fails at commit against Postgres, whose JSONB refuses them.
    # Failing here names the value; failing there names a column.
    return json.loads(
        json.dumps(value, ensure_ascii=False, allow_nan=False, default=_strict_default)
    )
