import datetime
import decimal
import json
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Any

import pytest
from reflex_base.utils.format import json_dumps
from reflex_base.vars.base import LiteralVar
from reflex_components_core.core.colors import Color

from reflex.utils import serializers

pytest.importorskip("pydantic")

from pydantic import BaseModel as Base


def test_optional_serializer_dependencies_are_lazy() -> None:
    """Importing serializers must not import heavyweight optional libraries."""
    script = """
import sys

from reflex_base.utils import serializers  # noqa: F401

optional_modules = ("pandas", "plotly", "PIL")
loaded = [name for name in optional_modules if name in sys.modules]
assert not loaded, f"optional serializer dependencies imported eagerly: {loaded}"
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_lazy_serializer_preserves_custom_registration() -> None:
    """Loading an optional output type must preserve custom serializers."""
    pytest.importorskip("pandas")
    script = """
from pandas import DataFrame
from reflex_base.utils import serializers

@serializers.serializer(overwrite=True)
def custom_dataframe(value: DataFrame):
    return "custom"

assert serializers.get_serializer(DataFrame) is custom_dataframe
assert serializers.get_serializer_type(DataFrame) is dict
serializers.get_serializer.cache_clear()
assert serializers.get_serializer(DataFrame) is custom_dataframe
assert serializers.serialize(DataFrame()) == "custom"
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_lazy_serializer_preserves_exact_type_precedence() -> None:
    """A broad fallback must not mask a built-in exact-type serializer."""
    pytest.importorskip("pandas")
    script = """
from pandas import DataFrame
from reflex_base.utils import serializers

class CustomFrame(DataFrame):
    pass

@serializers.serializer
def fallback(value: object) -> str:
    return "fallback"

assert serializers.get_serializer(DataFrame) is serializers.serialize_dataframe
assert serializers.get_serializer_type(DataFrame) is dict
assert serializers.get_serializer(CustomFrame) is fallback
assert serializers.get_serializer_type(CustomFrame) is str
serializers.get_serializer.cache_clear()
assert serializers.get_serializer(CustomFrame) is fallback
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_optional_serializer_annotations_resolve() -> None:
    """Runtime introspection must resolve optional serializer argument types."""
    pytest.importorskip("pandas")
    pytest.importorskip("plotly")
    pytest.importorskip("PIL")
    script = """
from typing import get_type_hints
from reflex_base.utils import serializers

for name in (
    "format_dataframe_values", "serialize_dataframe", "serialize_figure",
    "serialize_template", "serialize_image",
):
    hints = get_type_hints(getattr(serializers, name))
    assert all(isinstance(value, type) for key, value in hints.items() if key != "return")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("lookup", ["get_serializer", "get_serializer_type"])
def test_optional_registration_during_subclass_lookup(lookup: str) -> None:
    """Concurrent first use must not invalidate an active registry iteration.

    Args:
        lookup: The serializer lookup to exercise.
    """
    pytest.importorskip("pandas")
    script = """
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from pandas import DataFrame
from reflex_base.utils import serializers

entered = Event()
registered = Event()

class Target:
    pass

class BlockingMeta(type):
    def __subclasscheck__(cls, candidate):
        if candidate is Target:
            entered.set()
            assert registered.wait(5), "optional registration blocked"
        return False

class Sentinel(metaclass=BlockingMeta):
    pass

@serializers.serializer
def sentinel(value: Sentinel) -> str:
    return "sentinel"

with ThreadPoolExecutor(max_workers=1) as pool:
    pending = pool.submit(getattr(serializers, LOOKUP), Target)
    assert entered.wait(5), "subclass lookup did not start"
    try:
        assert serializers.get_serializer(DataFrame) is serializers.serialize_dataframe
    finally:
        registered.set()
    assert pending.result(timeout=5) is None
""".replace("LOOKUP", repr(lookup))
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("type_", "expected"),
    [(Enum, True)],
)
def test_has_serializer(type_: type, expected: bool):
    """Test that has_serializer returns the correct value.

    Args:
        type_: The type to check.
        expected: The expected result.
    """
    assert serializers.has_serializer(type_) == expected


@pytest.mark.parametrize(
    ("type_", "expected"),
    [
        (datetime.datetime, serializers.serialize_datetime),
        (datetime.date, serializers.serialize_datetime),
        (datetime.time, serializers.serialize_datetime),
        (datetime.timedelta, serializers.serialize_datetime),
        (Enum, serializers.serialize_enum),
    ],
)
def test_get_serializer(type_: type, expected: serializers.Serializer):
    """Test that get_serializer returns the correct value.

    Args:
        type_: The type to check.
        expected: The expected result.
    """
    assert serializers.get_serializer(type_) == expected


def test_add_serializer():
    """Test that adding a serializer works."""

    class Foo:  # noqa: B903
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


class FooBarEnum(Enum):
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
    ("value", "expected"),
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
        (FooBarEnum.FOO, "foo"),
        ([FooBarEnum.FOO, FooBarEnum.BAR], ["foo", "bar"]),
        (
            {"key1": FooBarEnum.FOO, "key2": FooBarEnum.BAR},
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
        (decimal.Decimal("123.456"), 123.456),
        (decimal.Decimal("-0.5"), -0.5),
        (decimal.Decimal(0), 0.0),
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
    ("value", "expected", "exp_var_is_string"),
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
        (datetime.date(2021, 1, 1), '"2021-01-01"', True),
        (Color(color="slate", shade=1), '"var(--slate-1)"', True),
        (BaseSubclass, '"BaseSubclass"', True),
        (Path(), '"."', True),
        (decimal.Decimal("123.456"), "123.456", True),
        (decimal.Decimal("-0.5"), "-0.5", True),
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
