"""Tests for reflex_base.state.proxy."""

import asyncio
import dataclasses
import pickle
import subprocess
import sys
from asyncio import CancelledError
from collections.abc import Mapping
from contextlib import asynccontextmanager
from operator import attrgetter
from typing import Any, ClassVar, TypeVar

import pytest
from reflex_base.constants.state import FIELD_MARKER
from reflex_base.event.context import EventContext
from reflex_base.state.proxy import MutableProxy
from reflex_base.state.token import BaseStateToken
from reflex_base.utils.exceptions import ImmutableStateError
from reflex_base.utils.types import is_mutable_type

import reflex as rx
from reflex.istate.data import HeaderData, PageData, RouterData
from reflex.istate.manager import StateManager
from reflex.state import BaseState

T_STATE = TypeVar("T_STATE", bound=BaseState)


def _detached_state(state: T_STATE, ctx: EventContext) -> T_STATE:
    """Bind a state's root to an event context without holding its lock.

    Simulates the state instance a background task receives: the event that
    loaded it already released the lock, so the state stays read-only until
    something enters it with `async with`.

    Args:
        state: The state instance to bind.
        ctx: The event context to bind the state's root to.

    Returns:
        The same state instance, for chaining.
    """
    state._get_root_state()._event_context = ctx
    return state


def test_proxy_does_not_import_sqlalchemy() -> None:
    """State mutation tracking must not load an unused database integration."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from reflex_base.state.proxy import is_mutable_type

assert is_mutable_type(list)
assert not is_mutable_type(str)
assert "sqlalchemy" not in sys.modules
""",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("models_first", [False, True])
def test_mutable_models_with_either_import_order(models_first: bool) -> None:
    """Model classification works before or after importing state tracking."""
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("sqlmodel")
    script = """
from pydantic import BaseModel
from pydantic.v1 import BaseModel as LegacyPydanticBase
from sqlalchemy.orm import DeclarativeBase, DeclarativeBaseNoMeta, declarative_base
from sqlmodel import SQLModel
"""
    proxy_import = "from reflex_base.state import proxy\n"
    script = script + proxy_import if models_first else proxy_import + script
    script += """
class DatabaseBase(DeclarativeBase):
    pass

class PydanticModel(BaseModel):
    value: int = 1

class SQLModelSubclass(SQLModel):
    value: int = 1

for cls in (DeclarativeBase, DatabaseBase, BaseModel, PydanticModel, SQLModel, SQLModelSubclass):
    assert proxy.is_mutable_type(cls), cls
    assert proxy.is_mutable_type(cls), cls  # Exercise the cached result too.

for cls in (LegacyPydanticBase, DeclarativeBaseNoMeta, declarative_base()):
    assert not proxy.is_mutable_type(cls), cls

Impostor = type("DeclarativeBase", (), {"__module__": "sqlalchemy.orm.decl_api"})
assert not proxy.is_mutable_type(Impostor)
assert proxy.MUTABLE_TYPES == (list, dict, set, DeclarativeBase, BaseModel)
assert "MUTABLE_TYPES" not in dir(proxy)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("type_", "expected"),
    [
        (list, True),
        (dict, True),
        (set, True),
        (type("ListSubclass", (list,), {}), True),
        (type("DictSubclass", (dict,), {}), True),
        (type("SetSubclass", (set,), {}), True),
        (dataclasses.make_dataclass("Data", []), True),
        (dataclasses.make_dataclass("FrozenData", [], frozen=True), True),
        (rx.Var, False),
        (int, False),
        (str, False),
        (tuple, False),
        (frozenset, False),
        (object, False),
    ],
)
def test_is_mutable_type(type_: type, expected: bool) -> None:
    """Keep the existing container, dataclass, and Var classification rules."""
    assert is_mutable_type(type_) is expected


@dataclasses.dataclass
class Item:
    """Simple picklable object for testing."""

    id: int


class ProxyTestState(rx.State):
    """Test state with a list field."""

    items: list[Item] = []


def test_mutable_proxy_pickle_preserves_object_identity():
    """Test that same object referenced directly and via proxy maintains identity."""
    state = ProxyTestState()
    obj = Item(1)

    data = {
        "direct": [obj],
        "proxied": [MutableProxy(obj, state, "items")],
    }

    unpickled = pickle.loads(pickle.dumps(data))

    assert unpickled["direct"][0].id == 1
    assert unpickled["proxied"][0].id == 1
    assert unpickled["direct"][0] is unpickled["proxied"][0]


@pytest.mark.asyncio
async def test_state_context_recovery(
    attached_mock_event_context: EventContext, monkeypatch: pytest.MonkeyPatch
):
    """Ensure that `async with self` can be re-entered after a lock issue."""
    state = _detached_state(ProxyTestState(), attached_mock_event_context)

    with monkeypatch.context() as m:

        @asynccontextmanager
        async def mock_modify_state_context(*args, **kwargs):
            msg = "Simulated lock issue"
            raise CancelledError(msg)
            yield

        m.setattr(
            attached_mock_event_context.state_manager,
            "modify_state",
            mock_modify_state_context,
        )

        with pytest.raises(CancelledError, match="Simulated lock issue"):
            async with state:
                pass

    # After the exception, we should be able to enter the context again without issues
    async with state:
        pass


@dataclasses.dataclass
class TaggedModel:
    """A dataclass with a mutable attribute for attr-path refresh tests."""

    ls: list[dict] = dataclasses.field(default_factory=list)


class MutableProxyState(BaseState):
    """A test state with a MutableProxy var."""

    data: dict[str, list[int]] = {"a": [1], "b": [2]}


class NestedMutableProxyState(BaseState):
    """A test state with nested mutable dict values."""

    data: dict[str, dict[str, int]] = {"a": {"x": 1}, "b": {"y": 2}}


class IterableMutableProxyState(BaseState):
    """A test state with mutable values that can be accessed by iteration."""

    data: list[list[int]] = [[1]]


class DataclassMutableProxyState(BaseState):
    """A test state with a dataclass field holding a mutable attribute."""

    dc: TaggedModel = TaggedModel(ls=[{"tag": 1}])


class RouterProxyState(BaseState):
    """A root state for testing the composed router through bound states."""


class RouterProxySubState(RouterProxyState):
    """A substate inheriting its router fields from the root state."""


@pytest.mark.parametrize("state_cls", [RouterProxyState, RouterProxySubState])
@pytest.mark.parametrize(
    "path",
    [
        "rx_router_page.params",
        "router._page.params",
        "router.page.params",
        "rx_router_headers.raw_headers",
        "router.headers.raw_headers",
    ],
)
def test_router_proxy_rejects_mutation(
    attached_mock_event_context: EventContext,
    state_cls: type[BaseState],
    path: str,
) -> None:
    """Router containers stay read-only on a bound but unlocked state.

    Args:
        attached_mock_event_context: The attached event context.
        state_cls: The root or substate to bind.
        path: The access path to a router container.
    """
    root = RouterProxyState()
    root.router = RouterData(
        _page=PageData(params={"x": "before", "parts": ["before"]}),
        headers=HeaderData(raw_headers={"x": "before"}),
    )
    root._clean()
    state = _detached_state(
        root.get_substate(state_cls.get_full_name().split(".")),
        attached_mock_event_context,
    )
    container = attrgetter(path)(state)

    with pytest.raises(ImmutableStateError):
        container["x"] = "after"
    with pytest.raises(ImmutableStateError):
        container.update(x="after")
    with pytest.raises(ImmutableStateError):
        del container["x"]
    if path.endswith("params"):
        with pytest.raises(ImmutableStateError):
            container["parts"].append("after")

    assert root.router._page.params == {"x": "before", "parts": ["before"]}
    assert root.router.headers.raw_headers == {"x": "before"}
    assert not root.dirty_vars


@pytest.mark.asyncio
@pytest.mark.parametrize("state_cls", [RouterProxyState, RouterProxySubState])
async def test_router_proxy_mutable_context(
    token: str,
    state_manager: StateManager,
    attached_mock_event_context: EventContext,
    emitted_deltas: list[tuple[str, Mapping[str, Mapping[str, Any]]]],
    state_cls: type[BaseState],
) -> None:
    """Router writes require the entering state's lock and dirty the backing field.

    Args:
        token: The client token.
        state_manager: The state manager to exercise.
        attached_mock_event_context: The attached event context.
        emitted_deltas: The captured state updates.
        state_cls: The root or substate to bind.
    """
    state_token = BaseStateToken(ident=token, cls=state_cls)
    async with state_manager.modify_state(state_token) as root:
        root.router = RouterData(_page=PageData(params={"x": "before"}))
        root._clean()
        state = _detached_state(
            root.get_substate(state_cls.get_full_name().split(".")),
            attached_mock_event_context,
        )

    async with state:
        router = state.router
        router._page.params["x"] = "after"
        assert state._get_root_state().dirty_vars == {"rx_router_page"}

    with pytest.raises(ImmutableStateError):
        router._page.params["x"] = "unlocked write"

    assert emitted_deltas == [
        (
            token,
            {
                RouterProxyState.get_full_name(): {
                    "rx_router_page" + FIELD_MARKER: PageData(params={"x": "after"}),
                },
            },
        ),
    ]
    async with state_manager.modify_state(state_token) as root:
        assert root.router._page.params == {"x": "after"}


class InheritedListState(BaseState):
    """A root state storing a list var its substate inherits."""

    items: list[int] = []

    @rx.event
    def add_item(self, value: int):
        """Append to the list.

        Args:
            value: The value to append.
        """
        self.items.append(value)


class InheritedListSubState(InheritedListState):
    """A substate changing the inherited list from a background task."""


class RedeclaringState(BaseState):
    """A root state whose handler writes a var its substate redeclares."""

    count: int = 0

    @rx.event
    def bump(self):
        """Increment the count."""
        self.count += 1


class RedeclaringSubState(RedeclaringState):
    """A substate with a count of its own."""

    count: int = 10


@pytest.mark.asyncio
async def test_inherited_mutable_var_marks_its_owner(
    token: str,
    state_manager: StateManager,
    attached_mock_event_context: EventContext,
    emitted_deltas: list[tuple[str, Mapping[str, Mapping[str, Any]]]],
) -> None:
    """An in-place change to an inherited var from a background task dirties the state storing it.

    Args:
        token: The client token.
        state_manager: The state manager to exercise.
        attached_mock_event_context: The attached event context.
        emitted_deltas: The captured state updates.
    """
    state_token = BaseStateToken(ident=token, cls=InheritedListSubState)
    async with state_manager.modify_state(state_token) as root:
        state = _detached_state(
            root.get_substate(InheritedListSubState.get_full_name().split(".")),
            attached_mock_event_context,
        )

    with pytest.raises(ImmutableStateError):
        state.items.append(0)  # pyright: ignore [reportAttributeAccessIssue]
    async with state:
        state.items.append(1)  # pyright: ignore [reportAttributeAccessIssue]

    assert emitted_deltas == [
        (token, {InheritedListState.get_full_name(): {"items" + FIELD_MARKER: [1]}}),
    ]
    async with state_manager.modify_state(state_token) as root:
        assert root.items == [1]  # pyright: ignore [reportAttributeAccessIssue]


@pytest.mark.asyncio
async def test_failed_reload_releases_the_lock(
    token: str,
    state_manager: StateManager,
    attached_mock_event_context: EventContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Entering a state releases the lock it took when reloading the state fails.

    Args:
        token: The client token.
        state_manager: The state manager to exercise.
        attached_mock_event_context: The attached event context.
        monkeypatch: The pytest monkeypatch fixture.
    """
    state_token = BaseStateToken(
        ident=attached_mock_event_context.token, cls=InheritedListSubState
    )
    async with attached_mock_event_context.state_manager.modify_state(
        state_token
    ) as root:
        state = _detached_state(
            root.get_substate(InheritedListSubState.get_full_name().split(".")),
            attached_mock_event_context,
        )

    def fail_to_load(self, state_cls):
        raise RuntimeError

    monkeypatch.setattr(BaseState, "get_state", fail_to_load)
    with pytest.raises(RuntimeError):
        async with state:
            pass
    monkeypatch.undo()

    ctx = attached_mock_event_context
    assert not ctx.state_locks.held

    async def reacquire():
        async with ctx.state_manager.modify_state(state_token):
            pass

    await asyncio.wait_for(reacquire(), 5)


@pytest.mark.asyncio
async def test_nested_entry_that_took_the_lock_raises(
    token: str,
    state_manager: StateManager,
    attached_mock_event_context: EventContext,
) -> None:
    """Entering a state again inside the `async with` that locked it raises.

    Args:
        token: The client token.
        state_manager: The state manager to exercise.
        attached_mock_event_context: The attached event context.
    """
    state_token = BaseStateToken(ident=token, cls=InheritedListSubState)
    async with state_manager.modify_state(state_token) as root:
        state = _detached_state(
            root.get_substate(InheritedListSubState.get_full_name().split(".")),
            attached_mock_event_context,
        )

    async with state:
        with pytest.raises(ImmutableStateError, match="Do not nest"):
            async with state:
                pass
        state.add_item(1)  # pyright: ignore [reportAttributeAccessIssue]


@pytest.mark.asyncio
async def test_inherited_handler_runs_on_its_state(
    token: str,
    state_manager: StateManager,
    attached_mock_event_context: EventContext,
) -> None:
    """An inherited event handler writes the vars of the state declaring it.

    Args:
        token: The client token.
        state_manager: The state manager to exercise.
        attached_mock_event_context: The attached event context.
    """
    state_token = BaseStateToken(ident=token, cls=RedeclaringSubState)
    async with state_manager.modify_state(state_token) as root:
        state = _detached_state(
            root.get_substate(RedeclaringSubState.get_full_name().split(".")),
            attached_mock_event_context,
        )

    async with state:
        state.bump()  # pyright: ignore [reportAttributeAccessIssue]
    # A handler taken before entering runs on the state reloaded by entering.
    bump = state.bump  # pyright: ignore [reportAttributeAccessIssue]
    async with state:
        bump()
    async with state_manager.modify_state(state_token) as root:
        assert root.count == 2  # pyright: ignore [reportAttributeAccessIssue]
        substate = root.get_substate(RedeclaringSubState.get_full_name().split("."))
        assert substate.count == 10  # pyright: ignore [reportAttributeAccessIssue]


@pytest.mark.asyncio
async def test_inherited_handler_is_guarded(
    token: str,
    state_manager: StateManager,
    attached_mock_event_context: EventContext,
) -> None:
    """An inherited event handler writes only while the state's lock is held.

    Args:
        token: The client token.
        state_manager: The state manager to exercise.
        attached_mock_event_context: The attached event context.
    """
    state_token = BaseStateToken(ident=token, cls=InheritedListSubState)
    async with state_manager.modify_state(state_token) as root:
        state = _detached_state(
            root.get_substate(InheritedListSubState.get_full_name().split(".")),
            attached_mock_event_context,
        )

    with pytest.raises(ImmutableStateError):
        state.add_item(0)  # pyright: ignore [reportAttributeAccessIssue]
    async with state:
        state.add_item(1)  # pyright: ignore [reportAttributeAccessIssue]
    async with state_manager.modify_state(state_token) as root:
        assert root.items == [1]  # pyright: ignore [reportAttributeAccessIssue]


@pytest.mark.asyncio
@pytest.mark.parametrize("state_cls", [RouterProxyState, RouterProxySubState])
async def test_router_proxy_nested_context(
    token: str,
    state_manager: StateManager,
    attached_mock_event_context: EventContext,
    state_cls: type[BaseState],
) -> None:
    """Nested router contexts refresh the backing field once the owning state is entered.

    Args:
        token: The client token.
        state_manager: The state manager to exercise.
        attached_mock_event_context: The attached event context.
        state_cls: The root or substate to bind.
    """
    state_token = BaseStateToken(ident=token, cls=state_cls)
    async with state_manager.modify_state(state_token) as root:
        root.router = RouterData(_page=PageData(params={"x": "before"}))
        state = _detached_state(
            root.get_substate(state_cls.get_full_name().split(".")),
            attached_mock_event_context,
        )
        params = state.router._page.params

    async with attached_mock_event_context.modify_state(state_token) as root:
        root.router = RouterData(_page=PageData(params={"x": "refreshed"}))

    with pytest.raises(ImmutableStateError):
        params["x"] = "unlocked write"

    async with params:  # pyright: ignore [reportGeneralTypeIssues]
        assert params["x"] == "refreshed"
        params["x"] = "after"

    with pytest.raises(ImmutableStateError):
        params["x"] = "unlocked write"

    async with state_manager.modify_state(state_token) as root:
        assert root.router._page.params["x"] == "after"


@pytest.mark.asyncio
async def test_rebind_mutable_proxy(
    token: str, attached_mock_event_context: EventContext
) -> None:
    """A MutableProxy tracks the state instance it was read from, and requires its lock."""
    state_manager = attached_mock_event_context.state_manager
    state_token = BaseStateToken(ident=token, cls=MutableProxyState)

    async with state_manager.modify_state(state_token) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        assert isinstance(state, MutableProxyState)
        assert isinstance(state.data, MutableProxy)
        # This assigns a MutableProxy to data["a"].
        state.data["a"] = state.data["b"]
        assert isinstance(state.data["a"], MutableProxy)
        assert state.data["a"] is not state.data["b"]
        assert (
            state.data["a"].__wrapped__  # pyright: ignore [reportAttributeAccessIssue]
            is state.data["b"].__wrapped__  # pyright: ignore [reportAttributeAccessIssue]
        )
        assert state.data["a"]._self_state is state  # pyright: ignore [reportAttributeAccessIssue]

    state = _detached_state(state, attached_mock_event_context)
    with pytest.raises(ImmutableStateError):
        state.data["a"].append(3)

    async with state:
        state.data["a"].append(3)

    async with state_manager.modify_state(state_token) as final_state:
        assert isinstance(final_state, MutableProxyState)
        assert final_state.data["a"] == [2, 3]
        # Object identity persists across serialization, so data["b"] is also mutated.
        assert final_state.data["b"] == [2, 3]


@pytest.mark.asyncio
async def test_mutable_proxy_async_context_manager(
    token: str, attached_mock_event_context: EventContext
) -> None:
    """Mutable proxies can enter the owning state's context to become writable."""
    state_manager = attached_mock_event_context.state_manager
    state_token = BaseStateToken(ident=token, cls=MutableProxyState)

    async with state_manager.modify_state(state_token) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        assert isinstance(state, MutableProxyState)
        state = _detached_state(state, attached_mock_event_context)
        data_proxy = state.data
        items_proxy = data_proxy["a"]

    assert isinstance(data_proxy, MutableProxy)
    assert isinstance(items_proxy, MutableProxy)
    # __aexit__ without a prior __aenter__ is a no-op.
    await data_proxy.__aexit__(None, None, None)
    with pytest.raises(ImmutableStateError):
        data_proxy["a"].append(3)
    with pytest.raises(ImmutableStateError):
        items_proxy.append(3)

    async with attached_mock_event_context.modify_state(
        state_token
    ) as concurrent_state:
        assert isinstance(concurrent_state, MutableProxyState)
        concurrent_state.data["a"].append(2)

    async with data_proxy as mutable_data:
        assert mutable_data is data_proxy
        with pytest.raises(RuntimeError, match="already in an async context"):
            async with data_proxy:
                pass
        data_proxy["a"].append(3)
        mutable_data["b"].append(4)

    async with items_proxy as mutable_items:
        assert mutable_items is items_proxy
        mutable_items.append(5)
        assert items_proxy.__wrapped__ == [1, 2, 3, 5]

    with pytest.raises(ImmutableStateError):
        data_proxy["a"].append(6)
    with pytest.raises(ImmutableStateError):
        items_proxy.append(6)

    async with state_manager.modify_state(state_token) as final_state:
        assert isinstance(final_state, MutableProxyState)
        assert final_state.data["a"] == [1, 2, 3, 5]
        assert final_state.data["b"] == [2, 4]


@pytest.mark.asyncio
async def test_immutable_mutable_proxy_async_context_dict_method_paths(
    token: str, attached_mock_event_context: EventContext
) -> None:
    """Dict method proxies refresh to the returned item, not the parent dict."""
    state_manager = attached_mock_event_context.state_manager
    state_token = BaseStateToken(ident=token, cls=NestedMutableProxyState)

    async with state_manager.modify_state(state_token) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        assert isinstance(state, NestedMutableProxyState)
        state = _detached_state(state, attached_mock_event_context)
        existing_proxy = state.data.get("a")
        default_proxy = state.data.get("missing", {"fallback": 4})

    async with state:
        new_proxy = state.data.setdefault("c", {"z": 3})

    assert isinstance(existing_proxy, MutableProxy)
    assert isinstance(new_proxy, MutableProxy)
    assert isinstance(default_proxy, MutableProxy)

    async with existing_proxy as mutable_existing:
        mutable_existing["x"] = 10

    async with new_proxy as mutable_new:
        mutable_new["z"] = 30

    with pytest.raises(RuntimeError, match="Unable to refresh mutable proxy"):
        async with default_proxy:
            pass

    async with state_manager.modify_state(state_token) as final_state:
        assert isinstance(final_state, NestedMutableProxyState)
        assert final_state.data == {
            "a": {"x": 10},
            "b": {"y": 2},
            "c": {"z": 30},
        }


@pytest.mark.asyncio
async def test_immutable_mutable_proxy_async_context_rejects_iter_proxy(
    token: str, attached_mock_event_context: EventContext
) -> None:
    """Iteration-sourced mutable proxies fail clearly as async context managers."""
    state_manager = attached_mock_event_context.state_manager
    state_token = BaseStateToken(ident=token, cls=IterableMutableProxyState)

    async with state_manager.modify_state(state_token) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        assert isinstance(state, IterableMutableProxyState)
        state = _detached_state(state, attached_mock_event_context)
        [items_proxy] = state.data

    assert isinstance(items_proxy, MutableProxy)
    with pytest.raises(RuntimeError, match="Unable to refresh mutable proxy"):
        async with items_proxy:
            pass

    async with state:
        state.data[0].append(2)

    async with state_manager.modify_state(state_token) as final_state:
        assert isinstance(final_state, IterableMutableProxyState)
        assert final_state.data == [[1, 2]]


@pytest.mark.asyncio
async def test_immutable_mutable_proxy_async_context_rejects_list_derived_proxies(
    token: str, attached_mock_event_context: EventContext
) -> None:
    """List-derived proxies cannot safely refresh after structural changes."""
    state_manager = attached_mock_event_context.state_manager
    state_token = BaseStateToken(ident=token, cls=IterableMutableProxyState)

    async with state_manager.modify_state(state_token) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        assert isinstance(state, IterableMutableProxyState)
        state = _detached_state(state, attached_mock_event_context)
        items_proxy = state.data[0]
        [sliced_items_proxy] = state.data[:1]

    async with attached_mock_event_context.modify_state(
        state_token
    ) as concurrent_state:
        assert isinstance(concurrent_state, IterableMutableProxyState)
        concurrent_state.data.insert(0, [0])

    for proxy in (items_proxy, sliced_items_proxy):
        with pytest.raises(RuntimeError, match="Unable to refresh mutable proxy"):
            async with proxy:  # pyright: ignore [reportGeneralTypeIssues]
                pass

    async with state_manager.modify_state(state_token) as final_state:
        assert isinstance(final_state, IterableMutableProxyState)
        assert final_state.data == [[0], [1]]


@pytest.mark.asyncio
async def test_immutable_mutable_proxy_async_context_missing_key(
    token: str, attached_mock_event_context: EventContext
) -> None:
    """A path whose key was deleted raises the refresh error, not KeyError."""
    state_manager = attached_mock_event_context.state_manager
    state_token = BaseStateToken(ident=token, cls=MutableProxyState)

    async with state_manager.modify_state(state_token) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        assert isinstance(state, MutableProxyState)
        state = _detached_state(state, attached_mock_event_context)
        items_proxy = state.data["a"]

    async with attached_mock_event_context.modify_state(
        state_token
    ) as concurrent_state:
        assert isinstance(concurrent_state, MutableProxyState)
        del concurrent_state.data["a"]

    with pytest.raises(RuntimeError, match="Unable to refresh mutable proxy"):
        async with items_proxy:  # pyright: ignore [reportGeneralTypeIssues]
            pass

    assert items_proxy._self_actx_state is None  # pyright: ignore [reportAttributeAccessIssue]


@pytest.mark.asyncio
async def test_immutable_mutable_proxy_async_context_attr_path(
    token: str, attached_mock_event_context: EventContext
) -> None:
    """Proxies reached through attribute access refresh via the attr path."""
    state_manager = attached_mock_event_context.state_manager
    state_token = BaseStateToken(ident=token, cls=DataclassMutableProxyState)

    async with state_manager.modify_state(state_token) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        assert isinstance(state, DataclassMutableProxyState)
        state = _detached_state(state, attached_mock_event_context)
        ls_proxy = state.dc.ls

    assert isinstance(ls_proxy, MutableProxy)
    async with ls_proxy as mutable_ls:
        assert mutable_ls is ls_proxy
        mutable_ls.append({"tag": 2})

    async with state_manager.modify_state(state_token) as final_state:
        assert isinstance(final_state, DataclassMutableProxyState)
        assert final_state.dc.ls == [{"tag": 1}, {"tag": 2}]


@pytest.mark.asyncio
async def test_mutable_proxy_async_context_plain_state() -> None:
    """A MutableProxy bound to a plain state enters as a no-op refresh."""
    state = MutableProxyState()
    data_proxy = state.data
    assert isinstance(data_proxy, MutableProxy)

    async with data_proxy as mutable_data:
        assert mutable_data is data_proxy
        mutable_data["a"].append(2)

    assert state.data["a"] == [1, 2]
    assert "data" in state.dirty_vars


@pytest.mark.asyncio
async def test_immutable_mutable_proxy_async_context_recovers_from_enter_failure(
    token: str,
    attached_mock_event_context: EventContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed owning-state enter does not permanently block the proxy."""
    state_manager = attached_mock_event_context.state_manager
    state_token = BaseStateToken(ident=token, cls=MutableProxyState)

    async with state_manager.modify_state(state_token) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        assert isinstance(state, MutableProxyState)
        state = _detached_state(state, attached_mock_event_context)
        data_proxy = state.data

    original_aenter = BaseState.__aenter__
    fail_once = True

    async def fail_first_enter(self: BaseState) -> BaseState:
        nonlocal fail_once
        if fail_once:
            fail_once = False
            raise asyncio.CancelledError
        return await original_aenter(self)

    monkeypatch.setattr(BaseState, "__aenter__", fail_first_enter)

    assert isinstance(data_proxy, MutableProxy)
    with pytest.raises(asyncio.CancelledError):
        async with data_proxy:
            pass

    assert data_proxy._self_actx_state is None
    async with data_proxy as mutable_data:
        mutable_data["a"].append(2)

    async with state_manager.modify_state(state_token) as final_state:
        assert isinstance(final_state, MutableProxyState)
        assert final_state.data["a"] == [1, 2]


@pytest.mark.asyncio
async def test_immutable_mutable_proxy_async_context_clears_state_when_cleanup_fails(
    token: str,
    attached_mock_event_context: EventContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed cleanup while entering does not leave the proxy marked mutable."""
    state_manager = attached_mock_event_context.state_manager
    state_token = BaseStateToken(ident=token, cls=IterableMutableProxyState)

    async with state_manager.modify_state(state_token) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        assert isinstance(state, IterableMutableProxyState)
        state = _detached_state(state, attached_mock_event_context)
        data_proxy = state.data

    original_aenter = BaseState.__aenter__

    async def unrefreshable_enter(self: BaseState) -> BaseState:
        """Enter normally, then make the target state's `data` field unrefreshable.

        Returns:
            The entered state.
        """
        entered = await original_aenter(self)
        if self is state:
            vars(entered)["data"] = 0
        return entered

    original_aexit = BaseState.__aexit__

    async def fail_exit(self: BaseState, *exc_info: Any) -> None:
        # Release the lock taken on entering, then fail.
        await original_aexit(self, *exc_info)
        msg = "cleanup failed"
        raise RuntimeError(msg)

    monkeypatch.setattr(BaseState, "__aenter__", unrefreshable_enter)
    monkeypatch.setattr(BaseState, "__aexit__", fail_exit)

    assert isinstance(data_proxy, MutableProxy)
    with pytest.raises(RuntimeError, match="cleanup failed"):
        async with data_proxy:
            pass

    assert data_proxy._self_actx_state is None


@pytest.mark.asyncio
async def test_immutable_mutable_proxy_async_context_cleans_up_base_exception(
    token: str,
    attached_mock_event_context: EventContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A BaseException during refresh releases the owning state context."""

    class FatalRefreshError(BaseException):
        """An error outside the Exception hierarchy."""

    state_manager = attached_mock_event_context.state_manager
    state_token = BaseStateToken(ident=token, cls=IterableMutableProxyState)

    async with state_manager.modify_state(state_token) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        assert isinstance(state, IterableMutableProxyState)
        state = _detached_state(state, attached_mock_event_context)
        data_proxy = state.data

    original_getattribute = IterableMutableProxyState.__getattribute__

    def raise_fatal_refresh_error(self: IterableMutableProxyState, name: str) -> Any:
        """Raise while reading the refreshed `data` field of the target state.

        Returns:
            The attribute value for all other reads.
        """
        if name == "data" and self is state:
            raise FatalRefreshError
        return original_getattribute(self, name)

    monkeypatch.setattr(
        IterableMutableProxyState, "__getattribute__", raise_fatal_refresh_error
    )

    assert isinstance(data_proxy, MutableProxy)
    with pytest.raises(FatalRefreshError):
        async with data_proxy:
            pass

    assert data_proxy._self_actx_state is None


@pytest.mark.asyncio
async def test_state_field_writable_after_entering(
    token: str, attached_mock_event_context: EventContext
) -> None:
    """A mutable field of a bound-but-unlocked state becomes writable once entered."""
    state_manager = attached_mock_event_context.state_manager
    state_token = BaseStateToken(ident=token, cls=MutableProxyState)

    async with state_manager.modify_state(state_token) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        assert isinstance(state, MutableProxyState)
        state = _detached_state(state, attached_mock_event_context)
        data_proxy = state.data

    assert isinstance(data_proxy, MutableProxy)
    with pytest.raises(ImmutableStateError):
        data_proxy["a"].append(3)

    async with data_proxy:
        data_proxy["a"].append(3)

    async with state_manager.modify_state(state_token) as final_state:
        assert isinstance(final_state, MutableProxyState)
        assert final_state.data["a"] == [1, 3]


@dataclasses.dataclass
class SuccessData:
    """A dataclass variant for union-typed field refresh tests."""

    values: list[int] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class ErrorData:
    """A different dataclass variant for union-typed field refresh tests."""

    messages: list[str] = dataclasses.field(default_factory=list)


class UnionDataclassState(BaseState):
    """A test state with a union-typed dataclass field."""

    result: SuccessData | ErrorData = SuccessData(values=[1])


@pytest.mark.asyncio
async def test_immutable_mutable_proxy_async_context_rejects_type_change(
    token: str, attached_mock_event_context: EventContext
) -> None:
    """Refreshing a dataclass proxy to a different wrapped type fails loudly."""
    state_manager = attached_mock_event_context.state_manager
    state_token = BaseStateToken(ident=token, cls=UnionDataclassState)

    async with state_manager.modify_state(state_token) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        assert isinstance(state, UnionDataclassState)
        state = _detached_state(state, attached_mock_event_context)
        result_proxy = state.result

    assert isinstance(result_proxy, MutableProxy)
    async with attached_mock_event_context.modify_state(
        state_token
    ) as concurrent_state:
        assert isinstance(concurrent_state, UnionDataclassState)
        concurrent_state.result = ErrorData(messages=["boom"])

    with pytest.raises(RuntimeError, match="Unable to refresh mutable proxy"):
        async with result_proxy:
            pass
    assert result_proxy._self_actx_state is None

    # A same-type replacement still refreshes normally.
    async with attached_mock_event_context.modify_state(
        state_token
    ) as concurrent_state:
        assert isinstance(concurrent_state, UnionDataclassState)
        concurrent_state.result = SuccessData(values=[2])

    async with result_proxy as mutable_result:
        mutable_result.values.append(3)

    async with state_manager.modify_state(state_token) as final_state:
        assert isinstance(final_state, UnionDataclassState)
        assert final_state.result == SuccessData(values=[2, 3])


@dataclasses.dataclass
class CustomGetRegistry:
    """A dataclass with a custom method shadowing the dict `get` method name."""

    entries: dict[str, list[int]] = dataclasses.field(default_factory=dict)

    def get(self, key: str) -> list[int] | None:
        """Look up an entry list by key.

        Args:
            key: The entry key.

        Returns:
            The entry list, or None if missing.
        """
        return self.entries.get(key)


class CustomGetState(BaseState):
    """A test state holding a dataclass with a custom `get` method."""

    registry: CustomGetRegistry = CustomGetRegistry(entries={"a": [1]})


@pytest.mark.asyncio
async def test_mutable_proxy_custom_get_method_path_tracking(
    token: str, attached_mock_event_context: EventContext
) -> None:
    """A custom `get` method on a proxied dataclass works and tracks paths."""
    state_manager = attached_mock_event_context.state_manager
    state_token = BaseStateToken(ident=token, cls=CustomGetState)

    async with state_manager.modify_state(state_token) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        assert isinstance(state, CustomGetState)
        state = _detached_state(state, attached_mock_event_context)
        entry_proxy = state.registry.get("a")
        assert state.registry.get("missing") is None

    assert isinstance(entry_proxy, MutableProxy)
    assert entry_proxy._self_path == (("attr", "entries"), ("item", "a"))

    async with entry_proxy as mutable_entry:
        mutable_entry.append(2)

    async with state_manager.modify_state(state_token) as final_state:
        assert isinstance(final_state, CustomGetState)
        assert final_state.registry.entries == {"a": [1, 2]}


@dataclasses.dataclass(frozen=True)
class FrozenTaggedModel:
    """A frozen dataclass for dataclass-protocol tests."""

    tag: str = "a"


@dataclasses.dataclass(match_args=False)
class UnmatchableModel:
    """A dataclass declared without `__match_args__`."""

    tag: str = "a"


@dataclasses.dataclass(slots=True)
class SlottedModel:
    """A slots dataclass, whose layout must not leak onto the proxy class."""

    tag: str = "default"
    ls: list[int] = dataclasses.field(default_factory=list)


def _dataclass_proxy(model: Any) -> Any:
    """Build a proxy for a dataclass value held by a state field.

    Args:
        model: The dataclass instance to proxy.

    Returns:
        The MutableProxy wrapping the model.
    """
    return MutableProxy(model, DataclassMutableProxyState(), "dc")


@pytest.mark.parametrize(
    ("model", "frozen"),
    [
        (TaggedModel(ls=[{"tag": 1}]), False),
        (FrozenTaggedModel(), True),
        (SlottedModel(), False),
    ],
)
def test_dataclass_proxy_class_carries_dataclass_metadata(
    model: Any, frozen: bool
) -> None:
    """The proxy class synthesized per dataclass type exposes its metadata."""
    proxy_cls = type(_dataclass_proxy(model))
    model_cls = type(model)

    assert proxy_cls is not model_cls
    assert dataclasses.is_dataclass(proxy_cls)
    assert dataclasses.fields(proxy_cls) == dataclasses.fields(model_cls)
    assert proxy_cls.__dataclass_params__ is model_cls.__dataclass_params__  # pyright: ignore [reportAttributeAccessIssue]
    assert proxy_cls.__dataclass_params__.frozen is frozen  # pyright: ignore [reportAttributeAccessIssue]
    assert proxy_cls.__match_args__ == model_cls.__match_args__  # pyright: ignore [reportAttributeAccessIssue]


def test_dataclass_proxy_class_omits_absent_metadata() -> None:
    """Metadata the wrapped dataclass was declared without is not invented."""
    proxy_cls = type(_dataclass_proxy(UnmatchableModel()))

    assert not hasattr(UnmatchableModel, "__match_args__")
    assert not hasattr(proxy_cls, "__match_args__")


def test_dataclass_proxy_class_copies_no_behavior() -> None:
    """Only metadata is copied: everything else resolves through the wrapped object."""
    model = SlottedModel(tag="instance", ls=[1])
    proxy = _dataclass_proxy(model)
    proxy_cls = type(proxy)

    for attr in (
        "__init__",
        "__repr__",
        "__eq__",
        "__setattr__",
        "__delattr__",
        "__slots__",
        "tag",
    ):
        assert attr not in vars(proxy_cls)

    assert proxy.tag == "instance"
    assert dataclasses.asdict(proxy) == {"tag": "instance", "ls": [1]}

    proxy.ls.append(2)
    assert model.ls == [1, 2]

    proxy.tag = "mutated"
    assert model.tag == "mutated"


@dataclasses.dataclass
class DunderFieldModel:
    """A dataclass whose field names collide with the copied metadata."""

    __match_args__: tuple[str, ...] = ()
    __dataclass_params__: int = 0


def test_dataclass_proxy_class_never_shadows_a_field() -> None:
    """A field named like copied metadata keeps its instance value through the proxy."""
    model = DunderFieldModel(__match_args__=("live",), __dataclass_params__=7)
    proxy = _dataclass_proxy(model)

    assert "__match_args__" not in vars(type(proxy))
    assert "__dataclass_params__" not in vars(type(proxy))
    assert proxy.__match_args__ == ("live",)
    assert proxy.__dataclass_params__ == 7
    assert dataclasses.asdict(proxy) == dataclasses.asdict(model)


@dataclasses.dataclass
class DunderClassVarModel:
    """A dataclass declaring the copied metadata names as class-level entries."""

    __match_args__: ClassVar[tuple[str, ...]] = ("custom",)
    __dataclass_fields__: ClassVar[dict[str, Any]] = {}
    other: int = 0


@dataclasses.dataclass
class DunderInitVarModel:
    """A dataclass declaring a copied metadata name as an InitVar."""

    __match_args__: dataclasses.InitVar[tuple[str, ...]] = ("initvar",)
    other: int = 0

    def __post_init__(self, __match_args__: tuple[str, ...]) -> None:
        """Accept the InitVar.

        Args:
            __match_args__: The InitVar value, unused.
        """


@pytest.mark.parametrize(
    ("model", "match_args"),
    [
        (DunderClassVarModel(other=1), ("custom",)),
        (DunderInitVarModel(other=1), ("initvar",)),
    ],
)
def test_dataclass_proxy_class_copies_class_level_pseudo_fields(
    model: Any, match_args: tuple[str, ...]
) -> None:
    """ClassVar and InitVar entries keep their value on the class, so they are copied."""
    proxy = _dataclass_proxy(model)
    proxy_cls = type(proxy)

    assert dataclasses.is_dataclass(proxy_cls)
    assert proxy_cls.__match_args__ == match_args  # pyright: ignore [reportAttributeAccessIssue]
    assert proxy.__match_args__ == match_args
    assert dataclasses.asdict(proxy) == {"other": 1}


def test_frozen_dataclass_proxy_rejects_mutation() -> None:
    """A frozen dataclass stays frozen through its proxy."""
    proxy = _dataclass_proxy(FrozenTaggedModel())

    with pytest.raises(dataclasses.FrozenInstanceError):
        proxy.tag = "b"


def test_interval_computed_vars_resolve_on_state(
    attached_mock_event_context: EventContext,
):
    """Marking dirty resolves the interval-var class cache via the state's own class.

    `_expired_computed_vars` caches the interval-var names per class, looked up
    via `type(self)`. This is exercised directly on a background-task-style
    state, since no wrapper type is involved in the new design.

    Args:
        attached_mock_event_context: The attached mock event context fixture.
    """
    import datetime

    from reflex.state import State
    from reflex.vars.base import computed_var

    class IntervalState(State):
        base: int = 0

        @computed_var(interval=datetime.timedelta(seconds=30))
        def timed(self) -> int:
            return self.base

    state = IntervalState(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    state = _detached_state(state, attached_mock_event_context)
    assert state._expired_computed_vars() == {"timed"}
    assert IntervalState._interval_computed_var_names == frozenset({"timed"})


def test_subclass_overrides_a_framework_method():
    """A marked override of a BaseState method is what the state instance uses.

    The class is a detached root (not a substate of ``State``) so the shadowed
    method never reaches the framework paths that other tests exercise on the
    shared state tree.
    """
    from reflex.state import BaseState

    def get_value(self, key: str):
        return f"shadow:{key}"

    get_value.__override_base_method__ = True  # pyright: ignore [reportFunctionMemberAccess]

    ShadowState = type(
        "ShadowState",
        (BaseState,),
        {
            "__module__": __name__,
            "__qualname__": "ShadowState",
            "get_value": get_value,
        },
    )
    state = ShadowState(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    assert state.get_value("k") == "shadow:k"
