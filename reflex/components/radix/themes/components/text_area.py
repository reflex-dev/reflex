"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal, Optional, Union

from reflex import el
from reflex.components.component import Component
from reflex.components.core.debounce import DebounceInput
from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    RadixThemesComponent,
)

LiteralTextAreaSize = Literal["1", "2", "3"]


class TextArea(RadixThemesComponent, el.Textarea):
    """The input part of a TextArea, may be used by itself."""

    tag = "TextArea"

    # The size of the text area: "1" | "2" | "3"
    size: Optional[Var[LiteralTextAreaSize]] = None

    # The variant of the text area
    variant: Optional[Var[Literal["classic", "surface", "soft"]]] = None

    # The color of the text area
    color_scheme: Optional[Var[LiteralAccentColor]] = None

    # Whether the form control should have autocomplete enabled
    auto_complete: Optional[Var[bool]] = None

    # Automatically focuses the textarea when the page loads
    auto_focus: Optional[Var[bool]] = None

    # Name part of the textarea to submit in 'dir' and 'name' pair when form is submitted
    dirname: Optional[Var[str]] = None

    # Disables the textarea
    disabled: Optional[Var[bool]] = None

    # Associates the textarea with a form (by id)
    form: Optional[Var[Union[str, int, bool]]] = None

    # Maximum number of characters allowed in the textarea
    max_length: Optional[Var[int]] = None

    # Minimum number of characters required in the textarea
    min_length: Optional[Var[int]] = None

    # Name of the textarea, used when submitting the form
    name: Optional[Var[str]] = None

    # Placeholder text in the textarea
    placeholder: Optional[Var[str]] = None

    # Indicates whether the textarea is read-only
    read_only: Optional[Var[bool]] = None

    # Indicates that the textarea is required
    required: Optional[Var[bool]] = None

    # Visible number of lines in the text control
    rows: Optional[Var[str]] = None

    # The controlled value of the textarea, read only unless used with on_change
    value: Optional[Var[str]] = None

    # How the text in the textarea is to be wrapped when submitting the form
    wrap: Optional[Var[str]] = None

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
