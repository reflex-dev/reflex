"""The Python API of every rx.ui component is the Radix component's.

``rx.button(...)`` becomes ``rx.ui.button(...)`` with the same arguments. An
intended difference is an ``[[api]]`` entry of the parity allowlist, with the
reason the migration guide gives for it.
"""

import types
from typing import Any, Literal

import reflex_components_ui
from reflex_base.components.component import Component
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

# The names of the namespace that create a component: a theme of the plugin
# and the design tokens are no components.
COMPONENTS = sorted(
    name
    for name in reflex_components_ui.__all__
    if isinstance(getattr(reflex_components_ui, name), types.MethodType)
)


def differences(component: str) -> list[ApiDifference]:
    """Compare a component of rx.ui with the one of the same name in rx.

    Args:
        component: The name of the component.

    Returns:
        The differences of their APIs.
    """
    return diff_api(
        component,
        component_class(getattr(rx, component)),
        component_class(getattr(reflex_components_ui, component)),
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


def test_box_differs_only_by_the_props_the_allowlist_gives_a_reason_for():
    found = differences("box")
    (entry,) = (item for item in allowlist.load().api if item.component == "box")
    assert entry.kind == "prop"
    assert [(item.kind, item.name, item.candidate) for item in found] == [
        ("prop", name, None) for name in entry.names
    ]


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
