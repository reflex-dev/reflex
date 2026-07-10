"""Tests for MutableProxy pickle behavior."""

import dataclasses
import pickle
from asyncio import CancelledError
from contextlib import asynccontextmanager

import pytest
from reflex_base.event.context import EventContext

import reflex as rx
from reflex.istate.proxy import MutableProxy, StateProxy


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


def test_mutable_proxy_cached_per_field():
    """Repeated reads of a mutable var reuse the proxy until reassignment."""
    state = ProxyTestState()
    first = state.items
    assert isinstance(first, MutableProxy)
    assert state.items is first
    # Reassignment invalidates the cached proxy.
    state.items = [Item(2)]
    second = state.items
    assert isinstance(second, MutableProxy)
    assert second is not first
    assert second[0].id == 2
    # In-place mutation keeps the same wrapped object, so the proxy is reused.
    second.append(Item(3))
    assert state.items is second


def test_mutable_proxy_cache_not_serialized():
    """The per-instance proxy cache never leaks into pickles or copies."""
    state = ProxyTestState()
    state.items.append(Item(1))  # populate the proxy cache
    assert "_mutable_proxy_cache" in state.__dict__
    assert "_mutable_proxy_cache" not in state.__getstate__()

    restored = pickle.loads(pickle.dumps(state))
    assert "_mutable_proxy_cache" not in restored.__dict__
    restored_items = restored.items
    assert isinstance(restored_items, MutableProxy)
    # The restored proxy tracks the restored state, not the original.
    assert restored_items._self_state is restored


def test_mutable_proxy_iteration_yields_plain_immutables():
    """Iterating a proxied container returns immutable elements unwrapped."""
    state = ProxyTestState()
    state.items = [Item(1), Item(2)]
    numbers = [item.id for item in state.items]
    assert numbers == [1, 2]
    assert all(type(n) is int for n in numbers)
    # Mutable elements remain wrapped so nested mutations mark the state dirty.
    assert all(isinstance(item, MutableProxy) for item in state.items)
