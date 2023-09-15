import datetime
from typing import Any, Type

import pytest

from reflex.utils import serializers


@pytest.mark.parametrize(
    "type_,expected",
    [
        (str, True),
        (dict, True),
        (dict[int, int], True),
    ],
)
def test_has_serializer(type_: Type, expected: bool):
    """Test that has_serializer returns the correct value.


    Args:
        type_: The type to check.
        expected: The expected result.
    """
    assert serializers.has_serializer(type_) == expected


@pytest.mark.parametrize(
    "type_,expected",
    [
        (str, serializers.serialize_str),
        (dict, serializers.serialize_dict),
        (dict[int, int], serializers.serialize_dict),
        (datetime.datetime, serializers.serialize_datetime),
        (datetime.date, serializers.serialize_datetime),
        (datetime.time, serializers.serialize_datetime),
        (datetime.timedelta, serializers.serialize_datetime),
    ],
)
def test_get_serializer(type_: Type, expected: serializers.Serializer):
    """Test that get_serializer returns the correct value.


    Args:
        type_: The type to check.
        expected: The expected result.
    """
    assert serializers.get_serializer(type_) == expected


def test_add_serializer():
    """Test that adding a serializer works."""

    def serialize_test(value: int) -> str:
        """Serialize an int to a string.

        Args:
            value: The value to serialize.

        Returns:
            The serialized value.
        """
        return str(value)

    # Initially there should be no serializer for int.
    assert not serializers.has_serializer(int)
    assert serializers.serialize(5) is None

    # Register the serializer.
    serializers.serializer(serialize_test)

    # There should now be a serializer for int.
    assert serializers.has_serializer(int)
    assert serializers.get_serializer(int) == serialize_test
    assert serializers.serialize(5) == "5"

    # Remove the serializer.
    serializers.SERIALIZERS.pop(int)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("test", "test"),
        (datetime.datetime(2021, 1, 1, 1, 1, 1, 1), "2021-01-01 01:01:01.000001"),
        (datetime.date(2021, 1, 1), "2021-01-01"),
        (datetime.time(1, 1, 1, 1), "01:01:01.000001"),
        (datetime.timedelta(1, 1, 1), "1 day, 0:00:01.000001"),
        (5, None),
        (None, None),
        ([], None),
    ],
)
def test_serialize(value: Any, expected: str):
    """Test that serialize returns the correct value.


    Args:
        value: The value to serialize.
        expected: The expected result.
    """
    assert serializers.serialize(value) == expected
