import datetime
import json
from enum import Enum
from pathlib import Path
from typing import Any, Type

import pytest

from reflex.base import Base
from reflex.components.core.colors import Color
from reflex.utils import serializers
from reflex.utils.format import json_dumps
from reflex.vars.base import LiteralVar


@pytest.mark.parametrize(
    "type_,expected",
    [(Enum, True)],
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
        (datetime.datetime, serializers.serialize_datetime),
        (datetime.date, serializers.serialize_datetime),
        (datetime.time, serializers.serialize_datetime),
        (datetime.timedelta, serializers.serialize_datetime),
        (Enum, serializers.serialize_enum),
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
    # LRU cache will still have the serializer, so we need to clear it.
    assert serializers.has_serializer(Foo)
    serializers.get_serializer.cache_clear()
    assert not serializers.has_serializer(Foo)


class StrEnum(str, Enum):
    """An enum also inheriting from str."""

    FOO = "foo"
    BAR = "bar"


class TestEnum(Enum):
    """A lone enum class."""

    FOO = "foo"
    BAR = "bar"


class EnumWithPrefix(Enum):
    """An enum with a serializer adding a prefix."""

    FOO = "foo"
    BAR = "bar"


@serializers.serializer
def serialize_EnumWithPrefix(enum: EnumWithPrefix) -> str:
    return "prefix_" + enum.value


class BaseSubclass(Base):
    """A class inheriting from Base for testing."""

    ts: datetime.timedelta = datetime.timedelta(1, 1, 1)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("test", "test"),
        (1, 1),
        (1.0, 1.0),
        (True, True),
        (False, False),
        (None, None),
        ([1, 2, 3], [1, 2, 3]),
        ([1, "2", 3.0], [1, "2", 3.0]),
        ([{"key": 1}, {"key": 2}], [{"key": 1}, {"key": 2}]),
        (StrEnum.FOO, "foo"),
        ([StrEnum.FOO, StrEnum.BAR], ["foo", "bar"]),
        (
            {"key1": [1, 2, 3], "key2": [StrEnum.FOO, StrEnum.BAR]},
            {
                "key1": [1, 2, 3],
                "key2": ["foo", "bar"],
            },
        ),
        (EnumWithPrefix.FOO, "prefix_foo"),
        ([EnumWithPrefix.FOO, EnumWithPrefix.BAR], ["prefix_foo", "prefix_bar"]),
        (
            {"key1": EnumWithPrefix.FOO, "key2": EnumWithPrefix.BAR},
            {
                "key1": "prefix_foo",
                "key2": "prefix_bar",
            },
        ),
        (TestEnum.FOO, "foo"),
        ([TestEnum.FOO, TestEnum.BAR], ["foo", "bar"]),
        (
            {"key1": TestEnum.FOO, "key2": TestEnum.BAR},
            {
                "key1": "foo",
                "key2": "bar",
            },
        ),
        (
            BaseSubclass(ts=datetime.timedelta(1, 1, 1)),
            {
                "ts": "1 day, 0:00:01.000001",
            },
        ),
        (
            [1, LiteralVar.create("hi")],
            [1, "hi"],
        ),
        (
            (1, LiteralVar.create("hi")),
            [1, "hi"],
        ),
        ({1: 2, 3: 4}, {1: 2, 3: 4}),
        (
            {1: LiteralVar.create("hi")},
            {1: "hi"},
        ),
        (datetime.datetime(2021, 1, 1, 1, 1, 1, 1), "2021-01-01 01:01:01.000001"),
        (datetime.date(2021, 1, 1), "2021-01-01"),
        (datetime.time(1, 1, 1, 1), "01:01:01.000001"),
        (datetime.timedelta(1, 1, 1), "1 day, 0:00:01.000001"),
        (
            [datetime.timedelta(1, 1, 1), datetime.timedelta(1, 1, 2)],
            ["1 day, 0:00:01.000001", "1 day, 0:00:01.000002"],
        ),
        (Color(color="slate", shade=1), "var(--slate-1)"),
        (Color(color="orange", shade=1, alpha=True), "var(--orange-a1)"),
        (Color(color="accent", shade=1, alpha=True), "var(--accent-a1)"),
    ],
)
def test_serialize(value: Any, expected: str):
    """Test that serialize returns the correct value.


    Args:
        value: The value to serialize.
        expected: The expected result.
    """
    assert json.loads(json_dumps(value)) == json.loads(json_dumps(expected))


@pytest.mark.parametrize(
    "value,expected,exp_var_is_string",
    [
        ("test", '"test"', False),
        (1, "1", False),
        (1.0, "1.0", False),
        (True, "true", False),
        (False, "false", False),
        ([1, 2, 3], "[1, 2, 3]", False),
        ([{"key": 1}, {"key": 2}], '[({ ["key"] : 1 }), ({ ["key"] : 2 })]', False),
        (StrEnum.FOO, '"foo"', False),
        ([StrEnum.FOO, StrEnum.BAR], '["foo", "bar"]', False),
        (
            BaseSubclass(ts=datetime.timedelta(1, 1, 1)),
            '({ ["ts"] : "1 day, 0:00:01.000001" })',
            False,
        ),
        (
            datetime.datetime(2021, 1, 1, 1, 1, 1, 1),
            '"2021-01-01 01:01:01.000001"',
            True,
        ),
        (Color(color="slate", shade=1), '"var(--slate-1)"', True),
        (BaseSubclass, '"BaseSubclass"', True),
        (Path("."), '"."', True),
    ],
)
def test_serialize_var_to_str(value: Any, expected: str, exp_var_is_string: bool):
    """Test that serialize with `to=str` passed to a Var is marked with _var_is_string.

    Args:
        value: The value to serialize.
        expected: The expected result.
        exp_var_is_string: The expected value of _var_is_string.
    """
    v = LiteralVar.create(value)
    assert str(v) == expected
