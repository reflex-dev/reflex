"""Compare the Python API of an rx.ui component with its Radix counterpart.

``rx.button(...)`` becomes ``rx.ui.button(...)`` with the same arguments, so
the props, the values their literals take and the event triggers must match.
"""

from __future__ import annotations

import dataclasses
import types
import typing
from typing import Any

from reflex_base.components.component import Component

from ui_parity.allowlist import Allowlist, ApiEntry


@dataclasses.dataclass(frozen=True)
class ApiDifference:
    """One way the API of a component differs between the two systems.

    Attributes:
        component: The component.
        kind: ``prop`` or ``event`` when only one system has the name,
            ``type`` when the prop takes different values.
        name: The prop or the event trigger.
        reference: The type of the prop or the presence of the name on the
            Radix component, None when it lacks it.
        candidate: The same on the rx.ui component.
    """

    component: str
    kind: str
    name: str
    reference: str | None
    candidate: str | None


def component_class(factory: Any) -> type[Component]:
    """Find the component class behind a name of a namespace.

    Args:
        factory: What ``rx.<name>`` or ``rx.ui.<name>`` is: a ``create``
            method, or a namespace that is called to create its root.

    Returns:
        The class whose ``create`` the name calls.
    """
    create = factory if isinstance(factory, types.MethodType) else factory.__call__
    return typing.cast("type[Component]", create.__self__)


def type_shape(annotation: Any) -> str:
    """Describe a prop's type by what it accepts, not by where it is defined.

    Two systems each define their own literals and containers, so classes are
    named without their module, and the values of a literal and the members of
    a union are sorted.

    Args:
        annotation: The annotation of the prop.

    Returns:
        The description.
    """
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin is typing.Literal:
        return f"Literal[{', '.join(sorted(repr(arg) for arg in args))}]"
    if origin in (typing.Union, types.UnionType):
        return " | ".join(sorted({type_shape(arg) for arg in args}))
    if origin is not None:
        return f"{origin.__name__}[{', '.join(type_shape(arg) for arg in args)}]"
    if annotation is None or annotation is type(None):
        return "None"
    return getattr(annotation, "__name__", repr(annotation))


def diff_api(
    component: str, reference: type[Component], candidate: type[Component]
) -> list[ApiDifference]:
    """Compare the props and event triggers of two component classes.

    Args:
        component: The name of the component.
        reference: The Radix component.
        candidate: The rx.ui component.

    Returns:
        The differences, in order of kind and name.
    """
    events = [set(cls.get_event_triggers()) for cls in (reference, candidate)]
    differences = [
        ApiDifference(
            component=component,
            kind="event",
            name=name,
            reference="trigger" if name in events[0] else None,
            candidate="trigger" if name in events[1] else None,
        )
        for name in events[0] ^ events[1]
    ]
    ours, theirs = reference.get_fields(), candidate.get_fields()
    # A trigger declared as a field is an event, not a prop.
    props = {*reference.get_props(), *candidate.get_props()} - events[0] - events[1]
    for name in props:
        shapes = [
            type_shape(fields[name].annotated_type) if name in fields else None
            for fields in (ours, theirs)
        ]
        if shapes[0] != shapes[1]:
            differences.append(
                ApiDifference(
                    component=component,
                    kind="prop" if None in shapes else "type",
                    name=name,
                    reference=shapes[0],
                    candidate=shapes[1],
                )
            )
    return sorted(differences, key=lambda item: (item.kind, item.name))


def unexplained(
    differences: list[ApiDifference], allowlist: Allowlist
) -> tuple[list[ApiDifference], list[tuple[ApiEntry, str]]]:
    """Hold the differences of the API to the allowlist.

    Args:
        differences: Every difference found, of any component.
        allowlist: The intended differences.

    Returns:
        The differences the allowlist does not list, and the names it lists
        that are not differences any more, each with its entry.
    """
    listed = {
        (entry.component, entry.kind, name): entry
        for entry in allowlist.api
        for name in entry.names
    }
    found = {(item.component, item.kind, item.name) for item in differences}
    return (
        [
            item
            for item in differences
            if (item.component, item.kind, item.name) not in listed
        ],
        [(entry, key[2]) for key, entry in listed.items() if key not in found],
    )
