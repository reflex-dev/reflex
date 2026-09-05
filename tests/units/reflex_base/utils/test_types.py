"""Tests for reflex_base.utils.types."""

import json
import subprocess
import sys
import typing
from collections.abc import Callable
from typing import Literal, TypeVar

import pytest
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
    from sqlalchemy.ext.hybrid import hybrid_property

    import reflex.utils.types as reflex_types

    expected_property_classes = (property, hybrid_property)
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
