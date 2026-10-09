"""Tests for reflex_base.utils.types."""

import importlib
import json
import subprocess
import sys
import typing
from collections.abc import Callable, Sequence
from typing import (
    Annotated,
    Any,
    Generic,
    Literal,
    NotRequired,
    Protocol,
    Required,
    TypeVar,
    runtime_checkable,
)

import pytest
import typing_extensions
from reflex_base.utils.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
    _isinstance,
    get_required_typed_dict_keys,
    get_typed_dict_field_types,
    resolve_type_alias,
    typehint_issubclass,
)
from typing_extensions import (
    ParamSpec,
    ReadOnly,
    TypeAliasType,
    TypedDict,
    TypeVarTuple,
)

P = ParamSpec("P")
Ts = TypeVarTuple("Ts")
Handlers = TypeAliasType("Handlers", tuple[Callable[P, int], *Ts], type_params=(P, Ts))


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

    That combination falls back to manual substitution on 3.11, which has to
    treat a ParamSpec as a type parameter too.
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


def test_isinstance_checks_type_parameter_bounds() -> None:
    """A type parameter, which a field never resolves, checks only its bound."""
    t = TypeVar("t")
    bounded = TypeVar("bounded", bound=str)
    constrained = TypeVar("constrained", int, str)
    forward = TypeVar("forward", bound="Unresolvable")  # noqa: F821  # pyright: ignore[reportUndefinedVariable]
    assert _isinstance(1, t, nested=1, treat_var_as_type=False)
    assert _isinstance("x", t | None, nested=1, treat_var_as_type=False)
    assert not _isinstance("x", list[t], nested=1, treat_var_as_type=False)  # pyright: ignore[reportGeneralTypeIssues]
    assert _isinstance("x", bounded, nested=1, treat_var_as_type=False)
    assert not _isinstance(1, bounded, nested=1, treat_var_as_type=False)
    assert _isinstance(1, constrained, nested=1, treat_var_as_type=False)
    assert _isinstance("x", constrained, nested=1, treat_var_as_type=False)
    assert not _isinstance(1.5, constrained, nested=1, treat_var_as_type=False)
    assert _isinstance(object(), forward, nested=1, treat_var_as_type=False)


def test_isinstance_accepts_unchecked_protocol() -> None:
    """A protocol without runtime_checkable cannot be checked, so it accepts any value."""
    t_co = TypeVar("t_co", covariant=True)

    class Reader(Protocol):
        def read(self) -> str: ...

    class Source(Protocol[t_co]):
        def get(self) -> t_co: ...

    @runtime_checkable
    class CheckedReader(Protocol):
        def read(self) -> str: ...

    bounded = TypeVar("bounded", bound=Reader)
    for annotation in (Reader, Reader | None, bounded, Source[int]):
        assert _isinstance(object(), annotation, nested=1, treat_var_as_type=False)
    assert not _isinstance(object(), CheckedReader, nested=1, treat_var_as_type=False)


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


class _OptionalBase(TypedDict, total=False):
    nickname: str
    email: Required[str]


class _SignupData(_OptionalBase):
    name: str
    message: NotRequired[str]


def test_get_required_typed_dict_keys():
    """Required keys honor NotRequired, Required and inherited totality."""
    assert get_required_typed_dict_keys(_SignupData) == {"name", "email"}


def test_get_required_typed_dict_keys_with_postponed_annotations(tmp_path, monkeypatch):
    """Qualifiers written as strings under postponed annotations still count."""
    (tmp_path / "postponed_typed_dicts.py").write_text(
        "from __future__ import annotations\n"
        "from typing import Annotated, TypedDict\n"
        "from typing_extensions import NotRequired, Required\n"
        "class Data(TypedDict):\n"
        "    name: str\n"
        "    message: NotRequired[str]\n"
        "    agree: Annotated[NotRequired[bool], 'optional consent']\n"
        "class Partial(TypedDict, total=False):\n"
        "    email: Required[str]\n"
        "    phone: Annotated[Required[str], 'contact']\n"
        "    nickname: str\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    module = importlib.import_module("postponed_typed_dicts")
    try:
        assert get_required_typed_dict_keys(module.Data) == {"name"}
        assert get_required_typed_dict_keys(module.Partial) == {"email", "phone"}
    finally:
        del sys.modules["postponed_typed_dicts"]


_FieldT = TypeVar("_FieldT")
_ItemT = TypeVar("_ItemT")


class _GenericBase(TypedDict, Generic[_FieldT]):
    value: _FieldT
    maybe: _FieldT | None


class _GenericMiddle(_GenericBase[list[_ItemT]], Generic[_ItemT]):
    flag: bool


class _Concrete(_GenericMiddle[str]):
    name: str


def test_get_typed_dict_field_types_through_generic_bases():
    """Inherited fields resolve through every specialized generic base."""
    assert get_typed_dict_field_types(_Concrete) == {
        "value": list[str],
        "maybe": list[str] | None,
        "flag": bool,
        "name": str,
    }
    assert get_typed_dict_field_types(_GenericMiddle[int])["value"] == list[int]


class _PlainSubclass(_Concrete):
    pass


def test_get_typed_dict_field_types_through_plain_subclass():
    """A subclass without type arguments keeps its bases' specialized fields."""
    assert get_typed_dict_field_types(_PlainSubclass) == get_typed_dict_field_types(
        _Concrete
    )


@pytest.mark.skipif(
    sys.version_info < (3, 11), reason="typing.TypedDict is generic from Python 3.11"
)
def test_get_typed_dict_field_types_through_stdlib_plain_subclass():
    """A plain subclass of a specialized typing.TypedDict resolves, or fails loudly.

    Python 3.11 keeps no trace of the specialized base on such a subclass.
    """

    class Base(typing.TypedDict, Generic[_FieldT]):
        value: _FieldT

    class Concrete(Base[list[str]]):
        pass

    class Plain(Concrete):
        pass

    if sys.version_info >= (3, 12):
        assert get_typed_dict_field_types(Plain) == {"value": list[str]}
    else:
        with pytest.raises(TypeError, match=r"typing_extensions\.TypedDict"):
            get_typed_dict_field_types(Plain)


class _Unresolved(TypedDict):
    value: _FieldT  # pyright: ignore[reportGeneralTypeIssues]


def test_get_typed_dict_field_types_rejects_unresolved_type_variables():
    """A field typed by a type variable its class does not declare is an error."""
    with pytest.raises(TypeError, match="_Unresolved"):
        get_typed_dict_field_types(_Unresolved)
    assert get_typed_dict_field_types(_GenericBase)["value"] is _FieldT


class _BareGenericChild(_GenericBase):
    name: str


class _BareGenericGrandchild(_BareGenericChild):
    pass


def test_get_typed_dict_field_types_through_unsubscripted_generic_base():
    """An unsubscripted generic base has Any for type parameters without defaults."""
    expected = {"value": Any, "maybe": Any | None, "name": str}
    assert get_typed_dict_field_types(_BareGenericChild) == expected
    assert get_typed_dict_field_types(_BareGenericGrandchild) == expected


_DefaultT = typing_extensions.TypeVar("_DefaultT", default=bool)


class _DefaultBase(TypedDict, Generic[_DefaultT]):
    flag: _DefaultT


class _DefaultChild(_DefaultBase):
    pass


def test_get_typed_dict_field_types_unsubscripted_base_uses_defaults():
    """An unsubscripted generic base takes its type parameters' defaults."""
    assert get_typed_dict_field_types(_DefaultChild) == {"flag": bool}


class _ReadOnlyBase(TypedDict, Generic[_FieldT]):
    value: ReadOnly[_FieldT]
    other: ReadOnly[_FieldT]


class _Narrowed(_ReadOnlyBase[Sequence[str]]):
    value: ReadOnly[list[str]]


def test_get_typed_dict_field_types_keeps_redeclared_fields():
    """A field a subclass redeclares keeps its own type over the base's."""
    assert get_typed_dict_field_types(_Narrowed) == {
        "value": list[str],
        "other": Sequence[str],
    }
