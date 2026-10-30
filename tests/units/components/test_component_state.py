"""Ensure that Components returned by ComponentState.create have independent State classes."""

import pytest
from reflex_base import constants
from reflex_base.utils.exceptions import ReflexRuntimeError
from reflex_components_core.base.bare import Bare

import reflex as rx
from reflex.compiler.utils import compile_client_storage
from reflex.constants.state import FIELD_MARKER


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


def test_component_state_default_assigned_in_create_is_not_shared():
    """A mutable default assigned to a field in create gives each session its own copy."""

    class Chat(rx.ComponentState):
        messages: list[str] = []

        @classmethod
        def create(cls, initial_messages: list[str]) -> rx.Component:
            """Set the default messages before creating the component.

            Args:
                initial_messages: The messages each session starts with.

            Returns:
                The chat component.
            """
            cls.__fields__["messages"].default = initial_messages
            return super().create()

        @classmethod
        def get_component(cls) -> rx.Component:
            """Show the messages.

            Returns:
                The component showing the messages.
            """
            return rx.text(cls.messages)

    initial_messages = ["hello"]
    state_cls = Chat.create(initial_messages).State
    assert state_cls is not None
    assert issubclass(state_cls, Chat)
    first, second = state_cls(), state_cls()
    first.messages.append("from first")
    assert second.messages == ["hello"]
    assert state_cls().messages == ["hello"]
    assert initial_messages == ["hello"]


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
