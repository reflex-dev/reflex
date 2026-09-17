"""Generate documentation for Reflex components."""

from dataclasses import dataclass
from typing import Any

from reflex_base.components.component import DEFAULT_TRIGGERS_AND_DESC, Component
from reflex_base.event import EventHandler


@dataclass(frozen=True, slots=True, kw_only=True)
class PropDocumentation:
    """Hold information about a prop.

    Attributes:
        name: The name of the prop.
        type: The type of the prop.
        description: The description of the prop.
        default_value: The default value of the prop.
    """

    name: str

    type: Any

    description: str | None

    default_value: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class EventHandlerDocumentation:
    """Hold information about an event handler.

    Attributes:
        name: The name of the event handler.
        description: The description of the event handler.
        is_inherited: Whether the event handler is inherited from DEFAULT_TRIGGERS.
    """

    name: str

    description: str | None

    is_inherited: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ComponentDocumentation:
    """Documentation for a Reflex component.

    Attributes:
        name: The name of the component.
        description: The docstring of the component class.
        props: The list of props for the component.
        event_handlers: The list of event handlers for the component.
    """

    name: str
    description: str | None = None
    props: tuple[PropDocumentation, ...] = ()
    event_handlers: tuple[EventHandlerDocumentation, ...] = ()


def get_component_props(
    component_cls: type[Component],
) -> tuple[PropDocumentation, ...]:
    """Get the props for a Reflex component.

    Args:
        component_cls: The component class to get the props for.

    Returns:
        The props for the component.
    """
    props = component_cls.get_js_fields()

    result = []
    for prop_name, component_field in props.items():
        if component_field.type_origin is EventHandler:
            continue
        doc = component_field.doc
        default_value = None

        # If the field has a doc attribute, use it as the description.
        if doc is not None:
            for default_indicator in ["Defaults to", "Default:"]:
                if default_indicator in doc:
                    doc, default_value = doc.split(default_indicator, maxsplit=1)
                    default_value = default_value.strip().rstrip(".")
                    doc = doc.strip().rstrip(".")
                    break

        result.append(
            PropDocumentation(
                name=prop_name,
                type=component_field.type_,
                description=doc.rstrip(".") + "." if doc else None,
                default_value=default_value,
            )
        )

    return tuple(result)


def get_component_event_handlers(
    component_cls: type[Component],
) -> tuple[EventHandlerDocumentation, ...]:
    """Get the event handlers for a Reflex component.

    Args:
        component_cls: The component class to get the event handlers for.

    Returns:
        The event handlers for the component.
    """
    event_triggers = component_cls.get_event_triggers()
    fields = component_cls.get_fields()

    return tuple(
        EventHandlerDocumentation(
            name=name,
            description=(
                field.doc.rstrip(".") + "."
                if (field := fields.get(name)) is not None and field.doc
                else (
                    DEFAULT_TRIGGERS_AND_DESC[name].description
                    if name in DEFAULT_TRIGGERS_AND_DESC
                    else None
                )
            ),
            is_inherited=name in DEFAULT_TRIGGERS_AND_DESC,
        )
        for name in event_triggers
    )


def generate_documentation(component_cls: type[Component]) -> ComponentDocumentation:
    """Generate documentation for a Reflex component.

    Args:
        component_cls: The component class to generate documentation for.

    Returns:
        The generated documentation for the component.
    """
    return ComponentDocumentation(
        name=component_cls.__name__,
        description=component_cls.__doc__,
        props=get_component_props(component_cls),
        event_handlers=get_component_event_handlers(component_cls),
    )
