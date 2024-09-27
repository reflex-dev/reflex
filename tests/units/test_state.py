from __future__ import annotations

import asyncio
import copy
import dataclasses
import datetime
import functools
import json
import os
import sys
from textwrap import dedent
from typing import Any, Callable, Dict, Generator, List, Optional, Union
from unittest.mock import AsyncMock, Mock

import pytest
from plotly.graph_objects import Figure

import reflex as rx
import reflex.config
from reflex import constants
from reflex.app import App
from reflex.base import Base
from reflex.components.sonner.toast import Toaster
from reflex.constants import CompileVars, RouteVar, SocketEvent
from reflex.event import Event, EventHandler
from reflex.state import (
    BaseState,
    ImmutableStateError,
    LockExpiredError,
    MutableProxy,
    OnLoadInternalState,
    RouterData,
    State,
    StateManager,
    StateManagerDisk,
    StateManagerMemory,
    StateManagerRedis,
    StateProxy,
    StateUpdate,
    _substate_key,
)
from reflex.testing import chdir
from reflex.utils import format, prerequisites, types
from reflex.utils.format import json_dumps
from reflex.vars.base import ComputedVar, Var
from tests.units.states.mutation import MutableSQLAModel, MutableTestState

from .states import GenState

CI = bool(os.environ.get("CI", False))
LOCK_EXPIRATION = 2000 if CI else 300
LOCK_EXPIRE_SLEEP = 2.5 if CI else 0.4


formatted_router = {
    "session": {"client_token": "", "client_ip": "", "session_id": ""},
    "headers": {
        "host": "",
        "origin": "",
        "upgrade": "",
        "connection": "",
        "cookie": "",
        "pragma": "",
        "cache_control": "",
        "user_agent": "",
        "sec_websocket_version": "",
        "sec_websocket_key": "",
        "sec_websocket_extensions": "",
        "accept_encoding": "",
        "accept_language": "",
    },
    "page": {
        "host": "",
        "path": "",
        "raw_path": "",
        "full_path": "",
        "full_raw_path": "",
        "params": {},
    },
}


class Object(Base):
    """A test object fixture."""

    prop1: int = 42
    prop2: str = "hello"


class TestState(BaseState):
    """A test state."""

    # Set this class as not test one
    __test__ = False

    num1: int
    num2: float = 3.14
    key: str
    map_key: str = "a"
    array: List[float] = [1, 2, 3.14]
    mapping: Dict[str, List[int]] = {"a": [1, 2, 3], "b": [4, 5, 6]}
    obj: Object = Object()
    complex: Dict[int, Object] = {1: Object(), 2: Object()}
    fig: Figure = Figure()
    dt: datetime.datetime = datetime.datetime.fromisoformat("1989-11-09T18:53:00+01:00")

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


class ChildState3(TestState):
    """A child state fixture."""

    value: str


class GrandchildState(ChildState):
    """A grandchild state fixture."""

    value2: str

    def do_nothing(self):
        """Do something."""
        pass


class GrandchildState2(ChildState2):
    """A grandchild state fixture."""

    @rx.var(cache=True)
    def cached(self) -> str:
        """A cached var.

        Returns:
            The value.
        """
        return self.value


class GrandchildState3(ChildState3):
    """A great grandchild state fixture."""

    @rx.var
    def computed(self) -> str:
        """A computed var.

        Returns:
            The value.
        """
        return self.value


class DateTimeState(BaseState):
    """A State with some datetime fields."""

    d: datetime.date = datetime.date.fromisoformat("1989-11-09")
    dt: datetime.datetime = datetime.datetime.fromisoformat("1989-11-09T18:53:00+01:00")
    t: datetime.time = datetime.time.fromisoformat("18:53:00+01:00")
    td: datetime.timedelta = datetime.timedelta(days=11, minutes=11)


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
    child_state = test_state.get_substate([ChildState.get_name()])
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
    child_state2 = test_state.get_substate([ChildState2.get_name()])
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
    grandchild_state = child_state.get_substate([GrandchildState.get_name()])
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
        assert isinstance(prop, Var)
        assert prop._js_expr.split(".")[-1] == field

    assert cls.num1._var_type == int
    assert cls.num2._var_type == float
    assert cls.key._var_type == str


def test_computed_class_var(test_state):
    """Test that the class computed vars are set correctly.

    Args:
        test_state: A state.
    """
    cls = type(test_state)
    vars = [(prop._js_expr, prop._var_type) for prop in cls.computed_vars.values()]
    assert ("sum", float) in vars
    assert ("upper", str) in vars


def test_class_vars(test_state):
    """Test that the class vars are set correctly.

    Args:
        test_state: A state.
    """
    cls = type(test_state)
    assert cls.vars.keys() == {
        "router",
        "num1",
        "num2",
        "key",
        "map_key",
        "array",
        "mapping",
        "obj",
        "complex",
        "sum",
        "upper",
        "fig",
        "dt",
    }


def test_event_handlers(test_state):
    """Test that event handler is set correctly.

    Args:
        test_state: A state.
    """
    expected_keys = (
        "do_something",
        "set_array",
        "set_complex",
        "set_fig",
        "set_key",
        "set_mapping",
        "set_num1",
        "set_num2",
        "set_obj",
    )

    cls = type(test_state)
    assert all(key in cls.event_handlers for key in expected_keys)


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


def test_dict(test_state: TestState):
    """Test that the dict representation of a state is correct.

    Args:
        test_state: A state.
    """
    substates = {
        test_state.get_full_name(),
        ChildState.get_full_name(),
        GrandchildState.get_full_name(),
        ChildState2.get_full_name(),
        GrandchildState2.get_full_name(),
        ChildState3.get_full_name(),
        GrandchildState3.get_full_name(),
    }
    test_state_dict = test_state.dict()
    assert set(test_state_dict) == substates
    assert set(test_state_dict[test_state.get_name()]) == set(test_state.vars)
    assert set(test_state.dict(include_computed=False)[test_state.get_name()]) == set(
        test_state.base_vars
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
    assert str(prop) == f"{TestState.get_name()}.array.at({TestState.get_name()}.num1)"

    prop = TestState.mapping["a"][TestState.num1]
    assert (
        str(prop)
        == f'{TestState.get_name()}.mapping["a"].at({TestState.get_name()}.num1)'
    )

    prop = TestState.mapping[TestState.map_key]
    assert (
        str(prop) == f"{TestState.get_name()}.mapping[{TestState.get_name()}.map_key]"
    )


def test_class_attributes():
    """Test that we can get class attributes."""
    prop = TestState.obj.prop1
    assert str(prop) == f'{TestState.get_name()}.obj["prop1"]'

    prop = TestState.complex[1].prop1
    assert str(prop) == f'{TestState.get_name()}.complex[1]["prop1"]'


def test_get_parent_state():
    """Test getting the parent state."""
    assert TestState.get_parent_state() is None
    assert ChildState.get_parent_state() == TestState
    assert ChildState2.get_parent_state() == TestState
    assert GrandchildState.get_parent_state() == ChildState


def test_get_substates():
    """Test getting the substates."""
    assert TestState.get_substates() == {ChildState, ChildState2, ChildState3}
    assert ChildState.get_substates() == {GrandchildState}
    assert ChildState2.get_substates() == {GrandchildState2}
    assert GrandchildState.get_substates() == set()
    assert GrandchildState2.get_substates() == set()


def test_get_name():
    """Test getting the name of a state."""
    assert TestState.get_name() == "tests___units___test_state____test_state"
    assert ChildState.get_name() == "tests___units___test_state____child_state"
    assert ChildState2.get_name() == "tests___units___test_state____child_state2"
    assert (
        GrandchildState.get_name() == "tests___units___test_state____grandchild_state"
    )


def test_get_full_name():
    """Test getting the full name."""
    assert TestState.get_full_name() == "tests___units___test_state____test_state"
    assert (
        ChildState.get_full_name()
        == "tests___units___test_state____test_state.tests___units___test_state____child_state"
    )
    assert (
        ChildState2.get_full_name()
        == "tests___units___test_state____test_state.tests___units___test_state____child_state2"
    )
    assert (
        GrandchildState.get_full_name()
        == "tests___units___test_state____test_state.tests___units___test_state____child_state.tests___units___test_state____grandchild_state"
    )


def test_get_class_substate():
    """Test getting the substate of a class."""
    assert TestState.get_class_substate((ChildState.get_name(),)) == ChildState
    assert TestState.get_class_substate((ChildState2.get_name(),)) == ChildState2
    assert (
        ChildState.get_class_substate((GrandchildState.get_name(),)) == GrandchildState
    )
    assert (
        TestState.get_class_substate(
            (ChildState.get_name(), GrandchildState.get_name())
        )
        == GrandchildState
    )
    with pytest.raises(ValueError):
        TestState.get_class_substate(("invalid_child",))
    with pytest.raises(ValueError):
        TestState.get_class_substate(
            (
                ChildState.get_name(),
                "invalid_child",
            )
        )


def test_get_class_var():
    """Test getting the var of a class."""
    assert TestState.get_class_var(("num1",)).equals(TestState.num1)
    assert TestState.get_class_var(("num2",)).equals(TestState.num2)
    assert ChildState.get_class_var(("value",)).equals(ChildState.value)
    assert GrandchildState.get_class_var(("value2",)).equals(GrandchildState.value2)
    assert TestState.get_class_var((ChildState.get_name(), "value")).equals(
        ChildState.value
    )
    assert TestState.get_class_var(
        (ChildState.get_name(), GrandchildState.get_name(), "value2")
    ).equals(
        GrandchildState.value2,
    )
    assert ChildState.get_class_var((GrandchildState.get_name(), "value2")).equals(
        GrandchildState.value2,
    )
    with pytest.raises(ValueError):
        TestState.get_class_var(("invalid_var",))
    with pytest.raises(ValueError):
        TestState.get_class_var(
            (
                ChildState.get_name(),
                "invalid_var",
            )
        )


def test_set_class_var():
    """Test setting the var of a class."""
    with pytest.raises(AttributeError):
        TestState.num3  # type: ignore
    TestState._set_var(Var(_js_expr="num3", _var_type=int)._var_set_state(TestState))
    var = TestState.num3  # type: ignore
    assert var._js_expr == TestState.get_full_name() + ".num3"
    assert var._var_type == int
    assert var._var_state == TestState.get_full_name()


def test_set_parent_and_substates(test_state, child_state, grandchild_state):
    """Test setting the parent and substates.

    Args:
        test_state: A state.
        child_state: A child state.
        grandchild_state: A grandchild state.
    """
    assert len(test_state.substates) == 3
    assert set(test_state.substates) == {
        ChildState.get_name(),
        ChildState2.get_name(),
        ChildState3.get_name(),
    }

    assert child_state.parent_state == test_state
    assert len(child_state.substates) == 1
    assert set(child_state.substates) == {GrandchildState.get_name()}

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
    assert test_state.get_substate((ChildState.get_name(),)) == child_state
    assert test_state.get_substate((ChildState2.get_name(),)) == child_state2
    assert (
        test_state.get_substate((ChildState.get_name(), GrandchildState.get_name()))
        == grandchild_state
    )
    assert child_state.get_substate((GrandchildState.get_name(),)) == grandchild_state
    with pytest.raises(ValueError):
        test_state.get_substate(("invalid",))
    with pytest.raises(ValueError):
        test_state.get_substate((ChildState.get_name(), "invalid"))
    with pytest.raises(ValueError):
        test_state.get_substate(
            (ChildState.get_name(), GrandchildState.get_name(), "invalid")
        )


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
    test_state._clean()
    assert test_state.dirty_vars == set()


def test_set_dirty_substate(
    test_state: TestState,
    child_state: ChildState,
    child_state2: ChildState2,
    grandchild_state: GrandchildState,
):
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
    assert test_state.dirty_substates == {ChildState.get_name()}
    assert child_state.dirty_substates == set()

    # Cleaning the parent state should remove the dirty substate.
    test_state._clean()
    assert test_state.dirty_substates == set()
    assert child_state.dirty_vars == set()

    # Setting a var on the grandchild should bubble up.
    grandchild_state.value2 = "test2"
    assert child_state.dirty_substates == {GrandchildState.get_name()}
    assert test_state.dirty_substates == {ChildState.get_name()}

    # Cleaning the middle state should keep the parent state dirty.
    child_state._clean()
    assert test_state.dirty_substates == {ChildState.get_name()}
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

    expected_dirty_vars = {
        "num1",
        "num2",
        "obj",
        "upper",
        "complex",
        "fig",
        "key",
        "sum",
        "array",
        "map_key",
        "mapping",
        "dt",
    }

    # The dirty vars should be reset.
    assert test_state.dirty_vars == expected_dirty_vars
    assert child_state.dirty_vars == {"count", "value"}

    # The dirty substates should be reset.
    assert test_state.dirty_substates == {
        ChildState.get_name(),
        ChildState2.get_name(),
        ChildState3.get_name(),
    }


@pytest.mark.asyncio
async def test_process_event_simple(test_state):
    """Test processing an event.

    Args:
        test_state: A state.
    """
    assert test_state.num1 == 0

    event = Event(token="t", name="set_num1", payload={"value": 69})
    update = await test_state._process(event).__anext__()

    # The event should update the value.
    assert test_state.num1 == 69

    # The delta should contain the changes, including computed vars.
    # assert update.delta == {"test_state": {"num1": 69, "sum": 72.14}}
    assert update.delta == {
        TestState.get_full_name(): {"num1": 69, "sum": 72.14, "upper": ""},
        GrandchildState3.get_full_name(): {"computed": ""},
    }
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
        token="t",
        name=f"{ChildState.get_name()}.change_both",
        payload={"value": "hi", "count": 12},
    )
    update = await test_state._process(event).__anext__()
    assert child_state.value == "HI"
    assert child_state.count == 24
    assert update.delta == {
        TestState.get_full_name(): {"sum": 3.14, "upper": ""},
        ChildState.get_full_name(): {"value": "HI", "count": 24},
        GrandchildState3.get_full_name(): {"computed": ""},
    }
    test_state._clean()

    # Test with the granchild state.
    assert grandchild_state.value2 == ""
    event = Event(
        token="t",
        name=f"{GrandchildState.get_full_name()}.set_value2",
        payload={"value": "new"},
    )
    update = await test_state._process(event).__anext__()
    assert grandchild_state.value2 == "new"
    assert update.delta == {
        TestState.get_full_name(): {"sum": 3.14, "upper": ""},
        GrandchildState.get_full_name(): {"value2": "new"},
        GrandchildState3.get_full_name(): {"computed": ""},
    }


@pytest.mark.asyncio
async def test_process_event_generator():
    """Test event handlers that generate multiple updates."""
    gen_state = GenState()  # type: ignore
    event = Event(
        token="t",
        name="go",
        payload={"c": 5},
    )
    gen = gen_state._process(event)

    count = 0
    async for update in gen:
        count += 1
        if count == 6:
            assert update.delta == {}
            assert update.final
        else:
            assert gen_state.value == count
            assert update.delta == {
                GenState.get_full_name(): {"value": count},
            }
            assert not update.final

    assert count == 6


def test_get_client_token(test_state, router_data):
    """Test that the token obtained from the router_data is correct.

    Args:
        test_state: The test state.
        router_data: The router data fixture.
    """
    test_state.router = RouterData(router_data)
    assert (
        test_state.router.session.client_token == "b181904c-3953-4a79-dc18-ae9518c22f05"
    )


def test_get_sid(test_state, router_data):
    """Test getting session id.

    Args:
        test_state: A state.
        router_data: The router data fixture.
    """
    test_state.router = RouterData(router_data)
    assert test_state.router.session.session_id == "9fpxSzPb9aFMb4wFAAAH"


def test_get_headers(test_state, router_data, router_data_headers):
    """Test getting client headers.

    Args:
        test_state: A state.
        router_data: The router data fixture.
        router_data_headers: The expected headers.
    """
    print(router_data_headers)
    test_state.router = RouterData(router_data)
    print(test_state.router.headers)
    assert dataclasses.asdict(test_state.router.headers) == {
        format.to_snake_case(k): v for k, v in router_data_headers.items()
    }


def test_get_client_ip(test_state, router_data):
    """Test getting client IP.

    Args:
        test_state: A state.
        router_data: The router data fixture.
    """
    test_state.router = RouterData(router_data)
    assert test_state.router.session.client_ip == "127.0.0.1"


def test_get_current_page(test_state):
    assert test_state.router.page.path == ""

    route = "mypage/subpage"
    test_state.router = RouterData({RouteVar.PATH: route})
    assert test_state.router.page.path == route


def test_get_query_params(test_state):
    assert test_state.router.page.params == {}

    params = {"p1": "a", "p2": "b"}
    test_state.router = RouterData({RouteVar.QUERY: params})
    assert dict(test_state.router.page.params) == params


def test_add_var():
    class DynamicState(BaseState):
        pass

    ds1 = DynamicState()
    assert "dynamic_int" not in ds1.__dict__
    assert not hasattr(ds1, "dynamic_int")
    ds1.add_var("dynamic_int", int, 42)
    # Existing instances get the BaseVar
    assert ds1.dynamic_int.equals(DynamicState.dynamic_int)  # type: ignore
    # New instances get an actual value with the default
    assert DynamicState().dynamic_int == 42

    ds1.add_var("dynamic_list", List[int], [5, 10])
    assert ds1.dynamic_list.equals(DynamicState.dynamic_list)  # type: ignore
    ds2 = DynamicState()
    assert ds2.dynamic_list == [5, 10]
    ds2.dynamic_list.append(15)
    assert ds2.dynamic_list == [5, 10, 15]
    assert DynamicState().dynamic_list == [5, 10]

    ds1.add_var("dynamic_dict", Dict[str, int], {"k1": 5, "k2": 10})
    assert ds1.dynamic_dict.equals(DynamicState.dynamic_dict)  # type: ignore
    assert ds2.dynamic_dict.equals(DynamicState.dynamic_dict)  # type: ignore
    assert DynamicState().dynamic_dict == {"k1": 5, "k2": 10}
    assert DynamicState().dynamic_dict == {"k1": 5, "k2": 10}


def test_add_var_default_handlers(test_state):
    test_state.add_var("rand_int", int, 10)
    assert "set_rand_int" in test_state.event_handlers
    assert isinstance(test_state.event_handlers["set_rand_int"], EventHandler)


class InterdependentState(BaseState):
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

    @rx.var(cache=True)
    def v1x2(self) -> int:
        """Depends on var v1.

        Returns:
            Var v1 multiplied by 2
        """
        return self.v1 * 2

    @rx.var(cache=True)
    def v2x2(self) -> int:
        """Depends on backend var _v2.

        Returns:
            backend var _v2 multiplied by 2
        """
        return self._v2 * 2

    @rx.var(cache=True, backend=True)
    def v2x2_backend(self) -> int:
        """Depends on backend var _v2.

        Returns:
            backend var _v2 multiplied by 2
        """
        return self._v2 * 2

    @rx.var(cache=True)
    def v1x2x2(self) -> int:
        """Depends on ComputedVar v1x2.

        Returns:
            ComputedVar v1x2 multiplied by 2
        """
        return self.v1x2 * 2  # type: ignore

    @rx.var(cache=True)
    def _v3(self) -> int:
        """Depends on backend var _v2.

        Returns:
            The value of the backend variable.
        """
        return self._v2

    @rx.var(cache=True)
    def v3x2(self) -> int:
        """Depends on ComputedVar _v3.

        Returns:
            ComputedVar _v3 multiplied by 2
        """
        return self._v3 * 2


@pytest.fixture
def interdependent_state() -> BaseState:
    """A state with varying dependency between vars.

    Returns:
        instance of InterdependentState
    """
    s = InterdependentState()
    s.dict()  # prime initial relationships by accessing all ComputedVars
    return s


def test_interdependent_state_initial_dict() -> None:
    s = InterdependentState()
    state_name = s.get_name()
    d = s.dict(initial=True)[state_name]
    d.pop("router")
    assert d == {
        "x": 0,
        "v1": 0,
        "v1x2": 0,
        "v2x2": 2,
        "v1x2x2": 0,
        "v3x2": 2,
    }


def test_not_dirty_computed_var_from_var(
    interdependent_state: InterdependentState,
) -> None:
    """Set Var that no ComputedVar depends on, expect no recalculation.

    Args:
        interdependent_state: A state with varying Var dependencies.
    """
    interdependent_state.x = 5
    assert interdependent_state.get_delta() == {
        interdependent_state.get_full_name(): {"x": 5},
    }


def test_dirty_computed_var_from_var(interdependent_state: InterdependentState) -> None:
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


def test_dirty_computed_var_from_backend_var(
    interdependent_state: InterdependentState,
) -> None:
    """Set backend var that ComputedVar depends on, expect recalculation.

    Args:
        interdependent_state: A state with varying Var dependencies.
    """
    # Accessing ._v3 returns the immutable var it represents instead of the actual computed var
    # assert InterdependentState._v3._backend is True
    interdependent_state._v2 = 2
    assert interdependent_state.get_delta() == {
        interdependent_state.get_full_name(): {"v2x2": 4, "v3x2": 4},
    }


def test_per_state_backend_var(interdependent_state: InterdependentState) -> None:
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

    class MainState(BaseState):
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

    class MainState(BaseState):
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
    assert ms.computed_vars["rendered_var"]._deps(objclass=MainState) == {
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

    class MainState(BaseState):
        v: int = 0

        def set_v(self, v: int):
            self.v = v

        def set_v2(self, v: int):
            self.set_v(v)

    class SubState(MainState):
        def set_v3(self, v: int):
            self.set_v2(v)

    class SubSubState(SubState):
        def set_v4(self, v: int):
            self.set_v(v)

    ms = MainState()
    ms.set_v2(1)
    assert ms.v == 1

    # ensure handler can be called from substate
    ms.substates[SubState.get_name()].set_v3(2)
    assert ms.v == 2

    # ensure handler can be called from substate (referencing grandparent handler)
    ms.get_substate(tuple(SubSubState.get_full_name().split("."))).set_v4(3)
    assert ms.v == 3


def test_computed_var_cached():
    """Test that a ComputedVar doesn't recalculate when accessed."""
    comp_v_calls = 0

    class ComputedState(BaseState):
        v: int = 0

        @rx.var(cache=True)
        def comp_v(self) -> int:
            nonlocal comp_v_calls
            comp_v_calls += 1
            return self.v

    cs = ComputedState()
    assert cs.dict()[cs.get_full_name()]["v"] == 0
    assert comp_v_calls == 1
    assert cs.dict()[cs.get_full_name()]["comp_v"] == 0
    assert comp_v_calls == 1
    assert cs.comp_v == 0
    assert comp_v_calls == 1
    cs.v = 1
    assert comp_v_calls == 1
    assert cs.comp_v == 1
    assert comp_v_calls == 2


def test_computed_var_cached_depends_on_non_cached():
    """Test that a cached var is recalculated if it depends on non-cached ComputedVar."""

    class ComputedState(BaseState):
        v: int = 0

        @rx.var
        def no_cache_v(self) -> int:
            return self.v

        @rx.var(cache=True)
        def dep_v(self) -> int:
            return self.no_cache_v  # type: ignore

        @rx.var(cache=True)
        def comp_v(self) -> int:
            return self.v

    cs = ComputedState()
    assert cs.dirty_vars == set()
    assert cs.get_delta() == {cs.get_name(): {"no_cache_v": 0, "dep_v": 0}}
    cs._clean()
    assert cs.dirty_vars == set()
    assert cs.get_delta() == {cs.get_name(): {"no_cache_v": 0, "dep_v": 0}}
    cs._clean()
    assert cs.dirty_vars == set()
    cs.v = 1
    assert cs.dirty_vars == {"v", "comp_v", "dep_v", "no_cache_v"}
    assert cs.get_delta() == {
        cs.get_name(): {"v": 1, "no_cache_v": 1, "dep_v": 1, "comp_v": 1}
    }
    cs._clean()
    assert cs.dirty_vars == set()
    assert cs.get_delta() == {cs.get_name(): {"no_cache_v": 1, "dep_v": 1}}
    cs._clean()
    assert cs.dirty_vars == set()
    assert cs.get_delta() == {cs.get_name(): {"no_cache_v": 1, "dep_v": 1}}
    cs._clean()
    assert cs.dirty_vars == set()


def test_computed_var_depends_on_parent_non_cached():
    """Child state cached var that depends on parent state un cached var is always recalculated."""
    counter = 0

    class ParentState(BaseState):
        @rx.var
        def no_cache_v(self) -> int:
            nonlocal counter
            counter += 1
            return counter

    class ChildState(ParentState):
        @rx.var(cache=True)
        def dep_v(self) -> int:
            return self.no_cache_v  # type: ignore

    ps = ParentState()
    cs = ps.substates[ChildState.get_name()]

    assert ps.dirty_vars == set()
    assert cs.dirty_vars == set()

    dict1 = ps.dict()
    assert dict1[ps.get_full_name()] == {
        "no_cache_v": 1,
        "router": formatted_router,
    }
    assert dict1[cs.get_full_name()] == {"dep_v": 2}
    dict2 = ps.dict()
    assert dict2[ps.get_full_name()] == {
        "no_cache_v": 3,
        "router": formatted_router,
    }
    assert dict2[cs.get_full_name()] == {"dep_v": 4}
    dict3 = ps.dict()
    assert dict3[ps.get_full_name()] == {
        "no_cache_v": 5,
        "router": formatted_router,
    }
    assert dict3[cs.get_full_name()] == {"dep_v": 6}
    assert counter == 6


@pytest.mark.parametrize("use_partial", [True, False])
def test_cached_var_depends_on_event_handler(use_partial: bool):
    """A cached var that calls an event handler calculates deps correctly.

    Args:
        use_partial: if true, replace the EventHandler with functools.partial
    """
    counter = 0

    class HandlerState(BaseState):
        x: int = 42

        def handler(self):
            self.x = self.x + 1

        @rx.var(cache=True)
        def cached_x_side_effect(self) -> int:
            self.handler()
            nonlocal counter
            counter += 1
            return counter

    if use_partial:
        HandlerState.handler = functools.partial(HandlerState.handler.fn)
        assert isinstance(HandlerState.handler, functools.partial)
    else:
        assert isinstance(HandlerState.handler, EventHandler)

    s = HandlerState()
    assert "cached_x_side_effect" in s._computed_var_dependencies["x"]
    assert s.cached_x_side_effect == 1
    assert s.x == 43
    s.handler()
    assert s.cached_x_side_effect == 2
    assert s.x == 45


def test_computed_var_dependencies():
    """Test that a ComputedVar correctly tracks its dependencies."""

    class ComputedState(BaseState):
        v: int = 0
        w: int = 0
        x: int = 0
        y: List[int] = [1, 2, 3]
        _z: List[int] = [1, 2, 3]

        @property
        def testprop(self) -> int:
            return self.v

        @rx.var(cache=True)
        def comp_v(self) -> int:
            """Direct access.

            Returns:
                The value of self.v.
            """
            return self.v

        @rx.var(cache=True, backend=True)
        def comp_v_backend(self) -> int:
            """Direct access backend var.

            Returns:
                The value of self.v.
            """
            return self.v

        @rx.var(cache=True)
        def comp_v_via_property(self) -> int:
            """Access v via property.

            Returns:
                The value of v via property.
            """
            return self.testprop

        @rx.var(cache=True)
        def comp_w(self):
            """Nested lambda.

            Returns:
                A lambda that returns the value of self.w.
            """
            return lambda: self.w

        @rx.var(cache=True)
        def comp_x(self):
            """Nested function.

            Returns:
                A function that returns the value of self.x.
            """

            def _():
                return self.x

            return _

        @rx.var(cache=True)
        def comp_y(self) -> List[int]:
            """Comprehension iterating over attribute.

            Returns:
                A list of the values of self.y.
            """
            return [round(y) for y in self.y]

        @rx.var(cache=True)
        def comp_z(self) -> List[bool]:
            """Comprehension accesses attribute.

            Returns:
                A list of whether the values 0-4 are in self._z.
            """
            return [z in self._z for z in range(5)]

    cs = ComputedState()
    assert cs._computed_var_dependencies["v"] == {
        "comp_v",
        "comp_v_backend",
        "comp_v_via_property",
    }
    assert cs._computed_var_dependencies["w"] == {"comp_w"}
    assert cs._computed_var_dependencies["x"] == {"comp_x"}
    assert cs._computed_var_dependencies["y"] == {"comp_y"}
    assert cs._computed_var_dependencies["_z"] == {"comp_z"}


def test_backend_method():
    """A method with leading underscore should be callable from event handler."""

    class BackendMethodState(BaseState):
        def _be_method(self):
            return True

        def handler(self):
            assert self._be_method()

    bms = BackendMethodState()
    bms.handler()
    assert bms._be_method()


def test_setattr_of_mutable_types(mutable_state: MutableTestState):
    """Test that mutable types are converted to corresponding Reflex wrappers.

    Args:
        mutable_state: A test state.
    """
    array = mutable_state.array
    hashmap = mutable_state.hashmap
    test_set = mutable_state.test_set
    sqla_model = mutable_state.sqla_model

    assert isinstance(array, MutableProxy)
    assert isinstance(array, list)
    assert isinstance(array[1], MutableProxy)
    assert isinstance(array[1], list)
    assert isinstance(array[2], MutableProxy)
    assert isinstance(array[2], dict)

    assert isinstance(hashmap, MutableProxy)
    assert isinstance(hashmap, dict)
    assert isinstance(hashmap["key"], MutableProxy)
    assert isinstance(hashmap["key"], list)
    assert isinstance(hashmap["third_key"], MutableProxy)
    assert isinstance(hashmap["third_key"], dict)

    assert isinstance(test_set, MutableProxy)
    assert isinstance(test_set, set)

    assert isinstance(mutable_state.custom, MutableProxy)
    assert isinstance(mutable_state.custom.array, MutableProxy)
    assert isinstance(mutable_state.custom.array, list)
    assert isinstance(mutable_state.custom.hashmap, MutableProxy)
    assert isinstance(mutable_state.custom.hashmap, dict)
    assert isinstance(mutable_state.custom.test_set, MutableProxy)
    assert isinstance(mutable_state.custom.test_set, set)
    assert isinstance(mutable_state.custom.custom, MutableProxy)

    assert isinstance(sqla_model, MutableProxy)
    assert isinstance(sqla_model, MutableSQLAModel)
    assert isinstance(sqla_model.strlist, MutableProxy)
    assert isinstance(sqla_model.strlist, list)
    assert isinstance(sqla_model.hashmap, MutableProxy)
    assert isinstance(sqla_model.hashmap, dict)
    assert isinstance(sqla_model.test_set, MutableProxy)
    assert isinstance(sqla_model.test_set, set)

    mutable_state.reassign_mutables()

    array = mutable_state.array
    hashmap = mutable_state.hashmap
    test_set = mutable_state.test_set
    sqla_model = mutable_state.sqla_model

    assert isinstance(array, MutableProxy)
    assert isinstance(array, list)
    assert isinstance(array[1], MutableProxy)
    assert isinstance(array[1], list)
    assert isinstance(array[2], MutableProxy)
    assert isinstance(array[2], dict)

    assert isinstance(hashmap, MutableProxy)
    assert isinstance(hashmap, dict)
    assert isinstance(hashmap["mod_key"], MutableProxy)
    assert isinstance(hashmap["mod_key"], list)
    assert isinstance(hashmap["mod_third_key"], MutableProxy)
    assert isinstance(hashmap["mod_third_key"], dict)

    assert isinstance(test_set, MutableProxy)
    assert isinstance(test_set, set)

    assert isinstance(sqla_model, MutableProxy)
    assert isinstance(sqla_model, MutableSQLAModel)
    assert isinstance(sqla_model.strlist, MutableProxy)
    assert isinstance(sqla_model.strlist, list)
    assert isinstance(sqla_model.hashmap, MutableProxy)
    assert isinstance(sqla_model.hashmap, dict)
    assert isinstance(sqla_model.test_set, MutableProxy)
    assert isinstance(sqla_model.test_set, set)


def test_error_on_state_method_shadow():
    """Test that an error is thrown when an event handler shadows a state method."""
    with pytest.raises(NameError) as err:

        class InvalidTest(BaseState):
            def reset(self):
                pass

    assert (
        err.value.args[0]
        == f"The event handler name `reset` shadows a builtin State method; use a different name instead"
    )


@pytest.mark.asyncio
async def test_state_with_invalid_yield(capsys, mock_app):
    """Test that an error is thrown when a state yields an invalid value.

    Args:
        capsys: Pytest fixture for capture standard streams.
        mock_app: Mock app fixture.
    """

    class StateWithInvalidYield(BaseState):
        """A state that yields an invalid value."""

        def invalid_handler(self):
            """Invalid handler.

            Yields:
                an invalid value.
            """
            yield 1

    invalid_state = StateWithInvalidYield()
    async for update in invalid_state._process(
        rx.event.Event(token="fake_token", name="invalid_handler")
    ):
        assert not update.delta
        if Toaster.is_used:
            assert update.events == rx.event.fix_events(
                [
                    rx.toast(
                        "An error occurred.",
                        description="TypeError: Your handler test_state_with_invalid_yield.<locals>.StateWithInvalidYield.invalid_handler must only return/yield: None, Events or other EventHandlers referenced by their class (not using `self`).<br/>See logs for details.",
                        level="error",
                        id="backend_error",
                        position="top-center",
                        style={"width": "500px"},
                    )  # type: ignore
                ],
                token="",
            )
        else:
            assert update.events == rx.event.fix_events(
                [
                    rx.window_alert(
                        "An error occurred.\nContact the website administrator."
                    )
                ],
                token="",
            )
    captured = capsys.readouterr()
    assert "must only return/yield: None, Events or other EventHandlers" in captured.out


@pytest.fixture(scope="function", params=["in_process", "disk", "redis"])
def state_manager(request) -> Generator[StateManager, None, None]:
    """Instance of state manager parametrized for redis and in-process.

    Args:
        request: pytest request object.

    Yields:
        A state manager instance
    """
    state_manager = StateManager.create(state=TestState)
    if request.param == "redis":
        if not isinstance(state_manager, StateManagerRedis):
            pytest.skip("Test requires redis")
    elif request.param == "disk":
        # explicitly NOT using redis
        state_manager = StateManagerDisk(state=TestState)
        assert not state_manager._states_locks
    else:
        state_manager = StateManagerMemory(state=TestState)
        assert not state_manager._states_locks

    yield state_manager

    if isinstance(state_manager, StateManagerRedis):
        asyncio.get_event_loop().run_until_complete(state_manager.close())


@pytest.fixture()
def substate_token(state_manager, token):
    """A token + substate name for looking up in state manager.

    Args:
        state_manager: A state manager instance.
        token: A token.

    Returns:
        Token concatenated with the state_manager's state full_name.
    """
    return _substate_key(token, state_manager.state)


@pytest.mark.asyncio
async def test_state_manager_modify_state(
    state_manager: StateManager, token: str, substate_token: str
):
    """Test that the state manager can modify a state exclusively.

    Args:
        state_manager: A state manager instance.
        token: A token.
        substate_token: A token + substate name for looking up in state manager.
    """
    async with state_manager.modify_state(substate_token) as state:
        if isinstance(state_manager, StateManagerRedis):
            assert await state_manager.redis.get(f"{token}_lock")
        elif isinstance(state_manager, (StateManagerMemory, StateManagerDisk)):
            assert token in state_manager._states_locks
            assert state_manager._states_locks[token].locked()
        # Should be able to write proxy objects inside mutables
        complex_1 = state.complex[1]
        assert isinstance(complex_1, MutableProxy)
        state.complex[3] = complex_1
    # lock should be dropped after exiting the context
    if isinstance(state_manager, StateManagerRedis):
        assert (await state_manager.redis.get(f"{token}_lock")) is None
    elif isinstance(state_manager, (StateManagerMemory, StateManagerDisk)):
        assert not state_manager._states_locks[token].locked()

        # separate instances should NOT share locks
        sm2 = state_manager.__class__(state=TestState)
        assert sm2._state_manager_lock is state_manager._state_manager_lock
        assert not sm2._states_locks
        if state_manager._states_locks:
            assert sm2._states_locks != state_manager._states_locks


@pytest.mark.asyncio
async def test_state_manager_contend(
    state_manager: StateManager, token: str, substate_token: str
):
    """Multiple coroutines attempting to access the same state.

    Args:
        state_manager: A state manager instance.
        token: A token.
        substate_token: A token + substate name for looking up in state manager.
    """
    n_coroutines = 10
    exp_num1 = 10

    async with state_manager.modify_state(substate_token) as state:
        state.num1 = 0

    async def _coro():
        async with state_manager.modify_state(substate_token) as state:
            await asyncio.sleep(0.01)
            state.num1 += 1

    tasks = [asyncio.create_task(_coro()) for _ in range(n_coroutines)]

    for f in asyncio.as_completed(tasks):
        await f

    assert (await state_manager.get_state(substate_token)).num1 == exp_num1

    if isinstance(state_manager, StateManagerRedis):
        assert (await state_manager.redis.get(f"{token}_lock")) is None
    elif isinstance(state_manager, (StateManagerMemory, StateManagerDisk)):
        assert token in state_manager._states_locks
        assert not state_manager._states_locks[token].locked()


@pytest.fixture(scope="function")
def state_manager_redis() -> Generator[StateManager, None, None]:
    """Instance of state manager for redis only.

    Yields:
        A state manager instance
    """
    state_manager = StateManager.create(TestState)

    if not isinstance(state_manager, StateManagerRedis):
        pytest.skip("Test requires redis")

    yield state_manager

    asyncio.get_event_loop().run_until_complete(state_manager.close())


@pytest.fixture()
def substate_token_redis(state_manager_redis, token):
    """A token + substate name for looking up in state manager.

    Args:
        state_manager_redis: A state manager instance.
        token: A token.

    Returns:
        Token concatenated with the state_manager's state full_name.
    """
    return _substate_key(token, state_manager_redis.state)


@pytest.mark.asyncio
async def test_state_manager_lock_expire(
    state_manager_redis: StateManager, token: str, substate_token_redis: str
):
    """Test that the state manager lock expires and raises exception exiting context.

    Args:
        state_manager_redis: A state manager instance.
        token: A token.
        substate_token_redis: A token + substate name for looking up in state manager.
    """
    state_manager_redis.lock_expiration = LOCK_EXPIRATION

    async with state_manager_redis.modify_state(substate_token_redis):
        await asyncio.sleep(0.01)

    with pytest.raises(LockExpiredError):
        async with state_manager_redis.modify_state(substate_token_redis):
            await asyncio.sleep(LOCK_EXPIRE_SLEEP)


@pytest.mark.asyncio
async def test_state_manager_lock_expire_contend(
    state_manager_redis: StateManager, token: str, substate_token_redis: str
):
    """Test that the state manager lock expires and queued waiters proceed.

    Args:
        state_manager_redis: A state manager instance.
        token: A token.
        substate_token_redis: A token + substate name for looking up in state manager.
    """
    exp_num1 = 4252
    unexp_num1 = 666

    state_manager_redis.lock_expiration = LOCK_EXPIRATION

    order = []

    async def _coro_blocker():
        async with state_manager_redis.modify_state(substate_token_redis) as state:
            order.append("blocker")
            await asyncio.sleep(LOCK_EXPIRE_SLEEP)
            state.num1 = unexp_num1

    async def _coro_waiter():
        while "blocker" not in order:
            await asyncio.sleep(0.005)
        async with state_manager_redis.modify_state(substate_token_redis) as state:
            order.append("waiter")
            assert state.num1 != unexp_num1
            state.num1 = exp_num1

    tasks = [
        asyncio.create_task(_coro_blocker()),
        asyncio.create_task(_coro_waiter()),
    ]
    with pytest.raises(LockExpiredError):
        await tasks[0]
    await tasks[1]

    assert order == ["blocker", "waiter"]
    assert (await state_manager_redis.get_state(substate_token_redis)).num1 == exp_num1


@pytest.fixture(scope="function")
def mock_app(monkeypatch, state_manager: StateManager) -> rx.App:
    """Mock app fixture.

    Args:
        monkeypatch: Pytest monkeypatch object.
        state_manager: A state manager.

    Returns:
        The app, after mocking out prerequisites.get_app()
    """
    app = App(state=TestState)

    app_module = Mock()

    setattr(app_module, CompileVars.APP, app)
    app.state = TestState
    app._state_manager = state_manager
    app.event_namespace.emit = AsyncMock()  # type: ignore

    def _mock_get_app(*args, **kwargs):
        return app_module

    monkeypatch.setattr(prerequisites, "get_app", _mock_get_app)
    return app


@pytest.mark.asyncio
async def test_state_proxy(grandchild_state: GrandchildState, mock_app: rx.App):
    """Test that the state proxy works.

    Args:
        grandchild_state: A grandchild state.
        mock_app: An app that will be returned by `get_app()`
    """
    child_state = grandchild_state.parent_state
    assert child_state is not None
    parent_state = child_state.parent_state
    assert parent_state is not None
    if isinstance(mock_app.state_manager, (StateManagerMemory, StateManagerDisk)):
        mock_app.state_manager.states[parent_state.router.session.client_token] = (
            parent_state
        )

    sp = StateProxy(grandchild_state)
    assert sp.__wrapped__ == grandchild_state
    assert sp._self_substate_path == tuple(grandchild_state.get_full_name().split("."))
    assert sp._self_app is mock_app
    assert not sp._self_mutable
    assert sp._self_actx is None

    # cannot use normal contextmanager protocol
    with pytest.raises(TypeError), sp:
        pass

    with pytest.raises(ImmutableStateError):
        # cannot directly modify state proxy outside of async context
        sp.value2 = "16"

    with pytest.raises(ImmutableStateError):
        # Cannot get_state
        await sp.get_state(ChildState)

    with pytest.raises(ImmutableStateError):
        # Cannot access get_substate
        sp.get_substate([])

    with pytest.raises(ImmutableStateError):
        # Cannot access parent state
        sp.parent_state.get_name()

    with pytest.raises(ImmutableStateError):
        # Cannot access substates
        sp.substates[""]

    async with sp:
        assert sp._self_actx is not None
        assert sp._self_mutable  # proxy is mutable inside context
        if isinstance(mock_app.state_manager, StateManagerMemory):
            # For in-process store, only one instance of the state exists
            assert sp.__wrapped__ is grandchild_state
        else:
            # When redis or disk is used, a new+updated instance is assigned to the proxy
            assert sp.__wrapped__ is not grandchild_state
        sp.value2 = "42"
    assert not sp._self_mutable  # proxy is not mutable after exiting context
    assert sp._self_actx is None
    assert sp.value2 == "42"

    # Get the state from the state manager directly and check that the value is updated
    gotten_state = await mock_app.state_manager.get_state(
        _substate_key(grandchild_state.router.session.client_token, grandchild_state)
    )
    if isinstance(mock_app.state_manager, StateManagerMemory):
        # For in-process store, only one instance of the state exists
        assert gotten_state is parent_state
    else:
        assert gotten_state is not parent_state
    gotten_grandchild_state = gotten_state.get_substate(sp._self_substate_path)
    assert gotten_grandchild_state is not None
    assert gotten_grandchild_state.value2 == "42"

    # ensure state update was emitted
    assert mock_app.event_namespace is not None
    mock_app.event_namespace.emit.assert_called_once()
    mcall = mock_app.event_namespace.emit.mock_calls[0]
    assert mcall.args[0] == str(SocketEvent.EVENT)
    assert json.loads(mcall.args[1]) == dataclasses.asdict(
        StateUpdate(
            delta={
                parent_state.get_full_name(): {
                    "upper": "",
                    "sum": 3.14,
                },
                grandchild_state.get_full_name(): {
                    "value2": "42",
                },
                GrandchildState3.get_full_name(): {
                    "computed": "",
                },
            }
        )
    )
    assert mcall.kwargs["to"] == grandchild_state.router.session.session_id


class BackgroundTaskState(BaseState):
    """A state with a background task."""

    order: List[str] = []
    dict_list: Dict[str, List[int]] = {"foo": [1, 2, 3]}

    @rx.var
    def computed_order(self) -> List[str]:
        """Get the order as a computed var.

        Returns:
            The value of 'order' var.
        """
        return self.order

    @rx.background
    async def background_task(self):
        """A background task that updates the state."""
        async with self:
            assert not self.order
            self.order.append("background_task:start")

        assert isinstance(self, StateProxy)
        with pytest.raises(ImmutableStateError):
            self.order.append("bad idea")

        with pytest.raises(ImmutableStateError):
            # Even nested access to mutables raises an exception.
            self.dict_list["foo"].append(42)

        with pytest.raises(ImmutableStateError):
            # Direct calling another handler that modifies state raises an exception.
            self.other()

        with pytest.raises(ImmutableStateError):
            # Calling other methods that modify state raises an exception.
            self._private_method()

        # wait for some other event to happen
        while len(self.order) == 1:
            await asyncio.sleep(0.01)
            async with self:
                pass  # update proxy instance

        async with self:
            # Methods on ImmutableMutableProxy should return their wrapped return value.
            assert self.dict_list.pop("foo") == [1, 2, 3]

            self.order.append("background_task:stop")
            self.other()  # direct calling event handlers works in context
            self._private_method()

    @rx.background
    async def background_task_reset(self):
        """A background task that resets the state."""
        with pytest.raises(ImmutableStateError):
            # Resetting the state should be explicitly blocked.
            self.reset()

        async with self:
            self.order.append("foo")
            self.reset()
        assert not self.order
        async with self:
            self.order.append("reset")

    @rx.background
    async def background_task_generator(self):
        """A background task generator that does nothing.

        Yields:
            None
        """
        yield

    def other(self):
        """Some other event that updates the state."""
        self.order.append("other")

    def _private_method(self):
        """Some private method that updates the state."""
        self.order.append("private")

    async def bad_chain1(self):
        """Test that a background task cannot be chained."""
        await self.background_task()

    async def bad_chain2(self):
        """Test that a background task generator cannot be chained."""
        async for _foo in self.background_task_generator():
            pass


@pytest.mark.asyncio
async def test_background_task_no_block(mock_app: rx.App, token: str):
    """Test that a background task does not block other events.

    Args:
        mock_app: An app that will be returned by `get_app()`
        token: A token.
    """
    router_data = {"query": {}}
    mock_app.state_manager.state = mock_app.state = BackgroundTaskState
    async for update in rx.app.process(  # type: ignore
        mock_app,
        Event(
            token=token,
            name=f"{BackgroundTaskState.get_full_name()}.background_task",
            router_data=router_data,
            payload={},
        ),
        sid="",
        headers={},
        client_ip="",
    ):
        # background task returns empty update immediately
        assert update == StateUpdate()

    # wait for the coroutine to start
    await asyncio.sleep(0.5 if CI else 0.1)
    assert len(mock_app.background_tasks) == 1

    # Process another normal event
    async for update in rx.app.process(  # type: ignore
        mock_app,
        Event(
            token=token,
            name=f"{BackgroundTaskState.get_full_name()}.other",
            router_data=router_data,
            payload={},
        ),
        sid="",
        headers={},
        client_ip="",
    ):
        # other task returns delta
        assert update == StateUpdate(
            delta={
                BackgroundTaskState.get_full_name(): {
                    "order": [
                        "background_task:start",
                        "other",
                    ],
                    "computed_order": [
                        "background_task:start",
                        "other",
                    ],
                }
            }
        )

    # Explicit wait for background tasks
    for task in tuple(mock_app.background_tasks):
        await task
    assert not mock_app.background_tasks

    exp_order = [
        "background_task:start",
        "other",
        "background_task:stop",
        "other",
        "private",
    ]

    assert (
        await mock_app.state_manager.get_state(
            _substate_key(token, BackgroundTaskState)
        )
    ).order == exp_order

    assert mock_app.event_namespace is not None
    emit_mock = mock_app.event_namespace.emit

    first_ws_message = json.loads(emit_mock.mock_calls[0].args[1])
    assert (
        first_ws_message["delta"][BackgroundTaskState.get_full_name()].pop("router")
        is not None
    )
    assert first_ws_message == {
        "delta": {
            BackgroundTaskState.get_full_name(): {
                "order": ["background_task:start"],
                "computed_order": ["background_task:start"],
            }
        },
        "events": [],
        "final": True,
    }
    for call in emit_mock.mock_calls[1:5]:
        assert json.loads(call.args[1]) == {
            "delta": {
                BackgroundTaskState.get_full_name(): {
                    "computed_order": ["background_task:start"],
                }
            },
            "events": [],
            "final": True,
        }
    assert json.loads(emit_mock.mock_calls[-2].args[1]) == {
        "delta": {
            BackgroundTaskState.get_full_name(): {
                "order": exp_order,
                "computed_order": exp_order,
                "dict_list": {},
            }
        },
        "events": [],
        "final": True,
    }
    assert json.loads(emit_mock.mock_calls[-1].args[1]) == {
        "delta": {
            BackgroundTaskState.get_full_name(): {
                "computed_order": exp_order,
            },
        },
        "events": [],
        "final": True,
    }


@pytest.mark.asyncio
async def test_background_task_reset(mock_app: rx.App, token: str):
    """Test that a background task calling reset is protected by the state proxy.

    Args:
        mock_app: An app that will be returned by `get_app()`
        token: A token.
    """
    router_data = {"query": {}}
    mock_app.state_manager.state = mock_app.state = BackgroundTaskState
    async for update in rx.app.process(  # type: ignore
        mock_app,
        Event(
            token=token,
            name=f"{BackgroundTaskState.get_name()}.background_task_reset",
            router_data=router_data,
            payload={},
        ),
        sid="",
        headers={},
        client_ip="",
    ):
        # background task returns empty update immediately
        assert update == StateUpdate()

    # Explicit wait for background tasks
    for task in tuple(mock_app.background_tasks):
        await task
    assert not mock_app.background_tasks

    assert (
        await mock_app.state_manager.get_state(
            _substate_key(token, BackgroundTaskState)
        )
    ).order == [
        "reset",
    ]


@pytest.mark.asyncio
async def test_background_task_no_chain():
    """Test that a background task cannot be chained."""
    bts = BackgroundTaskState()
    with pytest.raises(RuntimeError):
        await bts.bad_chain1()
    with pytest.raises(RuntimeError):
        await bts.bad_chain2()


def test_mutable_list(mutable_state: MutableTestState):
    """Test that mutable lists are tracked correctly.

    Args:
        mutable_state: A test state.
    """
    assert not mutable_state.dirty_vars

    def assert_array_dirty():
        assert mutable_state.dirty_vars == {"array"}
        mutable_state._clean()
        assert not mutable_state.dirty_vars

    # Test all list operations
    mutable_state.array.append(42)
    assert_array_dirty()
    mutable_state.array.extend([1, 2, 3])
    assert_array_dirty()
    mutable_state.array.insert(0, 0)
    assert_array_dirty()
    mutable_state.array.pop()
    assert_array_dirty()
    mutable_state.array.remove(42)
    assert_array_dirty()
    mutable_state.array.clear()
    assert_array_dirty()
    mutable_state.array += [1, 2, 3]
    assert_array_dirty()
    mutable_state.array.reverse()
    assert_array_dirty()
    mutable_state.array.sort()  # type: ignore[reportCallIssue,reportUnknownMemberType]
    assert_array_dirty()
    mutable_state.array[0] = 666
    assert_array_dirty()
    del mutable_state.array[0]
    assert_array_dirty()

    # Test nested list operations
    mutable_state.array[0] = [1, 2, 3]
    assert_array_dirty()
    mutable_state.array[0].append(4)
    assert_array_dirty()
    assert isinstance(mutable_state.array[0], MutableProxy)

    # Test proxy returned from __iter__
    mutable_state.array = [{}]
    assert_array_dirty()
    assert isinstance(mutable_state.array[0], MutableProxy)
    for item in mutable_state.array:
        assert isinstance(item, MutableProxy)
        item["foo"] = "bar"
        assert_array_dirty()


def test_mutable_dict(mutable_state: MutableTestState):
    """Test that mutable dicts are tracked correctly.

    Args:
        mutable_state: A test state.
    """
    assert not mutable_state.dirty_vars

    def assert_hashmap_dirty():
        assert mutable_state.dirty_vars == {"hashmap"}
        mutable_state._clean()
        assert not mutable_state.dirty_vars

    # Test all dict operations
    mutable_state.hashmap.update({"new_key": "43"})
    assert_hashmap_dirty()
    assert mutable_state.hashmap.setdefault("another_key", "66") == "another_value"
    assert_hashmap_dirty()
    assert mutable_state.hashmap.setdefault("setdefault_key", "67") == "67"
    assert_hashmap_dirty()
    assert mutable_state.hashmap.setdefault("setdefault_key", "68") == "67"
    assert_hashmap_dirty()
    assert mutable_state.hashmap.pop("new_key") == "43"
    assert_hashmap_dirty()
    mutable_state.hashmap.popitem()
    assert_hashmap_dirty()
    mutable_state.hashmap.clear()
    assert_hashmap_dirty()
    mutable_state.hashmap["new_key"] = "42"
    assert_hashmap_dirty()
    del mutable_state.hashmap["new_key"]
    assert_hashmap_dirty()
    if sys.version_info >= (3, 9):
        mutable_state.hashmap |= {"new_key": "44"}
        assert_hashmap_dirty()

    # Test nested dict operations
    mutable_state.hashmap["array"] = []
    assert_hashmap_dirty()
    mutable_state.hashmap["array"].append("1")
    assert_hashmap_dirty()
    mutable_state.hashmap["dict"] = {}
    assert_hashmap_dirty()
    mutable_state.hashmap["dict"]["key"] = "42"
    assert_hashmap_dirty()
    mutable_state.hashmap["dict"]["dict"] = {}
    assert_hashmap_dirty()
    mutable_state.hashmap["dict"]["dict"]["key"] = "43"
    assert_hashmap_dirty()

    # Test proxy returned from `setdefault` and `get`
    mutable_value = mutable_state.hashmap.setdefault("setdefault_mutable_key", [])
    assert_hashmap_dirty()
    assert mutable_value == []
    assert isinstance(mutable_value, MutableProxy)
    mutable_value.append("foo")
    assert_hashmap_dirty()
    mutable_value_other_ref = mutable_state.hashmap.get("setdefault_mutable_key")
    assert isinstance(mutable_value_other_ref, MutableProxy)
    assert mutable_value is not mutable_value_other_ref
    assert mutable_value == mutable_value_other_ref
    assert not mutable_state.dirty_vars
    mutable_value_other_ref.append("bar")
    assert_hashmap_dirty()

    # `pop` should NOT return a proxy, because the returned value is no longer in the dict
    mutable_value_third_ref = mutable_state.hashmap.pop("setdefault_mutable_key")
    assert not isinstance(mutable_value_third_ref, MutableProxy)
    assert_hashmap_dirty()
    mutable_value_third_ref.append("baz")  # type: ignore[reportUnknownMemberType,reportAttributeAccessIssue,reportUnusedCallResult]
    assert not mutable_state.dirty_vars
    # Unfortunately previous refs still will mark the state dirty... nothing doing about that
    assert mutable_value.pop()
    assert_hashmap_dirty()


def test_mutable_set(mutable_state: MutableTestState):
    """Test that mutable sets are tracked correctly.

    Args:
        mutable_state: A test state.
    """
    assert not mutable_state.dirty_vars

    def assert_set_dirty():
        assert mutable_state.dirty_vars == {"test_set"}
        mutable_state._clean()
        assert not mutable_state.dirty_vars

    # Test all set operations
    mutable_state.test_set.add(42)
    assert_set_dirty()
    mutable_state.test_set.update([1, 2, 3])
    assert_set_dirty()
    mutable_state.test_set.remove(42)
    assert_set_dirty()
    mutable_state.test_set.discard(3)
    assert_set_dirty()
    mutable_state.test_set.pop()
    assert_set_dirty()
    mutable_state.test_set.intersection_update([1, 2, 3])
    assert_set_dirty()
    mutable_state.test_set.difference_update([99])
    assert_set_dirty()
    mutable_state.test_set.symmetric_difference_update([102, 99])
    assert_set_dirty()
    mutable_state.test_set |= {1, 2, 3}
    assert_set_dirty()
    mutable_state.test_set &= {2, 3, 4}
    assert_set_dirty()
    mutable_state.test_set -= {2}
    assert_set_dirty()
    mutable_state.test_set ^= {42}
    assert_set_dirty()
    mutable_state.test_set.clear()
    assert_set_dirty()


def test_mutable_custom(mutable_state: MutableTestState):
    """Test that mutable custom types derived from Base are tracked correctly.

    Args:
        mutable_state: A test state.
    """
    assert not mutable_state.dirty_vars

    def assert_custom_dirty():
        assert mutable_state.dirty_vars == {"custom"}
        mutable_state._clean()
        assert not mutable_state.dirty_vars

    mutable_state.custom.foo = "bar"
    assert_custom_dirty()
    mutable_state.custom.array.append("42")
    assert_custom_dirty()
    mutable_state.custom.hashmap["key"] = "value"
    assert_custom_dirty()
    mutable_state.custom.test_set.add("foo")
    assert_custom_dirty()
    mutable_state.custom.custom.bar = "baz"
    assert_custom_dirty()


def test_mutable_sqla_model(mutable_state: MutableTestState):
    """Test that mutable SQLA models are tracked correctly.

    Args:
        mutable_state: A test state.
    """
    assert not mutable_state.dirty_vars

    def assert_sqla_model_dirty():
        assert mutable_state.dirty_vars == {"sqla_model"}
        mutable_state._clean()
        assert not mutable_state.dirty_vars

    mutable_state.sqla_model.strlist.append("foo")
    assert_sqla_model_dirty()
    mutable_state.sqla_model.hashmap["key"] = "value"
    assert_sqla_model_dirty()
    mutable_state.sqla_model.test_set.add("bar")
    assert_sqla_model_dirty()


def test_mutable_backend(mutable_state: MutableTestState):
    """Test that mutable backend vars are tracked correctly.

    Args:
        mutable_state: A test state.
    """
    assert not mutable_state.dirty_vars

    def assert_custom_dirty():
        assert mutable_state.dirty_vars == {"_be_custom"}
        mutable_state._clean()
        assert not mutable_state.dirty_vars

    mutable_state._be_custom.foo = "bar"
    assert_custom_dirty()
    mutable_state._be_custom.array.append("baz")
    assert_custom_dirty()
    mutable_state._be_custom.hashmap["key"] = "value"
    assert_custom_dirty()
    mutable_state._be_custom.test_set.add("foo")
    assert_custom_dirty()
    mutable_state._be_custom.custom.bar = "baz"
    assert_custom_dirty()


@pytest.mark.parametrize(
    ("copy_func",),
    [
        (copy.copy,),
        (copy.deepcopy,),
    ],
)
def test_mutable_copy(mutable_state: MutableTestState, copy_func: Callable):
    """Test that mutable types are copied correctly.

    Args:
        mutable_state: A test state.
        copy_func: A copy function.
    """
    ms_copy = copy_func(mutable_state)
    assert ms_copy is not mutable_state
    for attr in ("array", "hashmap", "test_set", "custom"):
        assert getattr(ms_copy, attr) == getattr(mutable_state, attr)
        assert getattr(ms_copy, attr) is not getattr(mutable_state, attr)
    ms_copy.custom.array.append(42)
    assert "custom" in ms_copy.dirty_vars
    if copy_func is copy.copy:
        assert "custom" in mutable_state.dirty_vars
    else:
        assert not mutable_state.dirty_vars


@pytest.mark.parametrize(
    ("copy_func",),
    [
        (copy.copy,),
        (copy.deepcopy,),
    ],
)
def test_mutable_copy_vars(mutable_state: MutableTestState, copy_func: Callable):
    """Test that mutable types are copied correctly.

    Args:
        mutable_state: A test state.
        copy_func: A copy function.
    """
    for attr in ("array", "hashmap", "test_set", "custom"):
        var_orig = getattr(mutable_state, attr)
        var_copy = copy_func(var_orig)
        assert var_orig is not var_copy
        assert var_orig == var_copy
        # copied vars should never be proxies, as they by definition are no longer attached to the state.
        assert not isinstance(var_copy, MutableProxy)


def test_duplicate_substate_class(mocker):
    mocker.patch("reflex.state.is_testing_env", lambda: False)
    with pytest.raises(ValueError):

        class TestState(BaseState):
            pass

        class ChildTestState(TestState):  # type: ignore # noqa
            pass

        class ChildTestState(TestState):  # type: ignore # noqa
            pass

        return TestState


class Foo(Base):
    """A class containing a list of str."""

    tags: List[str] = ["123", "456"]


def test_json_dumps_with_mutables():
    """Test that json.dumps works with Base vars inside mutable types."""

    class MutableContainsBase(BaseState):
        items: List[Foo] = [Foo()]

    dict_val = MutableContainsBase().dict()
    assert isinstance(dict_val[MutableContainsBase.get_full_name()]["items"][0], Foo)
    val = json_dumps(dict_val)
    f_items = '[{"tags": ["123", "456"]}]'
    f_formatted_router = str(formatted_router).replace("'", '"')
    assert (
        val
        == f'{{"{MutableContainsBase.get_full_name()}": {{"items": {f_items}, "router": {f_formatted_router}}}}}'
    )


def test_reset_with_mutables():
    """Calling reset should always reset fields to a copy of the defaults."""
    default = [[0, 0], [0, 1], [1, 1]]
    copied_default = copy.deepcopy(default)

    class MutableResetState(BaseState):
        items: List[List[int]] = default

    instance = MutableResetState()
    assert instance.items.__wrapped__ is not default  # type: ignore
    assert instance.items == default == copied_default
    instance.items.append([3, 3])
    assert instance.items != default
    assert instance.items != copied_default

    instance.reset()
    assert instance.items.__wrapped__ is not default  # type: ignore
    assert instance.items == default == copied_default
    instance.items.append([3, 3])
    assert instance.items != default
    assert instance.items != copied_default

    instance.reset()
    assert instance.items.__wrapped__ is not default  # type: ignore
    assert instance.items == default == copied_default
    instance.items.append([3, 3])
    assert instance.items != default
    assert instance.items != copied_default


class Custom1(Base):
    """A custom class with a str field."""

    foo: str

    def set_foo(self, val: str):
        """Set the attribute foo.

        Args:
            val: The value to set.
        """
        self.foo = val

    def double_foo(self) -> str:
        """Concantenate foo with foo.

        Returns:
            foo + foo
        """
        return self.foo + self.foo


class Custom2(Base):
    """A custom class with a Custom1 field."""

    c1: Optional[Custom1] = None
    c1r: Custom1

    def set_c1r_foo(self, val: str):
        """Set the foo attribute of the c1 field.

        Args:
            val: The value to set.
        """
        self.c1r.set_foo(val)


class Custom3(Base):
    """A custom class with a Custom2 field."""

    c2: Optional[Custom2] = None
    c2r: Custom2


def test_state_union_optional():
    """Test that state can be defined with Union and Optional vars."""

    class UnionState(BaseState):
        int_float: Union[int, float] = 0
        opt_int: Optional[int]
        c3: Optional[Custom3]
        c3i: Custom3  # implicitly required
        c3r: Custom3 = Custom3(c2r=Custom2(c1r=Custom1(foo="")))
        custom_union: Union[Custom1, Custom2, Custom3] = Custom1(foo="")

    assert str(UnionState.c3.c2) == f'{str(UnionState.c3)}?.["c2"]'  # type: ignore
    assert str(UnionState.c3.c2.c1) == f'{str(UnionState.c3)}?.["c2"]?.["c1"]'  # type: ignore
    assert (
        str(UnionState.c3.c2.c1.foo) == f'{str(UnionState.c3)}?.["c2"]?.["c1"]?.["foo"]'  # type: ignore
    )
    assert (
        str(UnionState.c3.c2.c1r.foo) == f'{str(UnionState.c3)}?.["c2"]?.["c1r"]["foo"]'  # type: ignore
    )
    assert str(UnionState.c3.c2r.c1) == f'{str(UnionState.c3)}?.["c2r"]["c1"]'  # type: ignore
    assert (
        str(UnionState.c3.c2r.c1.foo) == f'{str(UnionState.c3)}?.["c2r"]["c1"]?.["foo"]'  # type: ignore
    )
    assert (
        str(UnionState.c3.c2r.c1r.foo) == f'{str(UnionState.c3)}?.["c2r"]["c1r"]["foo"]'  # type: ignore
    )
    assert str(UnionState.c3i.c2) == f'{str(UnionState.c3i)}["c2"]'  # type: ignore
    assert str(UnionState.c3r.c2) == f'{str(UnionState.c3r)}["c2"]'  # type: ignore
    assert UnionState.custom_union.foo is not None  # type: ignore
    assert UnionState.custom_union.c1 is not None  # type: ignore
    assert UnionState.custom_union.c1r is not None  # type: ignore
    assert UnionState.custom_union.c2 is not None  # type: ignore
    assert UnionState.custom_union.c2r is not None  # type: ignore
    assert types.is_optional(UnionState.opt_int._var_type)  # type: ignore
    assert types.is_union(UnionState.int_float._var_type)  # type: ignore


def test_set_base_field_via_setter():
    """When calling a setter on a Base instance, also track changes."""

    class BaseFieldSetterState(BaseState):
        c1: Custom1 = Custom1(foo="")
        c2: Custom2 = Custom2(c1r=Custom1(foo=""))

    bfss = BaseFieldSetterState()
    assert "c1" not in bfss.dirty_vars

    # Non-mutating function, not dirty
    bfss.c1.double_foo()
    assert "c1" not in bfss.dirty_vars

    # Mutating function, dirty
    bfss.c1.set_foo("bar")
    assert "c1" in bfss.dirty_vars
    bfss.dirty_vars.clear()
    assert "c1" not in bfss.dirty_vars

    # Mutating function from Base, dirty
    bfss.c1.set(foo="bar")
    assert "c1" in bfss.dirty_vars
    bfss.dirty_vars.clear()
    assert "c1" not in bfss.dirty_vars

    # Assert identity of MutableProxy
    mp = bfss.c1
    assert isinstance(mp, MutableProxy)
    mp2 = mp.set()
    assert mp is mp2
    mp3 = bfss.c1.set()
    assert mp is not mp3
    # Since none of these set calls had values, the state should not be dirty
    assert not bfss.dirty_vars

    # Chained Mutating function, dirty
    bfss.c2.set_c1r_foo("baz")
    assert "c2" in bfss.dirty_vars


def exp_is_hydrated(state: State, is_hydrated: bool = True) -> Dict[str, Any]:
    """Expected IS_HYDRATED delta that would be emitted by HydrateMiddleware.

    Args:
        state: the State that is hydrated.
        is_hydrated: whether the state is hydrated.

    Returns:
        dict similar to that returned by `State.get_delta` with IS_HYDRATED: is_hydrated
    """
    return {state.get_full_name(): {CompileVars.IS_HYDRATED: is_hydrated}}


class OnLoadState(State):
    """A test state with no return in handler."""

    num: int = 0

    def test_handler(self):
        """Test handler."""
        self.num += 1


class OnLoadState2(State):
    """A test state with return in handler."""

    num: int = 0
    name: str

    def test_handler(self):
        """Test handler that calls another handler.

        Returns:
            Chain of EventHandlers
        """
        self.num += 1
        return self.change_name

    def change_name(self):
        """Test handler to change name."""
        self.name = "random"


class OnLoadState3(State):
    """A test state with async handler."""

    num: int = 0

    async def test_handler(self):
        """Test handler."""
        self.num += 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "test_state, expected",
    [
        (OnLoadState, {"on_load_state": {"num": 1}}),
        (OnLoadState2, {"on_load_state2": {"num": 1}}),
        (OnLoadState3, {"on_load_state3": {"num": 1}}),
    ],
)
async def test_preprocess(app_module_mock, token, test_state, expected, mocker):
    """Test that a state hydrate event is processed correctly.

    Args:
        app_module_mock: The app module that will be returned by get_app().
        token: A token.
        test_state: State to process event.
        expected: Expected delta.
        mocker: pytest mock object.
    """
    mocker.patch(
        "reflex.state.State.class_subclasses", {test_state, OnLoadInternalState}
    )
    app = app_module_mock.app = App(
        state=State, load_events={"index": [test_state.test_handler]}
    )
    state = State()

    updates = []
    async for update in rx.app.process(
        app=app,
        event=Event(
            token=token,
            name=f"{state.get_name()}.{CompileVars.ON_LOAD_INTERNAL}",
            router_data={RouteVar.PATH: "/", RouteVar.ORIGIN: "/", RouteVar.QUERY: {}},
        ),
        sid="sid",
        headers={},
        client_ip="",
    ):
        assert isinstance(update, StateUpdate)
        updates.append(update)
    assert len(updates) == 1
    assert updates[0].delta[State.get_name()].pop("router") is not None
    assert updates[0].delta == exp_is_hydrated(state, False)

    events = updates[0].events
    assert len(events) == 2
    assert (await state._process(events[0]).__anext__()).delta == {
        test_state.get_full_name(): {"num": 1}
    }
    assert (await state._process(events[1]).__anext__()).delta == exp_is_hydrated(state)


@pytest.mark.asyncio
async def test_preprocess_multiple_load_events(app_module_mock, token, mocker):
    """Test that a state hydrate event for multiple on-load events is processed correctly.

    Args:
        app_module_mock: The app module that will be returned by get_app().
        token: A token.
        mocker: pytest mock object.
    """
    mocker.patch(
        "reflex.state.State.class_subclasses", {OnLoadState, OnLoadInternalState}
    )
    app = app_module_mock.app = App(
        state=State,
        load_events={"index": [OnLoadState.test_handler, OnLoadState.test_handler]},
    )
    state = State()

    updates = []
    async for update in rx.app.process(
        app=app,
        event=Event(
            token=token,
            name=f"{state.get_full_name()}.{CompileVars.ON_LOAD_INTERNAL}",
            router_data={RouteVar.PATH: "/", RouteVar.ORIGIN: "/", RouteVar.QUERY: {}},
        ),
        sid="sid",
        headers={},
        client_ip="",
    ):
        assert isinstance(update, StateUpdate)
        updates.append(update)
    assert len(updates) == 1
    assert updates[0].delta[State.get_name()].pop("router") is not None
    assert updates[0].delta == exp_is_hydrated(state, False)

    events = updates[0].events
    assert len(events) == 3
    assert (await state._process(events[0]).__anext__()).delta == {
        OnLoadState.get_full_name(): {"num": 1}
    }
    assert (await state._process(events[1]).__anext__()).delta == {
        OnLoadState.get_full_name(): {"num": 2}
    }
    assert (await state._process(events[2]).__anext__()).delta == exp_is_hydrated(state)


@pytest.mark.asyncio
async def test_get_state(mock_app: rx.App, token: str):
    """Test that a get_state populates the top level state and delta calculation is correct.

    Args:
        mock_app: An app that will be returned by `get_app()`
        token: A token.
    """
    mock_app.state_manager.state = mock_app.state = TestState

    # Get instance of ChildState2.
    test_state = await mock_app.state_manager.get_state(
        _substate_key(token, ChildState2)
    )
    assert isinstance(test_state, TestState)
    if isinstance(mock_app.state_manager, (StateManagerMemory, StateManagerDisk)):
        # All substates are available
        assert tuple(sorted(test_state.substates)) == (
            ChildState.get_name(),
            ChildState2.get_name(),
            ChildState3.get_name(),
        )
    else:
        # Sibling states are only populated if they have computed vars
        assert tuple(sorted(test_state.substates)) == (
            ChildState2.get_name(),
            ChildState3.get_name(),
        )

    # Because ChildState3 has a computed var, it is always dirty, and always populated.
    assert (
        test_state.substates[ChildState3.get_name()]
        .substates[GrandchildState3.get_name()]
        .computed
        == ""
    )

    # Get the child_state2 directly.
    child_state2_direct = test_state.get_substate([ChildState2.get_name()])
    child_state2_get_state = await test_state.get_state(ChildState2)
    # These should be the same object.
    assert child_state2_direct is child_state2_get_state

    # Get arbitrary GrandchildState.
    grandchild_state = await child_state2_get_state.get_state(GrandchildState)
    assert isinstance(grandchild_state, GrandchildState)

    # Now the original root should have all substates populated.
    assert tuple(sorted(test_state.substates)) == (
        ChildState.get_name(),
        ChildState2.get_name(),
        ChildState3.get_name(),
    )

    # ChildState should be retrievable
    child_state_direct = test_state.get_substate([ChildState.get_name()])
    child_state_get_state = await test_state.get_state(ChildState)
    # These should be the same object.
    assert child_state_direct is child_state_get_state

    # GrandchildState instance should be the same as the one retrieved from the child_state2.
    assert grandchild_state is child_state_direct.get_substate(
        [GrandchildState.get_name()]
    )
    grandchild_state.value2 = "set_value"

    assert test_state.get_delta() == {
        TestState.get_full_name(): {
            "sum": 3.14,
            "upper": "",
        },
        GrandchildState.get_full_name(): {
            "value2": "set_value",
        },
        GrandchildState3.get_full_name(): {
            "computed": "",
        },
    }

    # Get a fresh instance
    new_test_state = await mock_app.state_manager.get_state(
        _substate_key(token, ChildState2)
    )
    assert isinstance(new_test_state, TestState)
    if isinstance(mock_app.state_manager, StateManagerMemory):
        # In memory, it's the same instance
        assert new_test_state is test_state
        test_state._clean()
        # All substates are available
        assert tuple(sorted(new_test_state.substates)) == (
            ChildState.get_name(),
            ChildState2.get_name(),
            ChildState3.get_name(),
        )
    elif isinstance(mock_app.state_manager, StateManagerDisk):
        # On disk, it's a new instance
        assert new_test_state is not test_state
        # All substates are available
        assert tuple(sorted(new_test_state.substates)) == (
            ChildState.get_name(),
            ChildState2.get_name(),
            ChildState3.get_name(),
        )
    else:
        # With redis, we get a whole new instance
        assert new_test_state is not test_state
        # Sibling states are only populated if they have computed vars
        assert tuple(sorted(new_test_state.substates)) == (
            ChildState2.get_name(),
            ChildState3.get_name(),
        )

    # Set a value on child_state2, should update cached var in grandchild_state2
    child_state2 = new_test_state.get_substate((ChildState2.get_name(),))
    child_state2.value = "set_c2_value"

    assert new_test_state.get_delta() == {
        TestState.get_full_name(): {
            "sum": 3.14,
            "upper": "",
        },
        ChildState2.get_full_name(): {
            "value": "set_c2_value",
        },
        GrandchildState2.get_full_name(): {
            "cached": "set_c2_value",
        },
        GrandchildState3.get_full_name(): {
            "computed": "",
        },
    }


@pytest.mark.asyncio
async def test_get_state_from_sibling_not_cached(mock_app: rx.App, token: str):
    """A test simulating update_vars_internal when setting cookies with computed vars.

    In that case, a sibling state, UpdateVarsInternalState handles the fetching
    of states that need to have values set. Only the states that have a computed
    var are pre-fetched (like Child3 in this test), so `get_state` needs to
    avoid refetching those already-cached states when getting substates,
    otherwise the set values will be overridden by the freshly deserialized
    version and lost.

    Explicit regression test for https://github.com/reflex-dev/reflex/issues/2851.

    Args:
        mock_app: An app that will be returned by `get_app()`
        token: A token.
    """

    class Parent(BaseState):
        """A root state like rx.State."""

        parent_var: int = 0

    class Child(Parent):
        """A state simulating UpdateVarsInternalState."""

        pass

    class Child2(Parent):
        """An unconnected child state."""

        pass

    class Child3(Parent):
        """A child state with a computed var causing it to be pre-fetched.

        If child3_var gets set to a value, and `get_state` erroneously
        re-fetches it from redis, the value will be lost.
        """

        child3_var: int = 0

        @rx.var
        def v(self):
            pass

    class Grandchild3(Child3):
        """An extra layer of substate to catch an issue discovered in
        _determine_missing_parent_states while writing the regression test where
        invalid parent state names were being constructed.
        """

        pass

    class GreatGrandchild3(Grandchild3):
        """Fetching this state wants to also fetch Child3 as a missing parent.
        However, Child3 should already be cached in the state tree because it
        has a computed var.
        """

        pass

    mock_app.state_manager.state = mock_app.state = Parent

    # Get the top level state via unconnected sibling.
    root = await mock_app.state_manager.get_state(_substate_key(token, Child))
    # Set value in parent_var to assert it does not get refetched later.
    root.parent_var = 1

    if isinstance(mock_app.state_manager, StateManagerRedis):
        # When redis is used, only states with computed vars are pre-fetched.
        assert Child2.get_name() not in root.substates
        assert Child3.get_name() in root.substates  # (due to @rx.var)

    # Get the unconnected sibling state, which will be used to `get_state` other instances.
    child = root.get_substate(Child.get_full_name().split("."))

    # Get an uncached child state.
    child2 = await child.get_state(Child2)
    assert child2.parent_var == 1

    # Set value on already-cached Child3 state (prefetched because it has a Computed Var).
    child3 = await child.get_state(Child3)
    child3.child3_var = 1

    # Get uncached great_grandchild3 state.
    great_grandchild3 = await child.get_state(GreatGrandchild3)

    # Assert that we didn't re-fetch the parent and child3 state from redis
    assert great_grandchild3.parent_var == 1
    assert great_grandchild3.child3_var == 1


# Save a reference to the rx.State to shadow the name State for testing.
RxState = State


def test_potentially_dirty_substates():
    """Test that potentially_dirty_substates returns the correct substates.

    Even if the name "State" is shadowed, it should still work correctly.
    """

    class State(RxState):
        @ComputedVar
        def foo(self) -> str:
            return ""

    class C1(State):
        @ComputedVar
        def bar(self) -> str:
            return ""

    assert RxState._potentially_dirty_substates() == {State}
    assert State._potentially_dirty_substates() == {C1}
    assert C1._potentially_dirty_substates() == set()


def test_router_var_dep() -> None:
    """Test that router var dependencies are correctly tracked."""

    class RouterVarParentState(State):
        """A parent state for testing router var dependency."""

        pass

    class RouterVarDepState(RouterVarParentState):
        """A state with a router var dependency."""

        @rx.var(cache=True)
        def foo(self) -> str:
            return self.router.page.params.get("foo", "")

    foo = RouterVarDepState.computed_vars["foo"]
    State._init_var_dependency_dicts()

    assert foo._deps(objclass=RouterVarDepState) == {"router"}
    assert RouterVarParentState._potentially_dirty_substates() == {RouterVarDepState}
    assert RouterVarParentState._substate_var_dependencies == {
        "router": {RouterVarDepState.get_name()}
    }
    assert RouterVarDepState._computed_var_dependencies == {
        "router": {"foo"},
    }

    rx_state = State()
    parent_state = RouterVarParentState()
    state = RouterVarDepState()

    # link states
    rx_state.substates = {RouterVarParentState.get_name(): parent_state}
    parent_state.parent_state = rx_state
    state.parent_state = parent_state
    parent_state.substates = {RouterVarDepState.get_name(): state}

    assert state.dirty_vars == set()

    # Reassign router var
    state.router = state.router
    assert state.dirty_vars == {"foo", "router"}
    assert parent_state.dirty_substates == {RouterVarDepState.get_name()}


@pytest.mark.asyncio
async def test_setvar(mock_app: rx.App, token: str):
    """Test that setvar works correctly.

    Args:
        mock_app: An app that will be returned by `get_app()`
        token: A token.
    """
    state = await mock_app.state_manager.get_state(_substate_key(token, TestState))

    # Set Var in same state (with Var type casting)
    for event in rx.event.fix_events(
        [TestState.setvar("num1", 42), TestState.setvar("num2", "4.2")], token
    ):
        async for update in state._process(event):
            print(update)
    assert state.num1 == 42
    assert state.num2 == 4.2

    # Set Var in parent state
    for event in rx.event.fix_events([GrandchildState.setvar("array", [43])], token):
        async for update in state._process(event):
            print(update)
    assert state.array == [43]

    # Cannot setvar for non-existant var
    with pytest.raises(AttributeError):
        TestState.setvar("non_existant_var")

    # Cannot setvar for computed vars
    with pytest.raises(AttributeError):
        TestState.setvar("sum")

    # Cannot setvar with non-string
    with pytest.raises(ValueError):
        TestState.setvar(42, 42)


@pytest.mark.skipif("REDIS_URL" not in os.environ, reason="Test requires redis")
@pytest.mark.parametrize(
    "expiration_kwargs, expected_values",
    [
        ({"redis_lock_expiration": 20000}, (20000, constants.Expiration.TOKEN)),
        (
            {"redis_lock_expiration": 50000, "redis_token_expiration": 5600},
            (50000, 5600),
        ),
        ({"redis_token_expiration": 7600}, (constants.Expiration.LOCK, 7600)),
    ],
)
def test_redis_state_manager_config_knobs(tmp_path, expiration_kwargs, expected_values):
    proj_root = tmp_path / "project1"
    proj_root.mkdir()

    config_items = ",\n    ".join(
        f"{key} = {value}" for key, value in expiration_kwargs.items()
    )

    config_string = f"""
import reflex as rx
config = rx.Config(
    app_name="project1",
    redis_url="redis://localhost:6379",
    {config_items}
)
"""
    (proj_root / "rxconfig.py").write_text(dedent(config_string))

    with chdir(proj_root):
        # reload config for each parameter to avoid stale values
        reflex.config.get_config(reload=True)
        from reflex.state import State, StateManager

        state_manager = StateManager.create(state=State)
        assert state_manager.lock_expiration == expected_values[0]  # type: ignore
        assert state_manager.token_expiration == expected_values[1]  # type: ignore


class MixinState(State, mixin=True):
    """A mixin state for testing."""

    num: int = 0
    _backend: int = 0
    _backend_no_default: dict

    @rx.var(cache=True)
    def computed(self) -> str:
        """A computed var on mixin state.

        Returns:
            A computed value.
        """
        return ""


class UsesMixinState(MixinState, State):
    """A state that uses the mixin state."""

    pass


class ChildUsesMixinState(UsesMixinState):
    """A child state that uses the mixin state."""

    pass


def test_mixin_state() -> None:
    """Test that a mixin state works correctly."""
    assert "num" in UsesMixinState.base_vars
    assert "num" in UsesMixinState.vars
    assert UsesMixinState.backend_vars == {"_backend": 0, "_backend_no_default": {}}

    assert "computed" in UsesMixinState.computed_vars
    assert "computed" in UsesMixinState.vars

    assert (
        UsesMixinState(_reflex_internal_init=True)._backend_no_default  # type: ignore
        is not UsesMixinState.backend_vars["_backend_no_default"]
    )


def test_child_mixin_state() -> None:
    """Test that mixin vars are only applied to the highest state in the hierarchy."""
    assert "num" in ChildUsesMixinState.inherited_vars
    assert "num" not in ChildUsesMixinState.base_vars

    assert "computed" in ChildUsesMixinState.inherited_vars
    assert "computed" not in ChildUsesMixinState.computed_vars
