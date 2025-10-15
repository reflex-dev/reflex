import decimal
import json
import math
import typing
from collections.abc import Mapping, Sequence
from typing import cast

import pytest
from pandas import DataFrame
from pytest_mock import MockerFixture

import reflex as rx
from reflex.base import Base
from reflex.constants.base import REFLEX_VAR_CLOSING_TAG, REFLEX_VAR_OPENING_TAG
from reflex.constants.state import FIELD_MARKER
from reflex.environment import PerformanceMode
from reflex.state import BaseState
from reflex.utils.exceptions import (
    PrimitiveUnserializableToJSONError,
    UntypedComputedVarError,
)
from reflex.utils.imports import ImportVar
from reflex.utils.types import get_default_value_for_type
from reflex.vars import VarData
from reflex.vars.base import (
    ComputedVar,
    LiteralVar,
    Var,
    computed_var,
    var_operation,
    var_operation_return,
)
from reflex.vars.function import (
    ArgsFunctionOperation,
    DestructuredArg,
    FunctionStringVar,
)
from reflex.vars.number import LiteralBooleanVar, LiteralNumberVar, NumberVar
from reflex.vars.object import LiteralObjectVar, ObjectVar
from reflex.vars.sequence import (
    ArrayVar,
    ConcatVarOperation,
    LiteralArrayVar,
    LiteralStringVar,
)

test_vars = [
    Var(_js_expr="prop1", _var_type=int),
    Var(_js_expr="key", _var_type=str),
    Var(_js_expr="value", _var_type=str)._var_set_state("state"),
    Var(_js_expr="local", _var_type=str)._var_set_state("state"),
    Var(_js_expr="local2", _var_type=str),
]


class ATestState(BaseState):
    """Test state."""

    value: str
    dict_val: dict[str, list] = {}


@pytest.fixture
def TestObj():
    class TestObj(Base):
        foo: int
        bar: str

    return TestObj


@pytest.fixture
def ParentState(TestObj):
    class ParentState(BaseState):
        foo: int
        bar: int

        @computed_var
        def var_without_annotation(self):
            return TestObj

    return ParentState


@pytest.fixture
def ChildState(ParentState, TestObj):
    class ChildState(ParentState):
        @computed_var
        def var_without_annotation(self):
            """This shadows ParentState.var_without_annotation.

            Returns:
                TestObj: Test object.
            """
            return TestObj

    return ChildState


@pytest.fixture
def GrandChildState(ChildState, TestObj):
    class GrandChildState(ChildState):
        @computed_var
        def var_without_annotation(self):
            """This shadows ChildState.var_without_annotation.

            Returns:
                TestObj: Test object.
            """
            return TestObj

    return GrandChildState


@pytest.fixture
def StateWithAnyVar(TestObj):
    class StateWithAnyVar(BaseState):
        @computed_var
        def var_without_annotation(self) -> typing.Any:
            return TestObj

    return StateWithAnyVar


@pytest.fixture
def StateWithCorrectVarAnnotation():
    class StateWithCorrectVarAnnotation(BaseState):
        @computed_var
        def var_with_annotation(self) -> str:
            return "Correct annotation"

    return StateWithCorrectVarAnnotation


@pytest.fixture
def StateWithWrongVarAnnotation(TestObj):
    class StateWithWrongVarAnnotation(BaseState):
        @computed_var
        def var_with_annotation(self) -> str:
            return TestObj

    return StateWithWrongVarAnnotation


@pytest.fixture
def StateWithInitialComputedVar():
    class StateWithInitialComputedVar(BaseState):
        @computed_var(initial_value="Initial value")
        def var_with_initial_value(self) -> str:
            return "Runtime value"

    return StateWithInitialComputedVar


@pytest.fixture
def ChildWithInitialComputedVar(StateWithInitialComputedVar):
    class ChildWithInitialComputedVar(StateWithInitialComputedVar):
        @computed_var(initial_value="Initial value")
        def var_with_initial_value_child(self) -> str:
            return "Runtime value"

    return ChildWithInitialComputedVar


@pytest.fixture
def StateWithRuntimeOnlyVar():
    class StateWithRuntimeOnlyVar(BaseState):
        @computed_var(initial_value=None)
        def var_raises_at_runtime(self) -> str:
            msg = "So nicht, mein Freund"
            raise ValueError(msg)

    return StateWithRuntimeOnlyVar


@pytest.fixture
def ChildWithRuntimeOnlyVar(StateWithRuntimeOnlyVar):
    class ChildWithRuntimeOnlyVar(StateWithRuntimeOnlyVar):
        @computed_var(initial_value="Initial value")
        def var_raises_at_runtime_child(self) -> str:
            msg = "So nicht, mein Freund"
            raise ValueError(msg)

    return ChildWithRuntimeOnlyVar


@pytest.mark.parametrize(
    ("prop", "expected"),
    zip(
        test_vars,
        [
            "prop1",
            "key",
            "state.value",
            "state.local",
            "local2",
        ],
        strict=True,
    ),
)
def test_full_name(prop, expected):
    """Test that the full name of a var is correct.

    Args:
        prop: The var to test.
        expected: The expected full name.
    """
    assert str(prop) == expected


@pytest.mark.parametrize(
    ("prop", "expected"),
    zip(
        test_vars,
        ["prop1", "key", "state.value", "state.local", "local2"],
        strict=True,
    ),
)
def test_str(prop, expected):
    """Test that the string representation of a var is correct.

    Args:
        prop: The var to test.
        expected: The expected string representation.
    """
    assert str(prop) == expected


@pytest.mark.parametrize(
    ("prop", "expected"),
    [
        (Var(_js_expr="p", _var_type=int), 0),
        (Var(_js_expr="p", _var_type=float), 0.0),
        (Var(_js_expr="p", _var_type=str), ""),
        (Var(_js_expr="p", _var_type=bool), False),
        (Var(_js_expr="p", _var_type=list), []),
        (Var(_js_expr="p", _var_type=dict), {}),
        (Var(_js_expr="p", _var_type=tuple), ()),
        (Var(_js_expr="p", _var_type=set), set()),
    ],
)
def test_default_value(prop: Var, expected):
    """Test that the default value of a var is correct.

    Args:
        prop: The var to test.
        expected: The expected default value.
    """
    assert get_default_value_for_type(prop._var_type) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, Var(_js_expr="null", _var_type=None)),
        (1, Var(_js_expr="1", _var_type=int)),
        ("key", Var(_js_expr='"key"', _var_type=str)),
        (math.pi, Var(_js_expr="3.14", _var_type=float)),
        ([1, 2, 3], Var(_js_expr="[1, 2, 3]", _var_type=Sequence[int])),
        (
            {"a": 1, "b": 2},
            Var(_js_expr='({ ["a"] : 1, ["b"] : 2 })', _var_type=Mapping[str, int]),
        ),
    ],
)
def test_create(value, expected):
    """Test the var create function.

    Args:
        value: The value to create a var from.
        expected: The expected name of the setter function.
    """
    prop = LiteralVar.create(value)
    assert prop.equals(expected)


def test_create_type_error():
    """Test the var create function when inputs type error."""

    class ErrorType:
        pass

    value = ErrorType()

    with pytest.raises(TypeError):
        LiteralVar.create(value)


def v(value) -> Var:
    return LiteralVar.create(value)


def test_basic_operations(TestObj):
    """Test the var operations.

    Args:
        TestObj: The test object.
    """
    assert str(v(1) == v(2)) == "(1?.valueOf?.() === 2?.valueOf?.())"
    assert str(v(1) != v(2)) == "(1?.valueOf?.() !== 2?.valueOf?.())"
    assert str(LiteralNumberVar.create(1) < 2) == "(1 < 2)"
    assert str(LiteralNumberVar.create(1) <= 2) == "(1 <= 2)"
    assert str(LiteralNumberVar.create(1) > 2) == "(1 > 2)"
    assert str(LiteralNumberVar.create(1) >= 2) == "(1 >= 2)"
    assert str(LiteralNumberVar.create(1) + 2) == "(1 + 2)"
    assert str(LiteralNumberVar.create(1) - 2) == "(1 - 2)"
    assert str(LiteralNumberVar.create(1) * 2) == "(1 * 2)"
    assert str(LiteralNumberVar.create(1) / 2) == "(1 / 2)"
    assert str(LiteralNumberVar.create(1) // 2) == "Math.floor(1 / 2)"
    assert str(LiteralNumberVar.create(1) % 2) == "(1 % 2)"
    assert str(LiteralNumberVar.create(1) ** 2) == "(1 ** 2)"
    assert str(LiteralNumberVar.create(1) & v(2)) == "(1 && 2)"
    assert str(LiteralNumberVar.create(1) | v(2)) == "(1 || 2)"
    assert str(LiteralArrayVar.create([1, 2, 3])[0]) == "[1, 2, 3]?.at?.(0)"
    assert (
        str(LiteralObjectVar.create({"a": 1, "b": 2})["a"])
        == '({ ["a"] : 1, ["b"] : 2 })?.["a"]'
    )
    assert str(v("foo") == v("bar")) == '("foo"?.valueOf?.() === "bar"?.valueOf?.())'
    assert (
        str(Var(_js_expr="foo") == Var(_js_expr="bar"))
        == "(foo?.valueOf?.() === bar?.valueOf?.())"
    )
    assert (
        str(LiteralVar.create("foo") == LiteralVar.create("bar"))
        == '("foo"?.valueOf?.() === "bar"?.valueOf?.())'
    )
    print(Var(_js_expr="foo").to(ObjectVar, TestObj)._var_set_state("state"))
    assert (
        str(
            Var(_js_expr="foo").to(ObjectVar, TestObj)._var_set_state("state").bar
            == LiteralVar.create("bar")
        )
        == '(state.foo?.["bar"]?.valueOf?.() === "bar"?.valueOf?.())'
    )
    assert (
        str(Var(_js_expr="foo").to(ObjectVar, TestObj)._var_set_state("state").bar)
        == 'state.foo?.["bar"]'
    )
    assert str(abs(LiteralNumberVar.create(1))) == "Math.abs(1)"
    assert str(LiteralArrayVar.create([1, 2, 3]).length()) == "[1, 2, 3].length"
    assert (
        str(LiteralArrayVar.create([1, 2]) + LiteralArrayVar.create([3, 4]))
        == "[...[1, 2], ...[3, 4]]"
    )

    # Tests for reverse operation
    assert (
        str(LiteralArrayVar.create([1, 2, 3]).reverse())
        == "[1, 2, 3].slice().reverse()"
    )
    assert (
        str(LiteralArrayVar.create(["1", "2", "3"]).reverse())
        == '["1", "2", "3"].slice().reverse()'
    )
    assert (
        str(Var(_js_expr="foo")._var_set_state("state").to(list).reverse())
        == "state.foo.slice().reverse()"
    )
    assert str(Var(_js_expr="foo").to(list).reverse()) == "foo.slice().reverse()"
    assert str(Var(_js_expr="foo", _var_type=str).js_type()) == "(typeof(foo))"


@pytest.mark.parametrize(
    ("var", "expected"),
    [
        (v([1, 2, 3]), "[1, 2, 3]"),
        (v({1, 2, 3}), "[1, 2, 3]"),
        (v(["1", "2", "3"]), '["1", "2", "3"]'),
        (
            Var(_js_expr="foo")._var_set_state("state").to(list),
            "state.foo",
        ),
        (Var(_js_expr="foo").to(list), "foo"),
        (v((1, 2, 3)), "[1, 2, 3]"),
        (v(("1", "2", "3")), '["1", "2", "3"]'),
        (
            Var(_js_expr="foo")._var_set_state("state").to(tuple),
            "state.foo",
        ),
        (Var(_js_expr="foo").to(tuple), "foo"),
    ],
)
def test_list_tuple_contains(var, expected):
    assert str(var.contains(1)) == f"{expected}.includes(1)"
    assert str(var.contains("1")) == f'{expected}.includes("1")'
    assert str(var.contains(v(1))) == f"{expected}.includes(1)"
    assert str(var.contains(v("1"))) == f'{expected}.includes("1")'
    other_state_var = Var(_js_expr="other", _var_type=str)._var_set_state("state")
    other_var = Var(_js_expr="other", _var_type=str)
    assert str(var.contains(other_state_var)) == f"{expected}.includes(state.other)"
    assert str(var.contains(other_var)) == f"{expected}.includes(other)"


class Foo(rx.Base):
    """Foo class."""

    bar: int
    baz: str


class Bar(rx.Base):
    """Bar class."""

    bar: str
    baz: str
    foo: int


@pytest.mark.parametrize(
    ("var", "var_type"),
    [
        (Var(_js_expr="").to(Foo | Bar), Foo | Bar),
        (Var(_js_expr="").to(Foo | Bar).bar, int | str),
        (Var(_js_expr="").to(Foo | Bar).baz, str),
        (
            Var(_js_expr="").to(Foo | Bar).foo,
            int | None,
        ),
    ],
)
def test_var_types(var, var_type):
    assert var._var_type == var_type


@pytest.mark.parametrize(
    ("var", "expected"),
    [
        (v("123"), json.dumps("123")),
        (Var(_js_expr="foo")._var_set_state("state").to(str), "state.foo"),
        (Var(_js_expr="foo").to(str), "foo"),
    ],
)
def test_str_contains(var, expected):
    assert str(var.contains("1")) == f'{expected}.includes("1")'
    assert str(var.contains(v("1"))) == f'{expected}.includes("1")'
    other_state_var = Var(_js_expr="other")._var_set_state("state").to(str)
    other_var = Var(_js_expr="other").to(str)
    assert str(var.contains(other_state_var)) == f"{expected}.includes(state.other)"
    assert str(var.contains(other_var)) == f"{expected}.includes(other)"
    assert (
        str(var.contains("1", "hello"))
        == f'{expected}.some(obj => obj["hello"] === "1")'
    )


@pytest.mark.parametrize(
    ("var", "expected"),
    [
        (v({"a": 1, "b": 2}), '({ ["a"] : 1, ["b"] : 2 })'),
        (Var(_js_expr="foo")._var_set_state("state").to(dict), "state.foo"),
        (Var(_js_expr="foo").to(dict), "foo"),
    ],
)
def test_dict_contains(var, expected):
    assert str(var.contains(1)) == f"{expected}.hasOwnProperty(1)"
    assert str(var.contains("1")) == f'{expected}.hasOwnProperty("1")'
    assert str(var.contains(v(1))) == f"{expected}.hasOwnProperty(1)"
    assert str(var.contains(v("1"))) == f'{expected}.hasOwnProperty("1")'
    other_state_var = Var(_js_expr="other")._var_set_state("state").to(str)
    other_var = Var(_js_expr="other").to(str)
    assert (
        str(var.contains(other_state_var)) == f"{expected}.hasOwnProperty(state.other)"
    )
    assert str(var.contains(other_var)) == f"{expected}.hasOwnProperty(other)"


@pytest.mark.parametrize(
    "var",
    [
        Var(_js_expr="list", _var_type=list[int]).guess_type(),
        Var(_js_expr="tuple", _var_type=tuple[int, int]).guess_type(),
        Var(_js_expr="str", _var_type=str).guess_type(),
    ],
)
def test_var_indexing_lists(var):
    """Test that we can index into str, list or tuple vars.

    Args:
        var : The str, list or tuple base var.
    """
    # Test basic indexing.
    assert str(var[0]) == f"{var._js_expr}?.at?.(0)"
    assert str(var[1]) == f"{var._js_expr}?.at?.(1)"

    # Test negative indexing.
    assert str(var[-1]) == f"{var._js_expr}?.at?.(-1)"


@pytest.mark.parametrize(
    ("var", "type_"),
    [
        (Var(_js_expr="list", _var_type=list[int]).guess_type(), [int, int]),
        (
            Var(_js_expr="tuple", _var_type=tuple[int, str]).guess_type(),
            [int, str],
        ),
        (Var.create((1, 2)), [int, int]),
    ],
)
def test_var_indexing_types(var, type_):
    """Test that indexing returns valid types.

    Args:
        var   : The list, tuple base var.
        type_ : The type on indexed object.

    """
    assert var[0]._var_type == type_[0]
    assert var[1]._var_type == type_[1]


def test_var_indexing_str():
    """Test that we can index into str vars."""
    str_var = Var(_js_expr="str").to(str)

    # Test that indexing gives a type of Var[str].
    assert isinstance(str_var[0], Var)
    assert str_var[0]._var_type is str

    # Test basic indexing.
    assert str(str_var[0]) == "str?.at?.(0)"
    assert str(str_var[1]) == "str?.at?.(1)"

    # Test negative indexing.
    assert str(str_var[-1]) == "str?.at?.(-1)"


@pytest.mark.parametrize(
    "var",
    [
        (Var(_js_expr="foo", _var_type=int).guess_type()),
        (Var(_js_expr="bar", _var_type=float).guess_type()),
    ],
)
def test_var_replace_with_invalid_kwargs(var):
    with pytest.raises(TypeError) as excinfo:
        var._replace(_this_should_fail=True)
    assert "unexpected keyword argument" in str(excinfo.value)


def test_computed_var_replace_with_invalid_kwargs():
    @computed_var(initial_value=1)
    def test_var(state) -> int:
        return 1

    with pytest.raises(TypeError) as excinfo:
        test_var._replace(_random_kwarg=True)
    assert "Unexpected keyword argument" in str(excinfo.value)


@pytest.mark.parametrize(
    ("var", "index"),
    [
        (Var(_js_expr="lst", _var_type=list[int]).guess_type(), [1, 2]),
        (
            Var(_js_expr="lst", _var_type=list[int]).guess_type(),
            {"name": "dict"},
        ),
        (Var(_js_expr="lst", _var_type=list[int]).guess_type(), {"set"}),
        (
            Var(_js_expr="lst", _var_type=list[int]).guess_type(),
            (
                1,
                2,
            ),
        ),
        (Var(_js_expr="lst", _var_type=list[int]).guess_type(), 1.5),
        (Var(_js_expr="lst", _var_type=list[int]).guess_type(), "str"),
        (
            Var(_js_expr="lst", _var_type=list[int]).guess_type(),
            Var(_js_expr="string_var", _var_type=str).guess_type(),
        ),
        (
            Var(_js_expr="lst", _var_type=list[int]).guess_type(),
            Var(_js_expr="float_var", _var_type=float).guess_type(),
        ),
        (
            Var(_js_expr="lst", _var_type=list[int]).guess_type(),
            Var(_js_expr="list_var", _var_type=list[int]).guess_type(),
        ),
        (
            Var(_js_expr="lst", _var_type=list[int]).guess_type(),
            Var(_js_expr="set_var", _var_type=set[str]).guess_type(),
        ),
        (
            Var(_js_expr="lst", _var_type=list[int]).guess_type(),
            Var(_js_expr="dict_var", _var_type=dict[str, str]).guess_type(),
        ),
        (Var(_js_expr="str", _var_type=str).guess_type(), [1, 2]),
        (Var(_js_expr="lst", _var_type=str).guess_type(), {"name": "dict"}),
        (Var(_js_expr="lst", _var_type=str).guess_type(), {"set"}),
        (
            Var(_js_expr="lst", _var_type=str).guess_type(),
            Var(_js_expr="string_var", _var_type=str).guess_type(),
        ),
        (
            Var(_js_expr="lst", _var_type=str).guess_type(),
            Var(_js_expr="float_var", _var_type=float).guess_type(),
        ),
        (Var(_js_expr="str", _var_type=tuple[str]).guess_type(), [1, 2]),
        (
            Var(_js_expr="lst", _var_type=tuple[str]).guess_type(),
            {"name": "dict"},
        ),
        (Var(_js_expr="lst", _var_type=tuple[str]).guess_type(), {"set"}),
        (
            Var(_js_expr="lst", _var_type=tuple[str]).guess_type(),
            Var(_js_expr="string_var", _var_type=str).guess_type(),
        ),
        (
            Var(_js_expr="lst", _var_type=tuple[str]).guess_type(),
            Var(_js_expr="float_var", _var_type=float).guess_type(),
        ),
    ],
)
def test_var_unsupported_indexing_lists(var, index):
    """Test unsupported indexing throws a type error.

    Args:
        var: The base var.
        index: The base var index.
    """
    with pytest.raises(TypeError):
        var[index]


@pytest.mark.parametrize(
    "var",
    [
        Var(_js_expr="lst", _var_type=list[int]).guess_type(),
        Var(_js_expr="tuple", _var_type=tuple[int, int]).guess_type(),
    ],
)
def test_var_list_slicing(var):
    """Test that we can slice into str, list or tuple vars.

    Args:
        var : The str, list or tuple base var.
    """
    assert str(var[:1]) == f"{var._js_expr}.slice(undefined, 1)"
    assert str(var[1:]) == f"{var._js_expr}.slice(1, undefined)"
    assert str(var[:]) == f"{var._js_expr}.slice(undefined, undefined)"


def test_str_var_slicing():
    """Test that we can slice into str vars."""
    str_var = Var(_js_expr="str").to(str)

    # Test that slicing gives a type of Var[str].
    assert isinstance(str_var[:1], Var)
    assert str_var[:1]._var_type is str

    # Test basic slicing.
    assert str(str_var[:1]) == 'str.split("").slice(undefined, 1).join("")'
    assert str(str_var[1:]) == 'str.split("").slice(1, undefined).join("")'
    assert str(str_var[:]) == 'str.split("").slice(undefined, undefined).join("")'
    assert str(str_var[1:2]) == 'str.split("").slice(1, 2).join("")'

    # Test negative slicing.
    assert str(str_var[:-1]) == 'str.split("").slice(undefined, -1).join("")'
    assert str(str_var[-1:]) == 'str.split("").slice(-1, undefined).join("")'
    assert str(str_var[:-2]) == 'str.split("").slice(undefined, -2).join("")'
    assert str(str_var[-2:]) == 'str.split("").slice(-2, undefined).join("")'


def test_dict_indexing():
    """Test that we can index into dict vars."""
    dct = Var(_js_expr="dct").to(ObjectVar, dict[str, str])

    # Check correct indexing.
    assert str(dct["a"]) == 'dct?.["a"]'
    assert str(dct["asdf"]) == 'dct?.["asdf"]'


@pytest.mark.parametrize(
    ("var", "index"),
    [
        (
            Var(_js_expr="dict", _var_type=dict[str, str]).guess_type(),
            [1, 2],
        ),
        (
            Var(_js_expr="dict", _var_type=dict[str, str]).guess_type(),
            {"name": "dict"},
        ),
        (
            Var(_js_expr="dict", _var_type=dict[str, str]).guess_type(),
            {"set"},
        ),
        (
            Var(_js_expr="dict", _var_type=dict[str, str]).guess_type(),
            (
                1,
                2,
            ),
        ),
        (
            Var(_js_expr="lst", _var_type=dict[str, str]).guess_type(),
            Var(_js_expr="list_var", _var_type=list[int]).guess_type(),
        ),
        (
            Var(_js_expr="lst", _var_type=dict[str, str]).guess_type(),
            Var(_js_expr="set_var", _var_type=set[str]).guess_type(),
        ),
        (
            Var(_js_expr="lst", _var_type=dict[str, str]).guess_type(),
            Var(_js_expr="dict_var", _var_type=dict[str, str]).guess_type(),
        ),
        (
            Var(_js_expr="df", _var_type=DataFrame).guess_type(),
            [1, 2],
        ),
        (
            Var(_js_expr="df", _var_type=DataFrame).guess_type(),
            {"name": "dict"},
        ),
        (
            Var(_js_expr="df", _var_type=DataFrame).guess_type(),
            {"set"},
        ),
        (
            Var(_js_expr="df", _var_type=DataFrame).guess_type(),
            (
                1,
                2,
            ),
        ),
        (
            Var(_js_expr="df", _var_type=DataFrame).guess_type(),
            Var(_js_expr="list_var", _var_type=list[int]).guess_type(),
        ),
        (
            Var(_js_expr="df", _var_type=DataFrame).guess_type(),
            Var(_js_expr="set_var", _var_type=set[str]).guess_type(),
        ),
        (
            Var(_js_expr="df", _var_type=DataFrame).guess_type(),
            Var(_js_expr="dict_var", _var_type=dict[str, str]).guess_type(),
        ),
    ],
)
def test_var_unsupported_indexing_dicts(var, index):
    """Test unsupported indexing throws a type error.

    Args:
        var: The base var.
        index: The base var index.
    """
    with pytest.raises(TypeError):
        var[index]


@pytest.mark.parametrize(
    "fixture",
    [
        "ParentState",
        "StateWithAnyVar",
    ],
)
def test_computed_var_without_annotation_error(request, fixture):
    """Test that a type error is thrown when an attribute of a computed var is
    accessed without annotating the computed var.

    Args:
        request: Fixture Request.
        fixture: The state fixture.
    """
    with pytest.raises(TypeError) as err:
        state = request.getfixturevalue(fixture)
        state.var_without_annotation.foo
        full_name = state.var_without_annotation._var_full_name
        assert (
            err.value.args[0]
            == f"You must provide an annotation for the state var `{full_name}`. Annotation cannot be `typing.Any`"
        )


@pytest.mark.parametrize(
    "fixture",
    [
        "ChildState",
        "GrandChildState",
    ],
)
def test_shadow_computed_var_error(request: pytest.FixtureRequest, fixture: str):
    """Test that a name error is thrown when an attribute of a computed var is
    shadowed by another attribute.

    Args:
        request: Fixture Request.
        fixture: The state fixture.
    """
    with pytest.raises(UntypedComputedVarError):
        state = request.getfixturevalue(fixture)
        state.var_without_annotation.foo


@pytest.mark.parametrize(
    "fixture",
    [
        "StateWithCorrectVarAnnotation",
        "StateWithWrongVarAnnotation",
    ],
)
def test_computed_var_with_annotation_error(request, fixture):
    """Test that an Attribute error is thrown when a non-existent attribute of an annotated computed var is
    accessed or when the wrong annotation is provided to a computed var.

    Args:
        request: Fixture Request.
        fixture: The state fixture.
    """
    with pytest.raises(AttributeError) as err:
        state = request.getfixturevalue(fixture)
        state.var_with_annotation.foo
        full_name = state.var_with_annotation._var_full_name
        assert (
            err.value.args[0]
            == f"The State var `{full_name}` has no attribute 'foo' or may have been annotated wrongly."
        )


@pytest.mark.parametrize(
    (
        "fixture",
        "var_name",
        "expected_initial",
        "expected_runtime",
        "raises_at_runtime",
    ),
    [
        (
            "StateWithInitialComputedVar",
            "var_with_initial_value" + FIELD_MARKER,
            "Initial value",
            "Runtime value",
            False,
        ),
        (
            "ChildWithInitialComputedVar",
            "var_with_initial_value_child" + FIELD_MARKER,
            "Initial value",
            "Runtime value",
            False,
        ),
        (
            "StateWithRuntimeOnlyVar",
            "var_raises_at_runtime" + FIELD_MARKER,
            None,
            None,
            True,
        ),
        (
            "ChildWithRuntimeOnlyVar",
            "var_raises_at_runtime_child" + FIELD_MARKER,
            "Initial value",
            None,
            True,
        ),
    ],
)
def test_state_with_initial_computed_var(
    request, fixture, var_name, expected_initial, expected_runtime, raises_at_runtime
):
    """Test that the initial and runtime values of a computed var are correct.

    Args:
        request: Fixture Request.
        fixture: The state fixture.
        var_name: The name of the computed var.
        expected_initial: The expected initial value of the computed var.
        expected_runtime: The expected runtime value of the computed var.
        raises_at_runtime: Whether the computed var is runtime only.
    """
    state = request.getfixturevalue(fixture)()
    state_name = state.get_full_name()
    initial_dict = state.dict(initial=True)[state_name]
    assert initial_dict[var_name] == expected_initial

    if raises_at_runtime:
        with pytest.raises(ValueError):
            state.dict()[state_name][var_name]
    else:
        runtime_dict = state.dict()[state_name]
        assert runtime_dict[var_name] == expected_runtime


def test_literal_var():
    complicated_var = LiteralVar.create([
        {"a": 1, "b": 2, "c": {"d": 3, "e": 4}},
        [1, 2, 3, 4],
        9,
        "string",
        True,
        False,
        None,
        {1, 2, 3},
    ])
    assert (
        str(complicated_var)
        == '[({ ["a"] : 1, ["b"] : 2, ["c"] : ({ ["d"] : 3, ["e"] : 4 }) }), [1, 2, 3, 4], 9, "string", true, false, null, [1, 2, 3]]'
    )


def test_function_var():
    addition_func = FunctionStringVar.create("((a, b) => a + b)")
    assert str(addition_func.call(1, 2)) == "(((a, b) => a + b)(1, 2))"

    manual_addition_func = ArgsFunctionOperation.create(
        ("a", "b"),
        {
            "args": [Var(_js_expr="a"), Var(_js_expr="b")],
            "result": Var(_js_expr="a + b"),
        },
    )
    assert (
        str(manual_addition_func.call(1, 2))
        == '(((a, b) => ({ ["args"] : [a, b], ["result"] : a + b }))(1, 2))'
    )

    increment_func = addition_func.partial(1)
    assert (
        str(increment_func.call(2))
        == "(((...args) => (((a, b) => a + b)(1, ...args)))(2))"
    )

    create_hello_statement = ArgsFunctionOperation.create(
        ("name",), f"Hello, {Var(_js_expr='name')}!"
    )
    first_name = LiteralStringVar.create("Steven")
    last_name = LiteralStringVar.create("Universe")
    assert (
        str(create_hello_statement.call(f"{first_name} {last_name}"))
        == '(((name) => ("Hello, "+name+"!"))("Steven Universe"))'
    )

    # Test with destructured arguments
    destructured_func = ArgsFunctionOperation.create(
        (DestructuredArg(fields=("a", "b")),),
        Var(_js_expr="a + b"),
    )
    assert (
        str(destructured_func.call({"a": 1, "b": 2}))
        == '((({a, b}) => a + b)(({ ["a"] : 1, ["b"] : 2 })))'
    )

    # Test with explicit return
    explicit_return_func = ArgsFunctionOperation.create(
        ("a", "b"), Var(_js_expr="return a + b"), explicit_return=True
    )
    assert str(explicit_return_func.call(1, 2)) == "(((a, b) => {return a + b})(1, 2))"


def test_var_operation():
    @var_operation
    def add(a: NumberVar | int, b: NumberVar | int):
        return var_operation_return(js_expression=f"({a} + {b})", var_type=int)

    assert str(add(1, 2)) == "(1 + 2)"
    assert str(add(a=4, b=-9)) == "(4 + -9)"

    five = LiteralNumberVar.create(5)
    seven = add(2, five)

    assert isinstance(seven, NumberVar)


def test_string_operations():
    basic_string = LiteralStringVar.create("Hello, World!")

    assert str(basic_string.length()) == '"Hello, World!".split("").length'
    assert str(basic_string.lower()) == '"Hello, World!".toLowerCase()'
    assert str(basic_string.upper()) == '"Hello, World!".toUpperCase()'
    assert str(basic_string.strip()) == '"Hello, World!".trim()'
    assert str(basic_string.contains("World")) == '"Hello, World!".includes("World")'
    assert (
        str(basic_string.split(" ").join(",")) == '"Hello, World!".split(" ").join(",")'
    )


def test_all_number_operations():
    starting_number = LiteralNumberVar.create(-5.4)

    complicated_number = (((-(starting_number + 1)) * 2 / 3) // 2 % 3) ** 2

    assert (
        str(complicated_number)
        == "((Math.floor(((-((-5.4 + 1)) * 2) / 3) / 2) % 3) ** 2)"
    )

    even_more_complicated_number = ~(
        abs(math.floor(complicated_number)) | 2 & 3 & round(complicated_number)
    )

    assert (
        str(even_more_complicated_number)
        == "!(isTrue((Math.abs(Math.floor(((Math.floor(((-((-5.4 + 1)) * 2) / 3) / 2) % 3) ** 2))) || (2 && Math.round(((Math.floor(((-((-5.4 + 1)) * 2) / 3) / 2) % 3) ** 2))))))"
    )

    assert str(LiteralNumberVar.create(5) > False) == "(5 > 0)"
    assert str(LiteralBooleanVar.create(False) < 5) == "(Number(false) < 5)"
    assert (
        str(LiteralBooleanVar.create(False) < LiteralBooleanVar.create(True))
        == "(Number(false) < Number(true))"
    )


@pytest.mark.parametrize(
    ("var", "expected"),
    [
        (Var.create(False), "false"),
        (Var.create(True), "true"),
        (Var.create("false"), 'isTrue("false")'),
        (Var.create([1, 2, 3]), "isTrue([1, 2, 3])"),
        (Var.create({"a": 1, "b": 2}), 'isTrue(({ ["a"] : 1, ["b"] : 2 }))'),
        (Var("mysterious_var"), "isTrue(mysterious_var)"),
    ],
)
def test_boolify_operations(var, expected):
    assert str(var.bool()) == expected


def test_index_operation():
    array_var = LiteralArrayVar.create([1, 2, 3, 4, 5])
    assert str(array_var[0]) == "[1, 2, 3, 4, 5]?.at?.(0)"
    assert str(array_var[1:2]) == "[1, 2, 3, 4, 5].slice(1, 2)"
    assert (
        str(array_var[1:4:2])
        == "[1, 2, 3, 4, 5].slice(1, 4).filter((_, i) => i % 2 === 0)"
    )
    assert (
        str(array_var[::-1])
        == "[1, 2, 3, 4, 5].slice(0, [1, 2, 3, 4, 5].length).slice().reverse().slice(undefined, undefined).filter((_, i) => i % 1 === 0)"
    )
    assert str(array_var.reverse()) == "[1, 2, 3, 4, 5].slice().reverse()"
    assert str(array_var[0].to(NumberVar) + 9) == "([1, 2, 3, 4, 5]?.at?.(0) + 9)"


@pytest.mark.parametrize(
    ("var", "expected_js"),
    [
        (Var.create(float("inf")), "Infinity"),
        (Var.create(-float("inf")), "-Infinity"),
        (Var.create(float("nan")), "NaN"),
    ],
)
def test_inf_and_nan(var, expected_js):
    assert str(var) == expected_js
    assert isinstance(var, NumberVar)
    assert isinstance(var, LiteralVar)
    with pytest.raises(PrimitiveUnserializableToJSONError):
        var.json()


def test_array_operations():
    array_var = LiteralArrayVar.create([1, 2, 3, 4, 5])

    assert str(array_var.length()) == "[1, 2, 3, 4, 5].length"
    assert str(array_var.contains(3)) == "[1, 2, 3, 4, 5].includes(3)"
    assert str(array_var.reverse()) == "[1, 2, 3, 4, 5].slice().reverse()"
    assert (
        str(ArrayVar.range(10))
        == "Array.from({ length: Math.ceil((10 - 0) / 1) }, (_, i) => 0 + i * 1)"
    )
    assert (
        str(ArrayVar.range(1, 10))
        == "Array.from({ length: Math.ceil((10 - 1) / 1) }, (_, i) => 1 + i * 1)"
    )
    assert (
        str(ArrayVar.range(1, 10, 2))
        == "Array.from({ length: Math.ceil((10 - 1) / 2) }, (_, i) => 1 + i * 2)"
    )
    assert (
        str(ArrayVar.range(1, 10, -1))
        == "Array.from({ length: Math.ceil((10 - 1) / -1) }, (_, i) => 1 + i * -1)"
    )


def test_object_operations():
    object_var = LiteralObjectVar.create({"a": 1, "b": 2, "c": 3})

    assert (
        str(object_var.keys())
        == 'Object.keys(({ ["a"] : 1, ["b"] : 2, ["c"] : 3 }) ?? {})'
    )
    assert (
        str(object_var.values())
        == 'Object.values(({ ["a"] : 1, ["b"] : 2, ["c"] : 3 }) ?? {})'
    )
    assert (
        str(object_var.entries())
        == 'Object.entries(({ ["a"] : 1, ["b"] : 2, ["c"] : 3 }) ?? {})'
    )
    assert str(object_var.a) == '({ ["a"] : 1, ["b"] : 2, ["c"] : 3 })?.["a"]'
    assert str(object_var["a"]) == '({ ["a"] : 1, ["b"] : 2, ["c"] : 3 })?.["a"]'
    assert (
        str(object_var.merge(LiteralObjectVar.create({"c": 4, "d": 5})))
        == '({...({ ["a"] : 1, ["b"] : 2, ["c"] : 3 }), ...({ ["c"] : 4, ["d"] : 5 })})'
    )


def test_var_component():
    class ComponentVarState(rx.State):
        field_var: rx.Field[rx.Component] = rx.field(rx.text("I am a field var"))

        @rx.var
        def computed_var(self) -> rx.Component:
            return rx.text("I am a computed var")

    def has_eval_react_component(var: Var):
        var_data = var._get_all_var_data()
        assert var_data is not None
        assert any(
            any(
                imported_object.name == "evalReactComponent"
                for imported_object in imported_objects
            )
            for _, imported_objects in var_data.imports
        )

    has_eval_react_component(ComponentVarState.field_var)
    has_eval_react_component(ComponentVarState.computed_var)


def test_type_chains():
    object_var = LiteralObjectVar.create({"a": 1, "b": 2, "c": 3})
    assert (object_var._key_type(), object_var._value_type()) == (str, int)
    assert (object_var.keys()._var_type, object_var.values()._var_type) == (
        list[str],
        list[int],
    )
    assert (
        str(object_var.keys()[0].upper())
        == 'Object.keys(({ ["a"] : 1, ["b"] : 2, ["c"] : 3 }) ?? {})?.at?.(0).toUpperCase()'
    )
    assert (
        str(object_var.entries()[1][1] - 1)
        == '(Object.entries(({ ["a"] : 1, ["b"] : 2, ["c"] : 3 }) ?? {})?.at?.(1)?.at?.(1) - 1)'
    )
    assert (
        str(object_var["c"] + object_var["b"])  # pyright: ignore [reportCallIssue, reportOperatorIssue]
        == '(({ ["a"] : 1, ["b"] : 2, ["c"] : 3 })?.["c"] + ({ ["a"] : 1, ["b"] : 2, ["c"] : 3 })?.["b"])'
    )


def test_nested_dict():
    arr = LiteralArrayVar.create([{"bar": ["foo", "bar"]}], list[dict[str, list[str]]])

    assert (
        str(arr[0]["bar"][0])
        == '[({ ["bar"] : ["foo", "bar"] })]?.at?.(0)?.["bar"]?.at?.(0)'  # pyright: ignore [reportIndexIssue]
    )


def nested_base():
    class Boo(Base):
        foo: str
        bar: int

    class Foo(Base):
        bar: Boo
        baz: int

    parent_obj = LiteralObjectVar.create(
        Foo(bar=Boo(foo="bar", bar=5), baz=5).dict(), Foo
    )

    assert (
        str(parent_obj.bar.foo)
        == '({ ["bar"] : ({ ["foo"] : "bar", ["bar"] : 5 }), ["baz"] : 5 })["bar"]["foo"]'
    )


def test_retrieval():
    var_without_data = Var(_js_expr="test")
    assert var_without_data is not None

    original_var_data = VarData(
        state="Test",
        imports={"react": [ImportVar(tag="useRef")]},
        hooks={"const state = useContext(StateContexts.state)": None},
    )

    var_with_data = var_without_data._replace(merge_var_data=original_var_data)

    f_string = f"foo{var_with_data}bar"

    assert REFLEX_VAR_OPENING_TAG in f_string
    assert REFLEX_VAR_CLOSING_TAG in f_string

    result_var_data = LiteralVar.create(f_string)._get_all_var_data()
    result_immutable_var_data = Var(_js_expr=f_string)._var_data
    assert result_var_data is not None
    assert result_immutable_var_data is not None
    assert (
        result_var_data.state
        == result_immutable_var_data.state
        == original_var_data.state
    )
    assert (
        result_var_data.imports
        == result_immutable_var_data.imports
        == original_var_data.imports
    )
    assert (
        tuple(result_var_data.hooks)
        == tuple(result_immutable_var_data.hooks)
        == tuple(original_var_data.hooks)
    )


def test_fstring_concat():
    original_var_with_data = LiteralVar.create(
        "imagination", _var_data=VarData(state="fear")
    )

    immutable_var_with_data = Var(
        _js_expr="consequences",
        _var_data=VarData(
            imports={
                "react": [ImportVar(tag="useRef")],
                "utils": [ImportVar(tag="useEffect")],
            }
        ),
    )

    f_string = f"foo{original_var_with_data}bar{immutable_var_with_data}baz"

    string_concat = LiteralStringVar.create(
        f_string,
        _var_data=VarData(
            hooks={"const state = useContext(StateContexts.state)": None}
        ),
    )

    assert str(string_concat) == '("fooimaginationbar"+consequences+"baz")'
    assert isinstance(string_concat, ConcatVarOperation)
    assert string_concat._get_all_var_data() == VarData(
        state="fear",
        imports={
            "react": [ImportVar(tag="useRef")],
            "utils": [ImportVar(tag="useEffect")],
        },
        hooks={"const state = useContext(StateContexts.state)": None},
    )


var = Var(_js_expr="var", _var_type=str)
myvar = Var(_js_expr="myvar", _var_type=int)._var_set_state("state")
x = Var(_js_expr="x", _var_type=str)


@pytest.mark.parametrize(
    ("out", "expected"),
    [
        (f"{var}", f"<reflex.Var>{hash(var)}</reflex.Var>var"),
        (
            f"testing f-string with {myvar}",
            f"testing f-string with <reflex.Var>{hash(myvar)}</reflex.Var>state.myvar",
        ),
        (
            f"testing local f-string {x}",
            f"testing local f-string <reflex.Var>{hash(x)}</reflex.Var>x",
        ),
    ],
)
def test_fstrings(out, expected):
    assert out == expected


@pytest.mark.parametrize(
    ("value", "expect_state"),
    [
        ([1], ""),
        ({"a": 1}, ""),
        ([LiteralVar.create(1)._var_set_state("foo")], "foo"),
        ({"a": LiteralVar.create(1)._var_set_state("foo")}, "foo"),
    ],
)
def test_extract_state_from_container(value, expect_state):
    """Test that _var_state is extracted from containers containing BaseVar.

    Args:
        value: The value to create a var from.
        expect_state: The expected state.
    """
    var_data = LiteralVar.create(value)._get_all_var_data()
    var_state = var_data.state if var_data else ""
    assert var_state == expect_state


@pytest.mark.parametrize(
    "value",
    [
        "var",
        "\nvar",
    ],
)
def test_fstring_roundtrip(value):
    """Test that f-string roundtrip carries state.

    Args:
        value: The value to create a Var from.
    """
    var = Var(_js_expr=value)._var_set_state("state")
    rt_var = LiteralVar.create(f"{var}")
    assert var._var_state == rt_var._var_state
    assert str(rt_var) == str(var)


@pytest.mark.parametrize(
    "var",
    [
        Var(_js_expr="var", _var_type=int).guess_type(),
        Var(_js_expr="var", _var_type=float).guess_type(),
        Var(_js_expr="var", _var_type=str).guess_type(),
        Var(_js_expr="var", _var_type=bool).guess_type(),
        Var(_js_expr="var", _var_type=None).guess_type(),
    ],
)
def test_unsupported_types_for_reverse(var):
    """Test that unsupported types for reverse throw a type error.

    Args:
        var: The base var.
    """
    with pytest.raises(TypeError) as err:
        var.reverse()
    assert err.value.args[0] == "Cannot reverse non-list var."


@pytest.mark.parametrize(
    "var",
    [
        Var(_js_expr="var", _var_type=int).guess_type(),
        Var(_js_expr="var", _var_type=float).guess_type(),
        Var(_js_expr="var", _var_type=bool).guess_type(),
        Var(_js_expr="var", _var_type=type(None)).guess_type(),
    ],
)
def test_unsupported_types_for_contains(var: Var):
    """Test that unsupported types for contains throw a type error.

    Args:
        var: The base var.
    """
    with pytest.raises(TypeError) as err:
        assert var.contains(1)  # pyright: ignore [reportAttributeAccessIssue]
    assert (
        err.value.args[0]
        == f"Var of type {var._var_type} does not support contains check."
    )


@pytest.mark.parametrize(
    "other",
    [
        Var(_js_expr="other", _var_type=int).guess_type(),
        Var(_js_expr="other", _var_type=float).guess_type(),
        Var(_js_expr="other", _var_type=bool).guess_type(),
        Var(_js_expr="other", _var_type=list).guess_type(),
        Var(_js_expr="other", _var_type=dict).guess_type(),
        Var(_js_expr="other", _var_type=tuple).guess_type(),
        Var(_js_expr="other", _var_type=set).guess_type(),
    ],
)
def test_unsupported_types_for_string_contains(other):
    with pytest.raises(TypeError) as err:
        assert Var(_js_expr="var").to(str).contains(other)
    assert (
        err.value.args[0]
        == f"Unsupported Operand type(s) for contains: StringCastedVar, {type(other).__name__}"
    )


def test_unsupported_default_contains():
    with pytest.raises(TypeError) as err:
        assert 1 in Var(_js_expr="var", _var_type=str).guess_type()  # pyright: ignore [reportOperatorIssue]
    assert (
        err.value.args[0]
        == "'in' operator not supported for Var types, use Var.contains() instead."
    )


@pytest.mark.parametrize(
    ("operand1_var", "operand2_var", "operators"),
    [
        (
            LiteralVar.create(10),
            LiteralVar.create(5),
            [
                "+",
                "-",
                "/",
                "//",
                "*",
                "%",
                "**",
                ">",
                "<",
                "<=",
                ">=",
                "|",
                "&",
            ],
        ),
        (
            LiteralVar.create(10.5),
            LiteralVar.create(5),
            ["+", "-", "/", "//", "*", "%", "**", ">", "<", "<=", ">="],
        ),
        (
            LiteralVar.create(5),
            LiteralVar.create(True),
            [
                "+",
                "-",
                "/",
                "//",
                "*",
                "%",
                "**",
                ">",
                "<",
                "<=",
                ">=",
                "|",
                "&",
            ],
        ),
        (
            LiteralVar.create(10.5),
            LiteralVar.create(5.5),
            ["+", "-", "/", "//", "*", "%", "**", ">", "<", "<=", ">="],
        ),
        (
            LiteralVar.create(10.5),
            LiteralVar.create(True),
            ["+", "-", "/", "//", "*", "%", "**", ">", "<", "<=", ">="],
        ),
        (LiteralVar.create("10"), LiteralVar.create("5"), ["+", ">", "<", "<=", ">="]),
        (
            LiteralVar.create([10, 20]),
            LiteralVar.create([5, 6]),
            ["+", ">", "<", "<=", ">="],
        ),
        (LiteralVar.create([10, 20]), LiteralVar.create(5), ["*"]),
        (LiteralVar.create([10, 20]), LiteralVar.create(True), ["*"]),
        (
            LiteralVar.create(True),
            LiteralVar.create(True),
            [
                "+",
                "-",
                "/",
                "//",
                "*",
                "%",
                "**",
                ">",
                "<",
                "<=",
                ">=",
                "|",
                "&",
            ],
        ),
    ],
)
def test_valid_var_operations(operand1_var: Var, operand2_var, operators: list[str]):
    """Test that operations do not raise a TypeError.

    Args:
        operand1_var: left operand.
        operand2_var: right operand.
        operators: list of supported operators.
    """
    for operator in operators:
        print(
            "testing",
            operator,
            "on",
            operand1_var,
            operand2_var,
            " of types",
            type(operand1_var),
            type(operand2_var),
        )
        eval(f"operand1_var {operator} operand2_var")
        eval(f"operand2_var {operator} operand1_var")


@pytest.mark.parametrize(
    ("operand1_var", "operand2_var", "operators"),
    [
        (
            LiteralVar.create(10),
            LiteralVar.create(5),
            [
                "^",
                "<<",
                ">>",
            ],
        ),
        (
            LiteralVar.create(10.5),
            LiteralVar.create(5),
            [
                "^",
                "<<",
                ">>",
            ],
        ),
        (
            LiteralVar.create(10.5),
            LiteralVar.create(True),
            [
                "^",
                "<<",
                ">>",
            ],
        ),
        (
            LiteralVar.create(10.5),
            LiteralVar.create(5.5),
            [
                "^",
                "<<",
                ">>",
            ],
        ),
        (
            LiteralVar.create("10"),
            LiteralVar.create("5"),
            [
                "-",
                "/",
                "//",
                "*",
                "%",
                "**",
                "^",
                "<<",
                ">>",
            ],
        ),
        (
            LiteralVar.create([10, 20]),
            LiteralVar.create([5, 6]),
            [
                "-",
                "/",
                "//",
                "*",
                "%",
                "**",
                "^",
                "<<",
                ">>",
            ],
        ),
        (
            LiteralVar.create([10, 20]),
            LiteralVar.create(5),
            [
                "+",
                "-",
                "/",
                "//",
                "%",
                "**",
                ">",
                "<",
                "<=",
                ">=",
                "^",
                "<<",
                ">>",
            ],
        ),
        (
            LiteralVar.create([10, 20]),
            LiteralVar.create(True),
            [
                "+",
                "-",
                "/",
                "//",
                "%",
                "**",
                ">",
                "<",
                "<=",
                ">=",
                "^",
                "<<",
                ">>",
            ],
        ),
        (
            LiteralVar.create([10, 20]),
            LiteralVar.create("5"),
            [
                "+",
                "-",
                "/",
                "//",
                "*",
                "%",
                "**",
                ">",
                "<",
                "<=",
                ">=",
                "^",
                "<<",
                ">>",
            ],
        ),
        (
            LiteralVar.create([10, 20]),
            LiteralVar.create({"key": "value"}),
            [
                "+",
                "-",
                "/",
                "//",
                "*",
                "%",
                "**",
                ">",
                "<",
                "<=",
                ">=",
                "^",
                "<<",
                ">>",
            ],
        ),
        (
            LiteralVar.create([10, 20]),
            LiteralVar.create(5.5),
            [
                "+",
                "-",
                "/",
                "//",
                "*",
                "%",
                "**",
                ">",
                "<",
                "<=",
                ">=",
                "^",
                "<<",
                ">>",
            ],
        ),
        (
            LiteralVar.create({"key": "value"}),
            LiteralVar.create({"another_key": "another_value"}),
            [
                "+",
                "-",
                "/",
                "//",
                "*",
                "%",
                "**",
                ">",
                "<",
                "<=",
                ">=",
                "^",
                "<<",
                ">>",
            ],
        ),
        (
            LiteralVar.create({"key": "value"}),
            LiteralVar.create(5),
            [
                "+",
                "-",
                "/",
                "//",
                "*",
                "%",
                "**",
                ">",
                "<",
                "<=",
                ">=",
                "^",
                "<<",
                ">>",
            ],
        ),
        (
            LiteralVar.create({"key": "value"}),
            LiteralVar.create(True),
            [
                "+",
                "-",
                "/",
                "//",
                "*",
                "%",
                "**",
                ">",
                "<",
                "<=",
                ">=",
                "^",
                "<<",
                ">>",
            ],
        ),
        (
            LiteralVar.create({"key": "value"}),
            LiteralVar.create(5.5),
            [
                "+",
                "-",
                "/",
                "//",
                "*",
                "%",
                "**",
                ">",
                "<",
                "<=",
                ">=",
                "^",
                "<<",
                ">>",
            ],
        ),
        (
            LiteralVar.create({"key": "value"}),
            LiteralVar.create("5"),
            [
                "+",
                "-",
                "/",
                "//",
                "*",
                "%",
                "**",
                ">",
                "<",
                "<=",
                ">=",
                "^",
                "<<",
                ">>",
            ],
        ),
    ],
)
def test_invalid_var_operations(operand1_var: Var, operand2_var, operators: list[str]):
    for operator in operators:
        print(f"testing {operator} on {operand1_var!s} and {operand2_var!s}")
        with pytest.raises(TypeError):
            print(eval(f"operand1_var {operator} operand2_var"))

        with pytest.raises(TypeError):
            print(eval(f"operand2_var {operator} operand1_var"))


@pytest.mark.parametrize(
    ("var", "expected"),
    [
        (LiteralVar.create("string_value"), '"string_value"'),
        (LiteralVar.create(1), "1"),
        (LiteralVar.create([1, 2, 3]), "[1, 2, 3]"),
        (LiteralVar.create({"foo": "bar"}), '({ ["foo"] : "bar" })'),
        (
            LiteralVar.create(ATestState.value),
            f"{ATestState.get_full_name()}.value" + FIELD_MARKER,
        ),
        (
            LiteralVar.create(f"{ATestState.value} string"),
            f'({ATestState.get_full_name()}.value{FIELD_MARKER}+" string")',
        ),
        (
            LiteralVar.create(ATestState.dict_val),
            f"{ATestState.get_full_name()}.dict_val" + FIELD_MARKER,
        ),
    ],
)
def test_var_name_unwrapped(var, expected):
    assert str(var) == expected


def cv_fget(state: BaseState) -> int:
    return 1


@pytest.mark.parametrize(
    ("deps", "expected"),
    [
        (["a"], {None: {"a"}}),
        (["b"], {None: {"b"}}),
        ([ComputedVar(fget=cv_fget)], {None: {"cv_fget"}}),
    ],
)
def test_computed_var_deps(deps: list[str | Var], expected: set[str]):
    @computed_var(deps=deps)
    def test_var(state) -> int:
        return 1

    assert test_var._static_deps == expected


@pytest.mark.parametrize(
    "deps",
    [
        [""],
        [1],
        ["", "abc"],
    ],
)
def test_invalid_computed_var_deps(deps: list):
    with pytest.raises(TypeError):

        @computed_var(deps=deps)
        def test_var(state) -> int:
            return 1


def test_to_string_operation():
    class Email(str): ...

    class TestState(BaseState):
        optional_email: Email | None = None
        email: Email = Email("test@reflex.dev")

    assert (
        str(TestState.optional_email)
        == f"{TestState.get_full_name()}.optional_email" + FIELD_MARKER
    )
    my_state = TestState()
    assert my_state.optional_email is None
    assert my_state.email == "test@reflex.dev"

    assert cast(Var, TestState.email)._var_type == Email
    assert cast(Var, TestState.optional_email)._var_type == Email | None

    single_var = Var.create(Email())
    assert single_var._var_type == Email


@pytest.mark.asyncio
async def test_async_computed_var():
    side_effect_counter = 0

    class AsyncComputedVarState(BaseState):
        v: int = 1

        @computed_var(cache=True)
        async def async_computed_var(self) -> int:
            nonlocal side_effect_counter
            side_effect_counter += 1
            return self.v + 1

    my_state = AsyncComputedVarState()
    assert await my_state.async_computed_var == 2
    assert await my_state.async_computed_var == 2
    my_state.v = 2
    assert await my_state.async_computed_var == 3
    assert await my_state.async_computed_var == 3
    assert side_effect_counter == 2


def test_var_data_hooks():
    var_data_str = VarData(hooks="what")
    var_data_list = VarData(hooks=["what"])
    var_data_dict = VarData(hooks={"what": None})
    assert var_data_str == var_data_list == var_data_dict

    var_data_list_multiple = VarData(hooks=["what", "whot"])
    var_data_dict_multiple = VarData(hooks={"what": None, "whot": None})
    assert var_data_list_multiple == var_data_dict_multiple


def test_var_data_with_hooks_value():
    var_data = VarData(hooks={"what": VarData(hooks={"whot": VarData(hooks="whott")})})
    assert var_data == VarData(hooks=["whott", "whot", "what"])


def test_str_var_in_components(mocker: MockerFixture):
    class StateWithVar(rx.State):
        field: int = 1

    mocker.patch(
        "reflex.components.base.bare.get_performance_mode",
        return_value=PerformanceMode.RAISE,
    )

    with pytest.raises(ValueError):
        rx.vstack(
            str(StateWithVar.field),
        )

    mocker.patch(
        "reflex.components.base.bare.get_performance_mode",
        return_value=PerformanceMode.OFF,
    )

    rx.vstack(
        str(StateWithVar.field),
    )


def test_decimal_number_operations():
    """Test that decimal.Decimal values work with NumberVar operations."""
    dec_num = Var.create(decimal.Decimal("123.456"))
    assert isinstance(dec_num._var_value, decimal.Decimal)
    assert str(dec_num) == "123.456"

    result = dec_num + 10
    assert str(result) == "(123.456 + 10)"

    result = dec_num * 2
    assert str(result) == "(123.456 * 2)"

    result = dec_num / 2
    assert str(result) == "(123.456 / 2)"

    result = dec_num > 100
    assert str(result) == "(123.456 > 100)"

    result = dec_num < 200
    assert str(result) == "(123.456 < 200)"

    assert dec_num.json() == "123.456"


def test_decimal_var_type_compatibility():
    """Test that decimal.Decimal values are compatible with NumberVar type system."""
    dec_num = Var.create(decimal.Decimal("123.456"))
    int_num = Var.create(42)
    float_num = Var.create(math.pi)

    result = dec_num + int_num
    assert str(result) == "(123.456 + 42)"

    result = dec_num * float_num
    assert str(result) == "(123.456 * 3.14)"

    result = (dec_num + int_num) / float_num
    assert str(result) == "((123.456 + 42) / 3.14)"


def test_computed_var_type_compatibility():
    """Test that different ComputedVar are compatible with Var annotations of their returned type."""

    class ComputedVarTypeState(BaseState):
        @computed_var
        def sync_plain(self) -> str:
            return "Hello"

        @computed_var(initial_value="Test")
        def sync_wrapper(self) -> str:
            return "World"

        @computed_var
        async def async_plain(self) -> str:
            return "Hello"

        @computed_var(initial_value="Test")
        async def async_wrapper(self) -> str:
            return "World"

    # All of these vars should be assignable to a str field statically.
    rx.input(placeholder=ComputedVarTypeState.sync_plain)
    rx.input(placeholder=ComputedVarTypeState.sync_wrapper)
    rx.input(placeholder=ComputedVarTypeState.async_plain)
    rx.input(placeholder=ComputedVarTypeState.async_wrapper)
