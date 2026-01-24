"""Tests for MutableProxy pickle behavior."""

import dataclasses
import pickle

import reflex as rx
from reflex.istate.proxy import MutableProxy


@dataclasses.dataclass
class Item:
    """Simple picklable object for testing."""

    id: int

    def __init__(self, id: int):
        """Initialize the item."""
        self.id = id


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
