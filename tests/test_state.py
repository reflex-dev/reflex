from typing import Dict, List

import pytest
from plotly.graph_objects import Figure

import pynecone as pc
from pynecone.base import Base
from pynecone.constants import IS_HYDRATED, RouteVar
from pynecone.event import Event, EventHandler
from pynecone.state import State
from pynecone.utils import format
from pynecone.vars import BaseVar, ComputedVar


class Object(Base):
    """A test object fixture."""

    prop1: int = 42
    prop2: str = "hello"


class TestState(State):
    """A test state."""

    # Set this class as not test one
    __test__ = False

    num1: int
    num2: float = 3.14
    key: str
    array: List[float] = [1, 2, 3.14]
    mapping: Dict[str, List[int]] = {"a": [1, 2, 3], "b": [4, 5, 6]}
    obj: Object = Object()
    complex: Dict[int, Object] = {1: Object(), 2: Object()}
    fig: Figure = Figure()

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


class ChildState2(TestState):
    """A child state fixture."""

    value: str


class GrandchildState(ChildState):
    """A grandchild state fixture."""

    value2: str

    def do_nothing(self):
        """Do something."""
        pass


@pytest.fixture
def test_state() -> TestState:
    """A state.

    Returns:
        A test state.
    """
    return TestState()  # type: ignore


@pytest.fixture
def child_state(test_state) -> ChildState:
    """A child state.

    Args:
        test_state: A test state.

    Returns:
        A test child state.
    """
    child_state = test_state.get_substate(["child_state"])
    assert child_state is not None
    return child_state


@pytest.fixture
def child_state2(test_state) -> ChildState2:
    """A second child state.

    Args:
        test_state: A test state.

    Returns:
        A second test child state.
    """
    child_state2 = test_state.get_substate(["child_state2"])
    assert child_state2 is not None
    return child_state2


@pytest.fixture
def grandchild_state(child_state) -> GrandchildState:
    """A state.

    Args:
        child_state: A child state.

    Returns:
        A test state.
    """
    grandchild_state = child_state.get_substate(["grandchild_state"])
    assert grandchild_state is not None
    return grandchild_state


def test_base_class_vars(test_state):
    """Test that the class vars are set correctly.

    Args:
        test_state: A state.
    """
    fields = test_state.get_fields()
    cls = type(test_state)

    for field in fields:
        if field in test_state.get_skip_vars():
            continue
        prop = getattr(cls, field)
        assert isinstance(prop, BaseVar)
        assert prop.name == field

    assert cls.num1.type_ == int
    assert cls.num2.type_ == float
    assert cls.key.type_ == str


def test_computed_class_var(test_state):
    """Test that the class computed vars are set correctly.

    Args:
        test_state: A state.
    """
    cls = type(test_state)
    vars = [(prop.name, prop.type_) for prop in cls.computed_vars.values()]
    assert ("sum", float) in vars
    assert ("upper", str) in vars


def test_class_vars(test_state):
    """Test that the class vars are set correctly.

    Args:
        test_state: A state.
    """
    cls = type(test_state)
    assert set(cls.vars.keys()) == {
        IS_HYDRATED,  # added by hydrate_middleware to all State
        "num1",
        "num2",
        "key",
        "array",
        "mapping",
        "obj",
        "complex",
        "sum",
        "upper",
        "fig",
    }


def test_event_handlers(test_state):
    """Test that event handler is set correctly.

    Args:
        test_state: A state.
    """
    expected = {
        "do_something",
        "set_array",
        "set_complex",
        "set_fig",
        "set_key",
        "set_mapping",
        "set_num1",
        "set_num2",
        "set_obj",
    }

    cls = type(test_state)
    assert set(cls.event_handlers.keys()).intersection(expected) == expected


def test_default_value(test_state):
    """Test that the default value of a var is correct.

    Args:
        test_state: A state.
    """
    assert test_state.num1 == 0
    assert test_state.num2 == 3.14
    assert test_state.key == ""
    assert test_state.sum == 3.14
    assert test_state.upper == ""


def test_computed_vars(test_state):
    """Test that the computed var is computed correctly.

    Args:
        test_state: A state.
    """
    test_state.num1 = 1
    test_state.num2 = 4
    assert test_state.sum == 5
    test_state.key = "hello world"
    assert test_state.upper == "HELLO WORLD"


def test_dict(test_state):
    """Test that the dict representation of a state is correct.

    Args:
        test_state: A state.
    """
    substates = {"child_state", "child_state2"}
    assert set(test_state.dict().keys()) == set(test_state.vars.keys()) | substates
    assert (
        set(test_state.dict(include_computed=False).keys())
        == set(test_state.base_vars) | substates
    )


def test_default_setters(test_state):
    """Test that we can set default values.

    Args:
        test_state: A state.
    """
    for prop_name in test_state.base_vars:
        # Each base var should have a default setter.
        assert hasattr(test_state, f"set_{prop_name}")


def test_class_indexing_with_vars():
    """Test that we can index into a state var with another var."""
    prop = TestState.array[TestState.num1]
    assert str(prop) == "{test_state.array.at(test_state.num1)}"

    prop = TestState.mapping["a"][TestState.num1]
    assert str(prop) == '{test_state.mapping["a"].at(test_state.num1)}'


def test_class_attributes():
    """Test that we can get class attributes."""
    prop = TestState.obj.prop1
    assert str(prop) == "{test_state.obj.prop1}"

    prop = TestState.complex[1].prop1
    assert str(prop) == "{test_state.complex[1].prop1}"


def test_get_parent_state():
    """Test getting the parent state."""
    assert TestState.get_parent_state() is None
    assert ChildState.get_parent_state() == TestState
    assert ChildState2.get_parent_state() == TestState
    assert GrandchildState.get_parent_state() == ChildState


def test_get_substates():
    """Test getting the substates."""
    assert TestState.get_substates() == {ChildState, ChildState2}
    assert ChildState.get_substates() == {GrandchildState}
    assert ChildState2.get_substates() == set()
    assert GrandchildState.get_substates() == set()


def test_get_name():
    """Test getting the name of a state."""
    assert TestState.get_name() == "test_state"
    assert ChildState.get_name() == "child_state"
    assert ChildState2.get_name() == "child_state2"
    assert GrandchildState.get_name() == "grandchild_state"


def test_get_full_name():
    """Test getting the full name."""
    assert TestState.get_full_name() == "test_state"
    assert ChildState.get_full_name() == "test_state.child_state"
    assert ChildState2.get_full_name() == "test_state.child_state2"
    assert GrandchildState.get_full_name() == "test_state.child_state.grandchild_state"


def test_get_class_substate():
    """Test getting the substate of a class."""
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


def test_get_class_var():
    """Test getting the var of a class."""
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


def test_set_class_var():
    """Test setting the var of a class."""
    with pytest.raises(AttributeError):
        TestState.num3  # type: ignore
    TestState._set_var(BaseVar(name="num3", type_=int).set_state(TestState))
    var = TestState.num3  # type: ignore
    assert var.name == "num3"
    assert var.type_ == int
    assert var.state == TestState.get_full_name()


def test_set_parent_and_substates(test_state, child_state, grandchild_state):
    """Test setting the parent and substates.

    Args:
        test_state: A state.
        child_state: A child state.
        grandchild_state: A grandchild state.
    """
    assert len(test_state.substates) == 2
    assert set(test_state.substates) == {"child_state", "child_state2"}

    assert child_state.parent_state == test_state
    assert len(child_state.substates) == 1
    assert set(child_state.substates) == {"grandchild_state"}

    assert grandchild_state.parent_state == child_state
    assert len(grandchild_state.substates) == 0


def test_get_child_attribute(test_state, child_state, child_state2, grandchild_state):
    """Test getting the attribute of a state.

    Args:
        test_state: A state.
        child_state: A child state.
        child_state2: A child state.
        grandchild_state: A grandchild state.
    """
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


def test_set_child_attribute(test_state, child_state, grandchild_state):
    """Test setting the attribute of a state.

    Args:
        test_state: A state.
        child_state: A child state.
        grandchild_state: A grandchild state.
    """
    test_state.num1 = 10
    assert test_state.num1 == 10
    assert child_state.num1 == 10
    assert grandchild_state.num1 == 10

    grandchild_state.num1 = 5
    assert test_state.num1 == 5
    assert child_state.num1 == 5
    assert grandchild_state.num1 == 5

    child_state.value = "test"
    assert child_state.value == "test"
    assert grandchild_state.value == "test"

    grandchild_state.value = "test2"
    assert child_state.value == "test2"
    assert grandchild_state.value == "test2"

    grandchild_state.value2 = "test3"
    assert grandchild_state.value2 == "test3"


def test_get_substate(test_state, child_state, child_state2, grandchild_state):
    """Test getting the substate of a state.

    Args:
        test_state: A state.
        child_state: A child state.
        child_state2: A child state.
        grandchild_state: A grandchild state.
    """
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


def test_set_dirty_var(test_state):
    """Test changing state vars marks the value as dirty.

    Args:
        test_state: A state.
    """
    # Initially there should be no dirty vars.
    assert test_state.dirty_vars == set()

    # Setting a var should mark it as dirty.
    test_state.num1 = 1
    assert test_state.dirty_vars == {"num1", "sum"}

    # Setting another var should mark it as dirty.
    test_state.num2 = 2
    assert test_state.dirty_vars == {"num1", "num2", "sum"}

    # Cleaning the state should remove all dirty vars.
    test_state.clean()
    assert test_state.dirty_vars == set()


def test_set_dirty_substate(test_state, child_state, child_state2, grandchild_state):
    """Test changing substate vars marks the value as dirty.

    Args:
        test_state: A state.
        child_state: A child state.
        child_state2: A child state.
        grandchild_state: A grandchild state.
    """
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


def test_reset(test_state, child_state):
    """Test resetting the state.

    Args:
        test_state: A state.
        child_state: A child state.
    """
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
async def test_process_event_simple(test_state):
    """Test processing an event.

    Args:
        test_state: A state.
    """
    assert test_state.num1 == 0

    event = Event(token="t", name="set_num1", payload={"value": 69})
    update = await test_state._process(event)

    # The event should update the value.
    assert test_state.num1 == 69

    # The delta should contain the changes, including computed vars.
    # assert update.delta == {"test_state": {"num1": 69, "sum": 72.14}}
    assert update.delta == {"test_state": {"num1": 69, "sum": 72.14, "upper": ""}}
    assert update.events == []


@pytest.mark.asyncio
async def test_process_event_substate(test_state, child_state, grandchild_state):
    """Test processing an event on a substate.

    Args:
        test_state: A state.
        child_state: A child state.
        grandchild_state: A grandchild state.
    """
    # Events should bubble down to the substate.
    assert child_state.value == ""
    assert child_state.count == 23
    event = Event(
        token="t", name="child_state.change_both", payload={"value": "hi", "count": 12}
    )
    update = await test_state._process(event)
    assert child_state.value == "HI"
    assert child_state.count == 24
    assert update.delta == {
        "test_state": {"sum": 3.14, "upper": ""},
        "test_state.child_state": {"value": "HI", "count": 24},
    }
    test_state.clean()

    # Test with the granchild state.
    assert grandchild_state.value2 == ""
    event = Event(
        token="t",
        name="child_state.grandchild_state.set_value2",
        payload={"value": "new"},
    )
    update = await test_state._process(event)
    assert grandchild_state.value2 == "new"
    assert update.delta == {
        "test_state": {"sum": 3.14, "upper": ""},
        "test_state.child_state.grandchild_state": {"value2": "new"},
    }


def test_format_event_handler():
    """Test formatting an event handler."""
    assert (
        format.format_event_handler(TestState.do_something) == "test_state.do_something"  # type: ignore
    )
    assert (
        format.format_event_handler(ChildState.change_both)  # type: ignore
        == "test_state.child_state.change_both"
    )
    assert (
        format.format_event_handler(GrandchildState.do_nothing)  # type: ignore
        == "test_state.child_state.grandchild_state.do_nothing"
    )


def test_get_token(test_state):
    assert test_state.get_token() == ""

    token = "b181904c-3953-4a79-dc18-ae9518c22f05"
    test_state.router_data = {RouteVar.CLIENT_TOKEN: token}

    assert test_state.get_token() == token


def test_get_sid(test_state):
    """Test getting session id.

    Args:
        test_state: A state.
    """
    assert test_state.get_sid() == ""

    sid = "9fpxSzPb9aFMb4wFAAAH"
    test_state.router_data = {RouteVar.SESSION_ID: sid}

    assert test_state.get_sid() == sid


def test_get_headers(test_state):
    """Test getting client headers.

    Args:
        test_state: A state.
    """
    assert test_state.get_headers() == {}

    headers = {"host": "localhost:8000", "connection": "keep-alive"}
    test_state.router_data = {RouteVar.HEADERS: headers}

    assert test_state.get_headers() == headers


def test_get_client_ip(test_state):
    """Test getting client IP.

    Args:
        test_state: A state.
    """
    assert test_state.get_client_ip() == ""

    client_ip = "127.0.0.1"
    test_state.router_data = {RouteVar.CLIENT_IP: client_ip}

    assert test_state.get_client_ip() == client_ip


def test_get_current_page(test_state):
    assert test_state.get_current_page() == ""

    route = "mypage/subpage"
    test_state.router_data = {RouteVar.PATH: route}

    assert test_state.get_current_page() == route


def test_get_query_params(test_state):
    assert test_state.get_query_params() == {}

    params = {"p1": "a", "p2": "b"}
    test_state.router_data = {RouteVar.QUERY: params}

    assert test_state.get_query_params() == params


def test_add_var(test_state):
    test_state.add_var("dynamic_int", int, 42)
    assert test_state.dynamic_int == 42

    test_state.add_var("dynamic_list", List[int], [5, 10])
    assert test_state.dynamic_list == [5, 10]
    assert test_state.dynamic_list == [5, 10]

    # how to test that one?
    # test_state.dynamic_list.append(15)
    # assert test_state.dynamic_list == [5, 10, 15]

    test_state.add_var("dynamic_dict", Dict[str, int], {"k1": 5, "k2": 10})
    assert test_state.dynamic_dict == {"k1": 5, "k2": 10}
    assert test_state.dynamic_dict == {"k1": 5, "k2": 10}


def test_add_var_default_handlers(test_state):
    test_state.add_var("rand_int", int, 10)
    assert "set_rand_int" in test_state.event_handlers
    assert isinstance(test_state.event_handlers["set_rand_int"], EventHandler)


class InterdependentState(State):
    """A state with 3 vars and 3 computed vars.

    x: a variable that no computed var depends on
    v1: a varable that one computed var directly depeneds on
    _v2: a backend variable that one computed var directly depends on

    v1x2: a computed var that depends on v1
    v2x2: a computed var that depends on backend var _v2
    v1x2x2: a computed var that depends on computed var v1x2
    """

    x: int = 0
    v1: int = 0
    _v2: int = 1

    @pc.cached_var
    def v1x2(self) -> int:
        """Depends on var v1.

        Returns:
            Var v1 multiplied by 2
        """
        return self.v1 * 2

    @pc.cached_var
    def v2x2(self) -> int:
        """Depends on backend var _v2.

        Returns:
            backend var _v2 multiplied by 2
        """
        return self._v2 * 2

    @pc.cached_var
    def v1x2x2(self) -> int:
        """Depends on ComputedVar v1x2.

        Returns:
            ComputedVar v1x2 multiplied by 2
        """
        return self.v1x2 * 2


@pytest.fixture
def interdependent_state() -> State:
    """A state with varying dependency between vars.

    Returns:
        instance of InterdependentState
    """
    s = InterdependentState()
    s.dict()  # prime initial relationships by accessing all ComputedVars
    return s


def test_not_dirty_computed_var_from_var(interdependent_state):
    """Set Var that no ComputedVar depends on, expect no recalculation.

    Args:
        interdependent_state: A state with varying Var dependencies.
    """
    interdependent_state.x = 5
    assert interdependent_state.get_delta() == {
        interdependent_state.get_full_name(): {"x": 5},
    }


def test_dirty_computed_var_from_var(interdependent_state):
    """Set Var that ComputedVar depends on, expect recalculation.

    The other ComputedVar depends on the changed ComputedVar and should also be
    recalculated. No other ComputedVars should be recalculated.

    Args:
        interdependent_state: A state with varying Var dependencies.
    """
    interdependent_state.v1 = 1
    assert interdependent_state.get_delta() == {
        interdependent_state.get_full_name(): {"v1": 1, "v1x2": 2, "v1x2x2": 4},
    }


def test_dirty_computed_var_from_backend_var(interdependent_state):
    """Set backend var that ComputedVar depends on, expect recalculation.

    Args:
        interdependent_state: A state with varying Var dependencies.
    """
    interdependent_state._v2 = 2
    assert interdependent_state.get_delta() == {
        interdependent_state.get_full_name(): {"v2x2": 4},
    }


def test_per_state_backend_var(interdependent_state):
    """Set backend var on one instance, expect no affect in other instances.

    Args:
        interdependent_state: A state with varying Var dependencies.
    """
    s2 = InterdependentState()
    assert s2._v2 == interdependent_state._v2
    interdependent_state._v2 = 2
    assert s2._v2 != interdependent_state._v2
    s3 = InterdependentState()
    assert s3._v2 != interdependent_state._v2
    # both s2 and s3 should still have the default value
    assert s2._v2 == s3._v2
    # changing s2._v2 should not affect others
    s2._v2 = 4
    assert s2._v2 != interdependent_state._v2
    assert s2._v2 != s3._v2


def test_child_state():
    """Test that the child state computed vars can reference parent state vars."""

    class MainState(State):
        v: int = 2

    class ChildState(MainState):
        @ComputedVar
        def rendered_var(self):
            return self.v

    ms = MainState()
    cs = ms.substates[ChildState.get_name()]
    assert ms.v == 2
    assert cs.v == 2
    assert cs.rendered_var == 2


def test_conditional_computed_vars():
    """Test that computed vars can have conditionals."""

    class MainState(State):
        flag: bool = False
        t1: str = "a"
        t2: str = "b"

        @ComputedVar
        def rendered_var(self) -> str:
            if self.flag:
                return self.t1
            return self.t2

    ms = MainState()
    # Initially there are no dirty computed vars.
    assert ms._dirty_computed_vars(from_vars={"flag"}) == {"rendered_var"}
    assert ms._dirty_computed_vars(from_vars={"t2"}) == {"rendered_var"}
    assert ms._dirty_computed_vars(from_vars={"t1"}) == {"rendered_var"}
    assert ms.computed_vars["rendered_var"].deps(objclass=MainState) == {
        "flag",
        "t1",
        "t2",
    }


def test_event_handlers_convert_to_fns(test_state, child_state):
    """Test that when the state is initialized, event handlers are converted to fns.

    Args:
        test_state: A state with event handlers.
        child_state: A child state with event handlers.
    """
    # The class instances should be event handlers.
    assert isinstance(TestState.do_something, EventHandler)
    assert isinstance(ChildState.change_both, EventHandler)

    # The object instances should be fns.
    test_state.do_something()

    child_state.change_both(value="goose", count=9)
    assert child_state.value == "GOOSE"
    assert child_state.count == 18


def test_event_handlers_call_other_handlers():
    """Test that event handlers can call other event handlers."""

    class MainState(State):
        v: int = 0

        def set_v(self, v: int):
            self.v = v

        def set_v2(self, v: int):
            self.set_v(v)

    ms = MainState()
    ms.set_v2(1)
    assert ms.v == 1


def test_computed_var_cached():
    """Test that a ComputedVar doesn't recalculate when accessed."""
    comp_v_calls = 0

    class ComputedState(State):
        v: int = 0

        @pc.cached_var
        def comp_v(self) -> int:
            nonlocal comp_v_calls
            comp_v_calls += 1
            return self.v

    cs = ComputedState()
    assert cs.dict()["v"] == 0
    assert comp_v_calls == 1
    assert cs.dict()["comp_v"] == 0
    assert comp_v_calls == 1
    assert cs.comp_v == 0
    assert comp_v_calls == 1
    cs.v = 1
    assert comp_v_calls == 1
    assert cs.comp_v == 1
    assert comp_v_calls == 2


def test_computed_var_cached_depends_on_non_cached():
    """Test that a cached_var is recalculated if it depends on non-cached ComputedVar."""

    class ComputedState(State):
        v: int = 0

        @pc.var
        def no_cache_v(self) -> int:
            return self.v

        @pc.cached_var
        def dep_v(self) -> int:
            return self.no_cache_v

        @pc.cached_var
        def comp_v(self) -> int:
            return self.v

    cs = ComputedState()
    assert cs.dirty_vars == set()
    assert cs.get_delta() == {cs.get_name(): {"no_cache_v": 0, "dep_v": 0}}
    cs.clean()
    assert cs.dirty_vars == set()
    assert cs.get_delta() == {cs.get_name(): {"no_cache_v": 0, "dep_v": 0}}
    cs.clean()
    assert cs.dirty_vars == set()
    cs.v = 1
    assert cs.dirty_vars == {"v", "comp_v", "dep_v", "no_cache_v"}
    assert cs.get_delta() == {
        cs.get_name(): {"v": 1, "no_cache_v": 1, "dep_v": 1, "comp_v": 1}
    }
    cs.clean()
    assert cs.dirty_vars == set()
    assert cs.get_delta() == {cs.get_name(): {"no_cache_v": 1, "dep_v": 1}}
    cs.clean()
    assert cs.dirty_vars == set()
    assert cs.get_delta() == {cs.get_name(): {"no_cache_v": 1, "dep_v": 1}}
    cs.clean()
    assert cs.dirty_vars == set()


def test_computed_var_depends_on_parent_non_cached():
    """Child state cached_var that depends on parent state un cached var is always recalculated."""
    counter = 0

    class ParentState(State):
        @pc.var
        def no_cache_v(self) -> int:
            nonlocal counter
            counter += 1
            return counter

    class ChildState(ParentState):
        @pc.cached_var
        def dep_v(self) -> int:
            return self.no_cache_v

    ps = ParentState()
    cs = ps.substates[ChildState.get_name()]

    assert ps.dirty_vars == set()
    assert cs.dirty_vars == set()

    assert ps.dict() == {
        cs.get_name(): {"dep_v": 2},
        "no_cache_v": 1,
        IS_HYDRATED: False,
    }
    assert ps.dict() == {
        cs.get_name(): {"dep_v": 4},
        "no_cache_v": 3,
        IS_HYDRATED: False,
    }
    assert ps.dict() == {
        cs.get_name(): {"dep_v": 6},
        "no_cache_v": 5,
        IS_HYDRATED: False,
    }
    assert counter == 6
