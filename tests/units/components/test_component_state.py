"""Ensure that Components returned by ComponentState.create have independent State classes."""

import pytest

import reflex as rx
from reflex.components.base.bare import Bare
from reflex.utils.exceptions import ReflexRuntimeError


def test_component_state():
    """Create two components with independent state classes."""

    class CS(rx.ComponentState):
        count: int = 0

        def increment(self):
            self.count += 1

        @classmethod
        def get_component(cls, *children, **props):
            return rx.el.div(
                *children,
                **props,
            )

    cs1, cs2 = CS.create("a", id="a"), CS.create("b", id="b")
    assert isinstance(cs1, rx.Component)
    assert isinstance(cs2, rx.Component)
    assert cs1.State is not None
    assert cs2.State is not None
    assert cs1.State != cs2.State
    assert issubclass(cs1.State, CS)
    assert issubclass(cs1.State, rx.State)
    assert issubclass(cs2.State, CS)
    assert issubclass(cs2.State, rx.State)
    assert CS._per_component_state_instance_count == 2
    assert isinstance(cs1.State.increment, rx.event.EventHandler)
    assert cs1.State.increment != cs2.State.increment

    assert len(cs1.children) == 1
    assert cs1.children[0].render() == Bare.create("a").render()
    assert cs1.id == "a"
    assert len(cs2.children) == 1
    assert cs2.children[0].render() == Bare.create("b").render()
    assert cs2.id == "b"


def test_init_component_state() -> None:
    """Ensure that ComponentState subclasses cannot be instantiated directly."""

    class CS(rx.ComponentState):
        @classmethod
        def get_component(cls, *children, **props):
            return rx.el.div()

    with pytest.raises(ReflexRuntimeError):
        CS()

    class SubCS(CS):
        pass

    with pytest.raises(ReflexRuntimeError):
        SubCS()
