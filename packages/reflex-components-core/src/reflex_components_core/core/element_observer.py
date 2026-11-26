"""Report the size, position and visibility of a DOM element to event triggers."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

from reflex_base.components.component import Component, field
from reflex_base.event import EventHandler, passthrough_event_spec
from reflex_base.utils.format import to_camel_case
from reflex_base.utils.imports import ImportVar
from reflex_base.vars import use_id
from reflex_base.vars.base import LiteralVar, Var

from reflex_components_core.base.fragment import Fragment

# The props the hook takes as options, and the event triggers it reports to.
_OPTIONS = ("layout", "disabled", "threshold", "root_margin")
_TRIGGERS = ("on_resize", "on_move", "on_intersect", "on_transition_end")


class ElementObserver(Fragment):
    """Reports the size, position and visibility of an element to event triggers.

    Renders its child unchanged, so it adds nothing to the page.
    """

    target: Var[str] = field(
        doc="The id of the element to observe, which may come onto the page later or pass to another element. Defaults to the id of the only child, which gets a generated one if it has none."
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

    on_resize: EventHandler[passthrough_event_spec(float, float)] = field(
        doc="Fired with the element's width and height in pixels, transforms included, when observing starts and whenever its border box changes size. A change of its transform alone does not fire it."
    )

    on_move: EventHandler[passthrough_event_spec(float, float)] = field(
        doc="Fired with the element's left and top edge in pixels from the viewport's when observing starts and whenever they change, after the page or a scroll container scrolled, the window resized or the element resized."
    )

    on_intersect: EventHandler[passthrough_event_spec(bool, float)] = field(
        doc="Fired with whether the element is in the viewport and which fraction of it is, when observing starts and whenever that fraction crosses a threshold."
    )

    on_transition_end: EventHandler[passthrough_event_spec(str)] = field(
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
        generated_id = False
        if "target" not in props:
            if len(children) != 1 or not isinstance(children[0], Component):
                msg = "rx.element_observer needs a `target` id or exactly one child component to observe."
                raise ValueError(msg)
            child = children[0]
            if child.id is None:
                child.id = use_id()
                generated_id = True
            props["target"] = child.id
        observer = super().create(*children, **props)
        if generated_id:
            # useId differs between the observers that one compiled component
            # renders, as in rx.foreach, but holds only within one compiled
            # component, so the child compiles into the observer's.
            observer._memoization_mode = dataclasses.replace(
                observer._memoization_mode, recursive=False
            )
        return observer  # pyright: ignore[reportReturnType]

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
            to_camel_case(trigger): self.event_triggers[trigger]
            for trigger in _TRIGGERS
            if trigger in self.event_triggers
        }
        if not handlers:
            return []
        options = {
            to_camel_case(prop): value
            for prop in _OPTIONS
            if (value := getattr(self, prop)) is not None
        }
        return [
            Var(
                f"useElementObserver({self.target}, {LiteralVar.create(handlers)}, {LiteralVar.create(options)});"
            )
        ]


element_observer = ElementObserver.create
