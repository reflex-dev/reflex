"""Popover components."""
from __future__ import annotations

from typing import Any, Union

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

    tag = "Popover"

    # The padding required to prevent the arrow from reaching the very edge of the popper.
    arrow_padding: Var[int]

    # The `box-shadow` of the popover arrow
    arrow_shadow_color: Var[str]

    # The size of the popover arrow
    arrow_size: Var[int]

    # If true, focus will be transferred to the first interactive element when the popover opens
    auto_focus: Var[bool]

    # The boundary area for the popper. Used within the preventOverflow modifier
    boundary: Var[str]

    # If true, the popover will close when you blur out it by clicking outside or tabbing out
    close_on_blur: Var[bool]

    # If true, the popover will close when you hit the Esc key
    close_on_esc: Var[bool]

    # If true, the popover will be initially opened.
    default_is_open: Var[bool]

    # Theme direction ltr or rtl. Popper's placement will be set accordingly
    direction: Var[LiteralChakraDirection]

    # If true, the popper will change its placement and flip when it's about to overflow its boundary area.
    flip: Var[bool]

    # The distance or margin between the reference and popper. It is used internally to create an offset modifier. NB: If you define offset prop, it'll override the gutter.
    gutter: Var[int]

    # The html id attribute of the popover. If not provided, we generate a unique id. This id is also used to auto-generate the `aria-labelledby` and `aria-describedby` attributes that points to the PopoverHeader and PopoverBody
    id_: Var[str]

    # Performance 🚀: If true, the PopoverContent rendering will be deferred until the popover is open.
    is_lazy: Var[bool]

    # Performance 🚀: The lazy behavior of popover's content when not visible. Only works when `isLazy={true}` - "unmount": The popover's content is always unmounted when not open. - "keepMounted": The popover's content initially unmounted, but stays mounted when popover is open.
    lazy_behavior: Var[str]

    # If true, the popover will be opened in controlled mode.
    is_open: Var[bool]

    # If true, the popper will match the width of the reference at all times. It's useful for autocomplete, `date-picker` and select patterns.
    match_width: Var[bool]

    # The placement of the popover. It's used internally by Popper.js.
    placement: Var[str]

    # If true, will prevent the popper from being cut off and ensure it's visible within the boundary area.
    prevent_overflow: Var[bool]

    # If true, focus will be returned to the element that triggers the popover when it closes
    return_focus_on_close: Var[bool]

    # The CSS positioning strategy to use. ("fixed" | "absolute")
    strategy: Var[LiteralMenuStrategy]

    # The interaction that triggers the popover. hover - means the popover will open when you hover with mouse or focus with keyboard on the popover trigger click - means the popover will open on click or press Enter to Space on keyboard ("click" | "hover")
    trigger: Var[LiteralPopOverTrigger]

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

    tag = "PopoverContent"


class PopoverHeader(ChakraComponent):
    """The header of the popover."""

    tag = "PopoverHeader"


class PopoverFooter(ChakraComponent):
    """Display a popover footer."""

    tag = "PopoverFooter"


class PopoverBody(ChakraComponent):
    """The body of the popover."""

    tag = "PopoverBody"


class PopoverArrow(ChakraComponent):
    """A visual arrow that points to the reference (or trigger)."""

    tag = "PopoverArrow"


class PopoverCloseButton(ChakraComponent):
    """A button to close the popover."""

    tag = "PopoverCloseButton"


class PopoverAnchor(ChakraComponent):
    """Used to wrap the position-reference element."""

    tag = "PopoverAnchor"


class PopoverTrigger(ChakraComponent):
    """Used to wrap the reference (or trigger) element."""

    tag = "PopoverTrigger"
