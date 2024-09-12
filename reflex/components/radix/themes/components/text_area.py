"""Interactive components provided by @radix-ui/themes."""

from typing import Literal, Union

from reflex.components.component import Component
from reflex.components.core.breakpoints import Responsive
from reflex.components.core.debounce import DebounceInput
from reflex.components.el import elements
from reflex.event import EventHandler
from reflex.ivars.base import ImmutableVar

from ..base import (
    LiteralAccentColor,
    LiteralRadius,
    RadixThemesComponent,
)

LiteralTextAreaSize = Literal["1", "2", "3"]

LiteralTextAreaResize = Literal["none", "vertical", "horizontal", "both"]


class TextArea(RadixThemesComponent, elements.Textarea):
    """The input part of a TextArea, may be used by itself."""

    tag = "TextArea"

    # The size of the text area: "1" | "2" | "3"
    size: ImmutableVar[Responsive[LiteralTextAreaSize]]

    # The variant of the text area
    variant: ImmutableVar[Literal["classic", "surface", "soft"]]

    # The resize behavior of the text area: "none" | "vertical" | "horizontal" | "both"
    resize: ImmutableVar[Responsive[LiteralTextAreaResize]]

    # The color of the text area
    color_scheme: ImmutableVar[LiteralAccentColor]

    # The radius of the text area: "none" | "small" | "medium" | "large" | "full"
    radius: ImmutableVar[LiteralRadius]

    # Whether the form control should have autocomplete enabled
    auto_complete: ImmutableVar[bool]

    # Automatically focuses the textarea when the page loads
    auto_focus: ImmutableVar[bool]

    # Name part of the textarea to submit in 'dir' and 'name' pair when form is submitted
    dirname: ImmutableVar[str]

    # Disables the textarea
    disabled: ImmutableVar[bool]

    # Associates the textarea with a form (by id)
    form: ImmutableVar[Union[str, int, bool]]

    # Maximum number of characters allowed in the textarea
    max_length: ImmutableVar[int]

    # Minimum number of characters required in the textarea
    min_length: ImmutableVar[int]

    # Name of the textarea, used when submitting the form
    name: ImmutableVar[str]

    # Placeholder text in the textarea
    placeholder: ImmutableVar[str]

    # Indicates whether the textarea is read-only
    read_only: ImmutableVar[bool]

    # Indicates that the textarea is required
    required: ImmutableVar[bool]

    # Visible number of lines in the text control
    rows: ImmutableVar[str]

    # The controlled value of the textarea, read only unless used with on_change
    value: ImmutableVar[str]

    # How the text in the textarea is to be wrapped when submitting the form
    wrap: ImmutableVar[str]

    # Fired when the value of the textarea changes.
    on_change: EventHandler[lambda e0: [e0.target.value]]

    # Fired when the textarea is focused.
    on_focus: EventHandler[lambda e0: [e0.target.value]]

    # Fired when the textarea is blurred.
    on_blur: EventHandler[lambda e0: [e0.target.value]]

    # Fired when a key is pressed down.
    on_key_down: EventHandler[lambda e0: [e0.key]]

    # Fired when a key is released.
    on_key_up: EventHandler[lambda e0: [e0.key]]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an Input component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The component.
        """
        if props.get("value") is not None and props.get("on_change") is not None:
            # create a debounced input if the user requests full control to avoid typing jank
            return DebounceInput.create(super().create(*children, **props))
        return super().create(*children, **props)


text_area = TextArea.create
