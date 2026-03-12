"""Tests for MutableProxy pickle behavior."""

import dataclasses
import pickle
from asyncio import CancelledError
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest

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


@pytest.mark.usefixtures("mock_app")
@pytest.mark.asyncio
async def test_state_proxy_recovery():
    """Ensure that `async with self` can be re-entered after a lock issue."""
    state = ProxyTestState()
    state_proxy = StateProxy(state)

    with patch("reflex.app.App.modify_state") as mock_modify_state:

        @asynccontextmanager
        async def mock_modify_state_context(*args, **kwargs):  # noqa: RUF029
            msg = "Simulated lock issue"
            raise CancelledError(msg)
            yield

        mock_modify_state.side_effect = mock_modify_state_context

        with pytest.raises(CancelledError, match="Simulated lock issue"):
            async with state_proxy:
                pass

    # After the exception, we should be able to enter the context again without issues
    async with state_proxy:
        pass
