"""Module for generating documentation for Reflex components."""

from dataclasses import dataclass
from typing import Annotated, Any, get_type_hints

from typing_extensions import Doc

from reflex.components.component import DEFAULT_TRIGGERS_AND_DESC, Component
from reflex.event import EventHandler


@dataclass(frozen=True, slots=True, kw_only=True)
class PropDocumentation:
    """Hold information about a prop."""

    name: Annotated[str, Doc("The name of the prop.")]

    type: Annotated[Any, Doc("The type of the prop.")]

    description: Annotated[str | None, Doc("The description of the prop.")]

    default_value: Annotated[str | None, Doc("The default value of the prop.")]


@dataclass(frozen=True, slots=True, kw_only=True)
class EventHandlerDocumentation:
    """Hold information about an event handler."""

    name: Annotated[str, Doc("The name of the event handler.")]

    description: Annotated[str | None, Doc("The description of the event handler.")]

    is_inherited: Annotated[
        bool, Doc("Whether the event handler is inherited from DEFAULT_TRIGGERS.")
    ]


@dataclass(frozen=True, slots=True, kw_only=True)
class ComponentDocumentation:
    """Documentation for a Reflex component."""

    name: Annotated[str, Doc("The name of the component.")]
    description: Annotated[str | None, Doc("The docstring of the component class.")] = (
        None
    )
    props: Annotated[
        tuple[PropDocumentation, ...], Doc("The list of props for the component.")
    ] = ()
    event_handlers: Annotated[
        tuple[EventHandlerDocumentation, ...],
        Doc("The list of event handlers for the component."),
    ] = ()


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

        # If the field has a doc attribute and no Annotated[..., Doc(...)] was found,
        # use the field's doc as the description.
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
