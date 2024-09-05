import json
import math
import typing
from typing import Dict, List, Optional, Set, Tuple, Union, cast

import pytest
from pandas import DataFrame

from reflex.base import Base
from reflex.constants.base import REFLEX_VAR_CLOSING_TAG, REFLEX_VAR_OPENING_TAG
from reflex.ivars.base import (
    ImmutableVar,
    LiteralVar,
    var_operation,
    var_operation_return,
)
from reflex.ivars.function import ArgsFunctionOperation, FunctionStringVar
from reflex.ivars.number import (
    LiteralBooleanVar,
    LiteralNumberVar,
    NumberVar,
)
from reflex.ivars.object import LiteralObjectVar
from reflex.ivars.sequence import (
    ArrayVar,
    ConcatVarOperation,
    LiteralArrayVar,
    LiteralStringVar,
)
from reflex.state import BaseState
from reflex.utils.imports import ImportVar
from reflex.vars import (
    BaseVar,
    ComputedVar,
    ImmutableVarData,
    Var,
    VarData,
    computed_var,
)

test_vars = [
    BaseVar(_var_name="prop1", _var_type=int),
    BaseVar(_var_name="key", _var_type=str),
    BaseVar(_var_name="value", _var_type=str)._var_set_state("state"),
    BaseVar(_var_name="local", _var_type=str, _var_is_local=True)._var_set_state(
        "state"
    ),
    BaseVar(_var_name="local2", _var_type=str, _var_is_local=True),
]


class ATestState(BaseState):
    """Test state."""

    value: str
    dict_val: Dict[str, List] = {}


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
            return TestObj

    return ChildState


@pytest.fixture
def GrandChildState(ChildState, TestObj):
    class GrandChildState(ChildState):
        @computed_var
        def var_without_annotation(self):
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
            raise ValueError("So nicht, mein Freund")

    return StateWithRuntimeOnlyVar


@pytest.fixture
def ChildWithRuntimeOnlyVar(StateWithRuntimeOnlyVar):
    class ChildWithRuntimeOnlyVar(StateWithRuntimeOnlyVar):
        @computed_var(initial_value="Initial value")
        def var_raises_at_runtime_child(self) -> str:
            raise ValueError("So nicht, mein Freund")

    return ChildWithRuntimeOnlyVar


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
    assert str(v(1) == v(2)) == "{((1) === (2))}"
    assert str(v(1) != v(2)) == "{((1) !== (2))}"
    assert str(v(1) < v(2)) == "{((1) < (2))}"
    assert str(v(1) <= v(2)) == "{((1) <= (2))}"
    assert str(v(1) > v(2)) == "{((1) > (2))}"
    assert str(v(1) >= v(2)) == "{((1) >= (2))}"
    assert str(v(1) + v(2)) == "{((1) + (2))}"
    assert str(v(1) - v(2)) == "{((1) - (2))}"
    assert str(v(1) * v(2)) == "{((1) * (2))}"
    assert str(v(1) / v(2)) == "{((1) / (2))}"
    assert str(v(1) // v(2)) == "{Math.floor((1) / (2))}"
    assert str(v(1) % v(2)) == "{((1) % (2))}"
    assert str(v(1) ** v(2)) == "{Math.pow((1) , (2))}"
    assert str(v(1) & v(2)) == "{((1) && (2))}"
    assert str(v(1) | v(2)) == "{((1) || (2))}"
    assert str(v([1, 2, 3])[v(0)]) == "{[1, 2, 3].at(0)}"
    assert str(v({"a": 1, "b": 2})["a"]) == '{{"a": 1, "b": 2}["a"]}'
    assert str(v("foo") == v("bar")) == '{(("foo") === ("bar"))}'
    assert (
        str(
            Var.create("foo", _var_is_local=False)
            == Var.create("bar", _var_is_local=False)
        )
        == "{((foo) === (bar))}"
    )
    assert (
        str(
            BaseVar(
                _var_name="foo", _var_type=str, _var_is_string=True, _var_is_local=True
            )
            == BaseVar(
                _var_name="bar", _var_type=str, _var_is_string=True, _var_is_local=True
            )
        )
        == "((`foo`) === (`bar`))"
    )
    assert (
        str(
            BaseVar(
                _var_name="foo",
                _var_type=TestObj,
                _var_is_string=True,
                _var_is_local=False,
            )
            ._var_set_state("state")
            .bar
            == BaseVar(
                _var_name="bar", _var_type=str, _var_is_string=True, _var_is_local=True
            )
        )
        == "{((state.foo.bar) === (`bar`))}"
    )
    assert (
        str(BaseVar(_var_name="foo", _var_type=TestObj)._var_set_state("state").bar)
        == "{state.foo.bar}"
    )
    assert str(abs(v(1))) == "{Math.abs(1)}"
    assert str(v([1, 2, 3]).length()) == "{[1, 2, 3].length}"
    assert str(v([1, 2]) + v([3, 4])) == "{spreadArraysOrObjects(([1, 2]) , ([3, 4]))}"

    # Tests for reverse operation
    assert str(v([1, 2, 3]).reverse()) == "{[...[1, 2, 3]].reverse()}"
    assert str(v(["1", "2", "3"]).reverse()) == '{[...["1", "2", "3"]].reverse()}'
    assert (
        str(BaseVar(_var_name="foo", _var_type=list)._var_set_state("state").reverse())
        == "{[...state.foo].reverse()}"
    )
    assert (
        str(BaseVar(_var_name="foo", _var_type=list).reverse())
        == "{[...foo].reverse()}"
    )
    assert str(BaseVar(_var_name="foo", _var_type=str)._type()) == "{typeof foo}"  # type: ignore
    assert (
        str(BaseVar(_var_name="foo", _var_type=str)._type() == str)  # type: ignore
        == "{((typeof foo) === (`string`))}"
    )
    assert (
        str(BaseVar(_var_name="foo", _var_type=str)._type() == str)  # type: ignore
        == "{((typeof foo) === (`string`))}"
    )
    assert (
        str(BaseVar(_var_name="foo", _var_type=str)._type() == int)  # type: ignore
        == "{((typeof foo) === (`number`))}"
    )
    assert (
        str(BaseVar(_var_name="foo", _var_type=str)._type() == list)  # type: ignore
        == "{((typeof foo) === (`Array`))}"
    )
    assert (
        str(BaseVar(_var_name="foo", _var_type=str)._type() == float)  # type: ignore
        == "{((typeof foo) === (`number`))}"
    )
    assert (
        str(BaseVar(_var_name="foo", _var_type=str)._type() == tuple)  # type: ignore
        == "{((typeof foo) === (`Array`))}"
    )
    assert (
        str(BaseVar(_var_name="foo", _var_type=str)._type() == dict)  # type: ignore
        == "{((typeof foo) === (`Object`))}"
    )
    assert (
        str(BaseVar(_var_name="foo", _var_type=str)._type() != str)  # type: ignore
        == "{((typeof foo) !== (`string`))}"
    )
    assert (
        str(BaseVar(_var_name="foo", _var_type=str)._type() != int)  # type: ignore
        == "{((typeof foo) !== (`number`))}"
    )
    assert (
        str(BaseVar(_var_name="foo", _var_type=str)._type() != list)  # type: ignore
        == "{((typeof foo) !== (`Array`))}"
    )
    assert (
        str(BaseVar(_var_name="foo", _var_type=str)._type() != float)  # type: ignore
        == "{((typeof foo) !== (`number`))}"
    )
    assert (
        str(BaseVar(_var_name="foo", _var_type=str)._type() != tuple)  # type: ignore
        == "{((typeof foo) !== (`Array`))}"
    )
    assert (
        str(BaseVar(_var_name="foo", _var_type=str)._type() != dict)  # type: ignore
        == "{((typeof foo) !== (`Object`))}"
    )


@pytest.mark.parametrize(
    "var, expected",
    [
        (v([1, 2, 3]), "[1, 2, 3]"),
        (v(set([1, 2, 3])), "[1, 2, 3]"),
        (v(["1", "2", "3"]), '["1", "2", "3"]'),
        (BaseVar(_var_name="foo", _var_type=list)._var_set_state("state"), "state.foo"),
        (BaseVar(_var_name="foo", _var_type=list), "foo"),
        (v((1, 2, 3)), "[1, 2, 3]"),
        (v(("1", "2", "3")), '["1", "2", "3"]'),
        (
            BaseVar(_var_name="foo", _var_type=tuple)._var_set_state("state"),
            "state.foo",
        ),
        (BaseVar(_var_name="foo", _var_type=tuple), "foo"),
    ],
)
def test_list_tuple_contains(var, expected):
    assert str(var.contains(1)) == f"{{{expected}.includes(1)}}"
    assert str(var.contains("1")) == f'{{{expected}.includes("1")}}'
    assert str(var.contains(v(1))) == f"{{{expected}.includes(1)}}"
    assert str(var.contains(v("1"))) == f'{{{expected}.includes("1")}}'
    other_state_var = BaseVar(_var_name="other", _var_type=str)._var_set_state("state")
    other_var = BaseVar(_var_name="other", _var_type=str)
    assert str(var.contains(other_state_var)) == f"{{{expected}.includes(state.other)}}"
    assert str(var.contains(other_var)) == f"{{{expected}.includes(other)}}"


@pytest.mark.parametrize(
    "var, expected",
    [
        (v("123"), json.dumps("123")),
        (BaseVar(_var_name="foo", _var_type=str)._var_set_state("state"), "state.foo"),
        (BaseVar(_var_name="foo", _var_type=str), "foo"),
    ],
)
def test_str_contains(var, expected):
    assert str(var.contains("1")) == f'{{{expected}.includes("1")}}'
    assert str(var.contains(v("1"))) == f'{{{expected}.includes("1")}}'
    other_state_var = BaseVar(_var_name="other", _var_type=str)._var_set_state("state")
    other_var = BaseVar(_var_name="other", _var_type=str)
    assert str(var.contains(other_state_var)) == f"{{{expected}.includes(state.other)}}"
    assert str(var.contains(other_var)) == f"{{{expected}.includes(other)}}"
    assert (
        str(var.contains("1", "hello")) == f'{{{expected}.some(e=>e[`hello`]==="1")}}'
    )


@pytest.mark.parametrize(
    "var, expected",
    [
        (v({"a": 1, "b": 2}), '{"a": 1, "b": 2}'),
        (BaseVar(_var_name="foo", _var_type=dict)._var_set_state("state"), "state.foo"),
        (BaseVar(_var_name="foo", _var_type=dict), "foo"),
    ],
)
def test_dict_contains(var, expected):
    assert str(var.contains(1)) == f"{{{expected}.hasOwnProperty(1)}}"
    assert str(var.contains("1")) == f'{{{expected}.hasOwnProperty("1")}}'
    assert str(var.contains(v(1))) == f"{{{expected}.hasOwnProperty(1)}}"
    assert str(var.contains(v("1"))) == f'{{{expected}.hasOwnProperty("1")}}'
    other_state_var = BaseVar(_var_name="other", _var_type=str)._var_set_state("state")
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
    "var, type_",
    [
        (BaseVar(_var_name="list", _var_type=List[int]), [int, int]),
        (BaseVar(_var_name="tuple", _var_type=Tuple[int, str]), [int, str]),
    ],
)
def test_var_indexing_types(var, type_):
    """Test that indexing returns valid types.

    Args:
        var   : The list, typle base var.
        type_ : The type on indexed object.

    """
    assert var[2]._var_type == type_[0]
    assert var[3]._var_type == type_[1]


def test_var_indexing_str():
    """Test that we can index into str vars."""
    str_var = BaseVar(_var_name="str", _var_type=str)

    # Test that indexing gives a type of Var[str].
    assert isinstance(str_var[0], Var)
    assert str_var[0]._var_type == str

    # Test basic indexing.
    assert str(str_var[0]) == "{str.at(0)}"
    assert str(str_var[1]) == "{str.at(1)}"

    # Test negative indexing.
    assert str(str_var[-1]) == "{str.at(-1)}"


@pytest.mark.parametrize(
    "var",
    [
        (BaseVar(_var_name="foo", _var_type=int)),
        (BaseVar(_var_name="bar", _var_type=float)),
    ],
)
def test_var_replace_with_invalid_kwargs(var):
    with pytest.raises(TypeError) as excinfo:
        var._replace(_this_should_fail=True)
    assert "Unexpected keyword arguments" in str(excinfo.value)


def test_computed_var_replace_with_invalid_kwargs():
    @computed_var(initial_value=1)
    def test_var(state) -> int:
        return 1

    with pytest.raises(TypeError) as excinfo:
        test_var._replace(_random_kwarg=True)
    assert "Unexpected keyword arguments" in str(excinfo.value)


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
    "fixture",
    [
        "ParentState",
        "ChildState",
        "GrandChildState",
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
    "fixture,var_name,expected_initial,expected_runtime,raises_at_runtime",
    [
        (
            "StateWithInitialComputedVar",
            "var_with_initial_value",
            "Initial value",
            "Runtime value",
            False,
        ),
        (
            "ChildWithInitialComputedVar",
            "var_with_initial_value_child",
            "Initial value",
            "Runtime value",
            False,
        ),
        (
            "StateWithRuntimeOnlyVar",
            "var_raises_at_runtime",
            None,
            None,
            True,
        ),
        (
            "ChildWithRuntimeOnlyVar",
            "var_raises_at_runtime_child",
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
    complicated_var = LiteralVar.create(
        [
            {"a": 1, "b": 2, "c": {"d": 3, "e": 4}},
            [1, 2, 3, 4],
            9,
            "string",
            True,
            False,
            None,
            set([1, 2, 3]),
        ]
    )
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
            "args": [ImmutableVar.create_safe("a"), ImmutableVar.create_safe("b")],
            "result": ImmutableVar.create_safe("a + b"),
        },
    )
    assert (
        str(manual_addition_func.call(1, 2))
        == '(((a, b) => (({ ["args"] : [a, b], ["result"] : a + b })))(1, 2))'
    )

    increment_func = addition_func(1)
    assert (
        str(increment_func.call(2))
        == "(((...args) => ((((a, b) => a + b)(1, ...args))))(2))"
    )

    create_hello_statement = ArgsFunctionOperation.create(
        ("name",), f"Hello, {ImmutableVar.create_safe('name')}!"
    )
    first_name = LiteralStringVar.create("Steven")
    last_name = LiteralStringVar.create("Universe")
    assert (
        str(create_hello_statement.call(f"{first_name} {last_name}"))
        == '(((name) => (("Hello, "+name+"!")))("Steven Universe"))'
    )


def test_var_operation():
    @var_operation
    def add(a: Union[NumberVar, int], b: Union[NumberVar, int]):
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
        == "!(((Math.abs(Math.floor(((Math.floor(((-((-5.4 + 1)) * 2) / 3) / 2) % 3) ** 2))) || (2 && Math.round(((Math.floor(((-((-5.4 + 1)) * 2) / 3) / 2) % 3) ** 2)))) !== 0))"
    )

    assert str(LiteralNumberVar.create(5) > False) == "(5 > 0)"
    assert str(LiteralBooleanVar.create(False) < 5) == "(Number(false) < 5)"
    assert (
        str(LiteralBooleanVar.create(False) < LiteralBooleanVar.create(True))
        == "(Number(false) < Number(true))"
    )


def test_index_operation():
    array_var = LiteralArrayVar.create([1, 2, 3, 4, 5])
    assert str(array_var[0]) == "[1, 2, 3, 4, 5].at(0)"
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
    assert str(array_var[0].to(NumberVar) + 9) == "([1, 2, 3, 4, 5].at(0) + 9)"


def test_array_operations():
    array_var = LiteralArrayVar.create([1, 2, 3, 4, 5])

    assert str(array_var.length()) == "[1, 2, 3, 4, 5].length"
    assert str(array_var.contains(3)) == "[1, 2, 3, 4, 5].includes(3)"
    assert str(array_var.reverse()) == "[1, 2, 3, 4, 5].slice().reverse()"
    assert (
        str(ArrayVar.range(10))
        == "Array.from({ length: (10 - 0) / 1 }, (_, i) => 0 + i * 1)"
    )
    assert (
        str(ArrayVar.range(1, 10))
        == "Array.from({ length: (10 - 1) / 1 }, (_, i) => 1 + i * 1)"
    )
    assert (
        str(ArrayVar.range(1, 10, 2))
        == "Array.from({ length: (10 - 1) / 2 }, (_, i) => 1 + i * 2)"
    )
    assert (
        str(ArrayVar.range(1, 10, -1))
        == "Array.from({ length: (10 - 1) / -1 }, (_, i) => 1 + i * -1)"
    )


def test_object_operations():
    object_var = LiteralObjectVar.create({"a": 1, "b": 2, "c": 3})

    assert (
        str(object_var.keys()) == 'Object.keys(({ ["a"] : 1, ["b"] : 2, ["c"] : 3 }))'
    )
    assert (
        str(object_var.values())
        == 'Object.values(({ ["a"] : 1, ["b"] : 2, ["c"] : 3 }))'
    )
    assert (
        str(object_var.entries())
        == 'Object.entries(({ ["a"] : 1, ["b"] : 2, ["c"] : 3 }))'
    )
    assert str(object_var.a) == '({ ["a"] : 1, ["b"] : 2, ["c"] : 3 })["a"]'
    assert str(object_var["a"]) == '({ ["a"] : 1, ["b"] : 2, ["c"] : 3 })["a"]'
    assert (
        str(object_var.merge(LiteralObjectVar.create({"c": 4, "d": 5})))
        == '({...({ ["a"] : 1, ["b"] : 2, ["c"] : 3 }), ...({ ["c"] : 4, ["d"] : 5 })})'
    )


def test_type_chains():
    object_var = LiteralObjectVar.create({"a": 1, "b": 2, "c": 3})
    assert (object_var._key_type(), object_var._value_type()) == (str, int)
    assert (object_var.keys()._var_type, object_var.values()._var_type) == (
        List[str],
        List[int],
    )
    assert (
        str(object_var.keys()[0].upper())  # type: ignore
        == 'Object.keys(({ ["a"] : 1, ["b"] : 2, ["c"] : 3 })).at(0).toUpperCase()'
    )
    assert (
        str(object_var.entries()[1][1] - 1)  # type: ignore
        == '(Object.entries(({ ["a"] : 1, ["b"] : 2, ["c"] : 3 })).at(1).at(1) - 1)'
    )
    assert (
        str(object_var["c"] + object_var["b"])  # type: ignore
        == '(({ ["a"] : 1, ["b"] : 2, ["c"] : 3 })["c"] + ({ ["a"] : 1, ["b"] : 2, ["c"] : 3 })["b"])'
    )


def test_nested_dict():
    arr = LiteralArrayVar.create([{"bar": ["foo", "bar"]}], List[Dict[str, List[str]]])

    assert (
        str(arr[0]["bar"][0]) == '[({ ["bar"] : ["foo", "bar"] })].at(0)["bar"].at(0)'
    )


def nested_base():
    class Boo(Base):
        foo: str
        bar: int

    class Foo(Base):
        bar: Boo
        baz: int

    parent_obj = LiteralVar.create(Foo(bar=Boo(foo="bar", bar=5), baz=5))

    assert (
        str(parent_obj.bar.foo)
        == '({ ["bar"] : ({ ["foo"] : "bar", ["bar"] : 5 }), ["baz"] : 5 })["bar"]["foo"]'
    )


def test_retrival():
    var_without_data = ImmutableVar.create("test")
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

    result_var_data = Var.create_safe(f_string)._var_data
    result_immutable_var_data = ImmutableVar.create_safe(f_string)._var_data
    assert result_var_data is not None and result_immutable_var_data is not None
    assert (
        result_var_data.state
        == result_immutable_var_data.state
        == original_var_data.state
    )
    assert (
        result_var_data.imports
        == (
            result_immutable_var_data.imports
            if isinstance(result_immutable_var_data.imports, dict)
            else {
                k: list(v)
                for k, v in result_immutable_var_data.imports
                if k in original_var_data.imports
            }
        )
        == original_var_data.imports
    )
    assert (
        list(result_var_data.hooks.keys())
        == (
            list(result_immutable_var_data.hooks.keys())
            if isinstance(result_immutable_var_data.hooks, dict)
            else list(result_immutable_var_data.hooks)
        )
        == list(original_var_data.hooks.keys())
    )


def test_fstring_concat():
    original_var_with_data = Var.create_safe(
        "imagination", _var_data=VarData(state="fear")
    )

    immutable_var_with_data = ImmutableVar.create_safe(
        "consequences",
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

    assert str(string_concat) == '("foo"+imagination+"bar"+consequences+"baz")'
    assert isinstance(string_concat, ConcatVarOperation)
    assert string_concat._get_all_var_data() == ImmutableVarData(
        state="fear",
        imports={
            "react": [ImportVar(tag="useRef")],
            "utils": [ImportVar(tag="useEffect")],
        },
        hooks={"const state = useContext(StateContexts.state)": None},
    )


@pytest.mark.parametrize(
    "out, expected",
    [
        (f"{BaseVar(_var_name='var', _var_type=str)}", "${var}"),
        (
            f"testing f-string with {BaseVar(_var_name='myvar', _var_type=int)._var_set_state('state')}",
            'testing f-string with $<reflex.Var>{"state": "state", "interpolations": [], "imports": {"/utils/context": [{"tag": "StateContexts", "is_default": false, "alias": null, "install": true, "render": true, "transpile": false}], "react": [{"tag": "useContext", "is_default": false, "alias": null, "install": true, "render": true, "transpile": false}]}, "hooks": {"const state = useContext(StateContexts.state)": null}, "string_length": 13}</reflex.Var>{state.myvar}',
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
    ("value", "expect_state"),
    [
        ([1], ""),
        ({"a": 1}, ""),
        ([Var.create_safe(1)._var_set_state("foo")], "foo"),
        ({"a": Var.create_safe(1)._var_set_state("foo")}, "foo"),
    ],
)
def test_extract_state_from_container(value, expect_state):
    """Test that _var_state is extracted from containers containing BaseVar.

    Args:
        value: The value to create a var from.
        expect_state: The expected state.
    """
    assert Var.create_safe(value)._var_state == expect_state


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
    var = BaseVar.create_safe(value)._var_set_state("state")
    rt_var = Var.create_safe(f"{var}")
    assert var._var_state == rt_var._var_state
    assert var._var_full_name_needs_state_prefix
    assert not rt_var._var_full_name_needs_state_prefix
    assert rt_var._var_name == var._var_full_name


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


@pytest.mark.parametrize(
    "var, expected",
    [
        (Var.create("string_value", _var_is_string=True), "`string_value`"),
        (Var.create(1), "1"),
        (Var.create([1, 2, 3]), "[1, 2, 3]"),
        (Var.create({"foo": "bar"}), '{"foo": "bar"}'),
        (
            Var.create(ATestState.value, _var_is_string=True),
            f"{ATestState.get_full_name()}.value",
        ),
        (
            LiteralVar.create(f"{ATestState.value} string"),
            f'({ATestState.get_full_name()}.value+" string")',
        ),
        (Var.create(ATestState.dict_val), f"{ATestState.get_full_name()}.dict_val"),
    ],
)
def test_var_name_unwrapped(var, expected):
    assert var._var_name_unwrapped == expected


def cv_fget(state: BaseState) -> int:
    return 1


@pytest.mark.parametrize(
    "deps,expected",
    [
        (["a"], {"a"}),
        (["b"], {"b"}),
        ([ComputedVar(fget=cv_fget)], {"cv_fget"}),
    ],
)
def test_computed_var_deps(deps: List[Union[str, Var]], expected: Set[str]):
    @computed_var(
        deps=deps,
        cache=True,
    )
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
def test_invalid_computed_var_deps(deps: List):
    with pytest.raises(TypeError):

        @computed_var(
            deps=deps,
            cache=True,
        )
        def test_var(state) -> int:
            return 1


def test_to_string_operation():
    class Email(str): ...

    class TestState(BaseState):
        optional_email: Optional[Email] = None
        email: Email = Email("test@reflex.dev")

    assert (
        str(TestState.optional_email) == f"{TestState.get_full_name()}.optional_email"
    )
    my_state = TestState()
    assert my_state.optional_email is None
    assert my_state.email == "test@reflex.dev"

    assert cast(ImmutableVar, TestState.email)._var_type == Email
    assert cast(ImmutableVar, TestState.optional_email)._var_type == Optional[Email]
