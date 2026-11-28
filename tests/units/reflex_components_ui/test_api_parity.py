"""The Python API of every rx.ui component is the Radix component's.

``rx.button(...)`` becomes ``rx.ui.button(...)`` with the same arguments. An
intended difference is an ``[[api]]`` entry of the parity allowlist, with the
reason the migration guide gives for it.
"""

import functools
import types
from typing import Any, Literal

import pytest
import reflex_components_ui
from reflex_base.components.component import Component, ComponentNamespace
from reflex_base.event import EventHandler, no_args_event_spec
from reflex_base.vars.base import Var
from reflex_components_ui.base import UIComponent
from reflex_components_ui.layout.box import Box
from ui_parity import allowlist
from ui_parity.allowlist import Allowlist, ApiEntry
from ui_parity.api import (
    ApiDifference,
    component_class,
    diff_api,
    type_shape,
    unexplained,
)

import reflex as rx


def members(namespace: ComponentNamespace) -> list[str]:
    """List the components a namespace creates beside the one it is called for.

    Args:
        namespace: A namespace of components, such as ``rx.text``.

    Returns:
        The names of its members, sorted.
    """
    return sorted(
        name
        for name in dir(namespace)
        if not name.startswith("_")
        and isinstance(getattr(namespace, name), types.MethodType)
    )


def component_names() -> list[str]:
    """List the names of rx.ui that create a component.

    A theme of the plugin and the design tokens are no components. A
    namespace is its own name when it is called, then each of its members:
    ``text``, ``text.em``.

    Returns:
        The names, sorted.
    """
    names = []
    for name in reflex_components_ui.__all__:
        value = getattr(reflex_components_ui, name)
        if isinstance(value, types.MethodType):
            names.append(name)
        elif isinstance(value, ComponentNamespace):
            # A namespace that is not called has members only.
            if callable(value):
                names.append(name)
            names.extend(f"{name}.{member}" for member in members(value))
    return sorted(names)


COMPONENTS = component_names()


def resolve(namespace: Any, component: str) -> Any:
    """Find a component by its name in a namespace.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        component: The name, dotted for a member of a namespace.

    Returns:
        What creates the component.
    """
    return functools.reduce(getattr, component.split("."), namespace)


def differences(component: str) -> list[ApiDifference]:
    """Compare a component of rx.ui with the one of the same name in rx.

    Args:
        component: The name of the component.

    Returns:
        The differences of their APIs.
    """
    return diff_api(
        component,
        component_class(resolve(rx, component)),
        component_class(resolve(reflex_components_ui, component)),
    )


def test_every_wave_is_in_the_namespace():
    assert COMPONENTS == [
        "aspect_ratio",
        "avatar",
        "badge",
        "blockquote",
        "box",
        "button",
        "callout",
        "callout.icon",
        "callout.root",
        "callout.text",
        "card",
        "center",
        "checkbox",
        "checkbox_cards.item",
        "checkbox_cards.root",
        "checkbox_group.item",
        "checkbox_group.root",
        "code",
        "container",
        "data_list.item",
        "data_list.label",
        "data_list.root",
        "data_list.value",
        "divider",
        "flex",
        "grid",
        "heading",
        "hstack",
        "icon_button",
        "inset",
        "link",
        "list",
        "list.item",
        "list.ordered",
        "list.unordered",
        "list_item",
        "ordered_list",
        "progress",
        "radio",
        "radio.item",
        "radio.root",
        "radio_cards.item",
        "radio_cards.root",
        "radio_group",
        "radio_group.item",
        "radio_group.root",
        "scroll_area",
        "section",
        "separator",
        "skeleton",
        "spacer",
        "spinner",
        "stack",
        "switch",
        "table.body",
        "table.cell",
        "table.column_header_cell",
        "table.header",
        "table.root",
        "table.row",
        "table.row_header_cell",
        "text",
        "text.em",
        "text.kbd",
        "text.quote",
        "text.span",
        "text.strong",
        "theme",
        "unordered_list",
        "vstack",
    ]


@pytest.mark.parametrize(
    "namespace",
    [
        "callout",
        "checkbox",
        "data_list",
        "list",
        "radio",
        "radio_group",
        "table",
        "text",
    ],
)
def test_namespace_has_the_members_of_its_radix_counterpart(namespace: str):
    assert members(getattr(reflex_components_ui, namespace)) == members(
        getattr(rx, namespace)
    )


def test_every_component_has_the_api_of_its_radix_counterpart():
    found = [item for name in COMPONENTS for item in differences(name)]
    unlisted, stale = unexplained(found, allowlist.load())
    assert unlisted == [], (
        "rx.ui differs from rx: match the Radix component, or list the "
        "difference under [[api]] in allowlist.toml with its reason."
    )
    assert stale == [], "These [[api]] names are differences no more: remove them."


def wrapper(without: str | None = None) -> type[Component]:
    """Fork the Radix box as a wave does: a wrapper with the same props.

    Args:
        without: A prop to leave out of the wrapper.

    Returns:
        The wrapper.
    """
    reference = component_class(rx.box)
    fields = reference.get_fields()
    return type(
        "Box",
        (UIComponent,),
        {
            "__annotations__": {
                name: fields[name].annotated_type
                for name in reference.get_props()
                if name != without
            },
            "__module__": __name__,
        },
    )


def test_box_wrapper_with_every_prop_has_no_difference():
    assert diff_api("box", component_class(rx.box), wrapper()) == []


def test_removing_a_prop_from_the_wrapper_is_a_difference():
    found = diff_api("box", component_class(rx.box), wrapper(without="title"))
    assert found == [
        ApiDifference(
            component="box",
            kind="prop",
            name="title",
            reference="Var[str]",
            candidate=None,
        )
    ]
    # The parity test fails on it: nothing lists the difference.
    assert unexplained(found, Allowlist()) == (found, [])


def test_box_has_the_props_of_the_radix_box_and_nothing_is_allowlisted():
    assert differences("box") == []
    assert allowlist.load().api == ()


class Reference(Component):
    """A component as Radix has it."""

    size: Var[Literal["1", "2", "3"]]
    variant: Var[Literal["solid", "soft"]]
    loading: Var[bool]
    on_open_change: EventHandler[no_args_event_spec]


class Candidate(Component):
    """Its fork: a size less, a renamed prop, another trigger."""

    size: Var[Literal["2", "1"]]
    variant: Var[Literal["soft", "solid"]]
    busy: Var[bool]
    on_toggle: EventHandler[no_args_event_spec]


def test_diff_api_finds_props_types_and_event_triggers():
    assert diff_api("thing", Reference, Candidate) == [
        ApiDifference("thing", "event", "on_open_change", "trigger", None),
        ApiDifference("thing", "event", "on_toggle", None, "trigger"),
        ApiDifference("thing", "prop", "busy", None, "Var[bool]"),
        ApiDifference("thing", "prop", "loading", "Var[bool]", None),
        ApiDifference(
            "thing",
            "type",
            "size",
            "Var[Literal['1', '2', '3']]",
            "Var[Literal['1', '2']]",
        ),
    ]


def test_unexplained_separates_the_unlisted_from_the_stale():
    found = diff_api("thing", Reference, Candidate)
    listed = ApiEntry(
        component="thing",
        kind="prop",
        names=("busy", "loading", "color"),
        reason="Renamed.",
    )
    other = ApiEntry(
        component="other", kind="event", names=("on_toggle",), reason="Another."
    )
    assert unexplained(found, Allowlist(api=(listed, other))) == (
        [found[0], found[1], found[4]],
        [(listed, "color"), (other, "on_toggle")],
    )


def test_type_shape_ignores_where_a_type_is_defined_and_its_order():
    responsive: Any = Var[Literal["2", "1"] | dict[str, Literal["1", "2"]]]
    assert type_shape(responsive) == (
        "Var[Literal['1', '2'] | dict[str, Literal['1', '2']]]"
    )
    assert type_shape(Var[int | None]) == "Var[None | int]"
    assert type_shape(Box) == "Box"


def test_component_class_reads_a_factory_and_a_namespace():
    assert component_class(rx.ui.box) is Box
    assert component_class(rx.select).__name__ == "HighLevelSelect"
