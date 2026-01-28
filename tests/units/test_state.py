from __future__ import annotations

import asyncio
import copy
import dataclasses
import datetime
import functools
import json
import os
import sys
import threading
from collections.abc import AsyncGenerator, Callable
from textwrap import dedent
from typing import Any, ClassVar
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from plotly.graph_objects import Figure
from pytest_mock import MockerFixture

import reflex as rx
import reflex.config
from reflex import constants
from reflex.app import App
from reflex.base import Base
from reflex.constants import CompileVars, RouteVar, SocketEvent
from reflex.constants.state import FIELD_MARKER
from reflex.environment import environment
from reflex.event import Event, EventHandler
from reflex.istate.data import HeaderData, _FrozenDictStrStr
from reflex.istate.manager import StateManager
from reflex.istate.manager.disk import StateManagerDisk
from reflex.istate.manager.memory import StateManagerMemory
from reflex.istate.manager.redis import StateManagerRedis
from reflex.state import (
    BaseState,
    ImmutableMutableProxy,
    ImmutableStateError,
    MutableProxy,
    OnLoadInternalState,
    RouterData,
    State,
    StateProxy,
    StateUpdate,
    _substate_key,
)
from reflex.testing import chdir
from reflex.utils import format, prerequisites, types
from reflex.utils.exceptions import (
    InvalidLockWarningThresholdError,
    LockExpiredError,
    ReflexRuntimeError,
    SetUndefinedStateVarError,
    StateSerializationError,
    UnretrievableVarValueError,
)
from reflex.utils.format import json_dumps
from reflex.utils.token_manager import SocketRecord
from reflex.vars.base import Field, Var, computed_var, field
from tests.units.mock_redis import mock_redis

from .states import GenState

pytest.importorskip("pydantic")


from pydantic import BaseModel as BaseModelV2
from pydantic.v1 import BaseModel as BaseModelV1

from tests.units.states.mutation import MutableTestState

CI = bool(os.environ.get("CI", False))
LOCK_EXPIRATION = 2500 if CI else 300
LOCK_WARNING_THRESHOLD = 1000 if CI else 100
LOCK_WARN_SLEEP = 1.5 if CI else 0.15
LOCK_EXPIRE_SLEEP = 2.5 if CI else 0.4


formatted_router = {
    "route_id": "",
    "url": "",
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
        "raw_headers": {},
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


class TestMixin(BaseState, mixin=True):
    """A test mixin."""

    mixin: rx.Field[str] = rx.field("mixin_value")
    _mixin_backend: rx.Field[int] = rx.field(default_factory=lambda: 10)


class TestState(TestMixin, BaseState):  # pyright: ignore[reportUnsafeMultipleInheritance]
    """A test state."""

    # Set this class as not test one
    __test__ = False

    num1: rx.Field[int]
    num2: float = 3.15
    key: str
    map_key: str = "a"
    array: list[float] = [1, 2, 3.15]
    mapping: rx.Field[dict[str, list[int]]] = rx.field({"a": [1, 2, 3], "b": [4, 5, 6]})
    obj: Object = Object()
    complex: dict[int, Object] = {1: Object(), 2: Object()}
    fig: Figure = Figure()
    dt: datetime.datetime = datetime.datetime.fromisoformat("1989-11-09T18:53:00+01:00")
    _backend: int = 0
    asynctest: int = 0

    @computed_var
    def sum(self) -> float:
        """Dynamically sum the numbers.

        Returns:
            The sum of the numbers.
        """
        return self.num1 + self.num2

    @computed_var
    def upper(self) -> str:
        """Uppercase the key.

        Returns:
            The uppercased key.
        """
        return self.key.upper()

    def do_something(self):
        """Do something."""

    async def set_asynctest(self, value: int):
        """Set the asynctest value. Intentionally overwrite the default setter with an async one.

        Args:
            value: The new value.
        """
        self.asynctest = value


class ChildState(TestState):
    """A child state fixture."""

    value: str
    count: rx.Field[int] = rx.field(23)

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


class GrandchildState2(ChildState2):
    """A grandchild state fixture."""

    @rx.var
    def cached(self) -> str:
        """A cached var.

        Returns:
            The value.
        """
        return self.value


class GrandchildState3(ChildState3):
    """A great grandchild state fixture."""

    @rx.var(cache=False)
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
    return TestState()  # pyright: ignore [reportCallIssue]


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

    for field_name in fields:
        if field_name.startswith("_") or field_name in cls.get_skip_vars():
            continue
        prop = getattr(cls, field_name)
        assert isinstance(prop, Var)
        assert prop._js_expr.split(".")[-1] == field_name + FIELD_MARKER

    assert cls.num1._var_type is int
    assert cls.num2._var_type is float
    assert cls.key._var_type is str


def test_computed_class_var(test_state):
    """Test that the class computed vars are set correctly.

    Args:
        test_state: A state.
    """
    cls = type(test_state)
    vars = [(prop._js_expr, prop._var_type) for prop in cls.computed_vars.values()]
    assert ("sum" + FIELD_MARKER, float) in vars
    assert ("upper" + FIELD_MARKER, str) in vars


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
        "asynctest",
        "mixin",
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


def test_default_value(test_state: TestState):
    """Test that the default value of a var is correct.

    Args:
        test_state: A state.
    """
    assert test_state.num1 == 0
    assert test_state.num2 == 3.15
    assert test_state.key == ""
    assert test_state.sum == 3.15
    assert test_state.upper == ""
    assert test_state._backend == 0
    assert test_state.mixin == "mixin_value"
    assert test_state._mixin_backend == 10
    assert test_state.array == [1, 2, 3.15]


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
    assert set(test_state_dict[test_state.get_name()]) == {
        var + FIELD_MARKER for var in test_state.vars
    }
    assert set(test_state.dict(include_computed=False)[test_state.get_name()]) == {
        var + FIELD_MARKER for var in test_state.base_vars
    }


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
    prop = TestState.array[TestState.num1]  # pyright: ignore [reportCallIssue, reportArgumentType]
    assert (
        str(prop)
        == f"{TestState.get_name()}.array{FIELD_MARKER}?.at?.({TestState.get_name()}.num1{FIELD_MARKER})"
    )

    prop = TestState.mapping["a"][TestState.num1]  # pyright: ignore [reportCallIssue, reportArgumentType]
    assert (
        str(prop)
        == f'{TestState.get_name()}.mapping{FIELD_MARKER}?.["a"]?.at?.({TestState.get_name()}.num1{FIELD_MARKER})'
    )

    prop = TestState.mapping[TestState.map_key]
    assert (
        str(prop)
        == f"{TestState.get_name()}.mapping{FIELD_MARKER}?.[{TestState.get_name()}.map_key{FIELD_MARKER}]"
    )


def test_class_attributes():
    """Test that we can get class attributes."""
    prop = TestState.obj.prop1
    assert str(prop) == f'{TestState.get_name()}.obj{FIELD_MARKER}?.["prop1"]'

    prop = TestState.complex[1].prop1
    assert str(prop) == f'{TestState.get_name()}.complex{FIELD_MARKER}?.[1]?.["prop1"]'


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
        TestState.get_class_substate((
            ChildState.get_name(),
            GrandchildState.get_name(),
        ))
        == GrandchildState
    )
    with pytest.raises(ValueError):
        TestState.get_class_substate(("invalid_child",))
    with pytest.raises(ValueError):
        TestState.get_class_substate((
            ChildState.get_name(),
            "invalid_child",
        ))


def test_get_class_var():
    """Test getting the var of a class."""
    assert TestState.get_class_var(("num1",)).equals(TestState.num1)
    assert TestState.get_class_var(("num2",)).equals(TestState.num2)
    assert ChildState.get_class_var(("value",)).equals(ChildState.value)
    assert GrandchildState.get_class_var(("value2",)).equals(GrandchildState.value2)
    assert TestState.get_class_var((ChildState.get_name(), "value")).equals(
        ChildState.value
    )
    assert TestState.get_class_var((
        ChildState.get_name(),
        GrandchildState.get_name(),
        "value2",
    )).equals(
        GrandchildState.value2,
    )
    assert ChildState.get_class_var((GrandchildState.get_name(), "value2")).equals(
        GrandchildState.value2,
    )
    with pytest.raises(ValueError):
        TestState.get_class_var(("invalid_var",))
    with pytest.raises(ValueError):
        TestState.get_class_var((
            ChildState.get_name(),
            "invalid_var",
        ))


def test_set_class_var():
    """Test setting the var of a class."""
    with pytest.raises(AttributeError):
        TestState.num3  # pyright: ignore [reportAttributeAccessIssue]
    TestState._set_var(
        "num3", Var(_js_expr="num3", _var_type=int)._var_set_state(TestState)
    )
    var = TestState.num3  # pyright: ignore [reportAttributeAccessIssue]
    assert var._js_expr == TestState.get_full_name() + ".num3"
    assert var._var_type is int
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
        test_state.get_substate((
            ChildState.get_name(),
            GrandchildState.get_name(),
            "invalid",
        ))


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


def test_reset(test_state: TestState, child_state: ChildState):
    """Test resetting the state.

    Args:
        test_state: A state.
        child_state: A child state.
    """
    # Set some values.
    test_state.num1 = 1
    test_state.num2 = 2
    test_state._backend = 3
    child_state.value = "test"

    # Reset the state.
    test_state.reset()

    # The values should be reset.
    assert test_state.num1 == 0
    assert test_state.num2 == 3.15
    assert test_state._backend == 0
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
        "_backend",
        "mixin",
        "_mixin_backend",
        "asynctest",
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
    async for update in test_state._process(event):
        # The event should update the value.
        assert test_state.num1 == 69

        # The delta should contain the changes, including computed vars.
        assert update.delta == {
            TestState.get_full_name(): {
                "num1" + FIELD_MARKER: 69,
                "sum" + FIELD_MARKER: 72.15,
            },
            GrandchildState3.get_full_name(): {"computed" + FIELD_MARKER: ""},
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
    async for update in test_state._process(event):
        assert child_state.value == "HI"
        assert child_state.count == 24
        assert update.delta == {
            # TestState.get_full_name(): {"sum": 3.14, "upper": ""},
            ChildState.get_full_name(): {
                "value" + FIELD_MARKER: "HI",
                "count" + FIELD_MARKER: 24,
            },
            GrandchildState3.get_full_name(): {"computed" + FIELD_MARKER: ""},
        }
        test_state._clean()

    # Test with the grandchild state.
    assert grandchild_state.value2 == ""
    event = Event(
        token="t",
        name=f"{GrandchildState.get_full_name()}.set_value2",
        payload={"value": "new"},
    )
    async for update in test_state._process(event):
        assert grandchild_state.value2 == "new"
        assert update.delta == {
            # TestState.get_full_name(): {"sum": 3.14, "upper": ""},
            GrandchildState.get_full_name(): {"value2" + FIELD_MARKER: "new"},
            GrandchildState3.get_full_name(): {"computed" + FIELD_MARKER: ""},
        }


@pytest.mark.asyncio
async def test_process_event_generator():
    """Test event handlers that generate multiple updates."""
    gen_state = GenState()  # pyright: ignore [reportCallIssue]
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
                GenState.get_full_name(): {"value" + FIELD_MARKER: count},
            }
            assert not update.final

    assert count == 6


def test_get_client_token(test_state, router_data):
    """Test that the token obtained from the router_data is correct.

    Args:
        test_state: The test state.
        router_data: The router data fixture.
    """
    test_state.router = RouterData.from_router_data(router_data)
    assert (
        test_state.router.session.client_token == "b181904c-3953-4a79-dc18-ae9518c22f05"
    )


def test_get_sid(test_state, router_data):
    """Test getting session id.

    Args:
        test_state: A state.
        router_data: The router data fixture.
    """
    test_state.router = RouterData.from_router_data(router_data)
    assert test_state.router.session.session_id == "9fpxSzPb9aFMb4wFAAAH"


def test_get_headers(
    test_state: TestState,
    router_data: dict[str, str | dict],
    router_data_headers: dict[str, str],
):
    """Test getting client headers.

    Args:
        test_state: A state.
        router_data: The router data fixture.
        router_data_headers: The expected headers.
    """
    print(router_data_headers)
    test_state.router = RouterData.from_router_data(router_data)
    print(test_state.router.headers)
    assert test_state.router.headers == HeaderData(
        **{format.to_snake_case(k): v for k, v in router_data_headers.items()},
        raw_headers=_FrozenDictStrStr(**router_data_headers),
    )


def test_get_client_ip(test_state, router_data):
    """Test getting client IP.

    Args:
        test_state: A state.
        router_data: The router data fixture.
    """
    test_state.router = RouterData.from_router_data(router_data)
    assert test_state.router.session.client_ip == "127.0.0.1"


def test_get_current_page(test_state):
    assert test_state.router._page.path == ""

    route = "mypage/subpage"
    test_state.router = RouterData.from_router_data({RouteVar.PATH: route})
    assert test_state.router._page.path == route


def test_get_query_params(test_state):
    assert test_state.router._page.params == {}

    params = {"p1": "a", "p2": "b"}
    test_state.router = RouterData.from_router_data({RouteVar.QUERY: params})
    assert dict(test_state.router._page.params) == params


def test_add_var():
    class DynamicState(BaseState):
        pass

    ds1 = DynamicState()
    assert "dynamic_int" not in ds1.__dict__
    assert not hasattr(ds1, "dynamic_int")
    ds1.add_var("dynamic_int", int, 42)
    # Existing instances get the BaseVar
    assert ds1.dynamic_int.equals(DynamicState.dynamic_int)  # pyright: ignore [reportAttributeAccessIssue]
    # New instances get an actual value with the default
    assert DynamicState().dynamic_int == 42  # pyright: ignore[reportAttributeAccessIssue]

    ds1.add_var("dynamic_list", list[int], [5, 10])
    assert ds1.dynamic_list.equals(DynamicState.dynamic_list)  # pyright: ignore [reportAttributeAccessIssue]
    ds2 = DynamicState()
    assert ds2.dynamic_list == [5, 10]  # pyright: ignore[reportAttributeAccessIssue]
    ds2.dynamic_list.append(15)  # pyright: ignore[reportAttributeAccessIssue]
    assert ds2.dynamic_list == [5, 10, 15]  # pyright: ignore[reportAttributeAccessIssue]
    assert DynamicState().dynamic_list == [5, 10]  # pyright: ignore[reportAttributeAccessIssue]

    ds1.add_var("dynamic_dict", dict[str, int], {"k1": 5, "k2": 10})
    assert ds1.dynamic_dict.equals(DynamicState.dynamic_dict)  # pyright: ignore [reportAttributeAccessIssue]
    assert ds2.dynamic_dict.equals(DynamicState.dynamic_dict)  # pyright: ignore [reportAttributeAccessIssue]
    assert DynamicState().dynamic_dict == {"k1": 5, "k2": 10}  # pyright: ignore[reportAttributeAccessIssue]


def test_add_var_default_handlers(test_state):
    test_state.add_var("rand_int", int, 10)
    assert "set_rand_int" in test_state.event_handlers
    assert isinstance(test_state.event_handlers["set_rand_int"], EventHandler)


class InterdependentState(BaseState):
    """A state with 3 vars and 3 computed vars.

    x: a variable that no computed var depends on
    v1: a variable that one computed var directly depends on
    _v2: a backend variable that one computed var directly depends on

    v1x2: a computed var that depends on v1
    v2x2: a computed var that depends on backend var _v2
    v1x2x2: a computed var that depends on computed var v1x2
    """

    x: int = 0
    v1: int = 0
    _v2: int = 1

    @rx.var
    def v1x2(self) -> int:
        """Depends on var v1.

        Returns:
            Var v1 multiplied by 2
        """
        return self.v1 * 2

    @rx.var
    def v2x2(self) -> int:
        """Depends on backend var _v2.

        Returns:
            backend var _v2 multiplied by 2
        """
        return self._v2 * 2

    @rx.var(backend=True)
    def v2x2_backend(self) -> int:
        """Depends on backend var _v2.

        Returns:
            backend var _v2 multiplied by 2
        """
        return self._v2 * 2

    @rx.var
    def v1x2x2(self) -> int:
        """Depends on ComputedVar v1x2.

        Returns:
            ComputedVar v1x2 multiplied by 2
        """
        return self.v1x2 * 2

    @rx.var
    def _v3(self) -> int:
        """Depends on backend var _v2.

        Returns:
            The value of the backend variable.
        """
        return self._v2

    @rx.var
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
    d.pop("router" + FIELD_MARKER)
    assert d == {
        "x" + FIELD_MARKER: 0,
        "v1" + FIELD_MARKER: 0,
        "v1x2" + FIELD_MARKER: 0,
        "v2x2" + FIELD_MARKER: 2,
        "v1x2x2" + FIELD_MARKER: 0,
        "v3x2" + FIELD_MARKER: 2,
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
        interdependent_state.get_full_name(): {"x" + FIELD_MARKER: 5},
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
        interdependent_state.get_full_name(): {
            "v1" + FIELD_MARKER: 1,
            "v1x2" + FIELD_MARKER: 2,
            "v1x2x2" + FIELD_MARKER: 4,
        },
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
        interdependent_state.get_full_name(): {
            "v2x2" + FIELD_MARKER: 4,
            "v3x2" + FIELD_MARKER: 4,
        },
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
        @computed_var
        def rendered_var(self) -> int:
            return self.v

    ms = MainState()
    cs = ms.substates[ChildState.get_name()]
    assert ms.v == 2
    assert isinstance(cs, ChildState)
    assert cs.v == 2
    assert cs.rendered_var == 2


def test_conditional_computed_vars():
    """Test that computed vars can have conditionals."""

    class MainState(BaseState):
        flag: bool = False
        t1: str = "a"
        t2: str = "b"

        @computed_var
        def rendered_var(self) -> str:
            if self.flag:
                return self.t1
            return self.t2

    ms = MainState()
    # Initially there are no dirty computed vars.
    assert ms._dirty_computed_vars(from_vars={"flag"}) == {
        (MainState.get_full_name(), "rendered_var")
    }
    assert ms._dirty_computed_vars(from_vars={"t2"}) == {
        (MainState.get_full_name(), "rendered_var")
    }
    assert ms._dirty_computed_vars(from_vars={"t1"}) == {
        (MainState.get_full_name(), "rendered_var")
    }
    assert ms.computed_vars["rendered_var"]._deps(objclass=MainState) == {
        MainState.get_full_name(): {"flag", "t1", "t2"}
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
    sub_state = ms.substates[SubState.get_name()]
    assert isinstance(sub_state, SubState)
    sub_state.set_v3(2)
    assert ms.v == 2

    # ensure handler can be called from substate (referencing grandparent handler)
    sub_sub_state = ms.get_substate(tuple(SubSubState.get_full_name().split(".")))
    assert isinstance(sub_sub_state, SubSubState)
    sub_sub_state.set_v4(3)
    assert ms.v == 3


def test_computed_var_cached():
    """Test that a ComputedVar doesn't recalculate when accessed."""
    comp_v_calls = 0

    class ComputedState(BaseState):
        v: int = 0

        @rx.var
        def comp_v(self) -> int:
            nonlocal comp_v_calls
            comp_v_calls += 1
            return self.v

    cs = ComputedState()
    assert cs.dict()[cs.get_full_name()]["v" + FIELD_MARKER] == 0
    assert comp_v_calls == 1
    assert cs.dict()[cs.get_full_name()]["comp_v" + FIELD_MARKER] == 0
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

        @rx.var(cache=False)
        def no_cache_v(self) -> int:
            return self.v

        @rx.var
        def dep_v(self) -> int:
            return self.no_cache_v

        @rx.var
        def comp_v(self) -> int:
            return self.v

    cs = ComputedState()
    assert cs.dirty_vars == set()
    assert cs.get_delta() == {
        cs.get_name(): {"no_cache_v" + FIELD_MARKER: 0, "dep_v" + FIELD_MARKER: 0}
    }
    cs._clean()
    assert cs.dirty_vars == set()
    assert cs.get_delta() == {
        cs.get_name(): {"no_cache_v" + FIELD_MARKER: 0, "dep_v" + FIELD_MARKER: 0}
    }
    cs._clean()
    assert cs.dirty_vars == set()
    cs.v = 1
    assert cs.dirty_vars == {"v", "comp_v", "dep_v", "no_cache_v"}
    assert cs.get_delta() == {
        cs.get_name(): {
            "v" + FIELD_MARKER: 1,
            "no_cache_v" + FIELD_MARKER: 1,
            "dep_v" + FIELD_MARKER: 1,
            "comp_v" + FIELD_MARKER: 1,
        }
    }
    cs._clean()
    assert cs.dirty_vars == set()
    assert cs.get_delta() == {
        cs.get_name(): {"no_cache_v" + FIELD_MARKER: 1, "dep_v" + FIELD_MARKER: 1}
    }
    cs._clean()
    assert cs.dirty_vars == set()
    assert cs.get_delta() == {
        cs.get_name(): {"no_cache_v" + FIELD_MARKER: 1, "dep_v" + FIELD_MARKER: 1}
    }
    cs._clean()
    assert cs.dirty_vars == set()


def test_computed_var_depends_on_parent_non_cached():
    """Child state cached var that depends on parent state un cached var is always recalculated."""
    counter = 0

    class ParentState(BaseState):
        @rx.var(cache=False)
        def no_cache_v(self) -> int:
            nonlocal counter
            counter += 1
            return counter

    class ChildState(ParentState):
        @rx.var
        def dep_v(self) -> int:
            return self.no_cache_v

    ps = ParentState()
    cs = ps.substates[ChildState.get_name()]

    assert ps.dirty_vars == set()
    assert cs.dirty_vars == set()

    dict1 = json.loads(json_dumps(ps.dict()))
    assert dict1[ps.get_full_name()] == {
        "no_cache_v" + FIELD_MARKER: 1,
        "router" + FIELD_MARKER: formatted_router,
    }
    assert dict1[cs.get_full_name()] == {"dep_v" + FIELD_MARKER: 2}
    dict2 = json.loads(json_dumps(ps.dict()))
    assert dict2[ps.get_full_name()] == {
        "no_cache_v" + FIELD_MARKER: 3,
        "router" + FIELD_MARKER: formatted_router,
    }
    assert dict2[cs.get_full_name()] == {"dep_v" + FIELD_MARKER: 4}
    dict3 = json.loads(json_dumps(ps.dict()))
    assert dict3[ps.get_full_name()] == {
        "no_cache_v" + FIELD_MARKER: 5,
        "router" + FIELD_MARKER: formatted_router,
    }
    assert dict3[cs.get_full_name()] == {"dep_v" + FIELD_MARKER: 6}
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

        @rx.var
        def cached_x_side_effect(self) -> int:
            self.handler()
            nonlocal counter
            counter += 1
            return counter

    if use_partial:
        HandlerState.handler = functools.partial(HandlerState.handler.fn)  # pyright: ignore [reportFunctionMemberAccess]
        assert isinstance(HandlerState.handler, functools.partial)
    else:
        assert isinstance(HandlerState.handler, EventHandler)

    s = HandlerState()
    assert (
        HandlerState.get_full_name(),
        "cached_x_side_effect",
    ) in s._var_dependencies["x"]
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
        y: list[int] = [1, 2, 3]
        _z: list[int] = [1, 2, 3]

        @property
        def testprop(self) -> int:
            return self.v

        @rx.var
        def comp_v(self) -> int:
            """Direct access.

            Returns:
                The value of self.v.
            """
            return self.v

        @rx.var(backend=True)
        def comp_v_backend(self) -> int:
            """Direct access backend var.

            Returns:
                The value of self.v.
            """
            return self.v

        @rx.var
        def comp_v_via_property(self) -> int:
            """Access v via property.

            Returns:
                The value of v via property.
            """
            return self.testprop

        @rx.var
        def comp_w(self) -> Callable[[], int]:
            """Nested lambda.

            Returns:
                A lambda that returns the value of self.w.
            """
            return lambda: self.w

        @rx.var
        def comp_x(self) -> Callable[[], int]:
            """Nested function.

            Returns:
                A function that returns the value of self.x.
            """

            def _():
                return self.x

            return _

        @rx.var
        def comp_y(self) -> list[int]:
            """Comprehension iterating over attribute.

            Returns:
                A list of the values of self.y.
            """
            return [round(y) for y in self.y]

        @rx.var
        def comp_z(self) -> list[bool]:
            """Comprehension accesses attribute.

            Returns:
                A list of whether the values 0-4 are in self._z.
            """
            return [z in self._z for z in range(5)]

    cs = ComputedState()
    assert cs._var_dependencies["v"] == {
        (ComputedState.get_full_name(), "comp_v"),
        (ComputedState.get_full_name(), "comp_v_backend"),
        (ComputedState.get_full_name(), "comp_v_via_property"),
    }
    assert cs._var_dependencies["w"] == {(ComputedState.get_full_name(), "comp_w")}
    assert cs._var_dependencies["x"] == {(ComputedState.get_full_name(), "comp_x")}
    assert cs._var_dependencies["y"] == {(ComputedState.get_full_name(), "comp_y")}
    assert cs._var_dependencies["_z"] == {(ComputedState.get_full_name(), "comp_z")}


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


@pytest.fixture
def mutable_state() -> MutableTestState:
    """Create a Test state containing mutable types.

    Returns:
        A state object.
    """
    return MutableTestState()


def test_setattr_of_mutable_types(mutable_state: MutableTestState):
    """Test that mutable types are converted to corresponding Reflex wrappers.

    Args:
        mutable_state: A test state.
    """
    array = mutable_state.array
    hashmap = mutable_state.hashmap
    test_set = mutable_state.test_set

    assert isinstance(array, MutableProxy)
    assert isinstance(array, list)
    assert isinstance(array[1], MutableProxy)
    assert isinstance(array[1], list)
    assert isinstance(array[2], MutableProxy)
    assert isinstance(array[2], dict)
    assert isinstance(array[:], list)
    assert not isinstance(array[:], MutableProxy)
    assert isinstance(array[:][1], MutableProxy)
    assert isinstance(array[:][1], list)

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

    mutable_state.reassign_mutables()

    array = mutable_state.array
    hashmap = mutable_state.hashmap
    test_set = mutable_state.test_set

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


def test_error_on_state_method_shadow():
    """Test that an error is thrown when an event handler shadows a state method."""
    with pytest.raises(NameError) as err:

        class InvalidTest(BaseState):
            def reset(self):
                pass

    assert (
        err.value.args[0]
        == "The event handler name `reset` shadows a builtin State method; use a different name instead"
    )


@pytest.mark.asyncio
async def test_state_with_invalid_yield(capsys: pytest.CaptureFixture[str], mock_app):
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
        assert update.events == rx.event.fix_events(
            [
                rx.toast(
                    "An error occurred.",
                    level="error",
                    fallback_to_alert=True,
                    description="TypeError: Your handler test_state_with_invalid_yield.<locals>.StateWithInvalidYield.invalid_handler must only return/yield: None, Events or other EventHandlers referenced by their class (i.e. using `type(self)` or other class references). Returned events of types <class 'int'>..<br/>See logs for details.",
                    id="backend_error",
                    position="top-center",
                    style={"width": "500px"},
                )
            ],
            token="",
        )
    captured = capsys.readouterr()
    assert "must only return/yield: None, Events or other EventHandlers" in captured.err


@pytest_asyncio.fixture(
    loop_scope="function", scope="function", params=["in_process", "disk", "redis"]
)
async def state_manager(request) -> AsyncGenerator[StateManager, None]:
    """Instance of state manager parametrized for redis and in-process.

    Args:
        request: pytest request object.

    Yields:
        A state manager instance
    """
    state_manager = StateManager.create(state=TestState)
    if request.param == "redis":
        if not isinstance(state_manager, StateManagerRedis):
            state_manager = StateManagerRedis(state=TestState, redis=mock_redis())
    elif request.param == "disk":
        # explicitly NOT using redis
        state_manager = StateManagerDisk(state=TestState)
        assert not state_manager._states_locks
    else:
        state_manager = StateManagerMemory(state=TestState)
        assert not state_manager._states_locks

    yield state_manager

    await state_manager.close()


@pytest.fixture
def substate_token(state_manager, token) -> str:
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
        assert isinstance(state, TestState)
        complex_1 = state.complex[1]
        assert isinstance(complex_1, MutableProxy)
        state.complex[3] = complex_1

    if environment.REFLEX_OPLOCK_ENABLED.get():
        await state_manager.close()

    # lock should be dropped after exiting the context
    if isinstance(state_manager, StateManagerRedis):
        assert (await state_manager.redis.get(f"{token}_lock")) is None
    elif isinstance(state_manager, (StateManagerMemory, StateManagerDisk)):
        assert not state_manager._states_locks[token].locked()

        # separate instances should NOT share locks
        sm2 = type(state_manager)(state=TestState)
        assert sm2._state_manager_lock is state_manager._state_manager_lock
        assert not sm2._states_locks
        if state_manager._states_locks:
            assert sm2._states_locks != state_manager._states_locks

        await sm2.close()


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
            assert isinstance(state, TestState)
            state.num1 += 1

    tasks = [asyncio.create_task(_coro()) for _ in range(n_coroutines)]

    for f in asyncio.as_completed(tasks):
        await f

    if environment.REFLEX_OPLOCK_ENABLED.get():
        await state_manager.close()

    test_state = await state_manager.get_state(substate_token)
    assert isinstance(test_state, TestState)
    assert test_state.num1 == exp_num1

    if isinstance(state_manager, StateManagerRedis):
        assert (await state_manager.redis.get(f"{token}_lock")) is None
    elif isinstance(state_manager, (StateManagerMemory, StateManagerDisk)):
        assert token in state_manager._states_locks
        assert not state_manager._states_locks[token].locked()


@pytest_asyncio.fixture(loop_scope="function", scope="function")
async def state_manager_redis() -> AsyncGenerator[StateManager, None]:
    """Instance of state manager for redis only.

    Yields:
        A state manager instance
    """
    state_manager = StateManager.create(TestState)

    if not isinstance(state_manager, StateManagerRedis):
        # Create a mocked redis client instead of skipping.
        state_manager = StateManagerRedis(state=TestState, redis=mock_redis())

    yield state_manager

    await state_manager.close()


@pytest.fixture
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
    state_manager_redis: StateManagerRedis, token: str, substate_token_redis: str
):
    """Test that the state manager lock expires and raises exception exiting context.

    Args:
        state_manager_redis: A state manager instance.
        token: A token.
        substate_token_redis: A token + substate name for looking up in state manager.
    """
    state_manager_redis.lock_expiration = LOCK_EXPIRATION
    state_manager_redis.lock_warning_threshold = LOCK_WARNING_THRESHOLD

    loop_exception = None

    def loop_exception_handler(loop, context):
        """Catch the LockExpiredError from the event loop.

        Args:
            loop: The event loop.
            context: The exception context.
        """
        nonlocal loop_exception
        loop_exception = context["exception"]

    asyncio.get_event_loop().set_exception_handler(loop_exception_handler)

    async with state_manager_redis.modify_state(substate_token_redis):
        await asyncio.sleep(0.01)

    if environment.REFLEX_OPLOCK_ENABLED.get():
        async with state_manager_redis.modify_state(substate_token_redis):
            await asyncio.sleep(LOCK_EXPIRE_SLEEP)
        await asyncio.sleep(LOCK_EXPIRE_SLEEP)
        assert loop_exception is not None
        with pytest.raises(LockExpiredError):
            raise loop_exception
    else:
        with pytest.raises(LockExpiredError):
            async with state_manager_redis.modify_state(substate_token_redis):
                await asyncio.sleep(LOCK_EXPIRE_SLEEP)
        assert loop_exception is None


@pytest.mark.asyncio
async def test_state_manager_lock_expire_contend(
    state_manager_redis: StateManagerRedis, token: str, substate_token_redis: str
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
    state_manager_redis.lock_warning_threshold = LOCK_WARNING_THRESHOLD

    loop_exception = None

    def loop_exception_handler(loop, context):
        """Catch the LockExpiredError from the event loop.

        Args:
            loop: The event loop.
            context: The exception context.
        """
        nonlocal loop_exception
        loop_exception = context["exception"]

    asyncio.get_event_loop().set_exception_handler(loop_exception_handler)

    order = []
    waiter_event = asyncio.Event()

    async def _coro_blocker():
        async with state_manager_redis.modify_state(substate_token_redis) as state:
            order.append("blocker")
            waiter_event.set()
            await asyncio.sleep(LOCK_EXPIRE_SLEEP)
            state.num1 = unexp_num1

    async def _coro_waiter():
        await waiter_event.wait()
        async with state_manager_redis.modify_state(substate_token_redis) as state:
            order.append("waiter")
            state.num1 = exp_num1

    tasks = [
        asyncio.create_task(_coro_blocker()),
        asyncio.create_task(_coro_waiter()),
    ]
    if environment.REFLEX_OPLOCK_ENABLED.get():
        await tasks[0]  # Doesn't raise during `modify_state`, only on exit
        await tasks[1]
        await asyncio.sleep(LOCK_EXPIRE_SLEEP)
        assert loop_exception is not None
        with pytest.raises(LockExpiredError):
            raise loop_exception
        # In oplock mode, the blocker block's both updates
        test_state = await state_manager_redis.get_state(substate_token_redis)
        assert isinstance(test_state, TestState)
        assert test_state.num1 == 0
    else:
        with pytest.raises(LockExpiredError):
            await tasks[0]
        await tasks[1]
        assert loop_exception is None
        test_state = await state_manager_redis.get_state(substate_token_redis)
        assert isinstance(test_state, TestState)
        assert test_state.num1 == exp_num1

    assert order == ["blocker", "waiter"]


@pytest.mark.asyncio
async def test_state_manager_lock_warning_threshold_contend(
    state_manager_redis: StateManagerRedis,
    token: str,
    substate_token_redis: str,
    mocker: MockerFixture,
):
    """Test that the state manager triggers a warning when lock contention exceeds the warning threshold.

    Args:
        state_manager_redis: A state manager instance.
        token: A token.
        substate_token_redis: A token + substate name for looking up in state manager.
        mocker: Pytest mocker object.
    """
    console_warn = mocker.patch("reflex.utils.console.warn")

    state_manager_redis.lock_expiration = LOCK_EXPIRATION
    state_manager_redis.lock_warning_threshold = LOCK_WARNING_THRESHOLD

    order = []

    async def _coro_blocker():
        async with state_manager_redis.modify_state(substate_token_redis):
            order.append("blocker")
            await asyncio.sleep(LOCK_WARN_SLEEP)

    tasks = [
        asyncio.create_task(_coro_blocker()),
    ]

    await tasks[0]
    if environment.REFLEX_OPLOCK_ENABLED.get():
        # When Oplock is enabled, we don't warn when lock is held too long.
        console_warn.assert_not_called()
    else:
        console_warn.assert_called()
        assert console_warn.call_count == 7


class CopyingAsyncMock(AsyncMock):
    """An AsyncMock, but deepcopy the args and kwargs first."""

    def __call__(self, *args, **kwargs):
        """Call the mock.

        Args:
            args: the arguments passed to the mock
            kwargs: the keyword arguments passed to the mock

        Returns:
            The result of the mock call
        """
        args = copy.deepcopy(args)
        kwargs = copy.deepcopy(kwargs)
        return super().__call__(*args, **kwargs)


@pytest.fixture
def mock_app_simple(monkeypatch) -> rx.App:
    """Simple Mock app fixture.

    Args:
        monkeypatch: Pytest monkeypatch object.

    Returns:
        The app, after mocking out prerequisites.get_app()
    """
    app = App(_state=TestState)

    app_module = Mock()

    setattr(app_module, CompileVars.APP, app)
    app._state = TestState
    app.event_namespace.emit = CopyingAsyncMock()  # pyright: ignore [reportOptionalMemberAccess]

    def _mock_get_app(*args, **kwargs):
        return app_module

    monkeypatch.setattr(prerequisites, "get_app", _mock_get_app)
    return app


@pytest.fixture
def mock_app(mock_app_simple: rx.App, state_manager: StateManager) -> rx.App:
    """Mock app fixture.

    Args:
        mock_app_simple: A simple mock app.
        state_manager: A state manager.

    Returns:
        The app, after mocking out prerequisites.get_app()
    """
    mock_app_simple._state_manager = state_manager
    return mock_app_simple


@dataclasses.dataclass
class ModelDC:
    """A dataclass."""

    foo: str = "bar"
    ls: list[dict] = dataclasses.field(default_factory=list)

    def set_foo(self, val: str):
        """Set the attribute foo.

        Args:
            val: The value to set.
        """
        self.foo = val

    def double_foo(self) -> str:
        """Concatenate foo with foo.

        Returns:
            foo + foo
        """
        return self.foo + self.foo

    def copy(self, **kwargs) -> ModelDC:
        """Create a copy of the dataclass with updated fields.

        Returns:
            A new instance of ModelDC with updated fields.
        """
        return dataclasses.replace(self, **kwargs)

    def append_to_ls(self, item: dict):
        """Append an item to the list attribute ls.

        Args:
            item: The item to append.
        """
        self.ls.append(item)

    @classmethod
    def from_dict(cls, data: dict) -> ModelDC:
        """Create an instance of ModelDC from a dictionary.

        Args:
            data: The dictionary to create the instance from.

        Returns:
            An instance of ModelDC.
        """
        return cls(**data)


@pytest.mark.asyncio
async def test_state_proxy(
    grandchild_state: GrandchildState, mock_app: rx.App, token: str
):
    """Test that the state proxy works.

    Args:
        grandchild_state: A grandchild state.
        mock_app: An app that will be returned by `get_app()`
        token: A token.
    """
    child_state = grandchild_state.parent_state
    assert child_state is not None
    parent_state = child_state.parent_state
    assert parent_state is not None
    router_data = RouterData.from_router_data({
        "query": {},
        "token": token,
        "sid": "test_sid",
    })
    grandchild_state.router = router_data
    namespace = mock_app.event_namespace
    assert namespace is not None
    namespace.sid_to_token[router_data.session.session_id] = token
    namespace._token_manager.instance_id = "mock"
    namespace._token_manager.token_to_socket[token] = SocketRecord(
        instance_id="mock", sid=router_data.session.session_id
    )
    if isinstance(mock_app.state_manager, (StateManagerMemory, StateManagerDisk)):
        mock_app.state_manager.states[parent_state.router.session.client_token] = (
            parent_state
        )
    elif isinstance(mock_app.state_manager, StateManagerRedis):
        pickle_state = parent_state._serialize()
        if pickle_state:
            await mock_app.state_manager.redis.set(
                _substate_key(parent_state.router.session.client_token, parent_state),
                pickle_state,
                ex=mock_app.state_manager.token_expiration,
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
        if isinstance(mock_app.state_manager, (StateManagerMemory, StateManagerDisk)):
            # For in-process store, only one instance of the state exists
            assert sp.__wrapped__ is grandchild_state
        else:
            # When redis is used, a new+updated instance is assigned to the proxy
            assert sp.__wrapped__ is not grandchild_state
        sp.value2 = "42"
    assert not sp._self_mutable  # proxy is not mutable after exiting context
    assert sp._self_actx is None
    assert sp.value2 == "42"

    if environment.REFLEX_OPLOCK_ENABLED.get():
        await mock_app.state_manager.close()

    # Get the state from the state manager directly and check that the value is updated
    gotten_state = await mock_app.state_manager.get_state(
        _substate_key(grandchild_state.router.session.client_token, grandchild_state)
    )
    if isinstance(mock_app.state_manager, (StateManagerMemory, StateManagerDisk)):
        # For in-process store, only one instance of the state exists
        assert gotten_state is parent_state
    else:
        assert gotten_state is not parent_state
    gotten_grandchild_state = gotten_state.get_substate(sp._self_substate_path)
    assert gotten_grandchild_state is not None
    assert isinstance(gotten_grandchild_state, GrandchildState)
    assert gotten_grandchild_state.value2 == "42"

    # ensure state update was emitted
    assert mock_app.event_namespace is not None
    mock_app.event_namespace.emit.assert_called_once()  # pyright: ignore [reportAttributeAccessIssue]
    mcall = mock_app.event_namespace.emit.mock_calls[0]  # pyright: ignore [reportAttributeAccessIssue]
    assert mcall.args[0] == str(SocketEvent.EVENT)
    assert mcall.args[1] == StateUpdate(
        delta={
            TestState.get_full_name(): {"router" + FIELD_MARKER: router_data},
            grandchild_state.get_full_name(): {
                "value2" + FIELD_MARKER: "42",
            },
            GrandchildState3.get_full_name(): {
                "computed" + FIELD_MARKER: "",
            },
        },
        final=None,
    )
    assert mcall.kwargs["to"] == grandchild_state.router.session.session_id


class BackgroundTaskState(BaseState):
    """A state with a background task."""

    order: list[str] = []
    dict_list: dict[str, list[int]] = {"foo": [1, 2, 3]}
    dc: ModelDC = ModelDC()

    def __init__(self, **kwargs):  # noqa: D107
        super().__init__(**kwargs)
        self.router_data = {"simulate": "hydrate"}

    @rx.var(cache=False)
    def computed_order(self) -> list[str]:
        """Get the order as a computed var.

        Returns:
            The value of 'order' var.
        """
        return self.order

    @rx.event(background=True)
    async def background_task(self):
        """A background task that updates the state."""
        async with self:
            assert not self.order
            self.order.append("background_task:start")

        assert isinstance(self, StateProxy)
        with pytest.raises(ImmutableStateError):
            self.order.append("bad idea")

        with pytest.raises(ImmutableStateError):
            # Cannot manipulate dataclass attributes.
            self.dc.foo = "baz"

        with pytest.raises(ImmutableStateError):
            # Even nested access to mutables raises an exception.
            self.dict_list["foo"].append(42)

        with pytest.raises(ImmutableStateError):
            # Cannot modify dataclass list attribute.
            self.dc.ls.append({"foo": "bar"})

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

    @rx.event(background=True)
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

    @rx.event(background=True)
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
    router_data = {"query": {}, "token": token}
    sid = "test_sid"
    namespace = mock_app.event_namespace
    assert namespace is not None
    namespace.sid_to_token[sid] = token
    namespace._token_manager.instance_id = "mock"
    namespace._token_manager.token_to_socket[token] = SocketRecord(
        instance_id="mock", sid=sid
    )
    mock_app.state_manager.state = mock_app._state = BackgroundTaskState
    async for update in rx.app.process(
        mock_app,
        Event(
            token=token,
            name=f"{BackgroundTaskState.get_full_name()}.background_task",
            router_data=router_data,
            payload={},
        ),
        sid=sid,
        headers={},
        client_ip="",
    ):
        # background task returns empty update immediately
        assert update == StateUpdate()

    # wait for the coroutine to start
    await asyncio.sleep(0.5 if CI else 0.1)
    assert len(mock_app._background_tasks) == 1

    # Process another normal event
    async for update in rx.app.process(
        mock_app,
        Event(
            token=token,
            name=f"{BackgroundTaskState.get_full_name()}.other",
            router_data=router_data,
            payload={},
        ),
        sid=sid,
        headers={},
        client_ip="",
    ):
        # other task returns delta
        assert update == StateUpdate(
            delta={
                BackgroundTaskState.get_full_name(): {
                    "order" + FIELD_MARKER: [
                        "background_task:start",
                        "other",
                    ],
                    "computed_order" + FIELD_MARKER: [
                        "background_task:start",
                        "other",
                    ],
                }
            },
        )

    # Explicit wait for background tasks
    for task in tuple(mock_app._background_tasks):
        await task
    assert not mock_app._background_tasks

    if environment.REFLEX_OPLOCK_ENABLED.get():
        await mock_app.state_manager.close()

    exp_order = [
        "background_task:start",
        "other",
        "background_task:stop",
        "other",
        "private",
    ]

    background_task_state = await mock_app.state_manager.get_state(
        _substate_key(token, BackgroundTaskState)
    )
    assert isinstance(background_task_state, BackgroundTaskState)
    assert background_task_state.order == exp_order
    assert mock_app.event_namespace is not None
    emit_mock = mock_app.event_namespace.emit

    first_ws_message = emit_mock.mock_calls[0].args[1]  # pyright: ignore [reportAttributeAccessIssue]
    assert (
        first_ws_message.delta[BackgroundTaskState.get_full_name()].pop(
            "router" + FIELD_MARKER
        )
        is not None
    )
    assert first_ws_message == StateUpdate(
        delta={
            BackgroundTaskState.get_full_name(): {
                "order" + FIELD_MARKER: ["background_task:start"],
                "computed_order" + FIELD_MARKER: ["background_task:start"],
            }
        },
        events=[],
        final=None,
    )
    for call in emit_mock.mock_calls[1:5]:  # pyright: ignore [reportAttributeAccessIssue]
        assert call.args[1] == StateUpdate(
            delta={
                BackgroundTaskState.get_full_name(): {
                    "computed_order" + FIELD_MARKER: ["background_task:start"],
                }
            },
            events=[],
            final=None,
        )
    assert emit_mock.mock_calls[-2].args[1] == StateUpdate(  # pyright: ignore [reportAttributeAccessIssue]
        delta={
            BackgroundTaskState.get_full_name(): {
                "order" + FIELD_MARKER: exp_order,
                "computed_order" + FIELD_MARKER: exp_order,
                "dict_list" + FIELD_MARKER: {},
            }
        },
        events=[],
        final=None,
    )
    assert emit_mock.mock_calls[-1].args[1] == StateUpdate(  # pyright: ignore [reportAttributeAccessIssue]
        delta={
            BackgroundTaskState.get_full_name(): {
                "computed_order" + FIELD_MARKER: exp_order,
            },
        },
        events=[],
        final=None,
    )


@pytest.mark.asyncio
async def test_background_task_reset(mock_app: rx.App, token: str):
    """Test that a background task calling reset is protected by the state proxy.

    Args:
        mock_app: An app that will be returned by `get_app()`
        token: A token.
    """
    router_data = {"query": {}}
    mock_app.state_manager.state = mock_app._state = BackgroundTaskState
    async for update in rx.app.process(
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
    for task in tuple(mock_app._background_tasks):
        await task
    assert not mock_app._background_tasks

    if environment.REFLEX_OPLOCK_ENABLED.get():
        await mock_app.state_manager.close()

    background_task_state = await mock_app.state_manager.get_state(
        _substate_key(token, BackgroundTaskState)
    )
    assert isinstance(background_task_state, BackgroundTaskState)
    assert background_task_state.order == ["reset"]


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
    mutable_state.array.sort()  # pyright: ignore[reportCallIssue]
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
        item["foo"] = "bar"  # pyright: ignore[reportArgumentType, reportCallIssue]
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
    mutable_value_third_ref.append("baz")  # pyright: ignore[reportAttributeAccessIssue]
    assert not mutable_state.dirty_vars
    # Unfortunately previous refs still will mark the state dirty... nothing doing about that
    assert mutable_value.pop()  # pyright: ignore[reportCallIssue]
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
    "copy_func",
    [
        copy.copy,
        copy.deepcopy,
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
    "copy_func",
    [
        copy.copy,
        copy.deepcopy,
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


def test_duplicate_substate_class(mocker: MockerFixture):
    # Neuter pytest escape hatch, because we want to test duplicate detection.
    mocker.patch("reflex.state.is_testing_env", return_value=False)
    # Neuter <locals> state handling since these _are_ defined inside a function.
    mocker.patch("reflex.state.BaseState._handle_local_def", return_value=False)
    with pytest.raises(ValueError):

        class TestState(BaseState):
            pass

        class ChildTestState(TestState):  # pyright: ignore [reportRedeclaration]
            pass

        class ChildTestState(TestState):  # noqa: F811
            pass

        return TestState


class Foo(Base):
    """A class containing a list of str."""

    tags: list[str] = ["123", "456"]


def test_json_dumps_with_mutables():
    """Test that json.dumps works with Base vars inside mutable types."""

    class MutableContainsBase(BaseState):
        items: list[Foo] = [Foo()]

    dict_val = MutableContainsBase().dict()
    assert isinstance(
        dict_val[MutableContainsBase.get_full_name()]["items" + FIELD_MARKER][0], Foo
    )
    val = json_dumps(dict_val)
    assert json.loads(val) == {
        MutableContainsBase.get_full_name(): {
            f"items{FIELD_MARKER}": [{"tags": ["123", "456"]}],
            f"router{FIELD_MARKER}": formatted_router,
        }
    }


def test_reset_with_mutables():
    """Calling reset should always reset fields to a copy of the defaults."""
    default = [[0, 0], [0, 1], [1, 1]]
    copied_default = copy.deepcopy(default)

    class MutableResetState(BaseState):
        items: list[list[int]] = default

    instance = MutableResetState()
    assert instance.items.__wrapped__ is not default  # pyright: ignore [reportAttributeAccessIssue]
    assert instance.items == default == copied_default
    instance.items.append([3, 3])
    assert instance.items != default
    assert instance.items != copied_default

    instance.reset()
    assert instance.items.__wrapped__ is not default  # pyright: ignore [reportAttributeAccessIssue]
    assert instance.items == default == copied_default
    instance.items.append([3, 3])
    assert instance.items != default
    assert instance.items != copied_default

    instance.reset()
    assert instance.items.__wrapped__ is not default  # pyright: ignore [reportAttributeAccessIssue]
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
        """Concatenate foo with foo.

        Returns:
            foo + foo
        """
        return self.foo + self.foo


class Custom2(Base):
    """A custom class with a Custom1 field."""

    c1: Custom1 | None = None
    c1r: Custom1

    def set_c1r_foo(self, val: str):
        """Set the foo attribute of the c1 field.

        Args:
            val: The value to set.
        """
        self.c1r.set_foo(val)


class Custom3(Base):
    """A custom class with a Custom2 field."""

    c2: Custom2 | None = None
    c2r: Custom2


def test_state_union_optional():
    """Test that state can be defined with Union and Optional vars."""

    class UnionState(BaseState):
        int_float: int | float = 0
        opt_int: int | None
        c3: Custom3 | None
        c3i: Custom3  # implicitly required
        c3r: Custom3 = Custom3(c2r=Custom2(c1r=Custom1(foo="")))
        custom_union: Custom1 | Custom2 | Custom3 = Custom1(foo="")

    assert str(UnionState.c3.c2) == f'{UnionState.c3!s}?.["c2"]'  # pyright: ignore [reportOptionalMemberAccess]
    assert str(UnionState.c3.c2.c1) == f'{UnionState.c3!s}?.["c2"]?.["c1"]'  # pyright: ignore [reportOptionalMemberAccess]
    assert (
        str(UnionState.c3.c2.c1.foo) == f'{UnionState.c3!s}?.["c2"]?.["c1"]?.["foo"]'  # pyright: ignore [reportOptionalMemberAccess]
    )
    assert (
        str(UnionState.c3.c2.c1r.foo) == f'{UnionState.c3!s}?.["c2"]?.["c1r"]?.["foo"]'  # pyright: ignore [reportOptionalMemberAccess]
    )
    assert str(UnionState.c3.c2r.c1) == f'{UnionState.c3!s}?.["c2r"]?.["c1"]'  # pyright: ignore [reportOptionalMemberAccess]
    assert (
        str(UnionState.c3.c2r.c1.foo) == f'{UnionState.c3!s}?.["c2r"]?.["c1"]?.["foo"]'  # pyright: ignore [reportOptionalMemberAccess]
    )
    assert (
        str(UnionState.c3.c2r.c1r.foo)  # pyright: ignore [reportOptionalMemberAccess]
        == f'{UnionState.c3!s}?.["c2r"]?.["c1r"]?.["foo"]'
    )
    assert str(UnionState.c3i.c2) == f'{UnionState.c3i!s}?.["c2"]'
    assert str(UnionState.c3r.c2) == f'{UnionState.c3r!s}?.["c2"]'
    assert UnionState.custom_union.foo is not None  # pyright: ignore [reportAttributeAccessIssue]
    assert UnionState.custom_union.c1 is not None  # pyright: ignore [reportAttributeAccessIssue]
    assert UnionState.custom_union.c1r is not None  # pyright: ignore [reportAttributeAccessIssue]
    assert UnionState.custom_union.c2 is not None  # pyright: ignore [reportAttributeAccessIssue]
    assert UnionState.custom_union.c2r is not None  # pyright: ignore [reportAttributeAccessIssue]
    assert types.is_optional(UnionState.opt_int._var_type)  # pyright: ignore [reportAttributeAccessIssue, reportOptionalMemberAccess]
    assert types.is_union(UnionState.int_float._var_type)  # pyright: ignore [reportAttributeAccessIssue]


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
    bfss.c1.foo = "bar"
    assert "c1" in bfss.dirty_vars
    bfss.dirty_vars.clear()
    assert "c1" not in bfss.dirty_vars

    # Assert identity of MutableProxy
    mp = bfss.c1
    assert isinstance(mp, MutableProxy)
    mp3 = bfss.c1
    assert mp is not mp3
    # Since none of these set calls had values, the state should not be dirty
    assert not bfss.dirty_vars

    # Chained Mutating function, dirty
    bfss.c2.set_c1r_foo("baz")
    assert "c2" in bfss.dirty_vars


def exp_is_hydrated(state: BaseState, is_hydrated: bool = True) -> dict[str, Any]:
    """Expected IS_HYDRATED delta that would be emitted by HydrateMiddleware.

    Args:
        state: the State that is hydrated.
        is_hydrated: whether the state is hydrated.

    Returns:
        dict similar to that returned by `State.get_delta` with IS_HYDRATED: is_hydrated
    """
    return {
        state.get_full_name(): {CompileVars.IS_HYDRATED + FIELD_MARKER: is_hydrated}
    }


class OnLoadState(State):
    """A test state with no return in handler."""

    num: int = 0

    @rx.event
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
    ("test_state", "expected"),
    [
        (OnLoadState, {"on_load_state": {"num": 1}}),
        (OnLoadState2, {"on_load_state2": {"num": 1}}),
        (OnLoadState3, {"on_load_state3": {"num": 1}}),
    ],
)
async def test_preprocess(
    app_module_mock, token, test_state, expected, mocker: MockerFixture
):
    """Test that a state hydrate event is processed correctly.

    Args:
        app_module_mock: The app module that will be returned by get_app().
        token: A token.
        test_state: State to process event.
        expected: Expected delta.
        mocker: pytest mock object.
    """
    OnLoadInternalState._app_ref = None
    mocker.patch(
        "reflex.state.State.class_subclasses", {test_state, OnLoadInternalState}
    )
    app = app_module_mock.app = App(_state=State)

    def index():
        return "hello"

    app.add_page(index, on_load=test_state.test_handler)
    app._compile_page("index")

    async with app.state_manager.modify_state(_substate_key(token, State)) as state:
        state.router_data = {"simulate": "hydrate"}

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
    assert updates[0].delta[State.get_name()].pop("router" + FIELD_MARKER) is not None
    assert updates[0].delta == exp_is_hydrated(state, False)

    events = updates[0].events
    assert len(events) == 2
    async for update in state._process(events[0]):
        assert update.delta == {test_state.get_full_name(): {"num" + FIELD_MARKER: 1}}
    async for update in state._process(events[1]):
        assert update.delta == exp_is_hydrated(state)

    await app.state_manager.close()


@pytest.mark.asyncio
async def test_preprocess_multiple_load_events(
    app_module_mock, token, mocker: MockerFixture
):
    """Test that a state hydrate event for multiple on-load events is processed correctly.

    Args:
        app_module_mock: The app module that will be returned by get_app().
        token: A token.
        mocker: pytest mock object.
    """
    OnLoadInternalState._app_ref = None
    mocker.patch(
        "reflex.state.State.class_subclasses", {OnLoadState, OnLoadInternalState}
    )
    app = app_module_mock.app = App(_state=State)

    def index():
        return "hello"

    app.add_page(index, on_load=[OnLoadState.test_handler, OnLoadState.test_handler])
    app._compile_page("index")
    async with app.state_manager.modify_state(_substate_key(token, State)) as state:
        state.router_data = {"simulate": "hydrate"}

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
    assert updates[0].delta[State.get_name()].pop("router" + FIELD_MARKER) is not None
    assert updates[0].delta == exp_is_hydrated(state, False)

    events = updates[0].events
    assert len(events) == 3
    async for update in state._process(events[0]):
        assert update.delta == {OnLoadState.get_full_name(): {"num" + FIELD_MARKER: 1}}
    async for update in state._process(events[1]):
        assert update.delta == {OnLoadState.get_full_name(): {"num" + FIELD_MARKER: 2}}
    async for update in state._process(events[2]):
        assert update.delta == exp_is_hydrated(state)

    await app.state_manager.close()


@pytest.mark.asyncio
async def test_get_state(mock_app: rx.App, token: str):
    """Test that a get_state populates the top level state and delta calculation is correct.

    Args:
        mock_app: An app that will be returned by `get_app()`
        token: A token.
    """
    mock_app.state_manager.state = mock_app._state = TestState

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
    grandchild_state3 = test_state.substates[ChildState3.get_name()].substates[
        GrandchildState3.get_name()
    ]
    assert isinstance(grandchild_state3, GrandchildState3)
    assert grandchild_state3.computed == ""

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
    assert grandchild_state is child_state_direct.get_substate([
        GrandchildState.get_name()
    ])
    grandchild_state.value2 = "set_value"

    assert test_state.get_delta() == {
        GrandchildState.get_full_name(): {
            "value2" + FIELD_MARKER: "set_value",
        },
        GrandchildState3.get_full_name(): {
            "computed" + FIELD_MARKER: "",
        },
    }

    # Get a fresh instance
    new_test_state = await mock_app.state_manager.get_state(
        _substate_key(token, ChildState2)
    )
    assert isinstance(new_test_state, TestState)
    if isinstance(mock_app.state_manager, (StateManagerMemory, StateManagerDisk)):
        # In memory, it's the same instance
        assert new_test_state is test_state
        test_state._clean()
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
        ChildState2.get_full_name(): {
            "value" + FIELD_MARKER: "set_c2_value",
        },
        GrandchildState2.get_full_name(): {
            "cached" + FIELD_MARKER: "set_c2_value",
        },
        GrandchildState3.get_full_name(): {
            "computed" + FIELD_MARKER: "",
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

    class Child2(Parent):
        """An unconnected child state."""

    class Child3(Parent):
        """A child state with a computed var causing it to be pre-fetched.

        If child3_var gets set to a value, and `get_state` erroneously
        re-fetches it from redis, the value will be lost.
        """

        child3_var: int = 0

        @rx.var(cache=False)
        def v(self) -> None:
            pass

    class Grandchild3(Child3):
        """An extra layer of substate to catch an issue discovered in
        _determine_missing_parent_states while writing the regression test where
        invalid parent state names were being constructed.
        """

    class GreatGrandchild3(Grandchild3):
        """Fetching this state wants to also fetch Child3 as a missing parent.
        However, Child3 should already be cached in the state tree because it
        has a computed var.
        """

    mock_app.state_manager.state = mock_app._state = Parent

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


def test_potentially_dirty_states():
    """Test that potentially_dirty_substates returns the correct substates.

    Even if the name "State" is shadowed, it should still work correctly.
    """

    class State(RxState):
        @computed_var
        def foo(self) -> str:
            return ""

    class C1(State):
        @computed_var
        def bar(self) -> str:
            return ""

    assert RxState._get_potentially_dirty_states() == set()
    assert State._get_potentially_dirty_states() == set()
    assert C1._get_potentially_dirty_states() == set()


@pytest.mark.asyncio
async def test_router_var_dep(state_manager: StateManager, token: str) -> None:
    """Test that router var dependencies are correctly tracked.

    Args:
        state_manager: A state manager.
        token: A token.
    """

    class RouterVarParentState(State):
        """A parent state for testing router var dependency."""

    class RouterVarDepState(RouterVarParentState):
        """A state with a router var dependency."""

        @rx.var
        def foo(self) -> str:
            return self.router._page.params.get("foo", "")

    foo = RouterVarDepState.computed_vars["foo"]
    State._init_var_dependency_dicts()

    assert foo._deps(objclass=RouterVarDepState) == {
        RouterVarDepState.get_full_name(): {"router"}
    }
    assert (RouterVarDepState.get_full_name(), "foo") in State._var_dependencies[
        "router"
    ]

    # Get state from state manager.
    state_manager.state = State
    rx_state = await state_manager.get_state(_substate_key(token, State))
    assert RouterVarParentState.get_name() in rx_state.substates
    parent_state = rx_state.substates[RouterVarParentState.get_name()]
    assert RouterVarDepState.get_name() in parent_state.substates
    state = parent_state.substates[RouterVarDepState.get_name()]

    assert state.dirty_vars == set()

    # Reassign router var
    state.router = state.router
    assert rx_state.dirty_vars == {"router"}
    assert state.dirty_vars == {"foo"}
    assert parent_state.dirty_substates == {RouterVarDepState.get_name()}


@pytest.mark.asyncio
async def test_setvar(mock_app: rx.App, token: str):
    """Test that setvar works correctly.

    Args:
        mock_app: An app that will be returned by `get_app()`
        token: A token.
    """
    state = await mock_app.state_manager.get_state(_substate_key(token, TestState))
    assert isinstance(state, TestState)

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

    # Cannot setvar for non-existent var
    with pytest.raises(AttributeError):
        TestState.setvar("non_existent_var")

    # Cannot setvar for computed vars
    with pytest.raises(AttributeError):
        TestState.setvar("sum")

    # Cannot setvar with non-string
    with pytest.raises(ValueError):
        TestState.setvar(42, 42)


def test_setvar_async_setter():
    """Test that overridden async setters raise Exception when used with setvar."""
    with pytest.raises(NotImplementedError):
        TestState.setvar("asynctest", 42)


@pytest.mark.parametrize(
    ("expiration_kwargs", "expected_values"),
    [
        (
            {"redis_lock_expiration": 20000},
            (
                20000,
                constants.Expiration.TOKEN,
                constants.Expiration.LOCK_WARNING_THRESHOLD,
            ),
        ),
        (
            {"redis_lock_expiration": 50000, "redis_token_expiration": 5600},
            (50000, 5600, constants.Expiration.LOCK_WARNING_THRESHOLD),
        ),
        (
            {"redis_token_expiration": 7600},
            (
                constants.Expiration.LOCK,
                7600,
                constants.Expiration.LOCK_WARNING_THRESHOLD,
            ),
        ),
        (
            {"redis_lock_expiration": 50000, "redis_lock_warning_threshold": 1500},
            (50000, constants.Expiration.TOKEN, 1500),
        ),
        (
            {"redis_token_expiration": 5600, "redis_lock_warning_threshold": 3000},
            (constants.Expiration.LOCK, 5600, 3000),
        ),
        (
            {
                "redis_lock_expiration": 50000,
                "redis_token_expiration": 5600,
                "redis_lock_warning_threshold": 2000,
            },
            (50000, 5600, 2000),
        ),
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
    state_manager_mode="redis",
    {config_items}
)
"""
    (proj_root / "rxconfig.py").write_text(dedent(config_string))

    with chdir(proj_root):
        # reload config for each parameter to avoid stale values
        reflex.config.get_config(reload=True)
        from reflex.state import State

        state_manager = StateManagerRedis(state=State, redis=mock_redis())
        assert state_manager.lock_expiration == expected_values[0]  # pyright: ignore [reportAttributeAccessIssue]
        assert state_manager.token_expiration == expected_values[1]  # pyright: ignore [reportAttributeAccessIssue]
        assert state_manager.lock_warning_threshold == expected_values[2]  # pyright: ignore [reportAttributeAccessIssue]


@pytest.mark.parametrize(
    ("redis_lock_expiration", "redis_lock_warning_threshold"),
    [
        (10000, 10000),
        (20000, 30000),
    ],
)
def test_redis_state_manager_config_knobs_invalid_lock_warning_threshold(
    tmp_path, redis_lock_expiration, redis_lock_warning_threshold
):
    proj_root = tmp_path / "project1"
    proj_root.mkdir()

    config_string = f"""
import reflex as rx
config = rx.Config(
    app_name="project1",
    redis_url="redis://localhost:6379",
    state_manager_mode="redis",
    redis_lock_expiration = {redis_lock_expiration},
    redis_lock_warning_threshold = {redis_lock_warning_threshold},
)
    """

    (proj_root / "rxconfig.py").write_text(dedent(config_string))

    with chdir(proj_root):
        # reload config for each parameter to avoid stale values
        reflex.config.get_config(reload=True)
        from reflex.state import State

        with pytest.raises(InvalidLockWarningThresholdError):
            StateManagerRedis(state=State, redis=mock_redis())
        del sys.modules[constants.Config.MODULE]


def test_auto_setters_off(tmp_path):
    proj_root = tmp_path / "project1"
    proj_root.mkdir()

    config_string = """
import reflex as rx
config = rx.Config(
    app_name="project1",
    state_auto_setters=False,
)
    """

    (proj_root / "rxconfig.py").write_text(dedent(config_string))

    with chdir(proj_root):
        # reload config for each parameter to avoid stale values
        reflex.config.get_config(reload=True)
        from reflex.state import State

        class TestState(State):
            """A test state."""

            num: int = 0

        assert list(TestState.event_handlers) == ["setvar"]


class MixinState(State, mixin=True):
    """A mixin state for testing."""

    num: int = 0
    _backend: int = 0
    _backend_no_default: dict

    @rx.var
    def computed(self) -> str:
        """A computed var on mixin state.

        Returns:
            A computed value.
        """
        return ""


class UsesMixinState(MixinState, State):
    """A state that uses the mixin state."""


class ChildUsesMixinState(UsesMixinState):
    """A child state that uses the mixin state."""


class ChildMixinState(ChildUsesMixinState, mixin=True):
    """A mixin state that inherits from a concrete state that uses mixins."""


class GrandchildUsesMixinState(ChildMixinState):
    """A grandchild state that uses the mixin state."""


class BareMixin:
    """A bare mixin which does not inherit from rx.State."""

    _bare_mixin: int = 0


class BareStateMixin(BareMixin, rx.State, mixin=True):
    """A state mixin that uses a bare mixin."""


class BareMixinState(BareStateMixin, State):
    """A state that uses a bare mixin."""


class ChildBareMixinState(BareMixinState):
    """A child state that uses a bare mixin."""


def test_mixin_state() -> None:
    """Test that a mixin state works correctly."""
    assert "num" in UsesMixinState.base_vars
    assert "num" in UsesMixinState.vars
    assert UsesMixinState.backend_vars == {
        "_backend": 0,
        "_backend_no_default": {},
        "_reflex_internal_links": None,
    }

    assert "computed" in UsesMixinState.computed_vars
    assert "computed" in UsesMixinState.vars

    assert (
        UsesMixinState(_reflex_internal_init=True)._backend_no_default  # pyright: ignore [reportCallIssue]
        is not UsesMixinState.backend_vars["_backend_no_default"]
    )

    assert UsesMixinState.get_parent_state() == State
    assert UsesMixinState.get_root_state() == State


def test_child_mixin_state() -> None:
    """Test that mixin vars are only applied to the highest state in the hierarchy."""
    assert "num" in ChildUsesMixinState.inherited_vars
    assert "num" not in ChildUsesMixinState.base_vars

    assert "computed" in ChildUsesMixinState.inherited_vars
    assert "computed" not in ChildUsesMixinState.computed_vars

    assert ChildUsesMixinState.get_parent_state() == UsesMixinState
    assert ChildUsesMixinState.get_root_state() == State


def test_grandchild_mixin_state() -> None:
    """Test that a mixin can inherit from a concrete state class."""
    assert "num" in GrandchildUsesMixinState.inherited_vars
    assert "num" not in GrandchildUsesMixinState.base_vars

    assert "computed" in GrandchildUsesMixinState.inherited_vars
    assert "computed" not in GrandchildUsesMixinState.computed_vars

    assert ChildMixinState.get_parent_state() == ChildUsesMixinState
    assert ChildMixinState.get_root_state() == State

    assert GrandchildUsesMixinState.get_parent_state() == ChildUsesMixinState
    assert GrandchildUsesMixinState.get_root_state() == State


def test_bare_mixin_state() -> None:
    """Test that a mixin can inherit from a concrete state class."""
    assert "_bare_mixin" not in BareMixinState.inherited_vars
    assert "_bare_mixin" not in BareMixinState.base_vars

    assert BareMixinState.get_parent_state() == State
    assert BareMixinState.get_root_state() == State

    assert "_bare_mixin" not in ChildBareMixinState.inherited_vars
    assert "_bare_mixin" not in ChildBareMixinState.base_vars

    assert ChildBareMixinState.get_parent_state() == BareMixinState
    assert ChildBareMixinState.get_root_state() == State


def test_mixin_event_handler_preserves_event_actions() -> None:
    """Test that event_actions from @rx.event decorator are preserved when inherited from mixins."""

    class EventActionsMixin(BaseState, mixin=True):
        @rx.event(prevent_default=True, stop_propagation=True)
        def handle_with_actions(self):
            pass

    class UsesEventActionsMixin(EventActionsMixin, State):
        pass

    handler = UsesEventActionsMixin.handle_with_actions
    assert handler.event_actions == {"preventDefault": True, "stopPropagation": True}


def test_assignment_to_undeclared_vars():
    """Test that an attribute error is thrown when undeclared vars are set."""

    class State(BaseState):
        val: str
        _val: str
        __val: str  # pyright: ignore [reportGeneralTypeIssues]

        def handle_supported_regular_vars(self):
            self.val = "no underscore"
            self._val = "single leading underscore"
            self.__val = "double leading underscore"

        def handle_regular_var(self):
            self.num = 5

        def handle_backend_var(self):
            self._num = 5

        def handle_non_var(self):
            self.__num = 5

    class Substate(State):
        def handle_var(self):
            self.value = 20

    state = State()  # pyright: ignore [reportCallIssue]
    sub_state = Substate()  # pyright: ignore [reportCallIssue]

    with pytest.raises(SetUndefinedStateVarError):
        state.handle_regular_var()

    with pytest.raises(SetUndefinedStateVarError):
        sub_state.handle_var()

    with pytest.raises(SetUndefinedStateVarError):
        state.handle_backend_var()

    state.handle_supported_regular_vars()
    state.handle_non_var()


@pytest.mark.asyncio
async def test_deserialize_gc_state_disk(token):
    """Test that a state can be deserialized from disk with a grandchild state.

    Args:
        token: A token.
    """

    class Root(BaseState):
        pass

    class State(Root):
        num: int = 42

    class Child(State):
        foo: str = "bar"

    dsm = StateManagerDisk(state=Root)
    async with dsm.modify_state(token) as root:
        s = await root.get_state(State)
        s.num += 1
        c = await root.get_state(Child)
        assert s._get_was_touched()
        assert not c._get_was_touched()
    await dsm.close()

    dsm2 = StateManagerDisk(state=Root)
    root = await dsm2.get_state(token)
    s = await root.get_state(State)
    assert s.num == 43
    c = await root.get_state(Child)
    assert c.foo == "bar"
    await dsm2.close()


class Obj(Base):
    """A object containing a callable for testing fallback pickle."""

    _f: Callable


def test_fallback_pickle():
    """Test that state serialization will fall back to dill."""

    class DillState(BaseState):
        _o: Obj | None = None
        _f: Callable | None = None
        _g: Any = None

    state = DillState(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    state._o = Obj(_f=lambda: 42)
    state._f = lambda: 420

    pk = state._serialize()

    unpickled_state = BaseState._deserialize(pk)
    assert isinstance(unpickled_state, DillState)
    assert unpickled_state._f is not None
    assert unpickled_state._f() == 420
    assert unpickled_state._o is not None
    assert unpickled_state._o._f() == 42

    # Threading locks are unpicklable normally, and raise TypeError instead of PicklingError.
    state2 = DillState(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    state2._g = threading.Lock()
    pk2 = state2._serialize()
    unpickled_state2 = BaseState._deserialize(pk2)
    assert isinstance(unpickled_state2, DillState)
    assert isinstance(unpickled_state2._g, type(threading.Lock()))

    # Some object, like generator, are still unpicklable with dill.
    state3 = DillState(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    state3._g = (i for i in range(10))

    with pytest.raises(StateSerializationError):
        _ = state3._serialize()


def test_typed_state() -> None:
    class TypedState(rx.State):
        field: rx.Field[str] = rx.field("")

    _ = TypedState(field="str")


class ModelV1(BaseModelV1):
    """A pydantic BaseModel v1."""

    foo: str = "bar"

    def set_foo(self, val: str):
        """Set the attribute foo.

        Args:
            val: The value to set.
        """
        self.foo = val

    def double_foo(self) -> str:
        """Concatenate foo with foo.

        Returns:
            foo + foo
        """
        return self.foo + self.foo


class ModelV2(BaseModelV2):
    """A pydantic BaseModel v2."""

    foo: str = "bar"

    def set_foo(self, val: str):
        """Set the attribute foo.

        Args:
            val: The value to set.
        """
        self.foo = val

    def double_foo(self) -> str:
        """Concatenate foo with foo.

        Returns:
            foo + foo
        """
        return self.foo + self.foo


class PydanticState(rx.State):
    """A state with pydantic BaseModel vars."""

    v1: ModelV1 = ModelV1()
    v2: ModelV2 = ModelV2()
    dc: ModelDC = ModelDC()


def test_mutable_models():
    """Test that dataclass and pydantic BaseModel v1 and v2 use dep tracking."""
    state = PydanticState()
    assert isinstance(state.v1, MutableProxy)
    state.v1.foo = "baz"
    assert state.dirty_vars == {"v1"}
    state.dirty_vars.clear()
    state.v1.set_foo("quuc")
    assert state.dirty_vars == {"v1"}
    state.dirty_vars.clear()
    assert state.v1.double_foo() == "quucquuc"
    assert state.dirty_vars == set()
    state.v1.copy(update={"foo": "larp"})
    assert state.dirty_vars == set()

    assert isinstance(state.v2, MutableProxy)
    state.v2.foo = "baz"
    assert state.dirty_vars == {"v2"}
    state.dirty_vars.clear()
    state.v2.set_foo("quuc")
    assert state.dirty_vars == {"v2"}
    state.dirty_vars.clear()
    assert state.v2.double_foo() == "quucquuc"
    assert state.dirty_vars == set()
    state.v2.model_copy(update={"foo": "larp"})
    assert state.dirty_vars == set()

    assert isinstance(state.dc, MutableProxy)
    state.dc.foo = "baz"
    assert state.dirty_vars == {"dc"}
    state.dirty_vars.clear()
    assert state.dirty_vars == set()
    state.dc.set_foo("quuc")
    assert state.dirty_vars == {"dc"}
    state.dirty_vars.clear()
    assert state.dirty_vars == set()
    assert state.dc.double_foo() == "quucquuc"
    assert state.dirty_vars == set()
    state.dc.ls.append({"hi": "reflex"})
    assert state.dirty_vars == {"dc"}
    state.dirty_vars.clear()
    assert state.dirty_vars == set()
    assert dataclasses.asdict(state.dc) == {"foo": "quuc", "ls": [{"hi": "reflex"}]}
    assert dataclasses.astuple(state.dc) == ("quuc", [{"hi": "reflex"}])
    # creating a new instance shouldn't mark the state dirty
    assert dataclasses.replace(state.dc, foo="larp") == ModelDC(
        foo="larp", ls=[{"hi": "reflex"}]
    )
    assert state.dirty_vars == set()
    dc_copy = state.dc.copy()
    assert dc_copy == state.dc
    assert dc_copy is not state.dc
    dc_copy.foo = "new_foo"
    assert state.dirty_vars == set()
    dc_copy.append_to_ls({"new": "item"})
    assert state.dirty_vars == set()
    state.dc.append_to_ls({"new": "item"})
    assert state.dirty_vars == {"dc"}
    state.dirty_vars.clear()

    dc_from_dict = state.dc.from_dict({"foo": "from_dict", "ls": []})
    assert dc_from_dict == ModelDC(foo="from_dict", ls=[])
    assert state.dirty_vars == set()


def test_dict_and_get_delta():
    class GetValueState(rx.State):
        foo: str = "FOO"
        bar: str = "BAR"

    state = GetValueState()

    assert state.dict() == {
        state.get_full_name(): {
            "foo" + FIELD_MARKER: "FOO",
            "bar" + FIELD_MARKER: "BAR",
        }
    }
    assert state.get_delta() == {}

    state.bar = "foo"

    assert state.dict() == {
        state.get_full_name(): {
            "foo" + FIELD_MARKER: "FOO",
            "bar" + FIELD_MARKER: "foo",
        }
    }
    assert state.get_delta() == {
        state.get_full_name(): {
            "bar" + FIELD_MARKER: "foo",
        }
    }


@pytest.mark.parametrize(
    ("key_factory", "expected_result", "should_raise"),
    [
        # Valid string keys
        (lambda state: "foo", "FOO", False),
        (lambda state: "bar", "BAR", False),
        # MutableProxy keys (deprecated but supported)
        (
            lambda state: MutableProxy(
                wrapped="test_wrapped_value", state=state, field_name="test_field"
            ),
            "test_wrapped_value",
            False,
        ),
        (
            lambda state: MutableProxy(
                wrapped=42, state=state, field_name="test_field"
            ),
            42,
            False,
        ),
        # Invalid key types
        (lambda state: 123, None, True),
        (lambda state: [], None, True),
        (lambda state: {}, None, True),
        (lambda state: None, None, True),
    ],
)
def test_get_value(key_factory, expected_result, should_raise):
    """Test the get_value method directly with various key types.

    Args:
        key_factory: Factory function to create the key for testing.
        expected_result: The expected return value from get_value.
        should_raise: Whether the test should expect a TypeError.
    """

    class GetValueState(rx.State):
        """Test state class for get_value testing."""

        foo: str = "FOO"
        bar: str = "BAR"

    state = GetValueState()
    key = key_factory(state)

    if should_raise:
        with pytest.raises(TypeError, match="Invalid key type"):
            state.get_value(key)
    else:
        result = state.get_value(key)
        assert result == expected_result

        # Verify dirty state is not affected
        initial_dirty_vars = copy.copy(state.dirty_vars)
        state.get_value(key)
        assert state.dirty_vars == initial_dirty_vars


def test_init_mixin() -> None:
    """Ensure that State mixins can not be instantiated directly."""

    class Mixin(BaseState, mixin=True):
        pass

    with pytest.raises(ReflexRuntimeError):
        Mixin()

    class SubMixin(Mixin, mixin=True):
        pass

    with pytest.raises(ReflexRuntimeError):
        SubMixin()


class UpcastState(rx.State):
    """A state for testing upcasting."""

    passed: bool = False

    def rx_base(self, o: Object):  # noqa: D102
        assert isinstance(o, Object)
        self.passed = True

    def rx_base_or_none(self, o: Object | None):  # noqa: D102
        if o is not None:
            assert isinstance(o, Object)
        self.passed = True

    def rx_basemodelv1(self, m: ModelV1):  # noqa: D102
        assert isinstance(m, ModelV1)
        self.passed = True

    def rx_basemodelv2(self, m: ModelV2):  # noqa: D102
        assert isinstance(m, ModelV2)
        self.passed = True

    def rx_dataclass(self, dc: ModelDC):  # noqa: D102
        assert isinstance(dc, ModelDC)
        self.passed = True

    def py_set(self, s: set):  # noqa: D102
        assert isinstance(s, set)
        self.passed = True

    def py_Set(self, s: set):  # noqa: D102
        assert isinstance(s, set)
        self.passed = True

    def py_tuple(self, t: tuple):  # noqa: D102
        assert isinstance(t, tuple)
        self.passed = True

    def py_Tuple(self, t: tuple):  # noqa: D102
        assert isinstance(t, tuple)
        self.passed = True

    def py_dict(self, d: dict[str, str]):  # noqa: D102
        assert isinstance(d, dict)
        self.passed = True

    def py_list(self, ls: list[str]):  # noqa: D102
        assert isinstance(ls, list)
        self.passed = True

    def py_Any(self, a: Any):  # noqa: D102
        assert isinstance(a, list)
        self.passed = True

    def py_unresolvable(self, u: Unresolvable):  # noqa: D102, F821 # pyright: ignore [reportUndefinedVariable]
        assert isinstance(u, list)
        self.passed = True


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_app_simple")
@pytest.mark.parametrize(
    ("handler", "payload"),
    [
        (UpcastState.rx_base, {"o": {"foo": "bar"}}),
        (UpcastState.rx_base_or_none, {"o": {"foo": "bar"}}),
        (UpcastState.rx_base_or_none, {"o": None}),
        (UpcastState.rx_basemodelv1, {"m": {"foo": "bar"}}),
        (UpcastState.rx_basemodelv2, {"m": {"foo": "bar"}}),
        (UpcastState.rx_dataclass, {"dc": {"foo": "bar"}}),
        (UpcastState.py_set, {"s": ["foo", "foo"]}),
        (UpcastState.py_Set, {"s": ["foo", "foo"]}),
        (UpcastState.py_tuple, {"t": ["foo", "foo"]}),
        (UpcastState.py_Tuple, {"t": ["foo", "foo"]}),
        (UpcastState.py_dict, {"d": {"foo": "bar"}}),
        (UpcastState.py_list, {"ls": ["foo", "foo"]}),
        (UpcastState.py_Any, {"a": ["foo"]}),
        (UpcastState.py_unresolvable, {"u": ["foo"]}),
    ],
)
async def test_upcast_event_handler_arg(handler, payload):
    """Test that upcast event handler args work correctly.

    Args:
        handler: The handler to test.
        payload: The payload to test.
    """
    state = UpcastState()
    async for update in state._process_event(handler, state, payload):
        assert update.delta == {
            UpcastState.get_full_name(): {"passed" + FIELD_MARKER: True}
        }


@pytest.mark.asyncio
async def test_get_var_value(state_manager: StateManager, substate_token: str):
    """Test that get_var_value works correctly.

    Args:
        state_manager: The state manager to use.
        substate_token: Token for the substate used by state_manager.
    """
    state = await state_manager.get_state(substate_token)

    # State Var from same state
    assert await state.get_var_value(TestState.num1) == 0
    state.num1 = 42
    assert await state.get_var_value(TestState.num1) == 42

    # State Var from another state
    child_state = await state.get_state(ChildState)
    assert await state.get_var_value(ChildState.count) == 23
    child_state.count = 66
    assert await state.get_var_value(ChildState.count) == 66

    # LiteralVar with known value
    assert await state.get_var_value(rx.Var.create([1, 2, 3])) == [1, 2, 3]

    # Generic Var with no state
    with pytest.raises(UnretrievableVarValueError):
        await state.get_var_value(rx.Var("undefined"))

    # ObjectVar
    assert await state.get_var_value(TestState.mapping) == {
        "a": [1, 2, 3],
        "b": [4, 5, 6],
    }


@pytest.mark.asyncio
async def test_async_computed_var_get_state(mock_app: rx.App, token: str):
    """A test where an async computed var depends on a var in another state.

    Args:
        mock_app: An app that will be returned by `get_app()`
        token: A token.
    """

    class Parent(BaseState):
        """A root state like rx.State."""

        parent_var: int = 0

    class Child2(Parent):
        """An unconnected child state."""

    class Child3(Parent):
        """A child state with a computed var causing it to be pre-fetched.

        If child3_var gets set to a value, and `get_state` erroneously
        re-fetches it from redis, the value will be lost.
        """

        child3_var: int = 0

        @rx.var(cache=True)
        def v(self) -> int:
            return self.child3_var

    class Child(Parent):
        """A state simulating UpdateVarsInternalState."""

        @rx.var(cache=True)
        async def v(self) -> int:
            p = await self.get_state(Parent)
            child3 = await self.get_state(Child3)
            return child3.child3_var + p.parent_var

    mock_app.state_manager.state = mock_app._state = Parent

    # Get the top level state via unconnected sibling.
    root = await mock_app.state_manager.get_state(_substate_key(token, Child))
    # Set value in parent_var to assert it does not get refetched later.
    root.parent_var = 1

    if isinstance(mock_app.state_manager, StateManagerRedis):
        # When redis is used, only states with uncached computed vars are pre-fetched.
        assert Child2.get_name() not in root.substates
        assert Child3.get_name() not in root.substates

    # Get the unconnected sibling state, which will be used to `get_state` other instances.
    child = root.get_substate(Child.get_full_name().split("."))
    assert isinstance(child, Child)

    # Get an uncached child state.
    child2 = await child.get_state(Child2)
    assert child2.parent_var == 1

    # Set value on already-cached Child3 state (prefetched because it has a Computed Var).
    child3 = await child.get_state(Child3)
    child3.child3_var = 1

    assert await child.v == 2
    assert await child.v == 2
    root.parent_var = 2
    assert await child.v == 3


class Table(rx.ComponentState):
    """A table state."""

    _data: ClassVar[Var]

    @rx.var(cache=True, auto_deps=False)
    async def data(self) -> list[dict[str, Any]]:
        """Computed var over the given rows.

        Returns:
            The data rows.
        """
        return await self.get_var_value(self._data)

    @rx.var
    async def foo(self) -> list[dict[str, Any]]:
        """Another computed var that depends on data in this state.

        Returns:
            The data rows.
        """
        return await self.data

    @classmethod
    def get_component(cls, data: Var) -> rx.Component:
        """Get the component for the table.

        Args:
            data: The data var.

        Returns:
            The component.
        """
        cls._data = data
        cls.computed_vars["data"].add_dependency(cls, data)
        return rx.foreach(data, lambda d: rx.text(d.to_string()))


@pytest.mark.asyncio
async def test_async_computed_var_get_var_value(mock_app: rx.App, token: str):
    """A test where an async computed var depends on a var in another state.

    Args:
        mock_app: An app that will be returned by `get_app()`
        token: A token.
    """

    class OtherState(rx.State):
        """A state with a var."""

        data: list[dict[str, Any]] = [{"foo": "bar"}]

    mock_app.state_manager.state = mock_app._state = rx.State
    comp = Table.create(data=OtherState.data)
    state = await mock_app.state_manager.get_state(_substate_key(token, OtherState))
    other_state = await state.get_state(OtherState)
    assert comp.State is not None
    # The state should have been pre-cached from the dependency.
    assert comp.State.get_name() in state.substates
    comp_state = await state.get_state(comp.State)
    assert comp_state.dirty_vars == set()

    other_state.data.append({"foo": "baz"})
    assert "data" in comp_state.dirty_vars
    assert "foo" in comp_state.dirty_vars


def test_computed_var_mutability() -> None:
    class CvMixin(rx.State, mixin=True):
        @rx.var(cache=True, deps=["hi"])
        def cv(self) -> int:
            return 42

    class FirstCvState(CvMixin, rx.State):
        pass

    class SecondCvState(CvMixin, rx.State):
        pass

    first_cv = FirstCvState.computed_vars["cv"]
    second_cv = SecondCvState.computed_vars["cv"]

    assert first_cv is not second_cv
    assert first_cv._static_deps is not second_cv._static_deps


@pytest.mark.asyncio
async def test_add_dependency_get_state_regression(mock_app: rx.App, token: str):
    """Ensure that a state class can be fetched separately when it's is explicit dep."""

    class DataState(rx.State):
        """A state with a var."""

        data: Field[list[int]] = field(default_factory=lambda: [1, 2, 3])

    class StatsState(rx.State):
        """A state with a computed var depending on DataState."""

        @rx.var(cache=True)
        async def total(self) -> int:
            data_state = await self.get_state(DataState)
            return sum(data_state.data)

    StatsState.computed_vars["total"].add_dependency(StatsState, DataState.data)

    class OtherState(rx.State):
        """A state that gets DataState."""

        @rx.event
        async def fetch_data_state(self) -> None:
            print(await self.get_state(DataState))

    mock_app.state_manager.state = mock_app._state = rx.State
    state = await mock_app.state_manager.get_state(_substate_key(token, OtherState))
    other_state = await state.get_state(OtherState)
    await other_state.fetch_data_state()  # Should not raise exception.


class MutableProxyState(BaseState):
    """A test state with a MutableProxy var."""

    data: dict[str, list[int]] = {"a": [1], "b": [2]}


@pytest.mark.asyncio
async def test_rebind_mutable_proxy(mock_app: rx.App, token: str) -> None:
    """Test that previously bound MutableProxy instances can be rebound correctly."""
    mock_app.state_manager.state = mock_app._state = MutableProxyState
    async with mock_app.state_manager.modify_state(
        _substate_key(token, MutableProxyState)
    ) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        assert isinstance(state, MutableProxyState)
        assert isinstance(state.data, MutableProxy)
        assert not isinstance(state.data, ImmutableMutableProxy)
        state_proxy = StateProxy(state)
        assert isinstance(state_proxy.data, ImmutableMutableProxy)
    async with state_proxy:
        # This assigns an ImmutableMutableProxy to data["a"].
        state_proxy.data["a"] = state_proxy.data["b"]
    assert isinstance(state_proxy.data["a"], ImmutableMutableProxy)
    assert state_proxy.data["a"] is not state_proxy.data["b"]
    assert state_proxy.data["a"].__wrapped__ is state_proxy.data["b"].__wrapped__

    # Rebinding with a non-proxy should return a MutableProxy object (not ImmutableMutableProxy).
    assert isinstance(state_proxy.__wrapped__.data["a"], MutableProxy)
    assert not isinstance(state_proxy.__wrapped__.data["a"], ImmutableMutableProxy)

    # Flush any oplock.
    await mock_app.state_manager.close()

    new_state_proxy = StateProxy(state)
    assert state_proxy is not new_state_proxy
    assert new_state_proxy.data["a"]._self_state is new_state_proxy
    assert state_proxy.data["a"]._self_state is state_proxy
    assert state_proxy.__wrapped__.data["a"]._self_state is state_proxy.__wrapped__

    async with state_proxy:
        state_proxy.data["a"].append(3)

    async with mock_app.state_manager.modify_state(
        _substate_key(token, MutableProxyState)
    ) as state:
        assert isinstance(state, MutableProxyState)
        assert state.data["a"] == [2, 3]
        if isinstance(mock_app.state_manager, StateManagerRedis):
            # In redis mode, the object identity does not persist across async with self calls.
            assert state.data["b"] == [2]
        else:
            # In disk/memory mode, the fact that data["b"] was mutated via data["a"] persists.
            assert state.data["b"] == [2, 3]
