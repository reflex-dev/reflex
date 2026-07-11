from collections.abc import Mapping, Sequence

import pytest
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import (
    Var,
    VarData,
    _global_vars,
    computed_var,
    figure_out_type,
    var_operation,
    var_operation_return,
)

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


def test_var_operation_does_not_register_global_vars() -> None:
    """Internal var operations bypass the f-string tag round-trip.

    Regression: each operand interpolation hashed the var and permanently
    registered it in the module-global ``_global_vars`` (a memory leak,
    worst under hot-reload), then the return expression regex-decoded the
    tag back out. Operand VarData already flows through
    ``CustomVarOperation._args``.
    """
    lhs = Var(
        _js_expr="tag_bypass_lhs",
        _var_data=VarData(imports={"op-lib": [ImportVar(tag="thing")]}),
    ).to(int)

    before = len(_global_vars)
    result = lhs + 1
    assert len(_global_vars) == before

    # The suppression flag does not persist on the operand after the op.
    assert "_format_without_tagging" not in lhs.__dict__

    # Operand VarData still reaches the merged operation VarData via _args.
    var_data = result._get_all_var_data()
    assert var_data is not None
    assert dict(var_data.imports)["op-lib"] == (ImportVar(tag="thing"),)
    assert str(result) == "(tag_bypass_lhs + 1)"

    # Formatting outside an operation still registers (and tags) as before.
    formatted = f"{lhs}"
    assert len(_global_vars) == before + 1
    assert formatted != str(lhs)


def test_var_operation_body_created_vars_keep_var_data() -> None:
    """Vars created inside an operation body still contribute their VarData.

    Only the operands bypass tagging; a var constructed inside the body is
    not carried by ``_args``, so it must keep flowing through the tagged
    return expression.
    """
    from reflex_base.vars.number import NumberVar

    @var_operation
    def op_with_derived(value: NumberVar):
        derived = Var(
            _js_expr="derivedHelper",
            _var_data=VarData(imports={"derived-lib": [ImportVar(tag="helper")]}),
        )
        return var_operation_return(f"({value} + {derived})", var_type=int)

    result = op_with_derived(Var(_js_expr="a").to(int))

    var_data = result._get_all_var_data()
    assert var_data is not None
    assert dict(var_data.imports)["derived-lib"] == (ImportVar(tag="helper"),)
    assert str(result) == "(a + derivedHelper)"


def test_computed_var_replace() -> None:
    class StateTest(State):
        @computed_var(cache=True)
        def cv(self) -> int:
            return 1

    cv = StateTest.cv
    assert cv._var_type is int

    replaced = cv._replace(_var_type=float)
    assert replaced._var_type is float
