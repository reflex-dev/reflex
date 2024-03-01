"""Popover components."""
from __future__ import annotations

from typing import Any, Optional, Union

from reflex.components.chakra import (
    ChakraComponent,
    LiteralChakraDirection,
    LiteralMenuStrategy,
    LiteralPopOverTrigger,
)
from reflex.components.component import Component
from reflex.vars import Var


class Popover(ChakraComponent):
    """The wrapper that provides props, state, and context to its children."""

    tag: str = "Popover"

    # The padding required to prevent the arrow from reaching the very edge of the popper.
    arrow_padding: Optional[Var[int]] = None

    # The `box-shadow` of the popover arrow
    arrow_shadow_color: Optional[Var[str]] = None

    # The size of the popover arrow
    arrow_size: Optional[Var[int]] = None

    # If true, focus will be transferred to the first interactive element when the popover opens
    auto_focus: Optional[Var[bool]] = None

    # The boundary area for the popper. Used within the preventOverflow modifier
    boundary: Optional[Var[str]] = None

    # If true, the popover will close when you blur out it by clicking outside or tabbing out
    close_on_blur: Optional[Var[bool]] = None

    # If true, the popover will close when you hit the Esc key
    close_on_esc: Optional[Var[bool]] = None

    # If true, the popover will be initially opened.
    default_is_open: Optional[Var[bool]] = None

    # Theme direction ltr or rtl. Popper's placement will be set accordingly
    direction: Optional[Var[LiteralChakraDirection]] = None

    # If true, the popper will change its placement and flip when it's about to overflow its boundary area.
    flip: Optional[Var[bool]] = None

    # The distance or margin between the reference and popper. It is used internally to create an offset modifier. NB: If you define offset prop, it'll override the gutter.
    gutter: Optional[Var[int]] = None

    # The html id attribute of the popover. If not provided, we generate a unique id. This id is also used to auto-generate the `aria-labelledby` and `aria-describedby` attributes that points to the PopoverHeader and PopoverBody
    id_: Optional[Var[str]] = None

    # Performance 🚀: If true, the PopoverContent rendering will be deferred until the popover is open.
    is_lazy: Optional[Var[bool]] = None

    # Performance 🚀: The lazy behavior of popover's content when not visible. Only works when `isLazy={true}` - "unmount": The popover's content is always unmounted when not open. - "keepMounted": The popover's content initially unmounted, but stays mounted when popover is open.
    lazy_behavior: Optional[Var[str]] = None

    # If true, the popover will be opened in controlled mode.
    is_open: Optional[Var[bool]] = None

    # If true, the popper will match the width of the reference at all times. It's useful for autocomplete, `date-picker` and select patterns.
    match_width: Optional[Var[bool]] = None

    # The placement of the popover. It's used internally by Popper.js.
    placement: Optional[Var[str]] = None

    # If true, will prevent the popper from being cut off and ensure it's visible within the boundary area.
    prevent_overflow: Optional[Var[bool]] = None

    # If true, focus will be returned to the element that triggers the popover when it closes
    return_focus_on_close: Optional[Var[bool]] = None

    # The CSS positioning strategy to use. ("fixed" | "absolute")
    strategy: Optional[Var[LiteralMenuStrategy]] = None

    # The interaction that triggers the popover. hover - means the popover will open when you hover with mouse or focus with keyboard on the popover trigger click - means the popover will open on click or press Enter to Space on keyboard ("click" | "hover")
    trigger: Optional[Var[LiteralPopOverTrigger]] = None

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers for the component.

        Returns:
            The event triggers.
        """
        return {
            **super().get_event_triggers(),
            "on_close": lambda: [],
            "on_open": lambda: [],
        }

    @classmethod
    def create(
        cls,
        *children,
        trigger=None,
        header=None,
        body=None,
        footer=None,
        use_close_button=False,
        **props,
    ) -> Component:
        """Create a popover component.

        Args:
            *children: The children of the component.
            trigger: The trigger that opens the popover.
            header: The header of the popover.
            body: The body of the popover.
            footer: The footer of the popover.
            use_close_button: Whether to add a close button on the popover.
            **props: The properties of the component.

        Returns:
            The popover component.
        """
        if len(children) == 0:
            contents = []

            trigger = PopoverTrigger.create(trigger)

            # add header if present in props
            if header:
                contents.append(PopoverHeader.create(header))

            if body:
                contents.append(PopoverBody.create(body))

            if footer:
                contents.append(PopoverFooter.create(footer))

            if use_close_button:
                contents.append(PopoverCloseButton.create())

            children = [trigger, PopoverContent.create(*contents)]

        return super().create(*children, **props)


class PopoverContent(ChakraComponent):
    """The popover itself."""

    tag: str = "PopoverContent"


class PopoverHeader(ChakraComponent):
    """The header of the popover."""

    tag: str = "PopoverHeader"


class PopoverFooter(ChakraComponent):
    """Display a popover footer."""

    tag: str = "PopoverFooter"


class PopoverBody(ChakraComponent):
    """The body of the popover."""

    tag: str = "PopoverBody"


class PopoverArrow(ChakraComponent):
    """A visual arrow that points to the reference (or trigger)."""

    tag: str = "PopoverArrow"


class PopoverCloseButton(ChakraComponent):
    """A button to close the popover."""

    tag: str = "PopoverCloseButton"


class PopoverAnchor(ChakraComponent):
    """Used to wrap the position-reference element."""

    tag: str = "PopoverAnchor"


class PopoverTrigger(ChakraComponent):
    """Used to wrap the reference (or trigger) element."""

    tag: str = "PopoverTrigger"
