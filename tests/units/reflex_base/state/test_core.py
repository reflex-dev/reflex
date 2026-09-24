"""Tests for reflex_base.state.core."""

import pickle

import pytest
from reflex_base.state.core import CoreState
from reflex_base.utils.exceptions import SetUndefinedStateVarError


class Root(CoreState, state_root=True):
    """A state root without the app-level machinery of rx.State."""


class Parent(Root):
    """A state at the top of a tree."""

    count: int = 0
    items: list[int] = []


class Child(Parent):
    """A substate."""

    name: str = ""


def _tree() -> tuple[Parent, Child]:
    parent = Parent()
    # Typed as the reflex BaseState, which the tree of any app state holds.
    child = Child(parent_state=parent)  # pyright: ignore[reportArgumentType]
    parent.substates[Child.get_name()] = child  # pyright: ignore[reportArgumentType]
    return parent, child


def test_tree_classes():
    """The first tree state among the bases is the parent."""
    assert Parent.get_parent_state() is None
    assert Child.get_parent_state() is Parent
    assert Child.get_root_state() is Parent
    assert Child.get_full_name() == f"{Parent.get_name()}.{Child.get_name()}"


def test_write_marks_owner_and_ancestors_dirty():
    """A write marks the var dirty on its owner, and the owner dirty on its ancestors."""
    parent, child = _tree()
    child.name = "a"
    assert child.dirty_vars == {"name"}
    assert parent.dirty_substates == {Child.get_name()}
    # An inherited var lives on the state it is declared on.
    child.count = 1
    assert parent.count == 1
    assert parent.dirty_vars == {"count"}
    child._clean()
    parent._clean()
    assert not parent.dirty_vars
    assert not child.dirty_vars


def test_in_place_change_marks_dirty():
    """Mutating a proxied value marks the var dirty."""
    parent, _ = _tree()
    parent.items.append(1)
    assert parent.dirty_vars == {"items"}
    assert parent.get_value("items") == [1]


def test_undeclared_attribute_rejected():
    """Assigning a name the state does not declare raises outside prod mode."""
    parent, _ = _tree()
    with pytest.raises(SetUndefinedStateVarError):
        parent.cuont = 1  # pyright: ignore[reportAttributeAccessIssue]


def test_pickle_keeps_own_fields_only():
    """A pickled state holds its own fields, not its bookkeeping or inherited fields."""
    parent, child = _tree()
    child.name = "a"
    child.count = 2
    restored = pickle.loads(pickle.dumps(child))
    assert vars(restored) == {"name": "a"}
    assert restored.parent_state is None
    assert not restored.dirty_vars
    assert pickle.loads(pickle.dumps(parent)).count == 2


def test_take_place_of():
    """An instance taking the place of another joins its tree with its values."""
    parent, child = _tree()
    child.name = "live"
    stale = Child()
    stale._take_place_of(child)
    assert stale.name == "live"
    assert stale.parent_state is parent
    assert parent.substates[Child.get_name()] is stale


async def test_enter_without_event_context():
    """Entering a state no event context manages does nothing."""
    parent, _ = _tree()
    async with parent as entered:
        assert entered is parent
        parent.count = 3
    assert parent.count == 3
