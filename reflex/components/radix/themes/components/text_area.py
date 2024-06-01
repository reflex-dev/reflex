"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal, Union

from reflex.components.component import Component
from reflex.components.core.debounce import DebounceInput
from reflex.components.el import elements
from reflex.constants import EventTriggers
from reflex.vars import Var

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
    size: Var[LiteralTextAreaSize]

    # The variant of the text area
    variant: Var[Literal["classic", "surface", "soft"]]

    # The resize behavior of the text area: "none" | "vertical" | "horizontal" | "both"
    resize: Var[LiteralTextAreaResize]

    # The color of the text area
    color_scheme: Var[LiteralAccentColor]

    # The radius of the text area: "none" | "small" | "medium" | "large" | "full"
    radius: Var[LiteralRadius]

    # Whether the form control should have autocomplete enabled
    auto_complete: Var[bool]

    # Automatically focuses the textarea when the page loads
    auto_focus: Var[bool]

    # Name part of the textarea to submit in 'dir' and 'name' pair when form is submitted
    dirname: Var[str]

    # Disables the textarea
    disabled: Var[bool]

    # Associates the textarea with a form (by id)
    form: Var[Union[str, int, bool]]

    # Maximum number of characters allowed in the textarea
    max_length: Var[int]

    # Minimum number of characters required in the textarea
    min_length: Var[int]

    # Name of the textarea, used when submitting the form
    name: Var[str]

    # Placeholder text in the textarea
    placeholder: Var[str]

    # Indicates whether the textarea is read-only
    read_only: Var[bool]

    # Indicates that the textarea is required
    required: Var[bool]

    # Visible number of lines in the text control
    rows: Var[str]

    # The controlled value of the textarea, read only unless used with on_change
    value: Var[str]

    # How the text in the textarea is to be wrapped when submitting the form
    wrap: Var[str]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an Input component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The component.
        """
        if props.get("value") is not None and props.get("on_change"):
            # create a debounced input if the user requests full control to avoid typing jank
            return DebounceInput.create(super().create(*children, **props))
        return super().create(*children, **props)

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_CHANGE: lambda e0: [e0.target.value],
            EventTriggers.ON_FOCUS: lambda e0: [e0.target.value],
            EventTriggers.ON_BLUR: lambda e0: [e0.target.value],
            EventTriggers.ON_KEY_DOWN: lambda e0: [e0.key],
            EventTriggers.ON_KEY_UP: lambda e0: [e0.key],
        }


text_area = TextArea.create
