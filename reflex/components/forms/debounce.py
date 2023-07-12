"""Wrapper around react-debounce-input."""
from __future__ import annotations

from typing import Any

from reflex.components import Component
from reflex.components.tags import Tag
from reflex.vars import Var


class DebounceInput(Component):
    """The DebounceInput component is used to buffer input events on the client side.

    It is intended to wrap various form controls and should be used whenever a
    fully-controlled input is needed to prevent lost input data when the backend
    is experiencing high latency.
    """

    library = "react-debounce-input"
    tag = "DebounceInput"

    # Minimum input characters before triggering the on_change event
    min_length: Var[int] = 0  # type: ignore

    # Time to wait between end of input and triggering on_change
    debounce_timeout: Var[int] = 100  # type: ignore

    # If true, notify when Enter key is pressed
    force_notify_by_enter: Var[bool] = True  # type: ignore

    # If true, notify when form control loses focus
    force_notify_on_blur: Var[bool] = True  # type: ignore

    def _render(self) -> Tag:
        """Carry first child props directly on this tag.

        Since react-debounce-input wants to create and manage the underlying
        input component itself, we carry all props, events, and styles from
        the child, and then neuter the child's render method so it produces no output.

        Returns:
            The rendered debounce element wrapping the first child element.

        Raises:
            RuntimeError: unless exactly one child element is provided.
        """
        if not self.children or len(self.children) > 1:
            raise RuntimeError(
                "Provide a single child for DebounceInput, such as rx.input() or "
                "rx.text_area()",
            )
        child = self.children[0]
        tag = super()._render()
        tag.add_props(
            **child.event_triggers,
            **props_not_none(child),
            sx=child.style,
            id=child.id,
            class_name=child.class_name,
            element=Var.create("{%s}" % child.tag, is_local=False, is_string=False),
        )
        # do NOT render the child, DebounceInput will create it
        object.__setattr__(child, "render", lambda: "")
        return tag


def props_not_none(c: Component) -> dict[str, Any]:
    """Get all properties of the component that are not None.

    Args:
        c: the component to get_props from

    Returns:
        dict of all props that are not None.
    """
    cdict = {a: getattr(c, a) for a in c.get_props() if getattr(c, a, None) is not None}
    return cdict
