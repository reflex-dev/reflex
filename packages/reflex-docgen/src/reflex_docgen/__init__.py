"""Module for generating documentation for Reflex components."""

from dataclasses import dataclass
from typing import Annotated, Any, get_type_hints

from typing_extensions import Doc
from typing_inspection.introspection import (
    AnnotationSource,
    InspectedAnnotation,
    inspect_annotation,
)

from reflex.components.component import Component


@dataclass(frozen=True, slots=True, kw_only=True)
class PropDocumentation:
    """Hold information about a prop."""

    name: Annotated[str, Doc("The name of the prop.")]

    type: Annotated[Any, Doc("The type of the prop.")]

    description: Annotated[str | None, Doc("The description of the prop.")]

    default_value: Annotated[str | None, Doc("The default value of the prop.")]


@dataclass(frozen=True, slots=True, kw_only=True)
class ComponentDocumentation:
    """Documentation for a Reflex component."""

    name: Annotated[str, Doc("The name of the component.")]
    props: Annotated[
        tuple[PropDocumentation, ...], Doc("The list of props for the component.")
    ] = ()


def get_prop(
    prop_name: str, prop_annotated_type: InspectedAnnotation
) -> PropDocumentation:
    """Get a Prop object from a prop name and annotated type.

    Args:
        prop_name: The name of the prop.
        prop_annotated_type: The annotated type of the prop.

    Returns:
        The Prop object for the prop.
    """
    doc = next(
        (
            annotation.documentation
            for annotation in prop_annotated_type.metadata
            if isinstance(annotation, Doc)
        ),
        None,
    )
    if doc is not None:
        default_value = None
        for default_indicator in ["Defaults to", "Default:"]:
            if default_indicator in doc:
                doc, default_value = doc.split(default_indicator, maxsplit=1)
                default_value = default_value.strip().rstrip(".")
                doc = doc.strip().rstrip(".")
                break
    else:
        default_value = None
    return PropDocumentation(
        name=prop_name,
        type=prop_annotated_type.type,
        description=doc.rstrip(".") + "." if doc else None,
        default_value=default_value,
    )


def get_component_props(
    component_cls: type[Component],
) -> tuple[PropDocumentation, ...]:
    """Get the props for a Reflex component.

    Args:
        component_cls: The component class to get the props for.

    Returns:
        The props for the component.
    """
    props = component_cls.get_props()
    hints = get_type_hints(component_cls, include_extras=True)

    return tuple(
        get_prop(
            prop_name,
            inspect_annotation(
                hints[prop_name], annotation_source=AnnotationSource.CLASS
            ),
        )
        for prop_name in props
    )


def generate_documentation(component_cls: type[Component]) -> ComponentDocumentation:
    """Generate documentation for a Reflex component.

    Args:
        component_cls: The component class to generate documentation for.

    Returns:
        The generated documentation for the component.
    """
    return ComponentDocumentation(
        name=component_cls.__name__, props=get_component_props(component_cls)
    )
