"""Ensure that Components returned by ComponentState.create have independent State classes."""

from pathlib import Path
from typing import Any

import pytest
from reflex_base import constants
from reflex_base.event import Event, EventSpec, event
from reflex_base.utils.exceptions import ReflexRuntimeError
from reflex_components_core.base.bare import Bare

import reflex as rx
from reflex.compiler.utils import compile_client_storage
from reflex.constants.state import FIELD_MARKER
from reflex.state import State


def test_component_state_callback_documentation():
    """Execute the documented recipe and check its per-instance event routing."""
    docs_path = (
        Path(__file__).resolve().parents[3] / "docs/state_structure/component_state.md"
    )
    section = docs_path.read_text().split("## Returning events to a caller\n", 1)[1]
    code = section.split("```python\n", 1)[1].split("\n```", 1)[0]
    namespace: dict[str, Any] = {"__name__": "component_state_callback_example"}
    exec(compile(code, str(docs_path), "exec"), namespace)
    counter_type = namespace["ThresholdCounter"]
    caller_type = namespace["CallbackState"]
    first = namespace["counter"]

    class OtherCaller(State):
        value: int = 0

        @event
        def receive(self, value: int):
            """Store this caller's count.

            Args:
                value: The counter's current count.
            """
            self.value = value

    second = counter_type.create(on_over_ten=OtherCaller.receive)
    omitted = counter_type.create()
    assert first.State is not None
    assert second.State is not None
    assert omitted.State is not None
    assert first.State is not second.State
    assert first.State._on_over_ten is caller_type.receive
    assert second.State._on_over_ten is OtherCaller.receive
    assert omitted.State._on_over_ten is None
    for component in (first, second, omitted):
        assert "_on_over_ten" not in component.State.get_fields()
        assert (
            component.children[0].event_triggers["on_click"].events[0].handler
            is component.State.decrement
        )
        assert (
            component.children[2].event_triggers["on_click"].events[0].handler
            is component.State.increment
        )

    first_state, second_state, omitted_state = (
        component.State() for component in (first, second, omitted)
    )
    other_client_state = first.State()
    first_state.count = 9
    for method, count, payload in (
        ("increment", 10, None),
        ("increment", 11, 11),
        ("increment", 12, 12),
        ("decrement", 11, 11),
        ("decrement", 10, None),
        ("decrement", 9, None),
    ):
        result = getattr(first_state, method)()
        assert first_state.count == count
        assert second_state.count == omitted_state.count == 0
        assert other_client_state.count == 0
        if payload is None:
            assert result is None
        else:
            assert isinstance(result, EventSpec)
            assert result.handler is caller_type.receive
            events = Event.from_event_type(result)
            assert len(events) == 1
            assert events[0].name == f"{caller_type.get_full_name()}.receive"
            assert events[0].payload == {"value": payload}

    second_state.count = 12
    events = Event.from_event_type(second_state.decrement())
    assert len(events) == 1
    assert events[0].name == f"{OtherCaller.get_full_name()}.receive"
    assert events[0].payload == {"value": 11}
    assert first_state.count == 9
    omitted_state.count = 11
    assert omitted_state.increment() is None
    assert omitted_state.decrement() is None
    caller = caller_type()
    caller.receive(11)
    assert caller.value == 11


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


def test_component_state_defaults_from_props():
    """Field defaults set in get_component configure each component independently."""

    class ConfiguredComponentState(rx.ComponentState):
        count: int = 0
        labels: rx.Field[list[str]] = rx.field(default_factory=list)

        @classmethod
        def get_component(cls, initial_count: int, label: str) -> rx.Component:
            """Configure the new state class before returning its component.

            Args:
                initial_count: The counter's default value.
                label: The label's default value.

            Returns:
                The component using the configured state vars.
            """
            cls.__fields__["count"].set_default(initial_count)
            cls.__fields__["labels"].set_default(default_factory=lambda: [label])
            return rx.text(cls.count, cls.labels)

    first = ConfiguredComponentState.create(initial_count=5, label="first")
    second = ConfiguredComponentState.create(initial_count=10, label="second")
    assert first.State is not None
    assert second.State is not None
    assert issubclass(first.State, ConfiguredComponentState)
    assert issubclass(second.State, ConfiguredComponentState)
    first_state, second_state = first.State(), second.State()
    assert first_state.count == 5
    assert second_state.count == 10
    assert first_state.labels == ["first"]
    assert second_state.labels == ["second"]
    assert ConfiguredComponentState.get_fields()["count"].default_value() == 0
    assert ConfiguredComponentState.get_fields()["labels"].default_value() == []
    assert first.State.count is first.State.base_vars["count"]
    assert first.State.labels is first.State.base_vars["labels"]
    first_state.count = 99
    first_state.labels.append("changed")
    first_state.reset()
    assert first_state.count == 5
    assert first_state.labels == ["first"]
    assert second_state.count == 10
    assert second_state.labels == ["second"]


def test_component_state_storage_default_per_component():
    """A browser storage default set in get_component gives each component its own key."""

    class PreferenceComponentState(rx.ComponentState):
        pref: str = rx.LocalStorage("light", name="pref", sync=True)

        @classmethod
        def get_component(cls, initial: str) -> rx.Component:
            """Configure the new state class before returning its component.

            Args:
                initial: The preference's default value.

            Returns:
                The component showing the preference.
            """
            cls.__fields__["pref"].set_default(
                rx.LocalStorage(initial, name=f"pref-{initial}", sync=True)
            )
            return rx.text(cls.pref)

    for initial in ("dark", "blue"):
        state_cls = PreferenceComponentState.create(initial=initial).State
        assert state_cls is not None
        default = state_cls.get_fields()["pref"].default
        assert isinstance(default, rx.LocalStorage)
        assert default == initial
        assert state_cls._is_client_storage("pref")
        compiled = compile_client_storage(state_cls)
        key = f"{state_cls.get_full_name()}.pref{FIELD_MARKER}"
        assert compiled[constants.LOCAL_STORAGE][key] == {
            "name": f"pref-{initial}",
            "sync": True,
        }
    declared = PreferenceComponentState.get_fields()["pref"].default
    assert isinstance(declared, rx.LocalStorage)
    assert declared.name == "pref"
