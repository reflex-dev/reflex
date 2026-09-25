from __future__ import annotations

import asyncio
import copy
import dataclasses
import datetime
import functools
import inspect
import json
import logging
import math
import os
import pickle
import sys
import threading
from collections.abc import AsyncGenerator, Callable, Mapping
from textwrap import dedent
from types import MethodType
from typing import Any, ClassVar, Literal, TypeVar, cast
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
import reflex_base.config
from plotly.graph_objects import Figure
from pytest_mock import MockerFixture
from reflex_base import constants
from reflex_base.constants import CompileVars, RouteVar
from reflex_base.constants.state import FIELD_MARKER
from reflex_base.event import Event, EventHandler
from reflex_base.event.context import EventContext
from reflex_base.event.processor import BaseStateEventProcessor
from reflex_base.state.delta import _suppress_delta_recording
from reflex_base.state.proxy import MutableProxy
from reflex_base.state.token import BaseStateToken
from reflex_base.utils import format, types
from reflex_base.utils.exceptions import (
    InvalidLockWarningThresholdError,
    LockExpiredError,
    ReflexRuntimeError,
    SetUndefinedStateVarError,
    StateSerializationError,
    StateValueError,
    UnretrievableVarValueError,
)
from reflex_base.utils.format import json_dumps
from reflex_base.vars.base import Field, Var, computed_var, field
from typing_extensions import TypeAliasType

import reflex as rx
from reflex.app import App
from reflex.environment import environment
from reflex.istate.data import (
    HeaderData,
    RouterData,
    RouterDataVar,
    SessionData,
    URLData,
    _FrozenDictStrStr,
)
from reflex.istate.manager import StateManager
from reflex.istate.manager.disk import StateManagerDisk
from reflex.istate.manager.memory import StateManagerMemory
from reflex.istate.manager.redis import StateManagerRedis
from reflex.state import (
    BaseState,
    Delta,
    ImmutableStateError,
    OnLoadInternalState,
    State,
)
from reflex.testing import chdir
from reflex.utils import prerequisites
from tests.units.mock_redis import mock_redis

from .states import GenState

pytest.importorskip("pydantic")


from pydantic import BaseModel
from pydantic import BaseModel as Base

from tests.units.states.mutation import MutableTestState

CI = bool(os.environ.get("CI", False))
LOCK_EXPIRATION = 2500 if CI else 300
LOCK_WARNING_THRESHOLD = 1000 if CI else 100
LOCK_WARN_SLEEP = 1.5 if CI else 0.15
LOCK_EXPIRE_SLEEP = 2.5 if CI else 0.4


formatted_router_vars = {
    "rx_router_route_id" + FIELD_MARKER: "",
    "rx_router_url" + FIELD_MARKER: {
        "scheme": "",
        "netloc": "",
        "origin": "://",
        "path": "",
        "query": "",
        "query_parameters": {},
        "fragment": "",
        "href": "",
    },
    "rx_router_session" + FIELD_MARKER: {
        "client_token": "",
        "client_ip": "",
        "session_id": "",
    },
    "rx_router_headers" + FIELD_MARKER: {
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
    "rx_router_page" + FIELD_MARKER: {
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

    @rx.event
    def set_num1(self, value: int):
        """Set num1.

        Args:
            value: The new value for num1.
        """
        self.num1 = value

    @rx.event
    def set_num2(self, value: float):
        """Set num2.

        Args:
            value: The new value for num2.
        """
        self.num2 = value

    @rx.event
    def set_array(self, value: list[float]):
        """Set array.

        Args:
            value: The new value for array.
        """
        self.array = value

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

    @rx.event
    def set_value2(self, value: str):
        """Set value2.

        Args:
            value: The new value for value2.
        """
        self.value2 = value

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

    for field_name, f in fields.items():
        if f._backend or f._owner is not cls:
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
        constants.ROUTER,
        *constants.ROUTER_VARS,
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
        "set_num1",
        "set_num2",
    )

    cls = type(test_state)
    assert all(key in cls.event_handlers for key in expected_keys)


def test_default_value(test_state: TestState):
    """Test that the default value of a var is correct.

    Args:
        test_state: A state.
    """
    assert test_state.num1 == 0
    assert math.isclose(test_state.num2, 3.15)
    assert test_state.key == ""
    assert math.isclose(test_state.sum, 3.15)
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
    # Only vars with a backing field are serialized; `router` is a switchboard
    # over the per-field router vars and has no field of its own.
    assert set(test_state_dict[test_state.get_name()]) == {
        var + FIELD_MARKER for var in (*test_state.base_vars, *test_state.computed_vars)
    }
    assert set(test_state.dict(include_computed=False)[test_state.get_name()]) == {
        var + FIELD_MARKER for var in test_state.base_vars
    }


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
    assert math.isclose(test_state.num2, 3.15)
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


def test_reset_does_not_reset_inherited_backend_vars(
    test_state: TestState, child_state: ChildState
):
    """Test that reset() does not reset backend vars from parent states.

    This is a regression test for the issue where calling reset() on a child state
    would also reset backend vars that are inherited from the parent state, which
    breaks SharedState linkage when an unrelated state calls reset().

    Args:
        test_state: A state with backend vars.
        child_state: A child state inheriting from test_state.
    """
    # Set a backend var on the parent state to a non-default value
    original_backend_value = 42
    test_state._backend = original_backend_value

    # Verify it's been changed
    assert test_state._backend == original_backend_value

    # Reset only the child state
    child_state.reset()

    # The parent state's backend vars should NOT be reset
    # (they should retain their modified value)
    assert test_state._backend == original_backend_value

    # Now verify that resetting the parent state DOES reset its own backend vars
    test_state.reset()
    assert test_state._backend == 0  # Reset to default


def test_backend_vars_does_not_include_inherited(
    test_state: TestState, child_state: ChildState
):
    """Test that an inherited backend var is stored only on the parent instance.

    Args:
        test_state: A state with backend vars.
        child_state: A child state inheriting from test_state.
    """
    # ChildState inherits _backend from TestState, which stores it.
    assert ChildState.get_fields()["_backend"]._owner is TestState
    child_state._backend = 5
    assert test_state.__dict__["_backend"] == 5
    assert "_backend" not in child_state.__dict__


def test_setting_inherited_backend_var_does_not_mark_child_touched(
    test_state: TestState, child_state: ChildState
):
    """Test that setting a parent's backend var through a child doesn't mark child as touched.

    When a backend var from a parent state is modified through a child state instance,
    only the parent should be marked as touched, not the child.

    Args:
        test_state: A state with backend vars.
        child_state: A child state inheriting from test_state.
    """
    # Initially neither should be touched
    assert not test_state._was_touched
    assert not child_state._was_touched

    # Modify an inherited backend var through the child: the field is bound
    # to the parent, which stores it.
    child_state._backend = 99

    parent_touched = test_state._was_touched
    child_touched = child_state._was_touched

    # The parent should be marked as touched (the var belongs to it)
    assert parent_touched

    # But the child should NOT be marked as touched
    # (the var doesn't belong to the child, it belongs to the parent)
    assert not child_touched


@pytest.mark.asyncio
async def test_process_event_simple(
    token: str,
    mock_base_state_event_processor: BaseStateEventProcessor,
    emitted_deltas: list,
):
    """Test processing an event.

    Args:
        token: A token.
        mock_base_state_event_processor: The event processor.
        emitted_deltas: List to capture emitted deltas.
    """
    event = Event(
        name=f"{TestState.get_full_name()}.set_num1",
        payload={"value": 69},
    )
    async with mock_base_state_event_processor as processor:
        await processor.enqueue(token, event)
    # The delta should contain the changes, including computed vars.
    assert emitted_deltas == [
        (
            token,
            {
                TestState.get_full_name(): {
                    "num1" + FIELD_MARKER: 69,
                    "sum" + FIELD_MARKER: 72.15,
                },
                GrandchildState3.get_full_name(): {"computed" + FIELD_MARKER: ""},
            },
        )
    ]


@pytest.mark.asyncio
async def test_process_event_substate(
    token: str,
    mock_base_state_event_processor: BaseStateEventProcessor,
    emitted_deltas: list,
):
    """Test processing an event on a substate.

    Args:
        token: A token.
        mock_base_state_event_processor: The event processor.
        emitted_deltas: List to capture emitted deltas.
    """
    # Events should bubble down to the substate.
    event = Event(
        name=f"{ChildState.get_full_name()}.change_both",
        payload={"value": "hi", "count": 12},
    )
    async with mock_base_state_event_processor as processor:
        await processor.enqueue(token, event)
    assert emitted_deltas == [
        (
            token,
            {
                ChildState.get_full_name(): {
                    "value" + FIELD_MARKER: "HI",
                    "count" + FIELD_MARKER: 24,
                },
                GrandchildState3.get_full_name(): {"computed" + FIELD_MARKER: ""},
            },
        )
    ]
    emitted_deltas.clear()

    # Test with the grandchild state.
    event = Event(
        name=f"{GrandchildState.get_full_name()}.set_value2",
        payload={"value": "new"},
    )
    async with mock_base_state_event_processor as processor:
        await processor.enqueue(token, event)
    # GrandchildState3.computed is uncached, but its value is unchanged since the
    # previous delta, so it is not sent again.
    assert emitted_deltas == [
        (
            token,
            {GrandchildState.get_full_name(): {"value2" + FIELD_MARKER: "new"}},
        )
    ]


@pytest.mark.asyncio
async def test_process_event_generator(
    token: str,
    mock_base_state_event_processor: BaseStateEventProcessor,
    emitted_deltas: list,
):
    """Test event handlers that generate multiple updates.

    Args:
        token: A token.
        mock_base_state_event_processor: The event processor.
        emitted_deltas: List to capture emitted deltas.
    """
    event = Event(
        name=f"{GenState.get_full_name()}.go",
        payload={"c": 5},
    )
    async with mock_base_state_event_processor as processor:
        await processor.enqueue(token, event)
    # Generator yields 5 deltas (one per increment).
    assert len(emitted_deltas) == 5
    for count, (delta_token, delta) in enumerate(emitted_deltas, 1):
        assert delta_token == token
        assert delta == {
            GenState.get_full_name(): {"value" + FIELD_MARKER: count},
        }


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
    # Existing and new instances get the default
    assert ds1.dynamic_int == 42  # pyright: ignore [reportAttributeAccessIssue]
    assert DynamicState().dynamic_int == 42  # pyright: ignore[reportAttributeAccessIssue]
    assert isinstance(DynamicState.dynamic_int, Var)  # pyright: ignore [reportAttributeAccessIssue]

    ds1.add_var("dynamic_list", list[int], [5, 10])
    assert ds1.dynamic_list == [5, 10]  # pyright: ignore [reportAttributeAccessIssue]
    ds2 = DynamicState()
    assert ds2.dynamic_list == [5, 10]  # pyright: ignore[reportAttributeAccessIssue]
    ds2.dynamic_list.append(15)  # pyright: ignore[reportAttributeAccessIssue]
    assert ds2.dynamic_list == [5, 10, 15]  # pyright: ignore[reportAttributeAccessIssue]
    assert DynamicState().dynamic_list == [5, 10]  # pyright: ignore[reportAttributeAccessIssue]

    ds1.add_var("dynamic_dict", dict[str, int], {"k1": 5, "k2": 10})
    assert ds1.dynamic_dict == {"k1": 5, "k2": 10}  # pyright: ignore [reportAttributeAccessIssue]
    assert ds2.dynamic_dict == {"k1": 5, "k2": 10}  # pyright: ignore [reportAttributeAccessIssue]
    assert DynamicState().dynamic_dict == {"k1": 5, "k2": 10}  # pyright: ignore[reportAttributeAccessIssue]


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
    for router_var in constants.ROUTER_VARS:
        d.pop(router_var + FIELD_MARKER)
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

    for name in ("flag", "t1", "t2"):
        assert MainState._var_dependencies[name] == {
            (MainState.get_full_name(), "rendered_var")
        }
    assert MainState.computed_vars["rendered_var"]._deps(objclass=MainState) == {
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


async def test_computed_var_cached_depends_on_non_cached():
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
    assert await cs._get_resolved_delta() == {
        cs.get_name(): {"no_cache_v" + FIELD_MARKER: 0, "dep_v" + FIELD_MARKER: 0}
    }
    cs._clean()
    assert cs.dirty_vars == set()
    # no_cache_v is recomputed, but the value is unchanged, so it is not resent.
    assert await cs._get_resolved_delta() == {
        cs.get_name(): {"dep_v" + FIELD_MARKER: 0}
    }
    cs._clean()
    assert cs.dirty_vars == set()
    cs.v = 1
    assert cs.dirty_vars == {"v", "comp_v", "dep_v", "no_cache_v"}
    assert await cs._get_resolved_delta() == {
        cs.get_name(): {
            "v" + FIELD_MARKER: 1,
            "no_cache_v" + FIELD_MARKER: 1,
            "dep_v" + FIELD_MARKER: 1,
            "comp_v" + FIELD_MARKER: 1,
        }
    }
    cs._clean()
    assert cs.dirty_vars == set()
    assert await cs._get_resolved_delta() == {
        cs.get_name(): {"dep_v" + FIELD_MARKER: 1}
    }
    cs._clean()
    assert cs.dirty_vars == set()
    assert await cs._get_resolved_delta() == {
        cs.get_name(): {"dep_v" + FIELD_MARKER: 1}
    }
    cs._clean()
    assert cs.dirty_vars == set()


async def test_uncached_computed_var_unchanged_omitted_from_delta():
    """An uncached var that recomputes to the same value is left out of the delta."""
    calls = 0

    class UncachedState(BaseState):
        v: int = 0

        @rx.var(cache=False)
        def no_cache_v(self) -> int:
            nonlocal calls
            calls += 1
            return self.v

    ucs = UncachedState()
    assert await ucs._get_resolved_delta() == {
        ucs.get_name(): {"no_cache_v" + FIELD_MARKER: 0}
    }
    assert calls == 1
    ucs._clean()

    # Still recomputed, but the unchanged value is not sent again.
    assert await ucs._get_resolved_delta() == {}
    assert calls == 2
    ucs._clean()

    ucs.v = 1
    assert await ucs._get_resolved_delta() == {
        ucs.get_name(): {"v" + FIELD_MARKER: 1, "no_cache_v" + FIELD_MARKER: 1}
    }
    ucs._clean()
    assert await ucs._get_resolved_delta() == {}


async def test_uncached_computed_var_scalar_key_distinguishes_types():
    """Python-equal but JSON-distinct scalars are not suppressed as unchanged."""
    values = iter([1, True, 1.0])

    class ScalarState(BaseState):
        @rx.var(cache=False)
        def v(self) -> int | float:
            return next(values)

    ss = ScalarState()
    key = "v" + FIELD_MARKER
    # 1, True and 1.0 are all Python-equal, but the client would receive 1,
    # true and 1.0, so each one has to be sent.
    for expected_type in (int, bool, float):
        delta = await ss._get_resolved_delta()
        assert type(delta[ss.get_name()][key]) is expected_type
        ss._clean()


async def test_uncached_computed_var_nan_value_not_resent():
    """NaN is keyed by its serialized form, so an unchanged NaN is not resent."""

    class NanState(BaseState):
        @rx.var(cache=False)
        def v(self) -> float:
            return float("nan")

    ns = NanState()
    assert math.isnan(
        (await ns._get_resolved_delta())[ns.get_name()]["v" + FIELD_MARKER]
    )
    ns._clean()
    assert await ns._get_resolved_delta() == {}


class UncachedRedisState(BaseState):
    """A state with uncached computed vars, defined at module level to be picklable."""

    _v: int = 0

    @rx.var(cache=False)
    def scalar_v(self) -> int:
        """An uncached var with an atomic value.

        Returns:
            The backend var value.
        """
        return self._v

    @rx.var(cache=False)
    def list_v(self) -> list[int]:
        """An uncached var with a value keyed by a digest.

        Returns:
            A list holding the backend var value.
        """
        return [self._v]


async def test_uncached_computed_var_records_last_value_for_redis():
    """Recorded delta keys mark the state touched and survive serialization."""
    urs = UncachedRedisState()
    assert urs._was_touched is False
    assert await urs._get_resolved_delta() == {
        urs.get_name(): {
            "scalar_v" + FIELD_MARKER: 0,
            "list_v" + FIELD_MARKER: [0],
        }
    }
    # The recorded keys have to reach redis, so the state counts as touched.
    assert urs._was_touched is True

    # Recomputing unchanged values does not force another redis write.
    urs._clean()
    urs._was_touched = False
    assert await urs._get_resolved_delta() == {}
    assert urs._was_touched is False

    # A state restored from its serialized form still knows what was sent.
    restored = BaseState._deserialize(urs._serialize())
    assert isinstance(restored, UncachedRedisState)
    assert await restored._get_resolved_delta() == {}

    restored._v = 1
    assert await restored._get_resolved_delta() == {
        restored.get_name(): {
            "scalar_v" + FIELD_MARKER: 1,
            "list_v" + FIELD_MARKER: [1],
        }
    }


async def test_uncached_computed_var_mutable_value_mutated_in_place():
    """An uncached var returning a state-owned mutable value still sees mutations."""

    class UncachedMutableState(BaseState):
        items: list[str] = []

        @rx.var(cache=False)
        def all_items(self) -> list[str]:
            return self.items

    ums = UncachedMutableState()
    assert await ums._get_resolved_delta() == {
        ums.get_name(): {"all_items" + FIELD_MARKER: []}
    }
    ums._clean()
    assert await ums._get_resolved_delta() == {}
    ums._clean()

    ums.items.append("a")
    assert await ums._get_resolved_delta() == {
        ums.get_name(): {
            "items" + FIELD_MARKER: ["a"],
            "all_items" + FIELD_MARKER: ["a"],
        }
    }
    ums._clean()
    assert await ums._get_resolved_delta() == {}


async def test_uncached_computed_var_recorded_per_client_token():
    """A value already sent to one client is still sent to another client.

    A single state instance can serve multiple clients (linked shared states),
    so the recorded value only suppresses the delta for the client that got it.
    """

    class MultiClientState(BaseState):
        @rx.var(cache=False)
        def no_cache_v(self) -> int:
            return 1

    mcs = MultiClientState()
    mcs.router = RouterData(session=SessionData(client_token="token_a"))
    mcs._clean()
    assert await mcs._get_resolved_delta() == {
        mcs.get_name(): {"no_cache_v" + FIELD_MARKER: 1}
    }
    mcs._clean()
    assert await mcs._get_resolved_delta() == {}
    mcs._clean()

    # The same state instance now produces a delta for a different client.
    mcs.router = RouterData(session=SessionData(client_token="token_b"))
    mcs._clean()
    assert await mcs._get_resolved_delta() == {
        mcs.get_name(): {"no_cache_v" + FIELD_MARKER: 1}
    }
    mcs._clean()
    assert await mcs._get_resolved_delta() == {}


async def test_uncached_computed_var_unkeyable_value_always_sent():
    """A value that cannot be serialized has no key and is always sent."""

    class CircularState(BaseState):
        @rx.var(cache=False)
        def circular(self) -> list:
            value = []
            value.append(value)
            return value

    cs = CircularState()
    for _ in range(2):
        # Compare the keys only: the values are self-referential.
        delta = await cs._get_resolved_delta()
        assert list(delta[cs.get_name()]) == ["circular" + FIELD_MARKER]
        cs._clean()


async def test_uncached_async_computed_var_unchanged_omitted_from_delta():
    """An unchanged async uncached var is dropped from the resolved delta."""

    class AsyncUncachedState(BaseState):
        v: int = 0

        @rx.var(cache=False)
        async def no_cache_v(self) -> int:
            return self.v

    aus = AsyncUncachedState()
    assert await aus._get_resolved_delta() == {
        aus.get_name(): {"no_cache_v" + FIELD_MARKER: 0}
    }
    aus._clean()
    assert await aus._get_resolved_delta() == {}
    aus._clean()

    aus.v = 1
    assert await aus._get_resolved_delta() == {
        aus.get_name(): {"v" + FIELD_MARKER: 1, "no_cache_v" + FIELD_MARKER: 1}
    }
    aus._clean()
    assert await aus._get_resolved_delta() == {}


# Withholding an async var can only close the wrapper coroutine; the getter
# coroutine it holds is then collected unawaited, which a filter cannot reach
# and this test is not about.
@pytest.mark.filterwarnings(
    "ignore:coroutine '.*_awaitable_result' was never awaited:RuntimeWarning",
)
@pytest.mark.parametrize("mode", ["dropped", "replaced"])
@pytest.mark.parametrize("is_async", [False, True])
async def test_uncached_var_withheld_by_delta_override_is_resent(
    mode: str, is_async: bool, monkeypatch: pytest.MonkeyPatch
):
    """An uncached var withheld by a `get_delta` override is sent once released.

    Downstream packages wrap `get_delta` to keep vars the current user may not
    see out of the delta, either by dropping the key or by replacing the value
    with a public placeholder. Neither value reaches the client, so the real one
    has to be delivered as soon as the override stops withholding it -- even
    though the var recomputes to the value that was withheld.

    Args:
        mode: Whether the override drops the key or replaces its value.
        is_async: Whether the uncached var is an async one.
        monkeypatch: Pytest monkeypatch fixture.
    """

    class WithheldState(BaseState):
        n: int = 0

        @rx.var(cache=False)
        def secret(self) -> str:
            return f"secret-{self.n}"

    class AsyncWithheldState(BaseState):
        n: int = 0

        @rx.var(cache=False)
        async def secret(self) -> str:
            return f"secret-{self.n}"

    state_cls = AsyncWithheldState if is_async else WithheldState
    full_name = state_cls.get_full_name()
    key = "secret" + FIELD_MARKER
    withholding = True
    # Bound through the base class: neither state overrides `get_delta`, and the
    # wrapper below replaces it on both, so its `self` is only a `BaseState`.
    original_get_delta = BaseState.get_delta

    def withholding_get_delta(self: BaseState) -> Delta:
        delta = original_get_delta(self)
        if not withholding:
            return delta
        filtered: Delta = {}
        for name, subdelta in delta.items():
            withheld_subdelta = dict(subdelta)
            if key in withheld_subdelta:
                value = withheld_subdelta.pop(key)
                if inspect.iscoroutine(value):
                    # Withheld before `_resolve_delta` could await it.
                    value.close()
                if mode == "replaced":
                    withheld_subdelta[key] = "anon"
            if withheld_subdelta:
                filtered[name] = withheld_subdelta
        return filtered

    monkeypatch.setattr(state_cls, "get_delta", withholding_get_delta)

    def expected_withheld(**other_vars: Any) -> Delta:
        subdelta = {name + FIELD_MARKER: value for name, value in other_vars.items()}
        if mode == "replaced":
            subdelta[key] = "anon"
        return {full_name: subdelta} if subdelta else {}

    state = state_cls()
    assert await state._get_resolved_delta() == expected_withheld()
    state._clean()

    # The value changes while it is still withheld: the client never sees it.
    state.n = 1
    assert await state._get_resolved_delta() == expected_withheld(n=1)
    state._clean()

    # The override releases the var: the value the client never got is sent...
    withholding = False
    assert await state._get_resolved_delta() == {full_name: {key: "secret-1"}}
    state._clean()

    # ...and, having been delivered, it is not sent again.
    assert await state._get_resolved_delta() == {}
    state._clean()

    # Withhold a fresh value, then release one the client was already sent. A
    # dropped key leaves the client on that value, so there is nothing to send;
    # a placeholder overwrote it, so the record it invalidated has to go and the
    # value has to be delivered again.
    withholding = True
    state.n = 2
    assert await state._get_resolved_delta() == expected_withheld(n=2)
    state._clean()

    withholding = False
    state.n = 1
    restored: Delta = {full_name: {"n" + FIELD_MARKER: 1}}
    if mode == "replaced":
        restored[full_name][key] = "secret-1"
    assert await state._get_resolved_delta() == restored


async def test_uncached_computed_var_recorded_only_once_delivered():
    """A delta that is built but never delivered does not count as sent.

    `get_delta` may be wrapped downstream by a filter that drops entries from
    it, so only the delta returned by `_get_resolved_delta` -- what the caller
    goes on to emit -- records the values the client has.
    """

    class UndeliveredState(BaseState):
        @rx.var(cache=False)
        def v(self) -> int:
            return 1

    us = UndeliveredState()
    expected = {UndeliveredState.get_full_name(): {"v" + FIELD_MARKER: 1}}

    # Building a delta is not delivering it: the value is still owed.
    assert us.get_delta() == expected
    us._clean()
    assert us.get_delta() == expected
    us._clean()

    assert await us._get_resolved_delta() == expected
    us._clean()
    assert await us._get_resolved_delta() == {}
    us._clean()

    # Nor is such a delta deduped against what the client has: leaving a value
    # out is only safe where its delivery is what records it.
    assert us.get_delta() == expected


def test_get_delta_tolerates_zero_argument_override(test_state: TestState, monkeypatch):
    """A `get_delta` override taking only `self` still serves the whole state tree.

    Downstream packages monkeypatch `get_delta` with a function that accepts no
    arguments, so no internal caller may pass it one -- including the recursion
    into substates, which reaches the override for every state in the tree.

    Args:
        test_state: A test state.
        monkeypatch: Pytest monkeypatch fixture.
    """
    original_get_delta = TestState.get_delta
    seen: list[str] = []

    def patched_get_delta(self: TestState) -> Delta:
        seen.append(self.get_full_name())
        return original_get_delta(self)

    monkeypatch.setattr(TestState, "get_delta", patched_get_delta)

    child_state = test_state.get_substate([ChildState.get_name()])
    assert child_state is not None
    child_state.value = "hi"

    delta = test_state.get_delta()
    assert delta[ChildState.get_full_name()]["value" + FIELD_MARKER] == "hi"
    # The override is reached for substates, not only for the root.
    assert ChildState.get_full_name() in seen


async def test_discarded_delta_does_not_record_values_of_substates():
    """A delta built only for its side effects does not count as sent, at any depth."""

    class DiscardedParentState(BaseState):
        pass

    class DiscardedChildState(DiscardedParentState):
        v: int = 0

        @rx.var(cache=False)
        def no_cache_v(self) -> int:
            return self.v

    dps = DiscardedParentState()
    expected = {DiscardedChildState.get_full_name(): {"no_cache_v" + FIELD_MARKER: 0}}

    # A discarded traversal must not record the values it computed...
    with _suppress_delta_recording():
        assert await dps._get_resolved_delta() == expected
    dps._clean()

    # ...so the client still receives them on the next real delta.
    assert await dps._get_resolved_delta() == expected
    dps._clean()
    assert await dps._get_resolved_delta() == {}


async def test_suppressed_delta_inside_a_delivered_one_records_nothing(
    monkeypatch: pytest.MonkeyPatch,
):
    """Suppression holds wherever it is entered, not only at the top of a delta.

    `_suppress_delta_recording` describes the block it wraps, so a `get_delta`
    override that enters it records nothing even though the traversal reaching
    that override is the one being delivered.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
    """

    class SuppressingState(BaseState):
        @rx.var(cache=False)
        def v(self) -> int:
            return 1

    expected = {SuppressingState.get_full_name(): {"v" + FIELD_MARKER: 1}}
    original_get_delta = BaseState.get_delta

    def suppressing_get_delta(self: BaseState) -> Delta:
        with _suppress_delta_recording():
            return original_get_delta(self)

    monkeypatch.setattr(SuppressingState, "get_delta", suppressing_get_delta)

    ss = SuppressingState()
    for _ in range(2):
        assert await ss._get_resolved_delta() == expected
        ss._clean()


def test_delta_methods_take_no_arguments():
    """`get_delta` and `_get_resolved_delta` must stay callable with no arguments.

    Downstream packages monkeypatch them with functions accepting only `self`, so
    a parameter here breaks every delta for them as soon as a caller passes it.
    """
    assert list(inspect.signature(BaseState.get_delta).parameters) == ["self"]
    assert list(inspect.signature(BaseState._get_resolved_delta).parameters) == ["self"]


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
        **formatted_router_vars,
    }
    assert dict1[cs.get_full_name()] == {"dep_v" + FIELD_MARKER: 2}
    dict2 = json.loads(json_dumps(ps.dict()))
    assert dict2[ps.get_full_name()] == {
        "no_cache_v" + FIELD_MARKER: 3,
        **formatted_router_vars,
    }
    assert dict2[cs.get_full_name()] == {"dep_v" + FIELD_MARKER: 4}
    dict3 = json.loads(json_dumps(ps.dict()))
    assert dict3[ps.get_full_name()] == {
        "no_cache_v" + FIELD_MARKER: 5,
        **formatted_router_vars,
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

        class MethodPartial(functools.partial):
            """A partial binding like a method, as partials do from Python 3.14."""

            def __get__(self, instance: Any, owner: Any = None) -> Any:
                return self if instance is None else MethodType(self, instance)

        HandlerState.handler = MethodPartial(HandlerState.handler.fn)  # pyright: ignore [reportFunctionMemberAccess]
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
async def test_state_with_invalid_yield(
    token: str,
    mock_base_state_event_processor: BaseStateEventProcessor,
):
    """Test that an error is thrown when a state yields an invalid value.

    Args:
        token: A token.
        mock_base_state_event_processor: The event processor.
    """

    class StateWithInvalidYield(BaseState):
        """A state that yields an invalid value."""

        def invalid_handler(self):
            """Invalid handler.

            Yields:
                an invalid value.
            """
            yield 1

    captured_exceptions: list[Exception] = []

    def capture_exception(ex: Exception) -> None:
        captured_exceptions.append(ex)

    mock_base_state_event_processor.backend_exception_handler = capture_exception

    event = Event(
        name=f"{StateWithInvalidYield.get_full_name()}.invalid_handler",
        payload={},
    )
    async with mock_base_state_event_processor as processor:
        await processor.enqueue(token, event)

    assert len(captured_exceptions) == 1
    assert isinstance(captured_exceptions[0], TypeError)
    assert "must only return/yield: None, Events or other EventHandlers" in str(
        captured_exceptions[0]
    )


@pytest.fixture
def substate_token(state_manager, token) -> BaseStateToken:
    """A token + substate name for looking up in state manager.

    Args:
        state_manager: A state manager instance.
        token: A token.

    Returns:
        Token concatenated with the state_manager's state full_name.
    """
    return BaseStateToken(ident=token, cls=TestState)


@pytest.mark.asyncio
async def test_state_manager_modify_state(
    state_manager: StateManager, token: str, substate_token: BaseStateToken
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
        lock = state_manager._states_locks.get(token)
        assert lock is None or not lock.locked()

        # separate instances should NOT share locks
        sm2 = type(state_manager)()
        assert sm2._state_manager_lock is not state_manager._state_manager_lock
        assert not sm2._states_locks
        if state_manager._states_locks:
            assert sm2._states_locks != state_manager._states_locks

        await sm2.close()


@pytest.mark.asyncio
async def test_state_manager_contend(
    state_manager: StateManager, token: str, substate_token: BaseStateToken
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
        lock = state_manager._states_locks.get(token)
        assert lock is None or not lock.locked()


@pytest.mark.asyncio
async def test_state_manager_legacy_token(state_manager: StateManager, token: str):
    """Test that passing a legacy string token to the state manager works with a deprecation warning.

    Args:
        state_manager: A state manager instance.
        token: A token.
    """
    from unittest.mock import patch

    from reflex_base.utils import console
    from reflex_base.utils import log as _base_log

    from reflex.state import State

    legacy_token = f"{token}_{OnLoadState.get_full_name()}"
    dedupe_state = _base_log._dedupe_filter().seen.copy()

    try:
        with patch.object(
            console, "deprecate", wraps=console.deprecate
        ) as mock_deprecate:
            _base_log._dedupe_filter().seen.clear()
            # The legacy modify_state token path emits the deprecation.
            async with state_manager.modify_state(legacy_token) as state:
                assert isinstance(state, State)
                assert OnLoadState.get_name() in state.substates
            mock_deprecate.assert_called()
            assert (
                mock_deprecate.call_args.kwargs["feature_name"]
                == "Passing a string to modify_state"
            )

        with patch.object(
            console, "deprecate", wraps=console.deprecate
        ) as mock_deprecate:
            _base_log._dedupe_filter().seen.clear()
            # The legacy get_state token path emits the same deprecation.
            retrieved = await state_manager.get_state(legacy_token)
            assert isinstance(retrieved, State)
            assert OnLoadState.get_name() in retrieved.substates
            mock_deprecate.assert_called()
            assert (
                mock_deprecate.call_args.kwargs["feature_name"]
                == "Passing a string to modify_state"
            )

        with patch.object(
            console, "deprecate", wraps=console.deprecate
        ) as mock_deprecate:
            _base_log._dedupe_filter().seen.clear()
            # The legacy set_state token path emits the same deprecation.
            await state_manager.set_state(legacy_token, retrieved)
            mock_deprecate.assert_called()
            assert (
                mock_deprecate.call_args.kwargs["feature_name"]
                == "Passing a string to modify_state"
            )

        with patch.object(
            console, "deprecate", wraps=console.deprecate
        ) as mock_deprecate:
            _base_log._dedupe_filter().seen.clear()
            # A final legacy get_state lookup remains supported.
            final = await state_manager.get_state(legacy_token)
            assert isinstance(final, State)
            assert OnLoadState.get_name() in final.substates
            mock_deprecate.assert_called()
            assert (
                mock_deprecate.call_args.kwargs["feature_name"]
                == "Passing a string to modify_state"
            )
    finally:
        _base_log._dedupe_filter().seen.clear()
        _base_log._dedupe_filter().seen.update(dedupe_state)


@pytest_asyncio.fixture(loop_scope="function")
async def state_manager_redis() -> AsyncGenerator[StateManager, None]:
    """Instance of state manager for redis only.

    Yields:
        A state manager instance
    """
    state_manager = StateManager.create()

    if not isinstance(state_manager, StateManagerRedis):
        # Create a mocked redis client instead of skipping.
        state_manager = StateManagerRedis(redis=mock_redis())

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
    return BaseStateToken(ident=token, cls=TestState)


@pytest.mark.asyncio
async def test_state_manager_lock_expire(
    state_manager_redis: StateManagerRedis,
    token: str,
    substate_token_redis: BaseStateToken,
):
    """Test that the state manager lock expires and raises exception exiting context.

    Args:
        state_manager_redis: A state manager instance.
        token: A token.
        substate_token_redis: A token + substate name for looking up in state manager.
    """
    state_manager_redis.lock_expiration = LOCK_EXPIRATION
    state_manager_redis.lock_warning_threshold = LOCK_WARNING_THRESHOLD
    state_manager_redis.oplock_hold_time_ms = LOCK_EXPIRATION // 2

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
    state_manager_redis: StateManagerRedis,
    token: str,
    substate_token_redis: BaseStateToken,
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
    state_manager_redis.oplock_hold_time_ms = LOCK_EXPIRATION // 2

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
    substate_token_redis: BaseStateToken,
    caplog: pytest.LogCaptureFixture,
):
    """Test that the state manager triggers a warning when lock contention exceeds the warning threshold.

    Args:
        state_manager_redis: A state manager instance.
        token: A token.
        substate_token_redis: A token + substate name for looking up in state manager.
        caplog: Pytest log capture fixture.
    """
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
    lock_warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "was held too long" in r.getMessage()
    ]
    if environment.REFLEX_OPLOCK_ENABLED.get():
        # When Oplock is enabled, we don't warn when lock is held too long.
        assert not lock_warnings
    else:
        assert len(lock_warnings) == 7


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
async def test_state_read_only_until_entered(
    grandchild_state: GrandchildState,
    token: str,
    attached_mock_base_state_event_processor: BaseStateEventProcessor,
    emitted_deltas: list[tuple[str, Mapping[str, Mapping[str, Any]]]],
    attached_mock_event_context: EventContext,
):
    """A state loaded by an event is read-only once the lock is released, until entered.

    Args:
        grandchild_state: A grandchild state.
        token: A token.
        attached_mock_base_state_event_processor: The event processor attached for this test.
        emitted_deltas: A list to capture emitted deltas.
        attached_mock_event_context: The event context attached for this test.
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
    state_manager = attached_mock_event_context.state_manager
    if isinstance(state_manager, (StateManagerMemory, StateManagerDisk)):
        state_manager.states[parent_state.router.session.client_token] = parent_state
    elif isinstance(state_manager, StateManagerRedis):
        pickle_state = parent_state._serialize()
        if pickle_state:
            await state_manager.redis.set(
                str(
                    BaseStateToken(
                        ident=parent_state.router.session.client_token,
                        cls=type(parent_state),
                    )
                ),
                pickle_state,
                ex=state_manager.token_expiration,
            )

    # As loaded by an event whose lock was released since.
    parent_state._event_context = attached_mock_event_context

    # cannot use normal contextmanager protocol: Python 3.10 raises AttributeError.
    with pytest.raises((TypeError, AttributeError)), grandchild_state:  # pyright: ignore [reportGeneralTypeIssues]
        pass

    with pytest.raises(ImmutableStateError):
        # cannot directly modify the state outside of async context
        grandchild_state.value2 = "16"

    # Reading, including other states in the tree, is allowed.
    assert await grandchild_state.get_state(ChildState) is child_state
    assert grandchild_state.get_substate([]) is grandchild_state
    assert grandchild_state.parent_state is child_state

    async with grandchild_state:
        if isinstance(state_manager, (StateManagerMemory, StateManagerDisk)):
            # For in-process store, only one instance of the state exists
            assert grandchild_state.parent_state is child_state
        else:
            # When redis is used, the state takes the place of the reloaded one.
            assert grandchild_state.parent_state is not child_state
        grandchild_state.value2 = "42"
    with pytest.raises(ImmutableStateError):
        grandchild_state.value2 = "43"
    assert grandchild_state.value2 == "42"

    if environment.REFLEX_OPLOCK_ENABLED.get():
        await state_manager.close()

    # Get the state from the state manager directly and check that the value is updated
    gotten_state = await state_manager.get_state(
        BaseStateToken(
            ident=grandchild_state.router.session.client_token,
            cls=type(grandchild_state),
        )
    )
    if isinstance(state_manager, (StateManagerMemory, StateManagerDisk)):
        # For in-process store, only one instance of the state exists
        assert gotten_state is parent_state
    else:
        assert gotten_state is not parent_state
    gotten_grandchild_state = gotten_state.get_substate(
        grandchild_state.get_full_name().split(".")
    )
    assert gotten_grandchild_state is not None
    assert isinstance(gotten_grandchild_state, GrandchildState)
    assert gotten_grandchild_state.value2 == "42"

    # ensure state update was emitted
    await attached_mock_base_state_event_processor.join(timeout=1)
    assert emitted_deltas == [
        (
            token,
            {
                TestState.get_full_name(): {
                    "rx_router_session" + FIELD_MARKER: router_data.session,
                    "rx_router_headers" + FIELD_MARKER: router_data.headers,
                    "rx_router_page" + FIELD_MARKER: router_data._page,
                    "rx_router_url" + FIELD_MARKER: URLData.from_url(router_data.url),
                    "rx_router_route_id" + FIELD_MARKER: router_data.route_id,
                },
                grandchild_state.get_full_name(): {
                    "value2" + FIELD_MARKER: "42",
                },
                GrandchildState3.get_full_name(): {
                    "computed" + FIELD_MARKER: "",
                },
            },
        )
    ]


class BackgroundTaskState(BaseState):
    """A state with a background task."""

    order: list[str] = []
    dict_list: dict[str, list[int]] = {"foo": [1, 2, 3]}
    dc: ModelDC = ModelDC()
    _started: ClassVar[asyncio.Event | None] = None

    @rx.var(cache=False)
    def computed_order(self) -> list[str]:
        """Get the order as a computed var.

        Returns:
            The value of 'order' var.
        """
        return self.order

    @rx.event(background=True)
    async def background_task(self, startup_delay: float = 0):
        """A background task that updates the state."""
        if startup_delay:
            await asyncio.sleep(startup_delay)
        async with self:
            assert not self.order
            self.order.append("background_task:start")

        if BackgroundTaskState._started is not None:
            BackgroundTaskState._started.set()

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
                pass  # reload the state

        async with self:
            # Methods on MutableProxy should return their wrapped return value.
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
        await self.background_task(0)

    async def bad_chain2(self):
        """Test that a background task generator cannot be chained."""
        async for _foo in self.background_task_generator():
            pass


@pytest.mark.asyncio
@pytest.mark.parametrize("startup_delay", [0, 0.6])
async def test_background_task_no_block(
    mock_app: rx.App,
    token: str,
    mock_base_state_event_processor: BaseStateEventProcessor,
    emitted_deltas: list,
    state_manager: StateManager,
    startup_delay: float,
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that a background task does not block other events.

    Args:
        mock_app: An app that will be returned by `get_app()`
        token: A token.
        mock_base_state_event_processor: The event processor.
        emitted_deltas: List to capture emitted deltas.
        state_manager: A state manager instance.
        startup_delay: Delay before the background task acquires its first lock.
        monkeypatch: Reset the test-only startup signal after each case.
    """
    background_started = asyncio.Event()
    monkeypatch.setattr(BackgroundTaskState, "_started", background_started)
    async with mock_base_state_event_processor as processor:
        # Start background task
        await processor.enqueue(
            token,
            Event(
                name=f"{BackgroundTaskState.get_full_name()}.background_task",
                payload={"startup_delay": startup_delay},
            ),
        )

        await asyncio.wait_for(background_started.wait(), timeout=10)

        # Process another normal event while background task is polling
        await processor.enqueue(
            token,
            Event(
                name=f"{BackgroundTaskState.get_full_name()}.other",
                payload={},
            ),
        )

    # After processor context exits, all tasks including background are done.
    exp_order = [
        "background_task:start",
        "other",
        "background_task:stop",
        "other",
        "private",
    ]

    if environment.REFLEX_OPLOCK_ENABLED.get():
        await state_manager.close()

    background_task_state = await state_manager.get_state(
        BaseStateToken(ident=token, cls=BackgroundTaskState)
    )
    assert isinstance(background_task_state, BackgroundTaskState)
    assert background_task_state.order == exp_order


@pytest.mark.asyncio
async def test_background_task_reset(
    mock_app: rx.App,
    token: str,
    mock_base_state_event_processor: BaseStateEventProcessor,
    state_manager: StateManager,
):
    """Test that a background task calling reset is protected by the state proxy.

    Args:
        mock_app: An app that will be returned by `get_app()`
        token: A token.
        mock_base_state_event_processor: The event processor.
        state_manager: A state manager instance.
    """
    async with mock_base_state_event_processor as processor:
        await processor.enqueue(
            token,
            Event(
                name=f"{BackgroundTaskState.get_full_name()}.background_task_reset",
                payload={},
            ),
        )

    if environment.REFLEX_OPLOCK_ENABLED.get():
        await state_manager.close()

    background_task_state = await state_manager.get_state(
        BaseStateToken(ident=token, cls=BackgroundTaskState)
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


class YieldFromBackgroundState(BaseState):
    """A state used to verify the type of `self` in a yielded event handler."""

    counter: int = 0
    follow_up_self_type: str = ""
    dict_field: dict[str, int] = {"a": 1}

    @rx.event(background=True)
    async def trigger(self):
        """A background handler that yields a non-background handler.

        Yields:
            A reference to the non-background follow_up handler.
        """
        yield YieldFromBackgroundState.follow_up()

    @rx.event(background=True)
    async def trigger_inside_lock(self):
        """A background handler that yields a non-background handler from inside `async with self`.

        Yields:
            A reference to the non-background follow_up handler.
        """
        async with self:
            self.counter += 1
            yield YieldFromBackgroundState.follow_up()

    @rx.event(background=True)
    async def trigger_with_arg(self):
        """A background handler that yields a non-background handler with a state mutable as arg.

        Yields:
            A reference to the non-background follow_up_with_arg handler,
            passing `self.dict_field` (a state-owned mutable) as the argument.
        """
        # Access the mutable outside the lock (a read-only MutableProxy) and
        # pass it as an argument to the yielded non-background handler.
        yield YieldFromBackgroundState.follow_up_with_arg(self.dict_field)

    @rx.event
    def follow_up(self):
        """A non-background handler invoked via yield from a background handler.

        Writes to state directly (no `async with self`); this only works if
        its event holds the lock.
        """
        self.follow_up_self_type = type(self).__name__
        self.counter += 1

    @rx.event
    def follow_up_with_arg(self, arg: dict[str, int]):
        """A non-background handler that mutates an argument passed to it.

        Args:
            arg: A dict argument that the handler will mutate.
        """
        # Mutating the arg should succeed: it must NOT be a MutableProxy bound
        # to the trigger's (now read-only) state.
        arg["b"] = 2
        # Persist a copy onto the (real) state so the test can verify what was seen.
        self.dict_field = dict(arg)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("trigger_handler", "expected_counter"),
    [
        ("trigger", 1),
        ("trigger_inside_lock", 2),
    ],
)
async def test_yielded_non_background_event_receives_real_state(
    mock_app: rx.App,
    token: str,
    mock_base_state_event_processor: BaseStateEventProcessor,
    state_manager: StateManager,
    trigger_handler: str,
    expected_counter: int,
):
    """A non-background event yielded by a background event must run on the real state.

    The yielded handler must be able to modify state directly without
    `async with self`. This holds whether the
    yield happens outside or inside the background handler's `async with self`.

    Args:
        mock_app: An app that will be returned by `get_app()`.
        token: A token.
        mock_base_state_event_processor: The event processor.
        state_manager: A state manager instance.
        trigger_handler: The name of the background handler to invoke.
        expected_counter: The expected counter value after both handlers run.
    """
    async with mock_base_state_event_processor as processor:
        future = await processor.enqueue(
            token,
            Event(
                name=f"{YieldFromBackgroundState.get_full_name()}.{trigger_handler}",
                payload={},
            ),
        )
        # Wait for the trigger and its yielded follow_up to fully complete.
        await future.wait_all()

    if environment.REFLEX_OPLOCK_ENABLED.get():
        await state_manager.close()

    state = await state_manager.get_state(
        BaseStateToken(ident=token, cls=YieldFromBackgroundState)
    )
    assert isinstance(state, YieldFromBackgroundState)
    # Direct mutation by the yielded handler succeeded and was persisted.
    assert state.counter == expected_counter
    assert state.follow_up_self_type == YieldFromBackgroundState.__name__


@pytest.mark.asyncio
async def test_yielded_event_arg_from_background_state_is_mutable(
    mock_app: rx.App,
    token: str,
    mock_base_state_event_processor: BaseStateEventProcessor,
    state_manager: StateManager,
):
    """A mutable arg passed by a background event must be mutable in the yielded handler.

    Regression: when a background handler yields ``Handler(self.some_dict)``,
    ``self.some_dict`` is a ``MutableProxy`` tied to the trigger's state,
    which is read-only outside of its lock: that proxy refuses writes -- so the yielded non-background handler can't mutate the arg it
    was given. The arg must be unwrapped (or otherwise made mutable) before
    being delivered to the yielded handler.

    Args:
        mock_app: An app that will be returned by `get_app()`.
        token: A token.
        mock_base_state_event_processor: The event processor.
        state_manager: A state manager instance.
    """
    async with mock_base_state_event_processor as processor:
        future = await processor.enqueue(
            token,
            Event(
                name=f"{YieldFromBackgroundState.get_full_name()}.trigger_with_arg",
                payload={},
            ),
        )
        await future.wait_all()

    if environment.REFLEX_OPLOCK_ENABLED.get():
        await state_manager.close()

    state = await state_manager.get_state(
        BaseStateToken(ident=token, cls=YieldFromBackgroundState)
    )
    assert isinstance(state, YieldFromBackgroundState)
    # The yielded handler successfully mutated the dict it was passed.
    assert state.dict_field == {"a": 1, "b": 2}


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
    # The copy tracks its own changes.
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


@pytest.mark.usefixtures("forked_registration_context")
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
            **formatted_router_vars,
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


def exp_is_hydrated(state: type[BaseState], is_hydrated: bool = True) -> dict[str, Any]:
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

    @rx.event
    def test_handler(self):
        """Test handler that calls another handler.

        Yields:
            EventHandler to change name.
        """
        self.num += 1
        yield type(self).change_name
        yield type(self).change_name("other")

    @rx.event
    def change_name(self, name: str = "default"):
        """Test handler to change name."""
        self.name = name


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
        (
            OnLoadState,
            [
                {OnLoadState.get_full_name(): {"num" + FIELD_MARKER: 1}},
                exp_is_hydrated(State, True),
            ],
        ),
        (
            OnLoadState2,
            [
                {OnLoadState2.get_full_name(): {"num" + FIELD_MARKER: 1}},
                exp_is_hydrated(State, True),
                {OnLoadState2.get_full_name(): {"name" + FIELD_MARKER: "default"}},
                {OnLoadState2.get_full_name(): {"name" + FIELD_MARKER: "other"}},
            ],
        ),
        (
            OnLoadState3,
            [
                {OnLoadState3.get_full_name(): {"num" + FIELD_MARKER: 1}},
                exp_is_hydrated(State, True),
            ],
        ),
    ],
)
async def test_preprocess(
    app_module_mock,
    token,
    test_state,
    expected,
    mocker: MockerFixture,
    mock_root_event_context: EventContext,
    mock_base_state_event_processor: BaseStateEventProcessor,
    emitted_deltas: list,
):
    """Test that a state hydrate event is processed correctly.

    Args:
        app_module_mock: The app module that will be returned by get_app().
        token: A token.
        test_state: State to process event.
        expected: Expected delta.
        mocker: pytest mock object.
        mock_root_event_context: The mock root event context.
        mock_base_state_event_processor: The event processor.
        emitted_deltas: List to capture emitted deltas.
    """
    app = app_module_mock.app = App(_state=State)
    app._state_manager = mock_root_event_context.state_manager

    def index():
        return "hello"

    app.add_page(index, on_load=test_state.test_handler)
    app._compile_page("index")

    on_load_internal_name = format.format_event_handler(
        OnLoadInternalState.on_load_internal  # pyright: ignore[reportArgumentType]
    )

    async with mock_base_state_event_processor as processor:
        on_load_future = await processor.enqueue(
            token,
            Event(
                name=on_load_internal_name,
                router_data={
                    RouteVar.PATH: "/",
                    RouteVar.ORIGIN: "/",
                    RouteVar.QUERY: {},
                },
            ),
        )
        await on_load_future.wait_all()

    # The processor chains all events: on_load_internal sets is_hydrated=False,
    # then the on_load handler runs, then set_is_hydrated(True) runs.
    # First delta: router + is_hydrated=False
    assert len(emitted_deltas) == 1 + len(expected)
    first_token, first_delta = emitted_deltas[0]
    assert first_token == token
    first_state_delta = first_delta[State.get_full_name()]
    assert first_state_delta.pop("rx_router_url" + FIELD_MARKER) is not None
    for router_var in constants.ROUTER_VARS:
        first_state_delta.pop(router_var + FIELD_MARKER, None)
    assert first_delta == exp_is_hydrated(State, False)

    # Find the deltas containing the test handler's state change
    for (delta_token, actual_delta), expected_delta in zip(
        emitted_deltas[1:], expected, strict=True
    ):
        assert delta_token == token
        assert actual_delta == expected_delta


@pytest.mark.asyncio
async def test_preprocess_multiple_load_events(
    app_module_mock,
    token,
    mocker: MockerFixture,
    mock_root_event_context: EventContext,
    mock_base_state_event_processor: BaseStateEventProcessor,
    emitted_deltas: list,
):
    """Test that a state hydrate event for multiple on-load events is processed correctly.

    Args:
        app_module_mock: The app module that will be returned by get_app().
        token: A token.
        mocker: pytest mock object.
        mock_root_event_context: The mock root event context.
        mock_base_state_event_processor: The event processor.
        emitted_deltas: List to capture emitted deltas.
    """
    app = app_module_mock.app = App(_state=State)
    app._state_manager = mock_root_event_context.state_manager

    def index():
        return "hello"

    app.add_page(index, on_load=[OnLoadState.test_handler, OnLoadState.test_handler])
    app._compile_page("index")

    on_load_internal_name = format.format_event_handler(
        OnLoadInternalState.on_load_internal  # pyright: ignore[reportArgumentType]
    )

    async with mock_base_state_event_processor as processor:
        await processor.enqueue(
            token,
            Event(
                name=on_load_internal_name,
                router_data={
                    RouteVar.PATH: "/",
                    RouteVar.ORIGIN: "/",
                    RouteVar.QUERY: {},
                },
            ),
        )
        await processor.join()

    # First delta: router + is_hydrated=False
    assert len(emitted_deltas) >= 2
    first_delta = emitted_deltas[0][1]
    first_state_delta = first_delta[State.get_full_name()]
    assert first_state_delta.pop("rx_router_url" + FIELD_MARKER) is not None
    for router_var in constants.ROUTER_VARS:
        first_state_delta.pop(router_var + FIELD_MARKER, None)
    assert first_delta == exp_is_hydrated(State, False)

    # Find deltas containing the test handler's state change (num incremented twice)
    handler_deltas = [
        d
        for _, d in emitted_deltas
        if OnLoadState.get_full_name() in d
        and "num" + FIELD_MARKER in d[OnLoadState.get_full_name()]
    ]
    assert len(handler_deltas) == 2
    assert handler_deltas[0][OnLoadState.get_full_name()]["num" + FIELD_MARKER] == 1
    assert handler_deltas[1][OnLoadState.get_full_name()]["num" + FIELD_MARKER] == 2

    # Find the delta that sets is_hydrated back to True
    hydrated_deltas = [
        d
        for _, d in emitted_deltas
        if State.get_full_name() in d
        and d[State.get_full_name()].get(CompileVars.IS_HYDRATED + FIELD_MARKER) is True
    ]
    assert len(hydrated_deltas) == 1


@pytest.mark.asyncio
async def test_get_state(token: str, attached_mock_event_context: EventContext):
    """Test that a get_state populates the top level state and delta calculation is correct.

    Args:
        token: A token.
        attached_mock_event_context: An event context with a state manager that has a TestState instance corresponding to the token.
    """
    state_manager = attached_mock_event_context.state_manager

    # Get instance of ChildState2.
    test_state = await state_manager.get_state(
        BaseStateToken(ident=token, cls=ChildState2)
    )
    assert isinstance(test_state, TestState)
    if isinstance(state_manager, (StateManagerMemory, StateManagerDisk)):
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

    assert await test_state._get_resolved_delta() == {
        GrandchildState.get_full_name(): {
            "value2" + FIELD_MARKER: "set_value",
        },
        GrandchildState3.get_full_name(): {
            "computed" + FIELD_MARKER: "",
        },
    }

    # Get a fresh instance
    new_test_state = await state_manager.get_state(
        BaseStateToken(ident=token, cls=ChildState2)
    )
    assert isinstance(new_test_state, TestState)
    if isinstance(state_manager, (StateManagerMemory, StateManagerDisk)):
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

    expected_delta = {
        ChildState2.get_full_name(): {
            "value" + FIELD_MARKER: "set_c2_value",
        },
        GrandchildState2.get_full_name(): {
            "cached" + FIELD_MARKER: "set_c2_value",
        },
    }
    if not isinstance(state_manager, (StateManagerMemory, StateManagerDisk)):
        # With redis this is a fresh instance which has not sent the uncached
        # GrandchildState3.computed yet; in memory it was sent by the delta above.
        expected_delta[GrandchildState3.get_full_name()] = {
            "computed" + FIELD_MARKER: "",
        }
    assert await new_test_state._get_resolved_delta() == expected_delta


@pytest.mark.asyncio
async def test_get_state_from_sibling_not_cached(
    token: str, attached_mock_event_context: EventContext
):
    """A test simulating update_vars_internal when setting cookies with computed vars.

    In that case, a sibling state, UpdateVarsInternalState handles the fetching
    of states that need to have values set. Only the states that have a computed
    var are pre-fetched (like Child3 in this test), so `get_state` needs to
    avoid refetching those already-cached states when getting substates,
    otherwise the set values will be overridden by the freshly deserialized
    version and lost.

    Explicit regression test for https://github.com/reflex-dev/reflex/issues/2851.

    Args:
        token: A token.
        attached_mock_event_context: An event context with a state manager that has a TestState instance corresponding to the token.
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

    state_manager = attached_mock_event_context.state_manager

    # Get the top level state via unconnected sibling.
    root = await state_manager.get_state(BaseStateToken(ident=token, cls=Child))
    # Set value in parent_var to assert it does not get refetched later.
    root.parent_var = 1

    if isinstance(state_manager, StateManagerRedis):
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

    # Reading self.router recurses into the router property getter, so the
    # dependency lands on each of the per-field router vars.
    assert foo._deps(objclass=RouterVarDepState) == {
        RouterVarDepState.get_full_name(): set(constants.ROUTER_VARS)
    }
    for router_var in constants.ROUTER_VARS:
        assert (RouterVarDepState.get_full_name(), "foo") in State._var_dependencies[
            router_var
        ]

    # Get state from state manager.
    rx_state = await state_manager.get_state(BaseStateToken(ident=token, cls=State))
    assert RouterVarParentState.get_name() in rx_state.substates
    parent_state = rx_state.substates[RouterVarParentState.get_name()]
    assert RouterVarDepState.get_name() in parent_state.substates
    state = parent_state.substates[RouterVarDepState.get_name()]

    assert state.dirty_vars == set()

    # Reassign router var
    state.router = state.router
    assert rx_state.dirty_vars == set(constants.ROUTER_VARS)
    assert state.dirty_vars == {"foo"}
    assert parent_state.dirty_substates == {RouterVarDepState.get_name()}

    # The locally-defined states above registered themselves in the class-level
    # dependency maps on State, which outlive this test. Left behind, a later
    # test that dirties a router var on a fresh State tree resolves the stale
    # entry and raises on the missing substate. Drop them.
    for dep_set in State._var_dependencies.values():
        dep_set.difference_update({
            (RouterVarDepState.get_full_name(), "foo"),
        })
    State._potentially_dirty_states.discard(RouterVarDepState.get_full_name())


@pytest.mark.parametrize("name", constants.ROUTER_VARS)
def test_router_field_names_are_reserved(name):
    """A state cannot replace framework-owned router storage.

    The router fields are declared on `BaseState`, so their names are reserved
    like any other framework member.
    """
    with pytest.raises(StateValueError, match=name):
        type(
            "InvalidRouterState",
            (State,),
            {"__module__": __name__, "__annotations__": {name: int}, name: 1},
        )


def test_router_var_dep_legacy_string() -> None:
    """An explicit deps=["router"] still fires when any router var changes.

    The `router` base var was split into per-field vars; a legacy string dep
    on "router" is expanded to all of them (with a deprecation warning).
    """

    class LegacyRouterDepState(State):
        """A state with a legacy string dependency on the router var."""

        @rx.var(deps=["router"], auto_deps=False)
        def foo(self) -> str:
            return self.router.url.path

    for router_var in constants.ROUTER_VARS:
        assert (
            LegacyRouterDepState.get_full_name(),
            "foo",
        ) in State._var_dependencies[router_var]
    assert "router" not in State._var_dependencies

    # Drop the class-level registrations this locally-defined state made; see
    # the note in test_router_var_dep.
    for dep_set in State._var_dependencies.values():
        dep_set.discard((LegacyRouterDepState.get_full_name(), "foo"))
    State._potentially_dirty_states.discard(LegacyRouterDepState.get_full_name())


def test_router_var_dep_legacy_string_still_compiles() -> None:
    """An app declaring deps=["router"] must still pass dependency validation.

    `_validate_var_dependencies` checks the raw `_deps()` names against
    `state_cls.vars` rather than the expanded registrations, so the deprecated
    string only keeps working while `router` is itself listed as a var.
    """

    class LegacyRouterCompileState(State):
        """A state with a legacy string dependency on the router var."""

        @rx.var(deps=["router"], auto_deps=False)
        def foo(self) -> str:
            return self.router.url.path

    assert constants.ROUTER in State.vars
    # Raises VarDependencyError if the dependency does not resolve to a var.
    App()._validate_var_dependencies()

    for dep_set in State._var_dependencies.values():
        dep_set.discard((LegacyRouterCompileState.get_full_name(), "foo"))
    State._potentially_dirty_states.discard(LegacyRouterCompileState.get_full_name())


@pytest.mark.asyncio
async def test_get_var_value_of_the_whole_router() -> None:
    """`get_var_value(State.router)` must hand back the composed RouterData.

    The switchboard renders as an object literal over the five per-field vars,
    so it has no field of its own to read. Without naming the `router`
    attribute it stands for, this raised UnretrievableVarValueError, while a
    state with a single `router` base var resolved it.
    """
    state = State(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]

    router = await state.get_var_value(State.router)

    assert isinstance(router, RouterData)
    # The per-field vars resolve too, which the pre-split single var could not do.
    assert await state.get_var_value(State.router.route_id) == router.route_id
    assert (
        await state.get_var_value(State.router.session)
    ).client_token == router.session.client_token


def test_router_var_dep_does_not_warn_for_the_var_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the legacy string form is deprecated, and it must name the var.

    `State.router` carries the per-field names as well as `router` itself, so
    the expansion has nothing to warn about; `deps=["router"]` arrives with
    only `router` and does. The warning has to identify the computed var,
    because the lazy dep scan means the reported caller frame is unrelated to
    the declaration.
    """
    # `console.deprecate` logs and dedupes rather than printing, so record the
    # calls instead of scraping output.
    from reflex import state as state_module

    deprecations: list[str] = []
    monkeypatch.setattr(
        state_module.console,
        "deprecate",
        lambda *, feature_name, **kwargs: deprecations.append(feature_name),
    )

    class VarFormRouterDepState(State):
        """A state depending on the router through the Var."""

        @rx.var(deps=[State.router], auto_deps=False)
        def from_var(self) -> str:
            return ""

    assert deprecations == []

    class StringFormRouterDepState(State):
        """A state depending on the router through the legacy string."""

        @rx.var(deps=["router"], auto_deps=False)
        def from_string(self) -> str:
            return ""

    assert len(deprecations) == 1
    assert "StringFormRouterDepState.from_string" in deprecations[0]

    for dep_set in State._var_dependencies.values():
        dep_set.discard((VarFormRouterDepState.get_full_name(), "from_var"))
        dep_set.discard((StringFormRouterDepState.get_full_name(), "from_string"))
    State._potentially_dirty_states.discard(VarFormRouterDepState.get_full_name())
    State._potentially_dirty_states.discard(StringFormRouterDepState.get_full_name())


def test_router_var_dep_whole_router() -> None:
    """deps=[State.router] must track every per-field router var.

    The switchboard is composed of the five per-field vars, so its VarData
    must carry all five field names; if it reported only one, a cached var
    declaring the whole router would go stale when any other router field
    changed -- a reconnect updates the session without touching the URL, for
    instance.
    """

    class WholeRouterDepState(State):
        """A state depending on the whole router var."""

        @rx.var(deps=[State.router], auto_deps=False)
        def summary(self) -> str:
            return ""

    # The declared set also names `router` itself, the switchboard the five
    # fields were read through; it is expanded away before registration.
    assert WholeRouterDepState.computed_vars["summary"]._static_deps == {
        State.get_full_name(): {constants.ROUTER, *constants.ROUTER_VARS}
    }
    for router_var in constants.ROUTER_VARS:
        assert (
            WholeRouterDepState.get_full_name(),
            "summary",
        ) in State._var_dependencies[router_var]
    # `router` has no backing field, so nothing may be registered against it --
    # it would never be dirtied and the dependent var would go stale.
    assert (
        WholeRouterDepState.get_full_name(),
        "summary",
    ) not in State._var_dependencies.get(constants.ROUTER, set())

    # Drop the class-level registrations; see the note in test_router_var_dep.
    for dep_set in State._var_dependencies.values():
        dep_set.discard((WholeRouterDepState.get_full_name(), "summary"))
    State._potentially_dirty_states.discard(WholeRouterDepState.get_full_name())


def test_router_is_listed_as_a_var_and_inherited_by_substates() -> None:
    """`router` is usable as a Var, so it is listed in vars and inherited.

    It has no backing field of its own, so it must stay out of anything that
    serializes vars: the switchboard resolves to the root state's per-field
    base vars instead.
    """

    class RouterVarListingState(State):
        """A substate that only inherits the router."""

    assert constants.ROUTER in State.vars
    assert constants.ROUTER in RouterVarListingState.vars
    assert constants.ROUTER not in State.base_vars
    assert constants.ROUTER not in State.computed_vars

    # The substate's entry is the root's switchboard, resolving to the root's
    # per-field base vars rather than to anything on the substate.
    router_var = RouterVarListingState.vars[constants.ROUTER]
    assert isinstance(router_var, RouterDataVar)
    assert router_var.equals(State.router)
    assert str(router_var.route_id) == str(State.rx_router_route_id)


def test_update_router_vars_ignores_omitted_static_keys(
    test_state: TestState,
) -> None:
    """A navigation-only payload must not reset the connection-scoped vars.

    A router_data carrying only the navigation keys says nothing about the
    session or headers; treating the omission as a change would wipe them to
    their defaults and ship a destructive delta.

    Args:
        test_state: A state.
    """
    full_router_data = {
        RouteVar.PATH: "/a",
        RouteVar.ORIGIN: "/a",
        RouteVar.QUERY: {},
        RouteVar.CLIENT_TOKEN: "tok",
        RouteVar.SESSION_ID: "sid1",
        RouteVar.CLIENT_IP: "127.0.0.1",
        RouteVar.HEADERS: {"origin": "http://localhost:3000", "cookie": "a=b"},
    }
    test_state._update_router_vars(full_router_data, {})
    test_state._clean()

    navigation_only = {
        RouteVar.PATH: "/b",
        RouteVar.ORIGIN: "/b",
        RouteVar.QUERY: {},
    }
    merged = test_state._update_router_vars(navigation_only, full_router_data)
    assert test_state.dirty_vars & set(constants.ROUTER_VARS) == {
        "rx_router_page",
        "rx_router_url",
        "rx_router_route_id",
    }
    assert test_state.router.session.client_token == "tok"
    assert test_state.router.session.session_id == "sid1"
    assert test_state.router.headers.cookie == "a=b"
    # The rebuilt navigation vars keep the host from the headers the payload
    # omitted, rather than being reconstructed from the partial dict alone.
    assert test_state.router.url.origin == "http://localhost:3000"
    assert test_state.router.url.path == "/b"
    assert test_state.router.page.host == "http://localhost:3000"
    # The merged data is what the caller stores, so the omitted keys are still
    # there to compare against next time.
    assert merged[RouteVar.CLIENT_TOKEN] == "tok"
    assert merged[RouteVar.HEADERS] == full_router_data[RouteVar.HEADERS]

    # A second consecutive partial payload still has the full picture.
    test_state._clean()
    merged2 = test_state._update_router_vars(
        {RouteVar.PATH: "/c", RouteVar.ORIGIN: "/c", RouteVar.QUERY: {}}, merged
    )
    assert test_state.router.url.origin == "http://localhost:3000"
    assert test_state.router.session.client_token == "tok"
    assert merged2[RouteVar.HEADERS] == full_router_data[RouteVar.HEADERS]


def test_update_router_vars_non_origin_header_leaves_navigation_clean(
    test_state: TestState,
) -> None:
    """Only the origin header feeds the page/URL, so other headers leave them alone.

    Args:
        test_state: A state.
    """
    router_data = {
        RouteVar.PATH: "/a",
        RouteVar.ORIGIN: "/a",
        RouteVar.QUERY: {},
        RouteVar.HEADERS: {"origin": "http://localhost:3000", "cookie": "a=b"},
    }
    test_state._update_router_vars(router_data, {})
    test_state._clean()

    new_cookie = {
        **router_data,
        RouteVar.HEADERS: {"origin": "http://localhost:3000", "cookie": "c=d"},
    }
    test_state._update_router_vars(new_cookie, router_data)
    assert test_state.dirty_vars & set(constants.ROUTER_VARS) == {"rx_router_headers"}


def test_update_router_vars_granular_delta(test_state: TestState) -> None:
    """_update_router_vars only dirties the vars whose source keys changed.

    Args:
        test_state: A state.
    """
    full_router_data = {
        RouteVar.PATH: "/a",
        RouteVar.ORIGIN: "/a",
        RouteVar.QUERY: {},
        RouteVar.CLIENT_TOKEN: "tok",
        RouteVar.SESSION_ID: "sid1",
        RouteVar.CLIENT_IP: "127.0.0.1",
        RouteVar.HEADERS: {"origin": "http://localhost:3000"},
    }
    test_state._update_router_vars(full_router_data, {})
    assert set(constants.ROUTER_VARS) <= test_state.dirty_vars
    test_state._clean()

    # Navigation: only the navigation-scoped vars are rebuilt.
    nav_router_data = {**full_router_data, RouteVar.PATH: "/b", RouteVar.ORIGIN: "/b"}
    test_state._update_router_vars(nav_router_data, full_router_data)
    assert test_state.dirty_vars & set(constants.ROUTER_VARS) == {
        "rx_router_page",
        "rx_router_url",
        "rx_router_route_id",
    }
    assert test_state.router.url.path == "/b"
    assert test_state.router.session.session_id == "sid1"
    test_state._clean()

    # Reconnect: only the session var is rebuilt.
    reconnect_router_data = {**nav_router_data, RouteVar.SESSION_ID: "sid2"}
    test_state._update_router_vars(reconnect_router_data, nav_router_data)
    assert test_state.dirty_vars & set(constants.ROUTER_VARS) == {"rx_router_session"}
    assert test_state.router.session.session_id == "sid2"
    test_state._clean()

    # Header change: headers, and the page/URL whose host derives from them.
    # route_id derives from the path alone, so it is left clean.
    new_headers_router_data = {
        **reconnect_router_data,
        RouteVar.HEADERS: {"origin": "http://example.com"},
    }
    test_state._update_router_vars(new_headers_router_data, reconnect_router_data)
    assert test_state.dirty_vars & set(constants.ROUTER_VARS) == {
        "rx_router_headers",
        "rx_router_page",
        "rx_router_url",
    }
    assert test_state.router.url.origin == "http://example.com"
    test_state._clean()

    # Keys that differ but derive the same values leave every var clean: an
    # absent key and an empty one both produce the default, and dirtying on
    # that alone would mark the state touched and persist it.
    equivalent_router_data = {
        k: v for k, v in new_headers_router_data.items() if k != RouteVar.QUERY
    }
    test_state._update_router_vars(equivalent_router_data, new_headers_router_data)
    assert test_state.dirty_vars & set(constants.ROUTER_VARS) == set()


@pytest.mark.asyncio
async def test_setvar(
    state_manager: StateManager,
    token: str,
    mock_base_state_event_processor: BaseStateEventProcessor,
):
    """Test that setvar works correctly.

    Args:
        state_manager: A state manager instance.
        token: A token.
        mock_base_state_event_processor: The event processor.
    """
    # Set Var in same state (with Var type casting)
    events = Event.from_event_type([
        TestState.set_num1(42),
        TestState.set_num2(4.2),
    ])
    async with mock_base_state_event_processor as processor:
        for fut in asyncio.as_completed(await processor.enqueue_many(token, *events)):
            await fut
        await processor.join(1)

    if environment.REFLEX_OPLOCK_ENABLED.get():
        await state_manager.close()

    state = await state_manager.get_state(BaseStateToken(ident=token, cls=TestState))
    assert isinstance(state, TestState)
    assert state.num1 == 42
    assert math.isclose(state.num2, 4.2)

    # Set Var in parent state
    events = Event.from_event_type([GrandchildState.setvar("array", [43])])
    async with mock_base_state_event_processor as processor:
        await (await processor.enqueue(token, events[0]))

    if environment.REFLEX_OPLOCK_ENABLED.get():
        await state_manager.close()

    state = await state_manager.get_state(BaseStateToken(ident=token, cls=TestState))
    assert isinstance(state, TestState)
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
        reflex_base.config.reload_config()

        state_manager = StateManagerRedis(redis=mock_redis())
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
        reflex_base.config.reload_config()

        with pytest.raises(InvalidLockWarningThresholdError):
            StateManagerRedis(redis=mock_redis())
        del sys.modules[constants.Config.MODULE]


def test_state_manager_create_respects_explicit_memory_mode_with_redis_url(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    proj_root = tmp_path / "project1"
    proj_root.mkdir()

    config_string = """
import reflex as rx
config = rx.Config(
    app_name="project1",
)
    """

    (proj_root / "rxconfig.py").write_text(dedent(config_string))
    monkeypatch.setenv("REFLEX_STATE_MANAGER_MODE", "memory")
    monkeypatch.setenv("REFLEX_REDIS_URL", "redis://localhost:6379")

    with chdir(proj_root):
        reflex_base.config.reload_config()
        monkeypatch.setattr(prerequisites, "get_redis", mock_redis)
        state_manager = StateManager.create()
        assert isinstance(state_manager, StateManagerMemory)

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
        reflex_base.config.reload_config()
        from reflex.state import State

        class TestState(State):
            """A test state."""

            num: int = 0

        assert list(TestState.event_handlers) == ["setvar"]


def test_auto_setters_on(tmp_path):
    proj_root = tmp_path / "project1"
    proj_root.mkdir()

    config_string = """
import reflex as rx
config = rx.Config(
    app_name="project1",
    state_auto_setters=True,
)
    """

    (proj_root / "rxconfig.py").write_text(dedent(config_string))

    with chdir(proj_root):
        # reload config for each parameter to avoid stale values
        reflex_base.config.reload_config()
        from reflex.state import State

        class TestState(State):
            """A test state."""

            num: int = 0

        assert "set_num" in TestState.event_handlers
        assert "setvar" in TestState.event_handlers


def test_state_defined_in_rxconfig_does_not_crash(tmp_path):
    """A State subclass defined in rxconfig.py must not crash config loading.

    Regression: _init_var read get_config().state_auto_setters at class-creation
    time, which re-entered config loading while rxconfig was still importing and
    raised AttributeError because the rxconfig module had no `config` attribute
    yet.
    """
    proj_root = tmp_path / "project1"
    proj_root.mkdir()

    config_string = """
import reflex as rx


class RxconfigDefinedState(rx.State):
    n: int = 0


config = rx.Config(
    app_name="project1",
)
"""

    (proj_root / "rxconfig.py").write_text(dedent(config_string))

    with chdir(proj_root):
        # Must not raise (previously raised AttributeError mid-import).
        reflex_base.config.reload_config()
        del sys.modules[constants.Config.MODULE]


def test_state_in_rxconfig_honors_env_auto_setters(tmp_path, monkeypatch):
    """A State defined in rxconfig.py (pre-config) honors REFLEX_STATE_AUTO_SETTERS.

    During rxconfig import the Config does not exist yet, so the cached value is
    unset and get_state_auto_setters falls back to the env var.
    """
    # Simulate a fresh process where no Config has been built yet.
    monkeypatch.setattr(reflex_base.config, "_state_auto_setters", None)
    monkeypatch.setenv("REFLEX_STATE_AUTO_SETTERS", "true")

    proj_root = tmp_path / "project1"
    proj_root.mkdir()
    config_string = """
import reflex as rx


class RxconfigEnvSetterState(rx.State):
    n: int = 0


config = rx.Config(app_name="project1")
"""
    (proj_root / "rxconfig.py").write_text(dedent(config_string))

    with chdir(proj_root):
        reflex_base.config.reload_config()
        state_cls = sys.modules[constants.Config.MODULE].RxconfigEnvSetterState
        assert "set_n" in state_cls.event_handlers
        del sys.modules[constants.Config.MODULE]


def test_state_in_rxconfig_defaults_to_no_auto_setters(tmp_path, monkeypatch):
    """A State defined in rxconfig.py gets no auto-setters by default (pre-config)."""
    monkeypatch.setattr(reflex_base.config, "_state_auto_setters", None)
    monkeypatch.delenv("REFLEX_STATE_AUTO_SETTERS", raising=False)

    proj_root = tmp_path / "project1"
    proj_root.mkdir()
    config_string = """
import reflex as rx


class RxconfigNoSetterState(rx.State):
    n: int = 0


config = rx.Config(app_name="project1")
"""
    (proj_root / "rxconfig.py").write_text(dedent(config_string))

    with chdir(proj_root):
        reflex_base.config.reload_config()
        state_cls = sys.modules[constants.Config.MODULE].RxconfigNoSetterState
        assert list(state_cls.event_handlers) == ["setvar"]
        del sys.modules[constants.Config.MODULE]


def test_state_auto_setters_cache_tracks_reload(tmp_path):
    """The cached state_auto_setters value follows config reloads (no stale flag)."""
    proj_root = tmp_path / "project1"
    proj_root.mkdir()
    rxconfig_path = proj_root / "rxconfig.py"
    off_config = """
import reflex as rx
config = rx.Config(app_name="project1", state_auto_setters=False)
"""
    on_config = """
import reflex as rx
config = rx.Config(app_name="project1", state_auto_setters=True)
"""

    with chdir(proj_root):
        rxconfig_path.write_text(dedent(off_config))
        reflex_base.config.reload_config()
        from reflex.state import State

        class ReloadOffState(State):
            num: int = 0

        assert list(ReloadOffState.event_handlers) == ["setvar"]

        rxconfig_path.write_text(dedent(on_config))
        reflex_base.config.reload_config()

        class ReloadOnState(State):
            num: int = 0

        assert "set_num" in ReloadOnState.event_handlers
        del sys.modules[constants.Config.MODULE]


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
    fields = UsesMixinState.get_fields()
    assert fields["_backend"]._owner is UsesMixinState
    assert fields["_backend_no_default"]._owner is UsesMixinState

    assert "computed" in UsesMixinState.computed_vars
    assert "computed" in UsesMixinState.vars

    state = UsesMixinState(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    assert state._backend == 0
    assert state._backend_no_default == {}
    other = UsesMixinState(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    assert state.get_value("_backend_no_default") is not other.get_value(
        "_backend_no_default"
    )

    assert UsesMixinState.get_parent_state() == State
    assert UsesMixinState.get_root_state() == State


def test_child_mixin_state() -> None:
    """Test that mixin vars are only applied to the highest state in the hierarchy."""
    assert ChildUsesMixinState.get_fields()["num"]._owner is UsesMixinState
    assert "num" in ChildUsesMixinState.vars
    assert "num" not in ChildUsesMixinState.base_vars

    assert "computed" in ChildUsesMixinState.vars
    assert "computed" not in ChildUsesMixinState.computed_vars

    assert ChildUsesMixinState.get_parent_state() == UsesMixinState
    assert ChildUsesMixinState.get_root_state() == State


def test_grandchild_mixin_state() -> None:
    """Test that a mixin can inherit from a concrete state class."""
    assert "num" in GrandchildUsesMixinState.vars
    assert "num" not in GrandchildUsesMixinState.base_vars

    assert "computed" in GrandchildUsesMixinState.vars
    assert "computed" not in GrandchildUsesMixinState.computed_vars

    assert ChildMixinState.get_parent_state() == ChildUsesMixinState
    assert ChildMixinState.get_root_state() == State

    assert GrandchildUsesMixinState.get_parent_state() == ChildUsesMixinState
    assert GrandchildUsesMixinState.get_root_state() == State


def test_bare_mixin_state() -> None:
    """Test that a plain mixin's backend attribute becomes a backend var."""
    assert BareMixinState.get_fields()["_bare_mixin"]._owner is BareMixinState
    assert "_bare_mixin" not in BareMixinState.base_vars

    assert BareMixinState.get_parent_state() == State
    assert BareMixinState.get_root_state() == State

    assert ChildBareMixinState.get_fields()["_bare_mixin"]._owner is BareMixinState
    assert "_bare_mixin" not in ChildBareMixinState.base_vars

    assert ChildBareMixinState.get_parent_state() == BareMixinState
    assert ChildBareMixinState.get_root_state() == State


class MarkerMixin(State, mixin=True):
    """A mixin state with a getter and handler carrying custom function attributes."""

    @rx.var
    def marked_computed(self) -> str:
        """A computed var whose getter is tagged with a custom attribute.

        Returns:
            A static string.
        """
        return "marked"

    marked_computed.fget._custom_marker = object()  # pyright: ignore [reportFunctionMemberAccess]

    def marked_handler(self):
        """An event handler tagged with a custom attribute."""

    marked_handler._custom_marker = object()  # pyright: ignore [reportFunctionMemberAccess]

    def kwonly_default_handler(self, *, count: int = 1) -> int:
        """An event handler with a keyword-only default argument.

        Args:
            count: A keyword-only argument with a default.

        Returns:
            The count.
        """
        return count


class UsesMarkerMixin(MarkerMixin, State):
    """A state that pulls in the marked mixin getter/handler."""


def test_copy_fn_preserves_custom_function_attributes() -> None:
    """Test that _copy_fn preserves arbitrary attributes set on mixin functions."""
    orig_computed_fget = MarkerMixin.__dict__["marked_computed"].fget
    copied_computed_fget = UsesMarkerMixin.computed_vars["marked_computed"].fget
    assert copied_computed_fget is not orig_computed_fget
    assert (
        copied_computed_fget._custom_marker  # pyright: ignore [reportFunctionMemberAccess]
        is orig_computed_fget._custom_marker  # pyright: ignore [reportFunctionMemberAccess]
    )

    orig_handler_fn = MarkerMixin.__dict__["marked_handler"]
    copied_handler_fn = UsesMarkerMixin.event_handlers["marked_handler"].fn
    assert copied_handler_fn is not orig_handler_fn
    assert (
        copied_handler_fn._custom_marker  # pyright: ignore [reportFunctionMemberAccess]
        is orig_handler_fn._custom_marker  # pyright: ignore [reportFunctionMemberAccess]
    )

    # The copy's __dict__ is independent of the source function's __dict__.
    assert copied_handler_fn.__dict__ is not orig_handler_fn.__dict__
    copied_handler_fn.__dict__["_leaked"] = True
    assert "_leaked" not in orig_handler_fn.__dict__


def test_copy_fn_preserves_kwonly_defaults() -> None:
    """Test that _copy_fn preserves keyword-only default arguments."""
    handler_fn = UsesMarkerMixin.event_handlers["kwonly_default_handler"].fn
    assert handler_fn.__kwdefaults__ == {"count": 1}
    instance = UsesMarkerMixin()
    assert handler_fn(instance) == 1


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


def test_mixin_event_handler_preserves_background_task_marker() -> None:
    """Test that the background task marker is preserved when inherited from mixins."""

    class BackgroundTaskMixin(BaseState, mixin=True):
        @rx.event(background=True)
        async def handle_in_background(self):
            pass

    class UsesBackgroundTaskMixin(BackgroundTaskMixin, State):
        pass

    handler = UsesBackgroundTaskMixin.handle_in_background
    assert handler.is_background  # pyright: ignore [reportAttributeAccessIssue]


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


def test_settable_names_are_kept_per_class():
    """The names found settable are kept on each state class, not in a global map."""

    class ParentState(BaseState):
        val: str = ""

    class ChildState(ParentState):
        num: int = 0

    ParentState().val = "set"  # pyright: ignore [reportCallIssue]
    ChildState().num = 1  # pyright: ignore [reportCallIssue]
    parent_names = ParentState.__dict__["_settable_names"]
    child_names = ChildState.__dict__["_settable_names"]
    assert "val" in parent_names
    assert "num" in child_names
    assert "num" not in parent_names


def test_substate_takes_place_of_twin_built_in_its_tree():
    """A substate takes the place of a twin that never held an event context."""

    class TwinRoot(BaseState):
        pass

    class TwinChild(TwinRoot):
        value: int = 0

    name = TwinChild.get_name()
    tree = TwinRoot()  # pyright: ignore [reportCallIssue]
    twin_tree = TwinRoot()  # pyright: ignore [reportCallIssue]
    kept, live = tree.substates[name], twin_tree.substates[name]
    live.value = 3  # pyright: ignore [reportAttributeAccessIssue]

    kept._take_place_of(live)
    assert kept.value == 3  # pyright: ignore [reportAttributeAccessIssue]
    assert kept.parent_state is twin_tree
    assert twin_tree.substates[name] is kept


def test_backend_var_inherits_field_default_and_surfaces_factory_errors():
    """A Field on a plain base supplies its default; a failing factory is not swallowed."""

    class WithDefault:
        _n = field(default=3)

    class InheritsDefault(WithDefault, BaseState):
        _n: int

    assert InheritsDefault()._n == 3  # pyright: ignore [reportCallIssue]

    def _boom() -> int:
        msg = "factory blew up"
        raise ValueError(msg)

    class WithFailingFactory:
        _n = field(default_factory=_boom)

    class FactoryState(WithFailingFactory, BaseState):
        _n: int

    with pytest.raises(ValueError, match="factory blew up"):
        _ = FactoryState()._n  # pyright: ignore [reportCallIssue]


def test_assignment_through_property_setter():
    """A property's setter runs instead of the undeclared-var guard."""

    class PropertyState(BaseState):
        first: str = "Jane"
        last: str = "Doe"

        @property
        def full(self) -> str:
            return f"{self.first} {self.last}"

        @full.setter
        def full(self, value: str) -> None:
            self.first, self.last = value.split(" ", 1)

        @full.deleter
        def full(self) -> None:
            self.first = self.last = ""

    state = PropertyState()  # pyright: ignore [reportCallIssue]
    state.full = "Ada Lovelace"
    assert (state.first, state.last) == ("Ada", "Lovelace")
    del state.full
    assert (state.first, state.last) == ("", "")

    # a read-only property raises its own error, not the undeclared-var guard
    class ReadOnlyState(BaseState):
        @property
        def derived(self) -> str:
            return ""

    with pytest.raises(AttributeError) as exc_info:
        ReadOnlyState().derived = "x"  # pyright: ignore [reportCallIssue, reportAttributeAccessIssue]
    # SetUndefinedStateVarError is itself an AttributeError, so exclude it by type
    assert not isinstance(exc_info.value, SetUndefinedStateVarError)


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

    bs_token = BaseStateToken(ident=token, cls=Root)

    dsm = StateManagerDisk()
    async with dsm.modify_state(bs_token) as root:
        s = await root.get_state(State)
        s.num += 1
        c = await root.get_state(Child)
        assert s._was_touched
        assert not c._was_touched
    await dsm.close()

    dsm2 = StateManagerDisk()
    root = await dsm2.get_state(bs_token)
    s = await root.get_state(State)
    assert s.num == 43
    c = await root.get_state(Child)
    assert c.foo == "bar"
    await dsm2.close()


@pytest.mark.asyncio
async def test_state_manager_disk_close_resets_write_queue_task():
    """Test that closing the disk state manager clears its write queue task."""
    state_manager = StateManagerDisk()
    await state_manager._schedule_process_write_queue()

    assert state_manager._write_queue_task is not None

    await state_manager.close()

    assert state_manager._write_queue_task is None


class Obj(Base):
    """A object containing a callable for testing fallback pickle."""

    f: Callable


# TODO: drop the xfail once the dill release fixing
# https://github.com/uqfoundation/dill/issues/753 lands in uv.lock
@pytest.mark.xfail(
    sys.version_info >= (3, 15),
    reason="dill <= 0.4.1 uses code.co_lnotab, removed in Python 3.15",
    raises=StateSerializationError,
)
def test_fallback_pickle():
    """Test that state serialization will fall back to dill."""

    class DillState(BaseState):
        _o: Obj | None = None
        _f: Callable | None = None
        _g: Any = None

    state = DillState(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    state._o = Obj(f=lambda: 42)
    state._f = lambda: 420

    pk = state._serialize()

    unpickled_state = BaseState._deserialize(pk)
    assert isinstance(unpickled_state, DillState)
    assert unpickled_state._f is not None
    assert unpickled_state._f() == 420
    assert unpickled_state._o is not None
    assert unpickled_state._o.f() == 42

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


class ModelV2(BaseModel):
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

    v2: ModelV2 = ModelV2()
    dc: ModelDC = ModelDC()


def test_mutable_models():
    """Test that dataclass and pydantic BaseModel v1 and v2 use dep tracking."""
    state = PydanticState()

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
@pytest.mark.parametrize(
    ("handler", "payload"),
    [
        (UpcastState.rx_base, {"o": {"foo": "bar"}}),
        (UpcastState.rx_base_or_none, {"o": {"foo": "bar"}}),
        (UpcastState.rx_base_or_none, {"o": None}),
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
async def test_upcast_event_handler_arg(
    handler,
    payload,
    token: str,
    mock_base_state_event_processor: BaseStateEventProcessor,
    emitted_deltas: list,
):
    """Test that upcast event handler args work correctly.

    Args:
        handler: The handler to test.
        payload: The payload to test.
        token: A token.
        mock_base_state_event_processor: The event processor.
        emitted_deltas: List to capture emitted deltas.
    """
    event = Event(
        name=format.format_event_handler(handler),
        payload=payload,
    )
    async with mock_base_state_event_processor as processor:
        await processor.enqueue(token, event)
    assert len(emitted_deltas) == 1
    assert emitted_deltas[0][1] == {
        UpcastState.get_full_name(): {"passed" + FIELD_MARKER: True}
    }


@pytest.mark.asyncio
async def test_get_var_value(
    state_manager: StateManager, substate_token: BaseStateToken
):
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

    # Regression for https://github.com/reflex-dev/reflex/issues/6629: a Var
    # operation / derived var (arithmetic, indexed or item access) must not
    # silently return the value of its first constituent field. Such vars have
    # no retrievable value, so raise instead of returning a plausible-but-wrong one.
    with pytest.raises(UnretrievableVarValueError):
        await state.get_var_value(TestState.num1 + TestState.num2)
    with pytest.raises(UnretrievableVarValueError):
        # array[0] is a Var operation at runtime, though statically typed as the element.
        await state.get_var_value(TestState.array[0])  # pyright: ignore[reportArgumentType]
    with pytest.raises(UnretrievableVarValueError):
        await state.get_var_value(TestState.mapping["a"])

    # Computed vars are derived but state-bound, so they remain resolvable.
    assert await state.get_var_value(TestState.sum) == pytest.approx(42 + 3.15)


@pytest.mark.asyncio
async def test_get_var_value_async_computed_var(
    token: str, attached_mock_event_context: EventContext
):
    """Test that get_var_value awaits async computed vars and returns their value.

    Regression test for https://github.com/reflex-dev/reflex/pull/6391: previously
    get_var_value returned the un-awaited coroutine for async computed vars rather
    than the underlying value.

    Args:
        token: A token.
        attached_mock_event_context: An event context that will be attached to the app's state manager.
    """

    class StateWithAsyncCV(BaseState):
        """A state with an async computed var."""

        base: int = 5

        @rx.var(cache=True)
        async def doubled(self) -> int:
            return self.base * 2

    class Substate(StateWithAsyncCV):
        """A substate to test get_var_value across states."""

    state_manager = attached_mock_event_context.state_manager
    state = await state_manager.get_state(
        BaseStateToken(ident=token, cls=StateWithAsyncCV)
    )

    # Fast path
    assert await state.get_var_value(StateWithAsyncCV.doubled) == 10

    # Slow path
    substate = await state.get_state(Substate)
    assert await substate.get_var_value(StateWithAsyncCV.doubled) == 10


@pytest.mark.asyncio
async def test_async_computed_var_get_state(
    token: str, attached_mock_event_context: EventContext
):
    """A test where an async computed var depends on a var in another state.

    Args:
        token: A token.
        attached_mock_event_context: An event context that will be attached to the app's state manager.
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

    state_manager = attached_mock_event_context.state_manager

    # Get the top level state via unconnected sibling.
    root = await state_manager.get_state(BaseStateToken(ident=token, cls=Child))
    # Set value in parent_var to assert it does not get refetched later.
    root.parent_var = 1

    if isinstance(state_manager, StateManagerRedis):
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

    mock_app._state = rx.State
    comp = Table.create(data=OtherState.data)
    state = await mock_app.state_manager.get_state(
        BaseStateToken(ident=token, cls=OtherState)
    )
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
async def test_add_dependency_get_state_regression(
    token: str, attached_mock_event_context: EventContext, mock_app: rx.App
):
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

    state = await attached_mock_event_context.state_manager.get_state(
        BaseStateToken(ident=token, cls=OtherState)
    )
    other_state = await state.get_state(OtherState)
    await other_state.fetch_data_state()  # Should not raise exception.


def test_override_base_method_skips_event_handler_wrapping():
    """A method marked with __override_base_method__ should not be wrapped as an EventHandler."""
    from reflex.state import _override_base_method

    class OverrideState(rx.State):
        @_override_base_method
        def custom_override(self) -> int:
            return 42

    # The marked method must remain a plain function, not an EventHandler.
    assert not isinstance(OverrideState.__dict__["custom_override"], EventHandler)
    assert "custom_override" not in OverrideState.event_handlers
    assert OverrideState().custom_override() == 42


def test_descriptor_attribute_is_not_a_field():
    """A custom descriptor on a state keeps its own access, and computed vars can depend on it."""

    class _IntDescriptor:
        def __init__(self):
            self._values: dict[int, int] = {}

        def __set_name__(self, owner, name):
            self._name = name

        def __get__(self, instance, owner):
            if instance is None:
                return self
            return self._values.get(id(instance), 0)

        def __set__(self, instance, value):
            self._values[id(instance)] = value

    class DescriptorState(rx.State):
        _desc_value: int = _IntDescriptor()  # pyright: ignore[reportAssignmentType]

        @rx.var
        def doubled(self) -> int:
            return self._desc_value * 2

    assert "_desc_value" not in DescriptorState.get_fields()
    assert "_desc_value" not in DescriptorState.base_vars
    # Descriptor remains the class-level attribute (not overwritten by a field).
    assert isinstance(DescriptorState.__dict__["_desc_value"], _IntDescriptor)
    state = DescriptorState(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    state._desc_value = 3
    assert state.doubled == 6

    # A computed var depending on the descriptor must register the dependency.
    deps = DescriptorState._var_dependencies.get("_desc_value", set())
    assert (DescriptorState.get_full_name(), "doubled") in deps


def test_descriptor_overrides_inherited_descriptor():
    """A child state defining a descriptor with the same name as a parent overrides it."""

    class _Sentinel:
        def __init__(self, label: str):
            self.label = label
            self._values: dict[int, int] = {}

        def __get__(self, instance, owner):
            if instance is None:
                return self
            return self._values.get(id(instance), 0)

        def __set__(self, instance, value):
            self._values[id(instance)] = value

    parent_descriptor = _Sentinel("parent")
    child_descriptor = _Sentinel("child")

    class ParentDescState(rx.State):
        _shared: int = parent_descriptor  # pyright: ignore[reportAssignmentType]

        @rx.var
        def parent_view(self) -> int:
            return self._shared

    class ChildDescState(ParentDescState):
        _shared: int = child_descriptor  # pyright: ignore[reportAssignmentType]

        @rx.var
        def child_view(self) -> int:
            return self._shared * 10

    # The child class's descriptor wins on the class itself.
    assert ChildDescState.__dict__["_shared"] is child_descriptor
    # Child's computed var depends on child's _shared, parent's stays at parent.
    child_deps = ChildDescState._var_dependencies.get("_shared", set())
    parent_deps = ParentDescState._var_dependencies.get("_shared", set())
    assert (ChildDescState.get_full_name(), "child_view") in child_deps
    assert (ParentDescState.get_full_name(), "parent_view") in parent_deps


class OnLoadCancelState(State):
    """A test state whose on_load handler blocks until cancelled."""

    # Signalling gates, populated per-test with loop-local events.
    _gates: ClassVar[dict[str, asyncio.Event]] = {}

    @rx.event
    async def slow_handler(self):
        """Signal start, then block; signal again if cancelled."""
        type(self)._gates["started"].set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            type(self)._gates["cancelled"].set()
            raise


async def test_on_load_internal_supersedes_previous_navigation(
    app_module_mock,
    token,
    mock_root_event_context: EventContext,
    mock_base_state_event_processor: BaseStateEventProcessor,
):
    """A newer navigation cancels the previous unfinished on_load chain (#6593).

    Args:
        app_module_mock: The app module that will be returned by get_app().
        token: A token.
        mock_root_event_context: The mock root event context.
        mock_base_state_event_processor: The event processor.
    """
    assert OnLoadInternalState.event_handlers["on_load_internal"].supersedes
    assert not State.event_handlers["hydrate"].supersedes

    app = app_module_mock.app = App(_state=State)
    app._state_manager = mock_root_event_context.state_manager

    def index():
        return "hello"

    app.add_page(index, on_load=OnLoadCancelState.slow_handler)
    app._compile_page("index")

    OnLoadCancelState._gates = {
        "started": asyncio.Event(),
        "cancelled": asyncio.Event(),
    }
    on_load_internal_name = format.format_event_handler(
        OnLoadInternalState.on_load_internal  # pyright: ignore[reportArgumentType]
    )

    async with mock_base_state_event_processor as processor:
        stale = await processor.enqueue(
            token,
            Event(
                name=on_load_internal_name,
                router_data={
                    RouteVar.PATH: "/",
                    RouteVar.ORIGIN: "/",
                    RouteVar.QUERY: {},
                },
            ),
        )
        await asyncio.wait_for(OnLoadCancelState._gates["started"].wait(), timeout=5)

        # Navigate to a page without on_load events (fast path).
        current = await processor.enqueue(
            token,
            Event(
                name=on_load_internal_name,
                router_data={
                    RouteVar.PATH: "/other",
                    RouteVar.ORIGIN: "/other",
                    RouteVar.QUERY: {},
                },
            ),
        )
        await asyncio.wait_for(OnLoadCancelState._gates["cancelled"].wait(), timeout=5)
        # The fresh navigation completes without waiting behind the stale chain.
        await asyncio.wait_for(current.wait_all(), timeout=5)
        assert stale.done()


_ALIAS_ITEM = TypeVar("_ALIAS_ITEM")
NameAlias = TypeAliasType("NameAlias", str)
KeyAlias = TypeAliasType("KeyAlias", Literal["a", "b"])
ItemsAlias = TypeAliasType("ItemsAlias", list[_ALIAS_ITEM], type_params=(_ALIAS_ITEM,))  # pyright: ignore[reportGeneralTypeIssues]


class AliasAnnotatedState(BaseState):
    """A state with vars annotated through TypeAliasType (PEP 695 aliases)."""

    name: NameAlias = "x"
    key: KeyAlias = "a"
    entries: ItemsAlias[str] = []
    maybe: KeyAlias | None = None

    @rx.event
    def assign(self):
        """Assign a new value to every alias-annotated var."""
        self.name = "y"
        self.key = "b"
        self.entries = ["z"]
        self.maybe = "a"


def test_setattr_alias_annotated_var(mocker: MockerFixture):
    """Assigning alias-annotated state vars via an event handler works.

    The __setattr__ type guard must resolve TypeAliasType annotations and only
    log a mismatch instead of raising TypeError from isinstance().

    Args:
        mocker: Pytest mock fixture.
    """
    error_mock = mocker.patch("reflex_base.vars.base.logger.error")
    state = AliasAnnotatedState(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    state.assign()
    assert state.name == "y"
    assert state.key == "b"
    assert state.entries == ["z"]
    assert state.maybe == "a"
    error_mock.assert_not_called()

    # A mismatched value is logged by the guard, not raised.
    state.key = 1  # pyright: ignore[reportAttributeAccessIssue]
    assert state.key == 1
    error_mock.assert_called_once()


def test_redeclared_var_is_independent_of_the_inherited_one() -> None:
    """A substate redeclaring an inherited var gets its own var, stored on the substate."""

    class ShadowParent(BaseState):
        shadowed_value: int = 1

        def set_value(self):
            self.shadowed_value = 2

    class ShadowChild(ShadowParent):
        shadowed_value: str = "ninety-nine"  # pyright: ignore[reportIncompatibleVariableOverride, reportAssignmentType]

    child_var = cast("Var", ShadowChild.shadowed_value)
    assert child_var._var_type is str
    assert child_var._js_expr != cast("Var", ShadowParent.shadowed_value)._js_expr

    parent = ShadowParent()  # pyright: ignore [reportCallIssue]
    child = cast("ShadowChild", parent.substates[ShadowChild.get_name()])
    # The inherited handler runs on the parent, which declared it.
    child.set_value()
    assert parent.shadowed_value == 2
    assert child.shadowed_value == "ninety-nine"
    child.shadowed_value = "changed"
    assert parent.shadowed_value == 2
    assert parent.get_delta() == {
        ShadowParent.get_full_name(): {"shadowed_value" + FIELD_MARKER: 2},
        ShadowChild.get_full_name(): {"shadowed_value" + FIELD_MARKER: "changed"},
    }


def test_base_var_shadowing_non_state_descriptor_does_not_raise() -> None:
    """Re-annotating to win over a descriptor from a non-state base is not a shadow."""
    from reflex_base.vars.hybrid_property import hybrid_property

    class SharedMixin:
        @hybrid_property
        def descriptor_value(self) -> int:
            return 1

    class PlainBase(SharedMixin):
        pass

    class OverridingState(SharedMixin, BaseState):
        descriptor_value: int = 5  # pyright: ignore[reportIncompatibleVariableOverride, reportAssignmentType]

    class DescriptorChild(PlainBase, OverridingState):
        descriptor_value: int  # pyright: ignore[reportGeneralTypeIssues, reportIncompatibleVariableOverride]

    assert isinstance(DescriptorChild.descriptor_value, Var)


def test_redeclared_var_wins_over_a_closer_descriptor() -> None:
    """A var declared on the class itself wins over any inherited descriptor."""
    from reflex_base.vars.hybrid_property import hybrid_property

    class CloserMixin:
        @hybrid_property
        def outranked_value(self) -> int:
            return 1

    class OutrankedParent(BaseState):
        outranked_value: int = 1  # pyright: ignore[reportIncompatibleVariableOverride, reportAssignmentType]

    class OutrankedChild(CloserMixin, OutrankedParent):
        outranked_value: str = "x"  # pyright: ignore[reportIncompatibleVariableOverride, reportAssignmentType]

    assert OutrankedChild.get_fields()["outranked_value"]._owner is OutrankedChild
    assert cast("Var", OutrankedChild.outranked_value)._var_type is str


def test_base_var_bare_reannotation_does_not_raise() -> None:
    """A bare re-annotation of an inherited var is inert and stays allowed."""

    class ReannotatedParent(BaseState):
        reannotated_value: int = 1

    class ReannotatingChild(ReannotatedParent):
        reannotated_value: int  # pyright: ignore[reportGeneralTypeIssues]

    assert isinstance(ReannotatingChild.reannotated_value, Var)


def test_composite_var_dep_tracks_fields_in_every_state():
    """A dependency on a var spanning two states must track both states' fields.

    `VarData` groups field names by the state that owns them, so merging a var
    built from `StateA.a_field` with one built from `StateB.b_field` keeps
    both. Before that grouping the merge kept only the first state's fields and
    a computed var depending on the composite went stale whenever the other
    state changed.
    """
    from reflex_base.vars.base import Var, VarData

    class _CompositeDepStateA(rx.State):
        a_field: str = "a"

    class _CompositeDepStateB(rx.State):
        b_field: str = "b"

    composite = Var(
        "combo",
        _var_data=VarData.merge(
            cast("Var", _CompositeDepStateA.a_field)._get_all_var_data(),
            cast("Var", _CompositeDepStateB.b_field)._get_all_var_data(),
        ),
    )

    a_name = _CompositeDepStateA.get_full_name()
    b_name = _CompositeDepStateB.get_full_name()
    assert dict(composite._dependency_fields()) == {
        a_name: ("a_field",),
        b_name: ("b_field",),
    }

    class _CompositeDepConsumer(rx.State):
        @rx.var(deps=[composite], cache=True)
        def combined(self) -> str:
            return "x"

    static_deps = _CompositeDepConsumer.__dict__["combined"]._static_deps
    assert "a_field" in static_deps.get(a_name, set())
    assert "b_field" in static_deps.get(b_name, set())

    # The consumer registered itself in both source states' class-level
    # dependency maps, which outlive this test. Left behind, a later test that
    # dirties a_field or b_field resolves the stale entry and raises on the
    # missing substate. Drop them.
    consumer_name = _CompositeDepConsumer.get_full_name()
    for state_cls in (_CompositeDepStateA, _CompositeDepStateB):
        for dep_set in state_cls._var_dependencies.values():
            dep_set.difference_update({(consumer_name, "combined")})
        state_cls._potentially_dirty_states.discard(consumer_name)


def test_setstate_migrates_older_pickles():
    """Older pickles kept backend vars in a dict of their own and the dirty sets."""

    class LegacyPickleState(BaseState):
        count: int = 0
        _secret: str = ""

    class LegacyPickleSubstate(LegacyPickleState):
        pass

    state = LegacyPickleState(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    state.__setstate__({
        "count": 3,
        "_backend_vars": {"_secret": "s"},
        "dirty_vars": {"count"},
        "dirty_substates": set(),
    })

    assert state.count == 3
    assert state._secret == "s"
    assert state.dirty_vars == set()
    assert "_backend_vars" not in state.__dict__

    # Substate pickles carried copies of inherited backend vars; they are dropped.
    substate = LegacyPickleSubstate(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    substate.__setstate__({"_backend_vars": {"_secret": "stale"}, "dirty_vars": set()})
    assert "_secret" not in substate.__dict__
    assert "dirty_vars" not in substate.__dict__


def test_pickle_keeps_generated_defaults():
    """A default from a factory is saved even if the field was never read."""
    import uuid

    class GeneratedDefaultState(BaseState):
        count: int = 0
        session_id: Field[str] = field(default_factory=lambda: uuid.uuid4().hex)
        _token: Field[str] = field(default_factory=lambda: uuid.uuid4().hex)

    state = GeneratedDefaultState(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    state.count = 1
    blob = pickle.dumps(state)
    first, second = pickle.loads(blob), pickle.loads(blob)
    assert first.session_id == second.session_id == state.session_id
    assert first._token == second._token == state._token


def test_bookkeeping_fields_are_not_proxied():
    """A field declared with is_var=False, like router_data, is returned as is."""
    state = BaseState(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    state.router_data = {"headers": {"a": "b"}}
    assert type(state.router_data) is dict
    assert type(state.router_data["headers"]) is dict


def test_handler_held_by_another_class_is_not_bound():
    """An event handler on a class that is not its state stays an EventHandler."""

    class HandlerState(BaseState):
        count: int = 0

        def increment(self):
            self.count += 1

    class Holder:
        on_done = HandlerState.increment

    class OtherHandlerState(BaseState):
        on_done = HandlerState.increment

    assert isinstance(Holder().on_done, EventHandler)
    assert isinstance(
        OtherHandlerState(_reflex_internal_init=True).on_done,  # pyright: ignore [reportCallIssue]
        EventHandler,
    )


def test_substate_on_its_own_holds_inherited_vars():
    """A substate instantiated without its parent stores the vars it inherits."""

    class OrphanParent(BaseState):
        value: int = 1

        def bump(self):
            self.value += 1

    class OrphanChild(OrphanParent):
        pass

    child = OrphanChild(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    assert child.value == 1
    child.bump()
    assert child.value == 2
    assert child.__dict__["value"] == 2


def test_setstate_drops_the_legacy_router_entry():
    """Unpickling a pre-split state must not route `router` through the setter.

    Older pickles stored the whole `RouterData` under `router`, which is now a
    descriptor. Restoring it with `object.__setattr__` would shadow that
    descriptor on the instance; assigning it would decompose into the per-field
    vars and resurrect stale connection data. The schema check in
    `_deserialize` discards such states anyway, so the entry is simply dropped.
    """
    state = BaseState(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    legacy = {
        "parent_state": None,
        "substates": {},
        "router": RouterData.from_router_data({
            constants.RouteVar.CLIENT_TOKEN: "stale-token",
        }),
        "dirty_vars": set(),
    }

    state.__setstate__(legacy)

    # The entry is gone rather than shadowing the descriptor...
    assert "router" not in state.__dict__
    # ...and `router` still resolves through the switchboard to live fields.
    assert state.router.session.client_token == ""


def test_previous_release_pickle_keys_are_reserved():
    """A field cannot take the name older pickles kept the backend vars under."""
    with pytest.raises(StateValueError, match="_backend_vars"):

        class ClashingState(BaseState):
            _backend_vars: dict = {}  # pyright: ignore[reportIncompatibleVariableOverride]
