from typing import Dict, List

import cloudpickle
import pytest

from pynecone.base import Base
from pynecone.var import BaseVar, PCList, Var

test_vars = [
    BaseVar(name="prop1", type_=int),
    BaseVar(name="key", type_=str),
    BaseVar(name="value", type_=str, state="state"),
    BaseVar(name="local", type_=str, state="state", is_local=True),
    BaseVar(name="local2", type_=str, is_local=True),
]


@pytest.fixture
def TestObj():
    class TestObj(Base):
        foo: int
        bar: str

    return TestObj


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
    assert prop.full_name == expected


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
        (BaseVar(name="p", type_=int), 0),
        (BaseVar(name="p", type_=float), 0.0),
        (BaseVar(name="p", type_=str), ""),
        (BaseVar(name="p", type_=bool), False),
        (BaseVar(name="p", type_=list), []),
        (BaseVar(name="p", type_=dict), {}),
        (BaseVar(name="p", type_=tuple), ()),
        (BaseVar(name="p", type_=set), set()),
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
        (1, BaseVar(name="1", type_=int, is_local=True)),
        ("key", BaseVar(name="key", type_=str, is_local=True)),
        (3.14, BaseVar(name="3.14", type_=float, is_local=True)),
        ([1, 2, 3], BaseVar(name="[1, 2, 3]", type_=list, is_local=True)),
        (
            {"a": 1, "b": 2},
            BaseVar(name='{"a": 1, "b": 2}', type_=dict, is_local=True),
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


def v(value) -> Var:
    val = Var.create(value)
    assert val is not None
    return val


def test_basic_operations(TestObj):
    """Test the var operations.

    Args:
        TestObj: The test object.
    """
    assert str(v(1) == v(2)) == "{(1 == 2)}"
    assert str(v(1) != v(2)) == "{(1 != 2)}"
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
        str(BaseVar(name="foo", state="state", type_=TestObj).bar) == "{state.foo.bar}"
    )
    assert str(abs(v(1))) == "{Math.abs(1)}"
    assert str(v([1, 2, 3]).length()) == "{[1, 2, 3].length}"


def test_var_indexing_lists():
    """Test that we can index into list vars."""
    lst = BaseVar(name="lst", type_=List[int])

    # Test basic indexing.
    assert str(lst[0]) == "{lst.at(0)}"
    assert str(lst[1]) == "{lst.at(1)}"

    # Test negative indexing.
    assert str(lst[-1]) == "{lst.at(-1)}"

    # Test non-integer indexing raises an error.
    with pytest.raises(TypeError):
        lst["a"]
    with pytest.raises(TypeError):
        lst[1.5]


def test_var_list_slicing():
    """Test that we can slice into list vars."""
    lst = BaseVar(name="lst", type_=List[int])

    assert str(lst[:1]) == "{lst.slice(0, 1)}"
    assert str(lst[:1]) == "{lst.slice(0, 1)}"
    assert str(lst[:]) == "{lst.slice(0, undefined)}"


def test_dict_indexing():
    """Test that we can index into dict vars."""
    dct = BaseVar(name="dct", type_=Dict[str, int])

    # Check correct indexing.
    assert str(dct["a"]) == '{dct["a"]}'
    assert str(dct["asdf"]) == '{dct["asdf"]}'


def test_pickleable_pc_list():
    """Test that PCList is pickleable."""
    pc_list = PCList(
        original_list=[1, 2, 3], reassign_field=lambda x: x, field_name="random"
    )

    pickled_list = cloudpickle.dumps(pc_list)
    assert cloudpickle.loads(pickled_list) == pc_list
