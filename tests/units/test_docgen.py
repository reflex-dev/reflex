"""Tests for reflex-docgen."""

from reflex_docgen import get_component_event_handlers

from reflex.components.component import (
    DEFAULT_TRIGGERS,
    DEFAULT_TRIGGERS_AND_DESC,
    Component,
    TriggerDefinition,
    field,
)
from reflex.constants import EventTriggers
from reflex.event import EventHandler, no_args_event_spec


def test_default_triggers_have_descriptions():
    """Every entry in DEFAULT_TRIGGERS should carry a non-empty description."""
    for name, trigger in DEFAULT_TRIGGERS_AND_DESC.items():
        assert isinstance(trigger, TriggerDefinition), (
            f"{name} should be a TriggerDefinition"
        )
        assert trigger.description, f"{name} has an empty description"
        assert trigger.spec is not None, f"{name} has no spec"


def test_get_component_event_handlers_returns_default_descriptions():
    """get_component_event_handlers should return descriptions for default triggers."""
    handlers = get_component_event_handlers(Component)
    handlers_by_name = {h.name: h for h in handlers}

    # All default triggers should be present.
    for name in DEFAULT_TRIGGERS_AND_DESC:
        assert name in handlers_by_name, f"Missing default trigger: {name}"
        handler = handlers_by_name[name]
        assert handler.is_inherited is True
        assert handler.description == DEFAULT_TRIGGERS[name].description


class _ComponentWithCustomTrigger(Component):
    on_custom: EventHandler[no_args_event_spec] = field(
        doc="Custom event fired on test."
    )

    @classmethod
    def create(cls, *children, **props):
        return super().create(*children, **props)


def test_custom_trigger_description_not_overridden():
    """Component-defined event handler docs should take priority over DEFAULT_TRIGGERS."""
    handlers = get_component_event_handlers(_ComponentWithCustomTrigger)
    handlers_by_name = {h.name: h for h in handlers}

    # Custom trigger should use its own doc.
    custom = handlers_by_name["on_custom"]
    assert custom.description == "Custom event fired on test."
    assert custom.is_inherited is False

    # Default triggers should still have their descriptions.
    click = handlers_by_name[EventTriggers.ON_CLICK]
    assert click.is_inherited is True
    assert click.description is not None
    assert "clicks" in click.description.lower()
