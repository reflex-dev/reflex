from __future__ import annotations

from typing import Any

from reflex.components.component import Component
from reflex.event import EventHandler


# This is a repeat of its namesake in test_component.py.
def test_custom_component_declare_event_handlers_in_fields():
    class ReferenceComponent(Component):
        def get_event_triggers(self) -> dict[str, Any]:
            """Test controlled triggers.

            Returns:
                Test controlled triggers.
            """
            return {
                **super().get_event_triggers(),
                "on_a": lambda e: [e],
                "on_b": lambda e: [e.target.value],
                "on_c": lambda e: [],
                "on_d": lambda: [],
            }

    class TestComponent(Component):
        on_a: EventHandler[lambda e0: [e0]]
        on_b: EventHandler[lambda e0: [e0.target.value]]
        on_c: EventHandler[lambda e0: []]
        on_d: EventHandler[lambda: []]

    custom_component = ReferenceComponent.create()
    test_component = TestComponent.create()
    assert (
        custom_component.get_event_triggers().keys()
        == test_component.get_event_triggers().keys()
    )
