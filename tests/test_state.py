from typing import Dict, List

import pytest

from pynecone.base import Base
from pynecone.event import Event
from pynecone.state import State
from pynecone.var import BaseVar, ComputedVar


@pytest.fixture
def TestObject():
    class TestObject(Base):
        """A test object fixture."""

        prop1: int = 42
        prop2: str = "hello"

    return TestObject


@pytest.fixture
def TestState(TestObject):
    class TestState(State):
        """A test state."""

        num1: int
        num2: float = 3.14
        key: str
        array: List[float] = [1, 2, 3.14]
        mapping: Dict[str, List[int]] = {"a": [1, 2, 3], "b": [4, 5, 6]}
        obj: TestObject = TestObject()
        complex: Dict[int, TestObject] = {1: TestObject(), 2: TestObject()}

        @ComputedVar
        def sum(self) -> float:
            """Dynamically sum the numbers.

            Returns:
                The sum of the numbers.
            """
            return self.num1 + self.num2

        @ComputedVar
        def upper(self) -> str:
            """Uppercase the key.

            Returns:
                The uppercased key.
            """
            return self.key.upper()

        def do_something(self):
            """Do something."""
            pass

    return TestState


@pytest.fixture
def ChildState(TestState):
    class ChildState(TestState):
        """A child state fixture."""

        value: str
        count: int = 23

        def change_both(self, value: str, count: int):
            """Change both the value and count.

            Args:
                value: The new value.
                count: The new count.
            """
            self.value = value.upper()
            self.count = count * 2

    return ChildState


@pytest.fixture
def ChildState2(TestState):
    class ChildState2(TestState):
        """A child state fixture."""

        value: str

    return ChildState2


@pytest.fixture
def GrandchildState(ChildState):
    class GrandchildState(ChildState):
        """A grandchild state fixture."""

        value2: str

    return GrandchildState


@pytest.fixture
def state(TestState) -> State:
    """A state.

    Args:
        TestState: The state class.

    Returns:
        A test state.
    """
    return TestState()  # type: ignore


def test_base_class_vars(state):
    """Test that the class vars are set correctly.

    Args:
        state: A state.
    """
    fields = state.get_fields()
    cls = type(state)

    for field in fields:
        if field in (
            "parent_state",
            "substates",
            "dirty_vars",
            "dirty_substates",
        ):
            continue
        prop = getattr(cls, field)
        assert isinstance(prop, BaseVar)
        assert prop.name == field

    assert cls.num1.type_ == int
    assert cls.num2.type_ == float
    assert cls.key.type_ == str


def test_computed_class_var(state):
    """Test that the class computed vars are set correctly.

    Args:
        state: A state.
    """
    cls = type(state)
    vars = [(prop.name, prop.type_) for prop in cls.computed_vars.values()]
    assert ("sum", float) in vars
    assert ("upper", str) in vars


def test_class_vars(state):
    """Test that the class vars are set correctly.

    Args:
        state: A state.
    """
    cls = type(state)
    assert set(cls.vars.keys()) == {
        "num1",
        "num2",
        "key",
        "array",
        "mapping",
        "obj",
        "complex",
        "sum",
        "upper",
    }


def test_default_value(state):
    """Test that the default value of a var is correct.

    Args:
        state: A state.
    """
    assert state.num1 == 0
    assert state.num2 == 3.14
    assert state.key == ""
    assert state.sum == 3.14
    assert state.upper == ""


def test_computed_vars(state):
    """Test that the computed var is computed correctly.

    Args:
        state: A state.
    """
    state.num1 = 1
    state.num2 = 4
    assert state.sum == 5
    state.key = "hello world"
    assert state.upper == "HELLO WORLD"


def test_dict(state):
    """Test that the dict representation of a state is correct.

    Args:
        state: A state.
    """
    assert set(state.dict().keys()) == set(state.vars.keys())
    assert set(state.dict(include_computed=False).keys()) == set(state.base_vars)


def test_default_setters(TestState):
    """Test that we can set default values.

    Args:
        TestState: The state class.
    """
    state = TestState()
    for prop_name in state.base_vars:
        # Each base var should have a default setter.
        assert hasattr(state, f"set_{prop_name}")


def test_class_indexing_with_vars(TestState):
    """Test that we can index into a state var with another var.

    Args:
        TestState: The state class.
    """
    prop = TestState.array[TestState.num1]
    assert str(prop) == "{test_state.array[test_state.num1]}"

    prop = TestState.mapping["a"][TestState.num1]
    assert str(prop) == '{test_state.mapping["a"][test_state.num1]}'


def test_class_attributes(TestState):
    """Test that we can get class attributes.

    Args:
        TestState: The state class.
    """
    prop = TestState.obj.prop1
    assert str(prop) == "{test_state.obj.prop1}"

    prop = TestState.complex[1].prop1
    assert str(prop) == "{test_state.complex[1].prop1}"


def test_get_parent_state(TestState, ChildState, ChildState2, GrandchildState):
    """Test getting the parent state.

    Args:
        TestState: The state class.
        ChildState: The child state class.
        ChildState2: The child state class.
        GrandchildState: The grandchild state class.
    """
    assert TestState.get_parent_state() is None
    assert ChildState.get_parent_state() == TestState
    assert ChildState2.get_parent_state() == TestState
    assert GrandchildState.get_parent_state() == ChildState


def test_get_substates(TestState, ChildState, ChildState2, GrandchildState):
    """Test getting the substates.

    Args:
        TestState: The state class.
        ChildState: The child state class.
        ChildState2: The child state class.
        GrandchildState: The grandchild state class.
    """
    assert TestState.get_substates() == {ChildState, ChildState2}
    assert ChildState.get_substates() == {GrandchildState}
    assert ChildState2.get_substates() == set()
    assert GrandchildState.get_substates() == set()


def test_get_name(TestState, ChildState, ChildState2, GrandchildState):
    """Test getting the name of a state.

    Args:
        TestState: The state class.
        ChildState: The child state class.
        ChildState2: The child state class.
        GrandchildState: The grandchild state class.
    """
    assert TestState.get_name() == "test_state"
    assert ChildState.get_name() == "child_state"
    assert ChildState2.get_name() == "child_state2"
    assert GrandchildState.get_name() == "grandchild_state"


def test_get_full_name(TestState, ChildState, ChildState2, GrandchildState):
    """Test getting the full name.

    Args:
        TestState: The state class.
        ChildState: The child state class.
        ChildState2: The child state class.
        GrandchildState: The grandchild state class.
    """
    assert TestState.get_full_name() == "test_state"
    assert ChildState.get_full_name() == "test_state.child_state"
    assert ChildState2.get_full_name() == "test_state.child_state2"
    assert GrandchildState.get_full_name() == "test_state.child_state.grandchild_state"


def test_get_class_substate(TestState, ChildState, ChildState2, GrandchildState):
    """Test getting the substate of a class.

    Args:
        TestState: The state class.
        ChildState: The child state class.
        ChildState2: The child state class.
        GrandchildState: The grandchild state class.
    """
    assert TestState.get_class_substate(("child_state",)) == ChildState
    assert TestState.get_class_substate(("child_state2",)) == ChildState2
    assert ChildState.get_class_substate(("grandchild_state",)) == GrandchildState
    assert (
        TestState.get_class_substate(("child_state", "grandchild_state"))
        == GrandchildState
    )
    with pytest.raises(ValueError):
        TestState.get_class_substate(("invalid_child",))
    with pytest.raises(ValueError):
        TestState.get_class_substate(
            (
                "child_state",
                "invalid_child",
            )
        )


def test_get_class_var(TestState, ChildState, ChildState2, GrandchildState):
    """Test getting the var of a class.

    Args:
        TestState: The state class.
        ChildState: The child state class.
        ChildState2: The child state class.
        GrandchildState: The grandchild state class.
    """
    assert TestState.get_class_var(("num1",)) == TestState.num1
    assert TestState.get_class_var(("num2",)) == TestState.num2
    assert ChildState.get_class_var(("value",)) == ChildState.value
    assert GrandchildState.get_class_var(("value2",)) == GrandchildState.value2
    assert TestState.get_class_var(("child_state", "value")) == ChildState.value
    assert (
        TestState.get_class_var(("child_state", "grandchild_state", "value2"))
        == GrandchildState.value2
    )
    assert (
        ChildState.get_class_var(("grandchild_state", "value2"))
        == GrandchildState.value2
    )
    with pytest.raises(ValueError):
        TestState.get_class_var(("invalid_var",))
    with pytest.raises(ValueError):
        TestState.get_class_var(
            (
                "child_state",
                "invalid_var",
            )
        )


def test_set_class_var(TestState):
    """Test setting the var of a class.

    Args:
        TestState: The state class.
    """
    with pytest.raises(AttributeError):
        TestState.num3
    TestState._set_var(BaseVar(name="num3", type_=int).set_state(TestState))
    var = TestState.num3
    assert var.name == "num3"
    assert var.type_ == int
    assert var.state == TestState.get_full_name()


def test_set_parent_and_substates(TestState, ChildState, ChildState2, GrandchildState):
    """Test setting the parent and substates.

    Args:
        TestState: The state class.
        ChildState: The child state class.
        ChildState2: The child state class.
        GrandchildState: The grandchild state class.
    """
    test_state = TestState()
    assert len(test_state.substates) == 2
    assert set(test_state.substates) == {"child_state", "child_state2"}

    child_state = test_state.substates["child_state"]
    assert child_state.parent_state == test_state
    assert len(child_state.substates) == 1
    assert set(child_state.substates) == {"grandchild_state"}

    grandchild_state = child_state.substates["grandchild_state"]
    assert grandchild_state.parent_state == child_state
    assert len(grandchild_state.substates) == 0


def test_get_child_attribute(TestState, ChildState, ChildState2, GrandchildState):
    """Test getting the attribute of a state.

    Args:
        TestState: The state class.
        ChildState: The child state class.
        ChildState2: The child state class.
        GrandchildState: The grandchild state class.
    """
    test_state = TestState()
    child_state = test_state.get_substate(["child_state"])
    child_state2 = test_state.get_substate(["child_state2"])
    grandchild_state = child_state.get_substate(["grandchild_state"])

    assert test_state.num1 == 0
    assert child_state.value == ""
    assert child_state2.value == ""
    assert child_state.count == 23
    assert grandchild_state.value2 == ""
    with pytest.raises(AttributeError):
        test_state.invalid
    with pytest.raises(AttributeError):
        test_state.child_state.invalid
    with pytest.raises(AttributeError):
        test_state.child_state.grandchild_state.invalid


def test_set_child_attribute(TestState, ChildState, ChildState2, GrandchildState):
    """Test setting the attribute of a state.

    Args:
        TestState: The state class.
        ChildState: The child state class.
        ChildState2: The child state class.
        GrandchildState: The grandchild state class.
    """
    test_state = TestState()
    child_state = test_state.get_substate(["child_state"])
    grandchild_state = child_state.get_substate(["grandchild_state"])

    test_state.num1 = 10
    assert test_state.num1 == 10
    child_state.value = "test"
    assert child_state.value == "test"
    grandchild_state.value2 = "test2"
    assert grandchild_state.value2 == "test2"


def test_get_substate(TestState, ChildState, ChildState2, GrandchildState):
    """Test getting the substate of a state.

    Args:
        TestState: The state class.
        ChildState: The child state class.
        ChildState2: The child state class.
        GrandchildState: The grandchild state class.
    """
    test_state = TestState()
    child_state = test_state.substates["child_state"]
    child_state2 = test_state.substates["child_state2"]
    grandchild_state = child_state.substates["grandchild_state"]

    assert test_state.get_substate(("child_state",)) == child_state
    assert test_state.get_substate(("child_state2",)) == child_state2
    assert (
        test_state.get_substate(("child_state", "grandchild_state")) == grandchild_state
    )
    assert child_state.get_substate(("grandchild_state",)) == grandchild_state
    with pytest.raises(ValueError):
        test_state.get_substate(("invalid",))
    with pytest.raises(ValueError):
        test_state.get_substate(("child_state", "invalid"))
    with pytest.raises(ValueError):
        test_state.get_substate(("child_state", "grandchild_state", "invalid"))


def test_set_dirty_var(TestState):
    """Test changing state vars marks the value as dirty.

    Args:
        TestState: The state class.
    """
    test_state = TestState()

    # Initially there should be no dirty vars.
    assert test_state.dirty_vars == set()

    # Setting a var should mark it as dirty.
    test_state.num1 = 1
    assert test_state.dirty_vars == {"num1"}

    # Setting another var should mark it as dirty.
    test_state.num2 = 2
    assert test_state.dirty_vars == {"num1", "num2"}

    # Cleaning the state should remove all dirty vars.
    test_state.clean()
    assert test_state.dirty_vars == set()


def test_set_dirty_substate(TestState, ChildState, ChildState2, GrandchildState):
    """Test changing substate vars marks the value as dirty.

    Args:
        TestState: The state class.
        ChildState: The child state class.
        ChildState2: The child state class.
        GrandchildState: The grandchild state class.
    """
    test_state = TestState()
    child_state = test_state.get_substate(["child_state"])
    child_state2 = test_state.get_substate(["child_state2"])
    grandchild_state = child_state.get_substate(["grandchild_state"])

    # Initially there should be no dirty vars.
    assert test_state.dirty_vars == set()
    assert child_state.dirty_vars == set()
    assert child_state2.dirty_vars == set()
    assert grandchild_state.dirty_vars == set()

    # Setting a var should mark it as dirty.
    child_state.value = "test"
    assert child_state.dirty_vars == {"value"}
    assert test_state.dirty_substates == {"child_state"}
    assert child_state.dirty_substates == set()

    # Cleaning the parent state should remove the dirty substate.
    test_state.clean()
    assert test_state.dirty_substates == set()
    assert child_state.dirty_vars == set()

    # Setting a var on the grandchild should bubble up.
    grandchild_state.value2 = "test2"
    assert child_state.dirty_substates == {"grandchild_state"}
    assert test_state.dirty_substates == {"child_state"}

    # Cleaning the middle state should keep the parent state dirty.
    child_state.clean()
    assert test_state.dirty_substates == {"child_state"}
    assert child_state.dirty_substates == set()
    assert grandchild_state.dirty_vars == set()


def test_reset(TestState, ChildState):
    """Test resetting the state.

    Args:
        TestState: The state class.
        ChildState: The child state class.
    """
    test_state = TestState()
    child_state = test_state.get_substate(["child_state"])

    # Set some values.
    test_state.num1 = 1
    test_state.num2 = 2
    child_state.value = "test"

    # Reset the state.
    test_state.reset()

    # The values should be reset.
    assert test_state.num1 == 0
    assert test_state.num2 == 3.14
    assert child_state.value == ""

    # The dirty vars should be reset.
    assert test_state.dirty_vars == set()
    assert child_state.dirty_vars == set()

    # The dirty substates should be reset.
    assert test_state.dirty_substates == set()


@pytest.mark.asyncio
async def test_process_event_simple(TestState):
    """Test processing an event.

    Args:
        TestState: The state class.
    """
    test_state = TestState()
    assert test_state.num1 == 0

    event = Event(token="t", name="set_num1", payload={"value": 69})
    update = await test_state.process(event)

    # The event should update the value.
    assert test_state.num1 == 69

    # The delta should contain the changes, including computed vars.
    assert update.delta == {"test_state": {"num1": 69, "sum": 72.14, "upper": ""}}
    assert update.events == []


@pytest.mark.asyncio
async def test_process_event_substate(TestState, ChildState, GrandchildState):
    """Test processing an event on a substate.

    Args:
        TestState: The state class.
        ChildState: The child state class.
        GrandchildState: The grandchild state class.
    """
    test_state = TestState()
    child_state = test_state.get_substate(["child_state"])
    grandchild_state = child_state.get_substate(["grandchild_state"])

    # Events should bubble down to the substate.
    assert child_state.value == ""
    assert child_state.count == 23
    event = Event(
        token="t", name="child_state.change_both", payload={"value": "hi", "count": 12}
    )
    update = await test_state.process(event)
    assert child_state.value == "HI"
    assert child_state.count == 24
    assert update.delta == {
        "test_state.child_state": {"value": "HI", "count": 24},
        "test_state": {"sum": 3.14, "upper": ""},
    }
    test_state.clean()

    # Test with the granchild state.
    assert grandchild_state.value2 == ""
    event = Event(
        token="t",
        name="child_state.grandchild_state.set_value2",
        payload={"value": "new"},
    )
    update = await test_state.process(event)
    assert grandchild_state.value2 == "new"
    assert update.delta == {
        "test_state.child_state.grandchild_state": {"value2": "new"},
        "test_state": {"sum": 3.14, "upper": ""},
    }
