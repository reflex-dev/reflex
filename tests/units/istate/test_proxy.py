"""Tests for reflex.istate.proxy."""

import asyncio
import dataclasses
import pickle
from asyncio import CancelledError
from contextlib import asynccontextmanager
from typing import Any

import pytest
from reflex_base.event.context import EventContext
from reflex_base.utils.exceptions import ImmutableStateError

import reflex as rx
from reflex.istate.data import RouterData
from reflex.istate.manager.token import BaseStateToken
from reflex.istate.proxy import (
    ImmutableMutableProxy,
    MutableProxy,
    ReadOnlyStateProxy,
    StateProxy,
)
from reflex.state import BaseState


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
async def test_state_proxy_recovery(
    attached_mock_event_context: EventContext, monkeypatch: pytest.MonkeyPatch
):
    """Ensure that `async with self` can be re-entered after a lock issue."""
    state = ProxyTestState()
    state_proxy = StateProxy(state)

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
            async with state_proxy:
                pass

    # After the exception, we should be able to enter the context again without issues
    async with state_proxy:
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


@pytest.mark.asyncio
async def test_rebind_mutable_proxy(
    token: str, attached_mock_event_context: EventContext
) -> None:
    """Test that previously bound MutableProxy instances can be rebound correctly."""
    state_manager = attached_mock_event_context.state_manager

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=MutableProxyState)
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
    await state_manager.close()

    new_state_proxy = StateProxy(state)
    assert state_proxy is not new_state_proxy
    assert new_state_proxy.data["a"]._self_state is new_state_proxy
    assert state_proxy.data["a"]._self_state is state_proxy
    assert state_proxy.__wrapped__.data["a"]._self_state is state_proxy.__wrapped__

    async with state_proxy:
        state_proxy.data["a"].append(3)

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=MutableProxyState)
    ) as state:
        assert isinstance(state, MutableProxyState)
        assert state.data["a"] == [2, 3]
        # Object identity persists across serialization, so data["b"] is also mutated.
        assert state.data["b"] == [2, 3]


@pytest.mark.asyncio
async def test_immutable_mutable_proxy_async_context_manager(
    token: str, attached_mock_event_context: EventContext
) -> None:
    """Mutable state proxies can enter the owning StateProxy context."""
    state_manager = attached_mock_event_context.state_manager

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=MutableProxyState)
    ) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        state_proxy = StateProxy(state)
        data_proxy = state_proxy.data
        items_proxy = data_proxy["a"]

    assert isinstance(data_proxy, ImmutableMutableProxy)
    assert isinstance(items_proxy, ImmutableMutableProxy)
    # __aexit__ without a prior __aenter__ is a no-op.
    await data_proxy.__aexit__(None, None, None)
    with pytest.raises(ImmutableStateError):
        data_proxy["a"].append(3)
    with pytest.raises(ImmutableStateError):
        items_proxy.append(3)

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=MutableProxyState)
    ) as state:
        assert isinstance(state, MutableProxyState)
        state.data["a"].append(2)

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

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=MutableProxyState)
    ) as state:
        assert isinstance(state, MutableProxyState)
        assert state.data["a"] == [1, 2, 3, 5]
        assert state.data["b"] == [2, 4]


@pytest.mark.asyncio
async def test_immutable_mutable_proxy_async_context_dict_method_paths(
    token: str, attached_mock_event_context: EventContext
) -> None:
    """Dict method proxies refresh to the returned item, not the parent dict."""
    state_manager = attached_mock_event_context.state_manager

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=NestedMutableProxyState)
    ) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        state_proxy = StateProxy(state)
        existing_proxy = state_proxy.data.get("a")
        default_proxy = state_proxy.data.get("missing", {"fallback": 4})

    async with state_proxy:
        new_proxy = state_proxy.data.setdefault("c", {"z": 3})

    assert isinstance(existing_proxy, ImmutableMutableProxy)
    assert isinstance(new_proxy, ImmutableMutableProxy)
    assert isinstance(default_proxy, ImmutableMutableProxy)

    async with existing_proxy as mutable_existing:
        mutable_existing["x"] = 10

    async with new_proxy as mutable_new:
        mutable_new["z"] = 30

    with pytest.raises(RuntimeError, match="Unable to refresh mutable proxy"):
        async with default_proxy:
            pass

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=NestedMutableProxyState)
    ) as state:
        assert isinstance(state, NestedMutableProxyState)
        assert state.data == {
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

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=IterableMutableProxyState)
    ) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        state_proxy = StateProxy(state)
        [items_proxy] = state_proxy.data

    assert isinstance(items_proxy, ImmutableMutableProxy)
    with pytest.raises(RuntimeError, match="Unable to refresh mutable proxy"):
        async with items_proxy:
            pass

    async with state_proxy:
        state_proxy.data[0].append(2)

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=IterableMutableProxyState)
    ) as state:
        assert isinstance(state, IterableMutableProxyState)
        assert state.data == [[1, 2]]


@pytest.mark.asyncio
async def test_immutable_mutable_proxy_async_context_rejects_list_derived_proxies(
    token: str, attached_mock_event_context: EventContext
) -> None:
    """List-derived proxies cannot safely refresh after structural changes."""
    state_manager = attached_mock_event_context.state_manager

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=IterableMutableProxyState)
    ) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        state_proxy = StateProxy(state)
        items_proxy = state_proxy.data[0]
        [sliced_items_proxy] = state_proxy.data[:1]

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=IterableMutableProxyState)
    ) as state:
        assert isinstance(state, IterableMutableProxyState)
        state.data.insert(0, [0])

    for proxy in (items_proxy, sliced_items_proxy):
        with pytest.raises(RuntimeError, match="Unable to refresh mutable proxy"):
            async with proxy:
                pass

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=IterableMutableProxyState)
    ) as state:
        assert isinstance(state, IterableMutableProxyState)
        assert state.data == [[0], [1]]


@pytest.mark.asyncio
async def test_immutable_mutable_proxy_async_context_missing_key(
    token: str, attached_mock_event_context: EventContext
) -> None:
    """A path whose key was deleted raises the refresh error, not KeyError."""
    state_manager = attached_mock_event_context.state_manager

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=MutableProxyState)
    ) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        state_proxy = StateProxy(state)
        items_proxy = state_proxy.data["a"]

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=MutableProxyState)
    ) as state:
        assert isinstance(state, MutableProxyState)
        del state.data["a"]

    with pytest.raises(RuntimeError, match="Unable to refresh mutable proxy"):
        async with items_proxy:
            pass

    assert items_proxy._self_actx_state is None


@pytest.mark.asyncio
async def test_immutable_mutable_proxy_async_context_attr_path(
    token: str, attached_mock_event_context: EventContext
) -> None:
    """Proxies reached through attribute access refresh via the attr path."""
    state_manager = attached_mock_event_context.state_manager

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=DataclassMutableProxyState)
    ) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        state_proxy = StateProxy(state)
        ls_proxy = state_proxy.dc.ls

    assert isinstance(ls_proxy, ImmutableMutableProxy)
    async with ls_proxy as mutable_ls:
        assert mutable_ls is ls_proxy
        mutable_ls.append({"tag": 2})

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=DataclassMutableProxyState)
    ) as state:
        assert isinstance(state, DataclassMutableProxyState)
        assert state.dc.ls == [{"tag": 1}, {"tag": 2}]


@pytest.mark.asyncio
async def test_mutable_proxy_async_context_plain_state() -> None:
    """A MutableProxy bound to a plain state enters as a no-op refresh."""
    state = MutableProxyState()
    data_proxy = state.data
    assert isinstance(data_proxy, MutableProxy)
    assert not isinstance(data_proxy, ImmutableMutableProxy)

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
    """A failed owning StateProxy enter does not permanently block the proxy."""
    state_manager = attached_mock_event_context.state_manager

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=MutableProxyState)
    ) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        state_proxy = StateProxy(state)
        data_proxy = state_proxy.data

    original_aenter = StateProxy.__aenter__
    fail_once = True

    async def fail_first_enter(self: StateProxy) -> StateProxy:
        nonlocal fail_once
        if fail_once:
            fail_once = False
            raise asyncio.CancelledError
        return await original_aenter(self)

    monkeypatch.setattr(StateProxy, "__aenter__", fail_first_enter)

    with pytest.raises(asyncio.CancelledError):
        async with data_proxy:
            pass

    assert data_proxy._self_actx_state is None
    async with data_proxy as mutable_data:
        mutable_data["a"].append(2)

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=MutableProxyState)
    ) as state:
        assert isinstance(state, MutableProxyState)
        assert state.data["a"] == [1, 2]


@pytest.mark.asyncio
async def test_immutable_mutable_proxy_async_context_clears_state_when_cleanup_fails(
    token: str,
    attached_mock_event_context: EventContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed cleanup while entering does not leave the proxy marked mutable."""
    state_manager = attached_mock_event_context.state_manager

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=IterableMutableProxyState)
    ) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        state_proxy = StateProxy(state)
        data_proxy = state_proxy.data

    original_getattr = StateProxy.__getattr__

    def return_unrefreshable_value(self: StateProxy, name: str) -> Any:
        """Return a non-proxy value while refreshing the test field.

        Returns:
            None for the refreshed data field, otherwise the original attribute.
        """
        if name == "data" and self._self_mutable:
            return None
        return original_getattr(self, name)

    async def fail_exit(self: StateProxy, *exc_info: Any) -> None:
        await asyncio.sleep(0)
        msg = "cleanup failed"
        raise RuntimeError(msg)

    monkeypatch.setattr(StateProxy, "__getattr__", return_unrefreshable_value)
    monkeypatch.setattr(StateProxy, "__aexit__", fail_exit)

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

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=IterableMutableProxyState)
    ) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        state_proxy = StateProxy(state)
        data_proxy = state_proxy.data

    original_getattr = StateProxy.__getattr__

    def raise_fatal_refresh_error(self: StateProxy, name: str) -> Any:
        """Raise a BaseException while reading the refreshed state field.

        Returns:
            The original attribute for all other reads.
        """
        if name == "data" and self._self_mutable:
            raise FatalRefreshError
        return original_getattr(self, name)

    monkeypatch.setattr(StateProxy, "__getattr__", raise_fatal_refresh_error)

    try:
        with pytest.raises(FatalRefreshError):
            async with data_proxy:
                pass

        assert data_proxy._self_actx_state is None
        assert state_proxy._self_actx is None
    finally:
        if state_proxy._self_actx is not None:
            await state_proxy.__aexit__(None, None, None)
        data_proxy._self_actx_state = None


@pytest.mark.asyncio
async def test_read_only_state_proxy_field_rejects_async_context(
    token: str, attached_mock_event_context: EventContext
) -> None:
    """Mutable fields of a read-only state proxy stay read-only under async with."""
    state_manager = attached_mock_event_context.state_manager

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=MutableProxyState)
    ) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        read_only_proxy = ReadOnlyStateProxy(state)
        data_proxy = read_only_proxy.data

    assert isinstance(data_proxy, ImmutableMutableProxy)
    with pytest.raises(ImmutableStateError, match="read-only"):
        async with data_proxy:
            pass
    assert data_proxy._self_actx_state is None
    with pytest.raises(ImmutableStateError):
        data_proxy["a"].append(3)


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

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=UnionDataclassState)
    ) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        state_proxy = StateProxy(state)
        result_proxy = state_proxy.result

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=UnionDataclassState)
    ) as state:
        assert isinstance(state, UnionDataclassState)
        state.result = ErrorData(messages=["boom"])

    with pytest.raises(RuntimeError, match="Unable to refresh mutable proxy"):
        async with result_proxy:
            pass
    assert result_proxy._self_actx_state is None

    # A same-type replacement still refreshes normally.
    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=UnionDataclassState)
    ) as state:
        assert isinstance(state, UnionDataclassState)
        state.result = SuccessData(values=[2])

    async with result_proxy as mutable_result:
        mutable_result.values.append(3)

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=UnionDataclassState)
    ) as state:
        assert isinstance(state, UnionDataclassState)
        assert state.result == SuccessData(values=[2, 3])


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

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=CustomGetState)
    ) as state:
        state.router = RouterData.from_router_data({
            "query": {},
            "token": token,
            "sid": "test_sid",
        })
        state_proxy = StateProxy(state)
        entry_proxy = state_proxy.registry.get("a")
        assert state_proxy.registry.get("missing") is None

    assert isinstance(entry_proxy, ImmutableMutableProxy)
    assert entry_proxy._self_path == (("attr", "entries"), ("item", "a"))

    async with entry_proxy as mutable_entry:
        mutable_entry.append(2)

    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=CustomGetState)
    ) as state:
        assert isinstance(state, CustomGetState)
        assert state.registry.entries == {"a": [1, 2]}


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
    # `is_dataclass` only tests for `__dataclass_fields__`, so a class that
    # answers it must also answer how the dataclass was declared.
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

    # Copying the generated methods would rebind them to the proxy and bypass
    # its dirty tracking; copying `__slots__`, a field default or a ClassVar
    # would shadow the wrapped instance, since a class attribute is found
    # before `__getattr__` runs.
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


def test_frozen_dataclass_proxy_rejects_mutation() -> None:
    """A frozen dataclass stays frozen through its proxy."""
    proxy = _dataclass_proxy(FrozenTaggedModel())

    with pytest.raises(dataclasses.FrozenInstanceError):
        proxy.tag = "b"
