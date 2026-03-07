"""Tests for MutableProxy behavior."""

import dataclasses
import math
import pickle

import reflex as rx
from reflex.istate.proxy import MutableProxy


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


class UnwrapListState(rx.State):
    """Test state for list unwrap tests."""

    data: list[dict[str, int]] = []


class UnwrapDictState(rx.State):
    """Test state for dict unwrap tests."""

    data: dict[str, dict[str, int]] = {}


class UnwrapSetState(rx.State):
    """Test state for set unwrap tests."""

    data: set[int] = set()


def test_append_unwraps_proxy():
    """Appending a proxy-wrapped value must store the unwrapped original."""
    state = UnwrapListState()
    state.data = [{"a": 1}]

    proxy = state.data
    assert isinstance(proxy, MutableProxy)

    # Iterate to get a proxy-wrapped element
    items = list(proxy)
    assert len(items) == 1
    assert isinstance(items[0], MutableProxy)

    # Append the proxy-wrapped item back
    proxy.append(items[0])

    # The underlying list must contain raw dicts, not proxies
    underlying: list[dict[str, int]] = object.__getattribute__(proxy, "__wrapped__")
    assert len(underlying) == 2
    for item in underlying:
        assert not isinstance(item, MutableProxy), (
            f"Proxy leaked into underlying list: {type(item)}"
        )
    assert underlying[0] is underlying[1]  # same object identity


def test_setitem_unwraps_proxy():
    """Setting an item via __setitem__ must unwrap proxy values."""
    state = UnwrapListState()
    state.data = [{"a": 1}, {"b": 2}]

    proxy = state.data
    assert isinstance(proxy, MutableProxy)

    # Get proxy-wrapped element via __getitem__
    item = proxy[0]
    assert isinstance(item, MutableProxy)

    # Assign it to a different index
    proxy[1] = item

    underlying: list[dict[str, int]] = object.__getattribute__(proxy, "__wrapped__")
    assert not isinstance(underlying[1], MutableProxy)
    assert underlying[0] is underlying[1]


def test_extend_unwraps_proxies():
    """Extending with a list of proxy-wrapped values must unwrap each."""
    state = UnwrapListState()
    state.data = [{"a": 1}, {"b": 2}]

    proxy = state.data
    # Collect proxy-wrapped elements via iteration
    wrapped_items = list(proxy)
    assert all(isinstance(item, MutableProxy) for item in wrapped_items)

    # Extend with the wrapped items
    proxy.extend(wrapped_items)

    underlying: list[dict[str, int]] = object.__getattribute__(proxy, "__wrapped__")
    assert len(underlying) == 4
    for item in underlying:
        assert not isinstance(item, MutableProxy), (
            f"Proxy leaked into underlying list via extend: {type(item)}"
        )


def test_insert_unwraps_proxy():
    """Inserting a proxy-wrapped value must unwrap it."""
    state = UnwrapListState()
    state.data = [{"a": 1}]

    proxy = state.data
    item = proxy[0]
    assert isinstance(item, MutableProxy)

    proxy.insert(0, item)

    underlying: list[dict[str, int]] = object.__getattribute__(proxy, "__wrapped__")
    assert len(underlying) == 2
    assert not isinstance(underlying[0], MutableProxy)


def test_dict_setitem_unwraps_proxy():
    """Setting a dict value via __setitem__ must unwrap proxy values."""
    state = UnwrapDictState()
    state.data = {"key": {"a": 1}}

    proxy = state.data
    assert isinstance(proxy, MutableProxy)

    value = proxy["key"]
    assert isinstance(value, MutableProxy)

    proxy["other"] = value

    underlying: dict[str, dict[str, int]] = object.__getattribute__(
        proxy, "__wrapped__"
    )
    assert not isinstance(underlying["other"], MutableProxy)
    assert underlying["key"] is underlying["other"]


def test_iterate_append_does_not_cause_infinite_growth():
    """Iterating + appending proxied values must not grow the list unboundedly."""
    state = UnwrapListState()
    state.data = [{"a": 1}]

    proxy = state.data
    original_len = 1

    # Iterate and append each item once
    for item in list(proxy):  # snapshot via list() to avoid mutation during iter
        proxy.append(item)

    underlying: list[dict[str, int]] = object.__getattribute__(proxy, "__wrapped__")
    assert len(underlying) == original_len * 2
    for item in underlying:
        assert not isinstance(item, MutableProxy)


def test_setattr_unwraps_proxy():
    """Setting an attribute on a proxied object must unwrap proxy values."""

    @dataclasses.dataclass
    class Container:
        items: list[int] = dataclasses.field(default_factory=list)

    class ContainerState(rx.State):
        container: Container = Container(items=[1, 2, 3])

    state = ContainerState()
    proxy = state.container
    assert isinstance(proxy, MutableProxy)

    # Get the items attribute (will be wrapped)
    items = proxy.items
    assert isinstance(items, MutableProxy)

    # Assign it back via setattr
    proxy.items = items

    underlying: Container = object.__getattribute__(proxy, "__wrapped__")
    assert not isinstance(underlying.items, MutableProxy)


def test_unwrap_proxy_arg_passthrough():
    """Non-proxy, non-container values pass through unchanged."""
    assert MutableProxy._unwrap_proxy_arg(42) == 42
    assert MutableProxy._unwrap_proxy_arg("hello") == "hello"
    assert MutableProxy._unwrap_proxy_arg(None) is None
    assert MutableProxy._unwrap_proxy_arg(math.pi) == math.pi


def test_unwrap_proxy_arg_tuple():
    """Tuples containing proxies are unwrapped element-wise."""
    state = UnwrapListState()
    obj1, obj2 = {"a": 1}, {"b": 2}
    p1 = MutableProxy(obj1, state, "data")
    p2 = MutableProxy(obj2, state, "data")

    result = MutableProxy._unwrap_proxy_arg((p1, p2))
    assert isinstance(result, tuple)
    assert result[0] is obj1
    assert result[1] is obj2


def test_unwrap_proxy_arg_set():
    """Sets containing proxies are unwrapped element-wise."""
    state = UnwrapSetState()
    p1 = MutableProxy(1, state, "data")
    p2 = MutableProxy(2, state, "data")

    result = MutableProxy._unwrap_proxy_arg({p1, p2})
    assert isinstance(result, set)
    assert result == {1, 2}


def test_unwrap_proxy_arg_dict():
    """Dict keys and values that are proxies are unwrapped."""
    state = UnwrapListState()
    key = MutableProxy("k", state, "data")
    val = MutableProxy({"a": 1}, state, "data")

    result = MutableProxy._unwrap_proxy_arg({key: val})
    assert isinstance(result, dict)
    assert "k" in result
    assert result["k"] is object.__getattribute__(val, "__wrapped__")


def test_dirty_tracking_preserved_after_unwrap():
    """Mutations via proxy must still mark the state dirty after the fix."""
    state = UnwrapListState()
    state.data = [{"a": 1}]
    state._clean()
    assert not state.dirty_vars

    # append via proxy should still mark dirty
    proxy = state.data
    proxy.append({"b": 2})
    assert "data" in state.dirty_vars

    state._clean()

    # __setitem__ via proxy should still mark dirty
    proxy[0] = {"c": 3}
    assert "data" in state.dirty_vars

    state._clean()

    # nested mutation via proxy should still mark dirty
    proxy[0]["d"] = 4
    assert "data" in state.dirty_vars
