import pytest

from pynecone.base import Base
from pynecone.var import BaseVar, Var

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


def test_basic_operations(TestObj):
    """Test the var operations.

    Args:
        TestObj: The test object.
    """

    def v(value) -> Var:
        val = Var.create(value)
        assert val is not None
        return val

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
    assert str(v([1, 2, 3])[v(0)]) == "{[1, 2, 3][0]}"
    assert str(v({"a": 1, "b": 2})["a"]) == '{{"a": 1, "b": 2}["a"]}'
    assert (
        str(BaseVar(name="foo", state="state", type_=TestObj).bar) == "{state.foo.bar}"
    )
