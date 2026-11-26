"""Report the size, position and visibility of a DOM element to event triggers."""

from __future__ import annotations

from collections.abc import Sequence

from reflex_base.components.component import Component, field
from reflex_base.event import EventHandler
from reflex_base.utils.imports import ImportVar
from reflex_base.vars import get_unique_variable_name
from reflex_base.vars.base import LiteralVar, Var

from reflex_components_core.base.fragment import Fragment


def _size_spec(width: Var[float], height: Var[float]) -> tuple[Var[float], Var[float]]:
    """Args spec for the on_resize event trigger.

    Args:
        width: The element's width in pixels.
        height: The element's height in pixels.

    Returns:
        The element's width and height.
    """
    return (width, height)


def _position_spec(x: Var[float], y: Var[float]) -> tuple[Var[float], Var[float]]:
    """Args spec for the on_move event trigger.

    Args:
        x: The element's left edge, in pixels from the left of the viewport.
        y: The element's top edge, in pixels from the top of the viewport.

    Returns:
        The element's position.
    """
    return (x, y)


def _intersect_spec(
    is_intersecting: Var[bool], ratio: Var[float]
) -> tuple[Var[bool], Var[float]]:
    """Args spec for the on_intersect event trigger.

    Args:
        is_intersecting: Whether the element is in the viewport.
        ratio: The fraction of the element in the viewport, between 0 and 1.

    Returns:
        Whether the element is in the viewport, and which fraction of it.
    """
    return (is_intersecting, ratio)


def _transition_end_spec(property_name: Var[str]) -> tuple[Var[str]]:
    """Args spec for the on_transition_end event trigger.

    Args:
        property_name: The CSS property whose transition ended.

    Returns:
        The CSS property whose transition ended.
    """
    return (property_name,)


# The event triggers the hook reports to, by the name it takes them under.
_HANDLERS = {
    "on_resize": "onResize",
    "on_move": "onMove",
    "on_intersect": "onIntersect",
    "on_transition_end": "onTransitionEnd",
}

# The props the hook takes as options, by the name it takes them under.
_OPTIONS = {
    "layout": "layout",
    "disabled": "disabled",
    "threshold": "threshold",
    "root_margin": "rootMargin",
}


class ElementObserver(Fragment):
    """Reports the size, position and visibility of an element to event triggers.

    Renders its child unchanged, so it adds nothing to the page.
    """

    target: Var[str] = field(
        doc="The id of the element to observe. Defaults to the id of the only child, which gets a generated one if it has none."
    )

    threshold: Var[float | Sequence[float]] = field(
        doc="The fractions of the element in view at which on_intersect fires, as for an IntersectionObserver. Defaults to 0: when the element enters or leaves the viewport."
    )

    root_margin: Var[str] = field(
        doc="Grows or shrinks the viewport for on_intersect, in CSS margin syntax such as '-100px 0px 0px 0px'. Defaults to '0px'."
    )

    layout: Var[bool] = field(
        doc="Start observing in a layout effect, so the first on_resize and on_move fire before the browser paints and client state they set is in the first frame."
    )

    disabled: Var[bool] = field(
        doc="Stop observing while true. Observing starts again, with a first report, once it is false."
    )

    on_resize: EventHandler[_size_spec] = field(
        doc="Fired with the element's width and height in pixels when observing starts and whenever they change."
    )

    on_move: EventHandler[_position_spec] = field(
        doc="Fired with the element's left and top edge in pixels from the viewport's when observing starts and whenever they change, after the page or a scroll container scrolled, the window resized or the element resized."
    )

    on_intersect: EventHandler[_intersect_spec] = field(
        doc="Fired with whether the element is in the viewport and which fraction of it is, when observing starts and whenever that fraction crosses a threshold."
    )

    on_transition_end: EventHandler[_transition_end_spec] = field(
        doc="Fired with the property name when a CSS transition of the element itself ends. Transitions of its descendants do not fire it."
    )

    @classmethod
    def create(cls, *children, **props) -> ElementObserver:
        """Create an ElementObserver component.

        Args:
            *children: The children to render. Without a target, the only child is observed.
            **props: The props of the component.

        Returns:
            The ElementObserver component.

        Raises:
            ValueError: If there is no target and not exactly one child component to observe.
        """
        if "target" not in props:
            if len(children) != 1 or not isinstance(children[0], Component):
                msg = "rx.element_observer needs a `target` id or exactly one child component to observe."
                raise ValueError(msg)
            child = children[0]
            if child.id is None:
                child.id = f"element_observer_{get_unique_variable_name()}"
            props["target"] = child.id
        return super().create(*children, **props)  # pyright: ignore[reportReturnType]

    def _exclude_props(self) -> list[str]:
        """Keep the observer's props off the rendered fragment.

        Returns:
            The props the fragment does not render.
        """
        return [
            *super()._exclude_props(),
            "target",
            *_OPTIONS,
            *self.event_triggers,
        ]

    def add_imports(self) -> dict[str, ImportVar]:
        """Add the hook that observes the element.

        Returns:
            The import dict for the component.
        """
        return {
            "$/utils/helpers/element_observer": ImportVar(
                tag="useElementObserver", is_default=True
            ),
        }

    def add_hooks(self) -> list[str | Var]:
        """Add the hook that observes the element and calls the event triggers.

        Returns:
            The hook, or none without an event trigger it reports to.
        """
        handlers = {
            js_name: self.event_triggers[trigger]
            for trigger, js_name in _HANDLERS.items()
            if trigger in self.event_triggers
        }
        if not handlers:
            return []
        options = {
            js_name: value
            for prop, js_name in _OPTIONS.items()
            if (value := getattr(self, prop)) is not None
        }
        return [
            Var(
                f"useElementObserver({self.target}, {LiteralVar.create(handlers)}, {LiteralVar.create(options)});"
            )
        ]


element_observer = ElementObserver.create
