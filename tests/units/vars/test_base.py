from collections.abc import Mapping, Sequence

import pytest
from reflex_base.vars.base import computed_var, figure_out_type

from reflex.state import State


class CustomDict(dict[str, str]):
    """A custom dict with generic arguments."""


class ChildCustomDict(CustomDict):
    """A child of CustomDict."""


class GenericDict(dict):
    """A generic dict with no generic arguments."""


class ChildGenericDict(GenericDict):
    """A child of GenericDict."""


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, int),
        (1.0, float),
        ("a", str),
        ([1, 2, 3], Sequence[int]),
        ([1, 2.0, "a"], Sequence[int | float | str]),
        ({"a": 1, "b": 2}, Mapping[str, int]),
        ({"a": 1, 2: "b"}, Mapping[int | str, str | int]),
        (CustomDict(), CustomDict),
        (ChildCustomDict(), ChildCustomDict),
        (GenericDict({1: 1}), Mapping[int, int]),
        (ChildGenericDict({1: 1}), Mapping[int, int]),
    ],
)
def test_figure_out_type(value, expected):
    assert figure_out_type(value) == expected


def test_var_subclass_registration_invalidates_lookup_caches() -> None:
    """A Var subclass registered after lookups were cached takes priority.

    ``Var.to`` / ``Var.guess_type`` dispatch through cached registry lookups;
    registering a new Var subclass must drop those caches so the new (higher
    priority) entry wins for types it claims.
    """
    from reflex_base.vars.base import Var
    from reflex_base.vars.sequence import StringVar

    class FancyTestStr(str):
        """A str subtype that later gets its own Var subclass."""

    assert isinstance(Var(_js_expr="a").to(FancyTestStr), StringVar)

    class FancyTestStrVar(Var, python_types=FancyTestStr):
        """Var subclass claiming FancyTestStr."""

    assert isinstance(Var(_js_expr="a").to(FancyTestStr), FancyTestStrVar)
    assert isinstance(
        Var(_js_expr="a", _var_type=FancyTestStr).guess_type(), FancyTestStrVar
    )


def test_computed_var_replace() -> None:
    class StateTest(State):
        @computed_var(cache=True)
        def cv(self) -> int:
            return 1

    cv = StateTest.cv
    assert cv._var_type is int

    replaced = cv._replace(_var_type=float)
    assert replaced._var_type is float


def _type_alias_types() -> list[type]:
    import typing

    from typing_extensions import TypeAliasType

    native = getattr(typing, "TypeAliasType", None)
    return (
        [TypeAliasType] if native in (None, TypeAliasType) else [TypeAliasType, native]
    )


@pytest.mark.parametrize("alias_cls", _type_alias_types())
def test_guess_type_resolves_type_alias(alias_cls: type) -> None:
    """A TypeAliasType (PEP 695 ``type`` statement) resolves to its value.

    State var annotations like ``type Key = Literal[...]`` reach guess_type as
    a TypeAliasType, which must be unwrapped instead of raising TypeError.
    """
    from typing import Literal

    from reflex_base.vars.base import Var
    from reflex_base.vars.sequence import StringVar

    alias = alias_cls("ChartKey", Literal["day", "week"])

    var = Var(_js_expr="key", _var_type=alias).guess_type()
    assert isinstance(var, StringVar)
    assert var._var_type == Literal["day", "week"]

    optional_var = Var(_js_expr="key", _var_type=alias | None).guess_type()
    assert isinstance(optional_var, StringVar)


@pytest.mark.parametrize("alias_cls", _type_alias_types())
def test_state_var_type_alias(alias_cls: type) -> None:
    """A state var annotated with a TypeAliasType compiles."""
    from typing import Literal

    from reflex_base.vars.sequence import StringVar

    chart_key = alias_cls("ChartKey", Literal["day", "week"])

    class TypeAliasState(State):
        key: chart_key = "day"  # pyright: ignore[reportInvalidTypeForm]

    assert isinstance(TypeAliasState.key, StringVar)
    assert TypeAliasState.key._var_type == Literal["day", "week"]
