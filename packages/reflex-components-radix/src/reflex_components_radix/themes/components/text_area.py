"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex_base.components.component import Component, field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.core.debounce import DebounceInput
from reflex_components_core.el import elements

from reflex_components_radix.themes.base import (
    LiteralAccentColor,
    LiteralRadius,
    RadixThemesComponent,
)

LiteralTextAreaSize = Literal["1", "2", "3"]

LiteralTextAreaResize = Literal["none", "vertical", "horizontal", "both"]


class TextArea(RadixThemesComponent, elements.Textarea):
    """The input part of a TextArea, may be used by itself."""

    tag = "TextArea"

    size: Var[Responsive[LiteralTextAreaSize]] = field(
        doc='The size of the text area: "1" | "2" | "3"'
    )

    variant: Var[Literal["classic", "surface", "soft"]] = field(
        doc="The variant of the text area"
    )

    resize: Var[Responsive[LiteralTextAreaResize]] = field(
        doc='The resize behavior of the text area: "none" | "vertical" | "horizontal" | "both"'
    )

    color_scheme: Var[LiteralAccentColor] = field(doc="The color of the text area")

    radius: Var[LiteralRadius] = field(
        doc='The radius of the text area: "none" | "small" | "medium" | "large" | "full"'
    )

    auto_complete: Var[bool] = field(
        doc="Whether the form control should have autocomplete enabled"
    )

    auto_focus: Var[bool] = field(
        doc="Automatically focuses the textarea when the page loads"
    )

    default_value: Var[str] = field(
        doc="The default value of the textarea when initially rendered"
    )

    dirname: Var[str] = field(
        doc="Name part of the textarea to submit in 'dir' and 'name' pair when form is submitted"
    )

    disabled: Var[bool] = field(doc="Disables the textarea")

    form: Var[str] = field(doc="Associates the textarea with a form (by id)")

    max_length: Var[int] = field(
        doc="Maximum number of characters allowed in the textarea"
    )

    min_length: Var[int] = field(
        doc="Minimum number of characters required in the textarea"
    )

    name: Var[str] = field(doc="Name of the textarea, used when submitting the form")

    placeholder: Var[str] = field(doc="Placeholder text in the textarea")

    read_only: Var[bool] = field(doc="Indicates whether the textarea is read-only")

    required: Var[bool] = field(doc="Indicates that the textarea is required")

    rows: Var[str] = field(doc="Visible number of lines in the text control")

    value: Var[str] = field(
        doc="The controlled value of the textarea, read only unless used with on_change"
    )

    wrap: Var[str] = field(
        doc="How the text in the textarea is to be wrapped when submitting the form"
    )

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

    def add_style(self):
        """Add the style to the component.

        Returns:
            The style of the component.
        """
        added_style: dict[str, dict] = {}
        added_style.setdefault("& textarea", {})
        if "padding" in self.style:
            added_style["& textarea"]["padding"] = self.style.pop("padding")
        return added_style


text_area = TextArea.create
