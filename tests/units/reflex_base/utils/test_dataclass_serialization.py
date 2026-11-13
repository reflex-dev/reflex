"""Return-type contracts for the fallback dataclass serializer."""

import dataclasses

import pytest
from reflex_base.utils import serializers


@pytest.mark.parametrize("slots", [False, True])
@pytest.mark.parametrize("field_count", [0, 1, 2, 3])
def test_dataclass_serialization_with_type(slots: bool, field_count: int) -> None:
    """Dataclasses keep the same typed result shape as registered serializers.

    Args:
        slots: Whether the dataclass uses slots.
        field_count: Number of fields to include in the dataclass.
    """
    record_type = dataclasses.make_dataclass(
        "Record", [(f"field_{i}", int) for i in range(field_count)], slots=slots
    )
    value = record_type(*range(field_count))
    expected = {f"field_{i}": i for i in range(field_count)}
    assert serializers.serialize(value) == expected
    assert serializers.serialize(value, get_type=True) == (expected, dict)


def test_registered_dataclass_serializer_keeps_its_result_type() -> None:
    """An explicit serializer still takes precedence over the dataclass fallback."""

    @dataclasses.dataclass
    class CustomRecord:
        value: int

    @serializers.serializer
    def serialize_record(value: CustomRecord) -> str:
        return str(value.value)

    try:
        assert serializers.serialize(CustomRecord(7), get_type=True) == ("7", str)
    finally:
        serializers.SERIALIZERS.pop(CustomRecord)
        serializers.SERIALIZER_TYPES.pop(CustomRecord)
        serializers.get_serializer.cache_clear()
        serializers.get_serializer_type.cache_clear()
