import datetime
from enum import Enum
from typing import Any, Dict, List, Type

import pytest

from reflex.utils import serializers
from reflex.vars import Var


@pytest.mark.parametrize(
    "type_,expected",
    [
        (str, True),
        (dict, True),
        (Dict[int, int], True),
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
        (list, serializers.serialize_list),
        (tuple, serializers.serialize_list),
        (set, serializers.serialize_list),
        (dict, serializers.serialize_dict),
        (List[str], serializers.serialize_list),
        (Dict[int, int], serializers.serialize_dict),
        (datetime.datetime, serializers.serialize_datetime),
        (datetime.date, serializers.serialize_datetime),
        (datetime.time, serializers.serialize_datetime),
        (datetime.timedelta, serializers.serialize_datetime),
        (int, serializers.serialize_primitive),
        (float, serializers.serialize_primitive),
        (bool, serializers.serialize_primitive),
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

    class Foo:
        """A test class."""

        def __init__(self, name: str):
            self.name = name

    def serialize_foo(value: Foo) -> str:
        """Serialize an foo to a string.

        Args:
            value: The value to serialize.

        Returns:
            The serialized value.
        """
        return value.name

    # Initially there should be no serializer for int.
    assert not serializers.has_serializer(Foo)
    assert serializers.serialize(Foo("hi")) is None

    # Register the serializer.
    assert serializers.serializer(serialize_foo) == serialize_foo

    # There should now be a serializer for int.
    assert serializers.has_serializer(Foo)
    assert serializers.get_serializer(Foo) == serialize_foo
    assert serializers.serialize(Foo("hi")) == "hi"

    # Remove the serializer.
    serializers.SERIALIZERS.pop(Foo)
    assert not serializers.has_serializer(Foo)


class TestEnum(str, Enum):
    """TestEnum."""

    FOO = "foo"
    BAR = "bar"


class TestEnum2(str, Enum):
    """TestEnum2."""

    FOO = "foo"
    BAR = "bar"


@serializers.serializer
def serialize_TestEnum2(enum: TestEnum2) -> str:
    return "prefix_" + enum.value


@pytest.mark.parametrize(
    "value,expected",
    [
        ("test", "test"),
        (1, "1"),
        (1.0, "1.0"),
        (True, "true"),
        (False, "false"),
        (None, "null"),
        ([1, 2, 3], "[1, 2, 3]"),
        ([1, "2", 3.0], '[1, "2", 3.0]'),
        ([{"key": 1}, {"key": 2}], '[{"key": 1}, {"key": 2}]'),
        (TestEnum.FOO, "foo"),
        ([TestEnum.FOO, TestEnum.BAR], '["foo", "bar"]'),
        (
            {"key1": [1, 2, 3], "key2": [TestEnum.FOO, TestEnum.BAR]},
            '{"key1": [1, 2, 3], "key2": ["foo", "bar"]}',
        ),
        (TestEnum2.FOO, "prefix_foo"),
        ([TestEnum2.FOO, TestEnum2.BAR], '["prefix_foo", "prefix_bar"]'),
        (
            {"key1": TestEnum2.FOO, "key2": TestEnum2.BAR},
            '{"key1": "prefix_foo", "key2": "prefix_bar"}',
        ),
        (
            [1, Var.create_safe("hi"), Var.create_safe("bye", is_local=False)],
            '[1, "hi", bye]',
        ),
        (
            (1, Var.create_safe("hi"), Var.create_safe("bye", is_local=False)),
            '[1, "hi", bye]',
        ),
        ({1: 2, 3: 4}, '{"1": 2, "3": 4}'),
        (
            {1: Var.create_safe("hi"), 3: Var.create_safe("bye", is_local=False)},
            '{"1": "hi", "3": bye}',
        ),
        (datetime.datetime(2021, 1, 1, 1, 1, 1, 1), "2021-01-01 01:01:01.000001"),
        (datetime.date(2021, 1, 1), "2021-01-01"),
        (datetime.time(1, 1, 1, 1), "01:01:01.000001"),
        (datetime.timedelta(1, 1, 1), "1 day, 0:00:01.000001"),
    ],
)
def test_serialize(value: Any, expected: str):
    """Test that serialize returns the correct value.


    Args:
        value: The value to serialize.
        expected: The expected result.
    """
    assert serializers.serialize(value) == expected
