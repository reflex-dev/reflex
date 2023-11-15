import json
import typing
from typing import Dict, List, Set, Tuple

import pytest
from pandas import DataFrame

from nextpy.core.base import Base
from nextpy.core.state import State
from nextpy.core.vars import (
    BaseVar,
    ComputedVar,
    ImportVar,
    Var,
)

test_vars = [
    BaseVar(_var_name="prop1", _var_type=int),
    BaseVar(_var_name="key", _var_type=str),
    BaseVar(_var_name="value", _var_type=str, _var_state="state"),
    BaseVar(_var_name="local", _var_type=str, _var_state="state", _var_is_local=True),
    BaseVar(_var_name="local2", _var_type=str, _var_is_local=True),
]

test_import_vars = [ImportVar(tag="DataGrid"), ImportVar(tag="DataGrid", alias="Grid")]


class BaseState(State):
    """A Test State."""

    val: str = "key"


@pytest.fixture
def TestObj():
    class TestObj(Base):
        foo: int
        bar: str

    return TestObj


@pytest.fixture
def ParentState(TestObj):
    class ParentState(State):
        foo: int
        bar: int

        @ComputedVar
        def var_without_annotation(self):
            return TestObj

    return ParentState


@pytest.fixture
def ChildState(ParentState, TestObj):
    class ChildState(ParentState):
        @ComputedVar
        def var_without_annotation(self):
            return TestObj

    return ChildState


@pytest.fixture
def GrandChildState(ChildState, TestObj):
    class GrandChildState(ChildState):
        @ComputedVar
        def var_without_annotation(self):
            return TestObj

    return GrandChildState


@pytest.fixture
def StateWithAnyVar(TestObj):
    class StateWithAnyVar(State):
        @ComputedVar
        def var_without_annotation(self) -> typing.Any:
            return TestObj

    return StateWithAnyVar


@pytest.fixture
def StateWithCorrectVarAnnotation():
    class StateWithCorrectVarAnnotation(State):
        @ComputedVar
        def var_with_annotation(self) -> str:
            return "Correct annotation"

    return StateWithCorrectVarAnnotation


@pytest.fixture
def StateWithWrongVarAnnotation(TestObj):
    class StateWithWrongVarAnnotation(State):
        @ComputedVar
        def var_with_annotation(self) -> str:
            return TestObj

    return StateWithWrongVarAnnotation


@pytest.mark.parametrize(
    "prop,expected",
    zip(
        test_vars,
        [
            "prop1",
            "key",
            "state.value",
            "state.local",
            "local2",
        ],
    ),
)
def test_full_name(prop, expected):
    """Test that the full name of a var is correct.

    Args:
        prop: The var to test.
        expected: The expected full name.
    """
    assert prop._var_full_name == expected


@pytest.mark.parametrize(
    "prop,expected",
    zip(
        test_vars,
        ["{prop1}", "{key}", "{state.value}", "state.local", "local2"],
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
    "prop,expected",
    [
        (BaseVar(_var_name="p", _var_type=int), 0),
        (BaseVar(_var_name="p", _var_type=float), 0.0),
        (BaseVar(_var_name="p", _var_type=str), ""),
        (BaseVar(_var_name="p", _var_type=bool), False),
        (BaseVar(_var_name="p", _var_type=list), []),
        (BaseVar(_var_name="p", _var_type=dict), {}),
        (BaseVar(_var_name="p", _var_type=tuple), ()),
        (BaseVar(_var_name="p", _var_type=set), set()),
    ],
)
def test_default_value(prop, expected):
    """Test that the default value of a var is correct.

    Args:
        prop: The var to test.
        expected: The expected default value.
    """
    assert prop.get_default_value() == expected


@pytest.mark.parametrize(
    "prop,expected",
    zip(
        test_vars,
        [
            "set_prop1",
            "set_key",
            "state.set_value",
            "state.set_local",
            "set_local2",
        ],
    ),
)
def test_get_setter(prop, expected):
    """Test that the name of the setter function of a var is correct.

    Args:
        prop: The var to test.
        expected: The expected name of the setter function.
    """
    assert prop.get_setter_name() == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        (1, BaseVar(_var_name="1", _var_type=int, _var_is_local=True)),
        ("key", BaseVar(_var_name="key", _var_type=str, _var_is_local=True)),
        (3.14, BaseVar(_var_name="3.14", _var_type=float, _var_is_local=True)),
        ([1, 2, 3], BaseVar(_var_name="[1, 2, 3]", _var_type=list, _var_is_local=True)),
        (
            {"a": 1, "b": 2},
            BaseVar(_var_name='{"a": 1, "b": 2}', _var_type=dict, _var_is_local=True),
        ),
    ],
)
def test_create(value, expected):
    """Test the var create function.

    Args:
        value: The value to create a var from.
        expected: The expected name of the setter function.
    """
    prop = Var.create(value)
    if value is None:
        assert prop == expected
    else:
        assert prop.equals(expected)  # type: ignore


def test_create_type_error():
    """Test the var create function when inputs type error."""

    class ErrorType:
        pass

    value = ErrorType()

    with pytest.raises(TypeError):
        Var.create(value)


def v(value) -> Var:
    val = (
        Var.create(json.dumps(value), _var_is_string=True, _var_is_local=False)
        if isinstance(value, str)
        else Var.create(value, _var_is_local=False)
    )
    assert val is not None
    return val


def test_basic_operations(TestObj):
    """Test the var operations.

    Args:
        TestObj: The test object.
    """
    assert str(v(1) == v(2)) == "{(1 === 2)}"
    assert str(v(1) != v(2)) == "{(1 !== 2)}"
    assert str(v(1) < v(2)) == "{(1 < 2)}"
    assert str(v(1) <= v(2)) == "{(1 <= 2)}"
    assert str(v(1) > v(2)) == "{(1 > 2)}"
    assert str(v(1) >= v(2)) == "{(1 >= 2)}"
    assert str(v(1) + v(2)) == "{(1 + 2)}"
    assert str(v(1) - v(2)) == "{(1 - 2)}"
    assert str(v(1) * v(2)) == "{(1 * 2)}"
    assert str(v(1) / v(2)) == "{(1 / 2)}"
    assert str(v(1) // v(2)) == "{Math.floor(1 / 2)}"
    assert str(v(1) % v(2)) == "{(1 % 2)}"
    assert str(v(1) ** v(2)) == "{Math.pow(1 , 2)}"
    assert str(v(1) & v(2)) == "{(1 && 2)}"
    assert str(v(1) | v(2)) == "{(1 || 2)}"
    assert str(v([1, 2, 3])[v(0)]) == "{[1, 2, 3].at(0)}"
    assert str(v({"a": 1, "b": 2})["a"]) == '{{"a": 1, "b": 2}["a"]}'
    assert (
        str(BaseVar(_var_name="foo", _var_state="state", _var_type=TestObj).bar)
        == "{state.foo.bar}"
    )
    assert str(abs(v(1))) == "{Math.abs(1)}"
    assert str(v([1, 2, 3]).length()) == "{[1, 2, 3].length}"
    assert str(v([1, 2]) + v([3, 4])) == "{spreadArraysOrObjects([1, 2] , [3, 4])}"

    # Tests for reverse operation
    assert str(v([1, 2, 3]).reverse()) == "{[...[1, 2, 3]].reverse()}"
    assert str(v(["1", "2", "3"]).reverse()) == '{[...["1", "2", "3"]].reverse()}'
    assert (
        str(BaseVar(_var_name="foo", _var_state="state", _var_type=list).reverse())
        == "{[...state.foo].reverse()}"
    )
    assert (
        str(BaseVar(_var_name="foo", _var_type=list).reverse())
        == "{[...foo].reverse()}"
    )


@pytest.mark.parametrize(
    "var, expected",
    [
        (v([1, 2, 3]), "[1, 2, 3]"),
        (v(["1", "2", "3"]), '["1", "2", "3"]'),
        (BaseVar(_var_name="foo", _var_state="state", _var_type=list), "state.foo"),
        (BaseVar(_var_name="foo", _var_type=list), "foo"),
        (v((1, 2, 3)), "[1, 2, 3]"),
        (v(("1", "2", "3")), '["1", "2", "3"]'),
        (BaseVar(_var_name="foo", _var_state="state", _var_type=tuple), "state.foo"),
        (BaseVar(_var_name="foo", _var_type=tuple), "foo"),
    ],
)
def test_list_tuple_contains(var, expected):
    assert str(var.contains(1)) == f"{{{expected}.includes(1)}}"
    assert str(var.contains("1")) == f'{{{expected}.includes("1")}}'
    assert str(var.contains(v(1))) == f"{{{expected}.includes(1)}}"
    assert str(var.contains(v("1"))) == f'{{{expected}.includes("1")}}'
    other_state_var = BaseVar(_var_name="other", _var_state="state", _var_type=str)
    other_var = BaseVar(_var_name="other", _var_type=str)
    assert str(var.contains(other_state_var)) == f"{{{expected}.includes(state.other)}}"
    assert str(var.contains(other_var)) == f"{{{expected}.includes(other)}}"


@pytest.mark.parametrize(
    "var, expected",
    [
        (v("123"), json.dumps("123")),
        (BaseVar(_var_name="foo", _var_state="state", _var_type=str), "state.foo"),
        (BaseVar(_var_name="foo", _var_type=str), "foo"),
    ],
)
def test_str_contains(var, expected):
    assert str(var.contains("1")) == f'{{{expected}.includes("1")}}'
    assert str(var.contains(v("1"))) == f'{{{expected}.includes("1")}}'
    other_state_var = BaseVar(_var_name="other", _var_state="state", _var_type=str)
    other_var = BaseVar(_var_name="other", _var_type=str)
    assert str(var.contains(other_state_var)) == f"{{{expected}.includes(state.other)}}"
    assert str(var.contains(other_var)) == f"{{{expected}.includes(other)}}"


@pytest.mark.parametrize(
    "var, expected",
    [
        (v({"a": 1, "b": 2}), '{"a": 1, "b": 2}'),
        (BaseVar(_var_name="foo", _var_state="state", _var_type=dict), "state.foo"),
        (BaseVar(_var_name="foo", _var_type=dict), "foo"),
    ],
)
def test_dict_contains(var, expected):
    assert str(var.contains(1)) == f"{{{expected}.hasOwnProperty(1)}}"
    assert str(var.contains("1")) == f'{{{expected}.hasOwnProperty("1")}}'
    assert str(var.contains(v(1))) == f"{{{expected}.hasOwnProperty(1)}}"
    assert str(var.contains(v("1"))) == f'{{{expected}.hasOwnProperty("1")}}'
    other_state_var = BaseVar(_var_name="other", _var_state="state", _var_type=str)
    other_var = BaseVar(_var_name="other", _var_type=str)
    assert (
        str(var.contains(other_state_var))
        == f"{{{expected}.hasOwnProperty(state.other)}}"
    )
    assert str(var.contains(other_var)) == f"{{{expected}.hasOwnProperty(other)}}"


@pytest.mark.parametrize(
    "var",
    [
        BaseVar(_var_name="list", _var_type=List[int]),
        BaseVar(_var_name="tuple", _var_type=Tuple[int, int]),
        BaseVar(_var_name="str", _var_type=str),
    ],
)
def test_var_indexing_lists(var):
    """Test that we can index into str, list or tuple vars.

    Args:
        var : The str, list or tuple base var.
    """
    # Test basic indexing.
    assert str(var[0]) == f"{{{var._var_name}.at(0)}}"
    assert str(var[1]) == f"{{{var._var_name}.at(1)}}"

    # Test negative indexing.
    assert str(var[-1]) == f"{{{var._var_name}.at(-1)}}"


@pytest.mark.parametrize(
    "var, index",
    [
        (BaseVar(_var_name="lst", _var_type=List[int]), [1, 2]),
        (BaseVar(_var_name="lst", _var_type=List[int]), {"name": "dict"}),
        (BaseVar(_var_name="lst", _var_type=List[int]), {"set"}),
        (
            BaseVar(_var_name="lst", _var_type=List[int]),
            (
                1,
                2,
            ),
        ),
        (BaseVar(_var_name="lst", _var_type=List[int]), 1.5),
        (BaseVar(_var_name="lst", _var_type=List[int]), "str"),
        (
            BaseVar(_var_name="lst", _var_type=List[int]),
            BaseVar(_var_name="string_var", _var_type=str),
        ),
        (
            BaseVar(_var_name="lst", _var_type=List[int]),
            BaseVar(_var_name="float_var", _var_type=float),
        ),
        (
            BaseVar(_var_name="lst", _var_type=List[int]),
            BaseVar(_var_name="list_var", _var_type=List[int]),
        ),
        (
            BaseVar(_var_name="lst", _var_type=List[int]),
            BaseVar(_var_name="set_var", _var_type=Set[str]),
        ),
        (
            BaseVar(_var_name="lst", _var_type=List[int]),
            BaseVar(_var_name="dict_var", _var_type=Dict[str, str]),
        ),
        (BaseVar(_var_name="str", _var_type=str), [1, 2]),
        (BaseVar(_var_name="lst", _var_type=str), {"name": "dict"}),
        (BaseVar(_var_name="lst", _var_type=str), {"set"}),
        (
            BaseVar(_var_name="lst", _var_type=str),
            BaseVar(_var_name="string_var", _var_type=str),
        ),
        (
            BaseVar(_var_name="lst", _var_type=str),
            BaseVar(_var_name="float_var", _var_type=float),
        ),
        (BaseVar(_var_name="str", _var_type=Tuple[str]), [1, 2]),
        (BaseVar(_var_name="lst", _var_type=Tuple[str]), {"name": "dict"}),
        (BaseVar(_var_name="lst", _var_type=Tuple[str]), {"set"}),
        (
            BaseVar(_var_name="lst", _var_type=Tuple[str]),
            BaseVar(_var_name="string_var", _var_type=str),
        ),
        (
            BaseVar(_var_name="lst", _var_type=Tuple[str]),
            BaseVar(_var_name="float_var", _var_type=float),
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
        BaseVar(_var_name="lst", _var_type=List[int]),
        BaseVar(_var_name="tuple", _var_type=Tuple[int, int]),
        BaseVar(_var_name="str", _var_type=str),
    ],
)
def test_var_list_slicing(var):
    """Test that we can slice into str, list or tuple vars.

    Args:
        var : The str, list or tuple base var.
    """
    assert str(var[:1]) == f"{{{var._var_name}.slice(0, 1)}}"
    assert str(var[:1]) == f"{{{var._var_name}.slice(0, 1)}}"
    assert str(var[:]) == f"{{{var._var_name}.slice(0, undefined)}}"


def test_dict_indexing():
    """Test that we can index into dict vars."""
    dct = BaseVar(_var_name="dct", _var_type=Dict[str, int])

    # Check correct indexing.
    assert str(dct["a"]) == '{dct["a"]}'
    assert str(dct["asdf"]) == '{dct["asdf"]}'


@pytest.mark.parametrize(
    "var, index",
    [
        (
            BaseVar(_var_name="dict", _var_type=Dict[str, str]),
            [1, 2],
        ),
        (
            BaseVar(_var_name="dict", _var_type=Dict[str, str]),
            {"name": "dict"},
        ),
        (
            BaseVar(_var_name="dict", _var_type=Dict[str, str]),
            {"set"},
        ),
        (
            BaseVar(_var_name="dict", _var_type=Dict[str, str]),
            (
                1,
                2,
            ),
        ),
        (
            BaseVar(_var_name="lst", _var_type=Dict[str, str]),
            BaseVar(_var_name="list_var", _var_type=List[int]),
        ),
        (
            BaseVar(_var_name="lst", _var_type=Dict[str, str]),
            BaseVar(_var_name="set_var", _var_type=Set[str]),
        ),
        (
            BaseVar(_var_name="lst", _var_type=Dict[str, str]),
            BaseVar(_var_name="dict_var", _var_type=Dict[str, str]),
        ),
        (
            BaseVar(_var_name="df", _var_type=DataFrame),
            [1, 2],
        ),
        (
            BaseVar(_var_name="df", _var_type=DataFrame),
            {"name": "dict"},
        ),
        (
            BaseVar(_var_name="df", _var_type=DataFrame),
            {"set"},
        ),
        (
            BaseVar(_var_name="df", _var_type=DataFrame),
            (
                1,
                2,
            ),
        ),
        (
            BaseVar(_var_name="df", _var_type=DataFrame),
            BaseVar(_var_name="list_var", _var_type=List[int]),
        ),
        (
            BaseVar(_var_name="df", _var_type=DataFrame),
            BaseVar(_var_name="set_var", _var_type=Set[str]),
        ),
        (
            BaseVar(_var_name="df", _var_type=DataFrame),
            BaseVar(_var_name="dict_var", _var_type=Dict[str, str]),
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
    "fixture,full_name",
    [
        ("ParentState", "parent_state.var_without_annotation"),
        ("ChildState", "parent_state.child_state.var_without_annotation"),
        (
            "GrandChildState",
            "parent_state.child_state.grand_child_state.var_without_annotation",
        ),
        ("StateWithAnyVar", "state_with_any_var.var_without_annotation"),
    ],
)
def test_computed_var_without_annotation_error(request, fixture, full_name):
    """Test that a type error is thrown when an attribute of a computed var is
    accessed without annotating the computed var.

    Args:
        request: Fixture Request.
        fixture: The state fixture.
        full_name: The full name of the state var.
    """
    with pytest.raises(TypeError) as err:
        state = request.getfixturevalue(fixture)
        state.var_without_annotation.foo
    assert (
        err.value.args[0]
        == f"You must provide an annotation for the state var `{full_name}`. Annotation cannot be `typing.Any`"
    )


@pytest.mark.parametrize(
    "fixture,full_name",
    [
        (
            "StateWithCorrectVarAnnotation",
            "state_with_correct_var_annotation.var_with_annotation",
        ),
        (
            "StateWithWrongVarAnnotation",
            "state_with_wrong_var_annotation.var_with_annotation",
        ),
    ],
)
def test_computed_var_with_annotation_error(request, fixture, full_name):
    """Test that an Attribute error is thrown when a non-existent attribute of an annotated computed var is
    accessed or when the wrong annotation is provided to a computed var.

    Args:
        request: Fixture Request.
        fixture: The state fixture.
        full_name: The full name of the state var.
    """
    with pytest.raises(AttributeError) as err:
        state = request.getfixturevalue(fixture)
        state.var_with_annotation.foo
    assert (
        err.value.args[0]
        == f"The State var `{full_name}` has no attribute 'foo' or may have been annotated wrongly."
    )


@pytest.mark.parametrize(
    "import_var,expected",
    zip(
        test_import_vars,
        [
            "DataGrid",
            "DataGrid as Grid",
        ],
    ),
)
def test_import_var(import_var, expected):
    """Test that the import var name is computed correctly.

    Args:
        import_var: The import var.
        expected: expected name
    """
    assert import_var.name == expected


@pytest.mark.parametrize(
    "out, expected",
    [
        (f"{BaseVar(_var_name='var', _var_type=str)}", "${var}"),
        (
            f"testing f-string with {BaseVar(_var_name='myvar', _var_state='state', _var_type=int)}",
            "testing f-string with ${state.myvar}",
        ),
        (
            f"testing local f-string {BaseVar(_var_name='x', _var_is_local=True, _var_type=str)}",
            "testing local f-string x",
        ),
    ],
)
def test_fstrings(out, expected):
    assert out == expected


@pytest.mark.parametrize(
    "var",
    [
        BaseVar(_var_name="var", _var_type=int),
        BaseVar(_var_name="var", _var_type=float),
        BaseVar(_var_name="var", _var_type=str),
        BaseVar(_var_name="var", _var_type=bool),
        BaseVar(_var_name="var", _var_type=dict),
        BaseVar(_var_name="var", _var_type=tuple),
        BaseVar(_var_name="var", _var_type=set),
        BaseVar(_var_name="var", _var_type=None),
    ],
)
def test_unsupported_types_for_reverse(var):
    """Test that unsupported types for reverse throw a type error.

    Args:
        var: The base var.
    """
    with pytest.raises(TypeError) as err:
        var.reverse()
    assert err.value.args[0] == f"Cannot reverse non-list var var."


@pytest.mark.parametrize(
    "var",
    [
        BaseVar(_var_name="var", _var_type=int),
        BaseVar(_var_name="var", _var_type=float),
        BaseVar(_var_name="var", _var_type=bool),
        BaseVar(_var_name="var", _var_type=set),
        BaseVar(_var_name="var", _var_type=None),
    ],
)
def test_unsupported_types_for_contains(var):
    """Test that unsupported types for contains throw a type error.

    Args:
        var: The base var.
    """
    with pytest.raises(TypeError) as err:
        assert var.contains(1)
    assert (
        err.value.args[0]
        == f"Var var of type {var._var_type} does not support contains check."
    )


@pytest.mark.parametrize(
    "other",
    [
        BaseVar(_var_name="other", _var_type=int),
        BaseVar(_var_name="other", _var_type=float),
        BaseVar(_var_name="other", _var_type=bool),
        BaseVar(_var_name="other", _var_type=list),
        BaseVar(_var_name="other", _var_type=dict),
        BaseVar(_var_name="other", _var_type=tuple),
        BaseVar(_var_name="other", _var_type=set),
    ],
)
def test_unsupported_types_for_string_contains(other):
    with pytest.raises(TypeError) as err:
        assert BaseVar(_var_name="var", _var_type=str).contains(other)
    assert (
        err.value.args[0]
        == f"'in <string>' requires string as left operand, not {other._var_type}"
    )


def test_unsupported_default_contains():
    with pytest.raises(TypeError) as err:
        assert 1 in BaseVar(_var_name="var", _var_type=str)
    assert (
        err.value.args[0]
        == "'in' operator not supported for Var types, use Var.contains() instead."
    )


@pytest.mark.parametrize(
    "operand1_var,operand2_var,operators",
    [
        (
            Var.create(10),
            Var.create(5),
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
            Var.create(10.5),
            Var.create(5),
            ["+", "-", "/", "//", "*", "%", "**", ">", "<", "<=", ">="],
        ),
        (
            Var.create(5),
            Var.create(True),
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
            Var.create(10.5),
            Var.create(5.5),
            ["+", "-", "/", "//", "*", "%", "**", ">", "<", "<=", ">="],
        ),
        (
            Var.create(10.5),
            Var.create(True),
            ["+", "-", "/", "//", "*", "%", "**", ">", "<", "<=", ">="],
        ),
        (Var.create("10"), Var.create("5"), ["+", ">", "<", "<=", ">="]),
        (Var.create([10, 20]), Var.create([5, 6]), ["+", ">", "<", "<=", ">="]),
        (Var.create([10, 20]), Var.create(5), ["*"]),
        (Var.create([10, 20]), Var.create(True), ["*"]),
        (
            Var.create(True),
            Var.create(True),
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
def test_valid_var_operations(operand1_var: Var, operand2_var, operators: List[str]):
    """Test that operations do not raise a TypeError.

    Args:
        operand1_var: left operand.
        operand2_var: right operand.
        operators: list of supported operators.
    """
    for operator in operators:
        operand1_var.operation(op=operator, other=operand2_var)
        operand1_var.operation(op=operator, other=operand2_var, flip=True)


@pytest.mark.parametrize(
    "operand1_var,operand2_var,operators",
    [
        (
            Var.create(10),
            Var.create(5),
            [
                "^",
                "<<",
                ">>",
            ],
        ),
        (
            Var.create(10.5),
            Var.create(5),
            [
                "|",
                "^",
                "<<",
                ">>",
                "&",
            ],
        ),
        (
            Var.create(10.5),
            Var.create(True),
            [
                "|",
                "^",
                "<<",
                ">>",
                "&",
            ],
        ),
        (
            Var.create(10.5),
            Var.create(5.5),
            [
                "|",
                "^",
                "<<",
                ">>",
                "&",
            ],
        ),
        (
            Var.create("10"),
            Var.create("5"),
            [
                "-",
                "/",
                "//",
                "*",
                "%",
                "**",
                "|",
                "^",
                "<<",
                ">>",
                "&",
            ],
        ),
        (
            Var.create([10, 20]),
            Var.create([5, 6]),
            [
                "-",
                "/",
                "//",
                "*",
                "%",
                "**",
                "|",
                "^",
                "<<",
                ">>",
                "&",
            ],
        ),
        (
            Var.create([10, 20]),
            Var.create(5),
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
                "|",
                "^",
                "<<",
                ">>",
                "&",
            ],
        ),
        (
            Var.create([10, 20]),
            Var.create(True),
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
                "|",
                "^",
                "<<",
                ">>",
                "&",
            ],
        ),
        (
            Var.create([10, 20]),
            Var.create("5"),
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
                "^",
                "<<",
                ">>",
                "&",
            ],
        ),
        (
            Var.create([10, 20]),
            Var.create({"key": "value"}),
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
                "^",
                "<<",
                ">>",
                "&",
            ],
        ),
        (
            Var.create([10, 20]),
            Var.create(5.5),
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
                "^",
                "<<",
                ">>",
                "&",
            ],
        ),
        (
            Var.create({"key": "value"}),
            Var.create({"another_key": "another_value"}),
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
                "^",
                "<<",
                ">>",
                "&",
            ],
        ),
        (
            Var.create({"key": "value"}),
            Var.create(5),
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
                "^",
                "<<",
                ">>",
                "&",
            ],
        ),
        (
            Var.create({"key": "value"}),
            Var.create(True),
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
                "^",
                "<<",
                ">>",
                "&",
            ],
        ),
        (
            Var.create({"key": "value"}),
            Var.create(5.5),
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
                "^",
                "<<",
                ">>",
                "&",
            ],
        ),
        (
            Var.create({"key": "value"}),
            Var.create("5"),
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
                "^",
                "<<",
                ">>",
                "&",
            ],
        ),
    ],
)
def test_invalid_var_operations(operand1_var: Var, operand2_var, operators: List[str]):
    for operator in operators:
        with pytest.raises(TypeError):
            operand1_var.operation(op=operator, other=operand2_var)

        with pytest.raises(TypeError):
            operand1_var.operation(op=operator, other=operand2_var, flip=True)
