"""Tests for reflex_base.utils.types."""

import json
import subprocess
import sys
import typing
from collections.abc import Callable
from typing import Annotated, Any, Literal, TypedDict, TypeVar

import pytest
from reflex_base.utils import types
from reflex_base.utils.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
    _isinstance,
    resolve_type_alias,
    typehint_issubclass,
)
from reflex_base.vars.base import Var
from typing_extensions import ParamSpec, TypeAliasType, TypeVarTuple, Unpack

P = ParamSpec("P")
Ts = TypeVarTuple("Ts")
Handlers = TypeAliasType(
    "Handlers", tuple[Callable[P, int], Unpack[Ts]], type_params=(P, Ts)
)


def test_types_import_keeps_optional_orm_lazy():
    """Importing type helpers does not import the optional SQLAlchemy stack."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json, sys; import reflex_base.utils.types; "
                "print(json.dumps(sorted(name for name in sys.modules "
                "if name == 'sqlalchemy' or name.startswith('sqlalchemy.'))))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == []


def test_property_classes_compatibility_export():
    """The legacy property-class tuple remains available from both modules."""
    import reflex_base.utils.types as base_types

    hybrid_module = pytest.importorskip("sqlalchemy.ext.hybrid")

    import reflex.utils.types as reflex_types

    expected_property_classes = (property, hybrid_module.hybrid_property)
    assert expected_property_classes == base_types.PROPERTY_CLASSES
    assert reflex_types.PROPERTY_CLASSES == base_types.PROPERTY_CLASSES


@pytest.mark.parametrize(
    "module_name", ["reflex_base.utils.types", "reflex.utils.types"]
)
def test_property_classes_wildcard_import_compatibility(module_name: str):
    """Wildcard imports retain the legacy property-class export."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"from {module_name} import *\nprint('PROPERTY_CLASSES' in locals())",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "True"


def test_import_does_not_load_sqlalchemy() -> None:
    """Generic type helpers must not import optional database support."""
    script = """
import sys

from reflex_base.utils import types  # noqa: F401

assert "sqlalchemy" not in sys.modules, "SQLAlchemy imported eagerly"
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def _type_alias_types() -> list[type]:
    """Collect the TypeAliasType classes available on this Python.

    Returns:
        The typing_extensions class, plus the distinct native ``typing`` class
        on 3.12+ (the two produce separate alias objects there).
    """
    native = getattr(typing, "TypeAliasType", None)
    return (
        [TypeAliasType] if native in (None, TypeAliasType) else [TypeAliasType, native]
    )


def test_asgi_aliases_keep_their_names():
    """The ASGI type aliases are TypeAliasTypes so docs render them by name, not expanded."""
    for alias in (Scope, Message, Receive, Send, ASGIApp):
        assert isinstance(alias, TypeAliasType)

    assert Scope.__name__ == "Scope"
    assert Message.__name__ == "Message"
    assert Receive.__name__ == "Receive"
    assert Send.__name__ == "Send"
    assert ASGIApp.__name__ == "ASGIApp"


def test_resolve_type_alias_substitutes_param_spec():
    """A ParamSpec is substituted even next to a TypeVarTuple.

    That combination falls back to manual substitution on 3.10 and 3.11, which
    has to treat a ParamSpec as a type parameter too.
    """
    resolved = resolve_type_alias(Handlers[[str], bool, float])
    assert resolved == tuple[Callable[[str], int], bool, float]


@pytest.mark.parametrize("alias_cls", _type_alias_types())
def test_isinstance_resolves_type_alias(alias_cls: type) -> None:
    """_isinstance unwraps a TypeAliasType annotation instead of raising.

    State.__setattr__ validates assignments against the raw field annotation,
    so an alias like ``type Key = Literal["a", "b"]`` must resolve rather than
    reach the bare ``isinstance`` call, which rejects a TypeAliasType.
    """
    name = alias_cls("Name", str)
    key = alias_cls("Key", Literal["a", "b"])
    t = TypeVar("t")
    items = alias_cls("Items", list[t], type_params=(t,))  # pyright: ignore[reportGeneralTypeIssues]

    assert _isinstance("y", name, nested=1, treat_var_as_type=False)
    assert not _isinstance(1, name, nested=1, treat_var_as_type=False)
    assert _isinstance("b", key, nested=1, treat_var_as_type=False)
    assert not _isinstance("c", key, nested=1, treat_var_as_type=False)
    assert _isinstance(["z"], items[str], nested=1, treat_var_as_type=False)
    assert not _isinstance([1], items[str], nested=1, treat_var_as_type=False)
    assert _isinstance(None, key | None, nested=1, treat_var_as_type=False)
    assert _isinstance("a", key | None, nested=1, treat_var_as_type=False)
    assert not _isinstance("c", key | None, nested=1, treat_var_as_type=False)

    maybe = alias_cls("Maybe", str | None)
    assert _isinstance(None, maybe, nested=1, treat_var_as_type=False)
    assert _isinstance("x", maybe, nested=1, treat_var_as_type=False)
    assert not _isinstance(1, maybe, nested=1, treat_var_as_type=False)


@pytest.mark.parametrize("alias_cls", _type_alias_types())
def test_typehint_issubclass_resolves_type_alias(alias_cls: type) -> None:
    """typehint_issubclass resolves TypeAliasType on either side.

    Event triggers compare their provided types against handler annotations,
    so an alias-annotated handler arg must resolve instead of reaching the
    bare ``issubclass`` call or failing the origin comparison.
    """
    name = alias_cls("Name", str)
    key = alias_cls("Key", Literal["a", "b"])
    k = TypeVar("k")
    v = TypeVar("v")
    pair = alias_cls("Pair", dict[k, v], type_params=(k, v))  # pyright: ignore[reportGeneralTypeIssues]

    assert typehint_issubclass(str, name)
    assert not typehint_issubclass(int, name)
    assert typehint_issubclass(name, str)
    assert typehint_issubclass(str, key)
    assert not typehint_issubclass(int, key)
    assert typehint_issubclass(key, str)
    assert typehint_issubclass(pair[str, str], dict[str, str])
    assert typehint_issubclass(dict[str, str], pair[str, str])
    assert not typehint_issubclass(pair[str, int], dict[str, str])
    assert typehint_issubclass(str, key | None)
    assert typehint_issubclass(key | None, str | None)
    assert not typehint_issubclass(key | None, str)

    # An alias of a union must compare with union semantics on either side.
    maybe = alias_cls("Maybe", str | None)
    assert typehint_issubclass(maybe, str | None)
    assert typehint_issubclass(str | None, maybe)
    assert typehint_issubclass(maybe, maybe)
    assert not typehint_issubclass(maybe, str)
    assert typehint_issubclass(str, maybe)


@pytest.mark.parametrize("alias_cls", _type_alias_types())
def test_resolve_type_alias_unwraps_annotated(alias_cls: type) -> None:
    """``Annotated`` metadata is stripped, including around and inside aliases."""
    assert resolve_type_alias(Annotated[int, "meta"]) is int
    assert resolve_type_alias(Annotated[Annotated[int, "a"], "b"]) is int
    assert resolve_type_alias(Annotated[int | str, "meta"]) == int | str
    # An alias on either side of the annotation resolves through it.
    assert resolve_type_alias(Annotated[alias_cls("Name", str), "meta"]) is str
    assert resolve_type_alias(alias_cls("Meta", Annotated[str, "meta"])) is str
    # A union member keeps resolving.
    assert resolve_type_alias(Annotated[int, "meta"] | str) == int | str


def test_typehint_issubclass_unwraps_annotated() -> None:
    """``Annotated`` compares as the type it annotates, on either side."""
    assert typehint_issubclass(Annotated[int, "meta"], int)
    assert typehint_issubclass(int, Annotated[int, "meta"])
    assert typehint_issubclass(Annotated[int, "a"], Annotated[int, "b"])
    assert not typehint_issubclass(Annotated[str, "meta"], int)
    # The union member-wise comparison must see a union, not the metadata.
    assert typehint_issubclass(Annotated[int | str, "meta"], int | str)
    assert typehint_issubclass(int, Annotated[int | str, "meta"])
    assert not typehint_issubclass(Annotated[int | str, "meta"], int)
    assert typehint_issubclass(list[Annotated[int, "meta"]], list[int])


def test_annotated_attributes_do_not_unwrap_user_classes() -> None:
    """User-defined metadata attributes must not identify an Annotated hint."""

    class MetadataType:
        __metadata__ = ("custom",)
        __origin__ = int

    assert resolve_type_alias(MetadataType) is MetadataType


def test_isinstance_unwraps_annotated() -> None:
    """``_isinstance`` validates against the annotated type, not the metadata."""
    assert _isinstance(1, Annotated[int, "meta"], nested=1, treat_var_as_type=False)
    assert not _isinstance(
        "x", Annotated[int, "meta"], nested=1, treat_var_as_type=False
    )
    assert _isinstance(
        {"a": 1}, dict[str, Annotated[int, "meta"]], nested=2, treat_var_as_type=False
    )
    assert not _isinstance(
        {"a": "x"}, dict[str, Annotated[int, "meta"]], nested=2, treat_var_as_type=False
    )


@pytest.mark.parametrize(
    ("params", "allowed_value_str", "value_str"),
    [
        (["size", 1, Literal["1", "2", "3"], "Heading"], "'1','2','3'", "1"),
        (["size", "1", Literal[1, 2, 3], "Heading"], "1,2,3", "'1'"),
    ],
)
def test_validate_literal_error_msg(params, allowed_value_str, value_str):
    with pytest.raises(ValueError) as err:
        types.validate_literal(*params)

    assert (
        err.value.args[0] == f"prop value for {params[0]!s} of the `{params[-1]}` "
        f"component should be one of the following: {allowed_value_str}. Got {value_str} instead"
    )


@pytest.mark.parametrize(
    ("cls", "cls_check", "expected"),
    [
        (int, Any, True),
        (tuple[int], Any, True),
        (list[int], Any, True),
        (int, int, True),
        (int, object, True),
        (int, int | str, True),
        (int, str | int, True),
        (str, str | int, True),
        (str, int | str, True),
        (int, str | float | int, True),
        (int, str | float, False),
        (int, float | str, False),
        (int, str, False),
        (int, list[int], False),
    ],
)
def test_issubclass(
    cls: types.GenericType, cls_check: types.GenericType, expected: bool
) -> None:
    assert types.typehint_issubclass(cls, cls_check) == expected


class CustomDict(dict[str, str]):
    """A custom dict with generic arguments."""


class ChildCustomDict(CustomDict):
    """A child of CustomDict."""


class GenericDict(dict):
    """A generic dict with no generic arguments."""


class ChildGenericDict(GenericDict):
    """A child of GenericDict."""


@pytest.mark.parametrize(
    ("cls", "expected"),
    [
        (int, False),
        (str, False),
        (float, False),
        (tuple[int], True),
        (list[int], True),
        (int | str, True),
        (str | int, True),
        (dict[str, int], True),
        (CustomDict, True),
        (ChildCustomDict, True),
        (GenericDict, False),
        (ChildGenericDict, False),
    ],
)
def test_has_args(cls, expected: bool) -> None:
    assert types.has_args(cls) == expected


class UserInfo(TypedDict, total=False):
    """A sample typed dict."""

    sub: str
    name: str
    email: str


class UserInfoTotal(TypedDict, total=True):
    """A sample typed dict."""

    sub: str
    name: str
    email: str


@pytest.mark.parametrize(
    ("value", "cls", "expected"),
    [
        (1, int, True),
        (1, str, False),
        (1, float, True),
        ("1", str, True),
        ("1", int, False),
        (1.0, float, True),
        (1.0, int, False),
        ([], list[int], True),
        ([1], list[int], True),
        ([1.0], list[int], False),
        ([1], list[str], False),
        ({}, dict[str, str], True),
        ({"a": "b"}, dict[str, str], True),
        ({"a": 1}, dict[str, str], False),
        (False, bool, True),
        (False, Var[bool], True),
        (False, Var[bool] | None, True),
        (Var.create(False), bool, True),
        (Var.create(False), Var[bool], True),
        (Var.create(False), Var[bool] | None, True),
        (Var.create(False), Var[bool] | str, True),
        ({"sub": "123", "name": "John"}, UserInfo, True),
        ({"sub": "123"}, UserInfo, True),
        ({"sub": 123}, UserInfo, False),
        ({"sub": "123", "age": 30}, UserInfo, True),
        ({"sub": "123", "name": "John"}, UserInfoTotal, False),
        ({"sub": "123"}, UserInfoTotal, False),
        ({"sub": 123}, UserInfoTotal, False),
        ({"sub": "123", "age": 30}, UserInfoTotal, False),
    ],
)
def test_isinstance(value, cls, expected: bool) -> None:
    assert types._isinstance(value, cls, nested=2, treat_var_as_type=True) == expected
