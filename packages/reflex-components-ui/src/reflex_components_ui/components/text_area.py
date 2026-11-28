"""A text area: a box around a native textarea."""

from __future__ import annotations

import functools
from typing import ClassVar, Literal

from reflex_base.components.component import Component, field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.el import elements

from reflex_components_ui.base import UIComponent
from reflex_components_ui.components.text_field import DebouncedControl, control_props
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.text_area import TEXT_AREA, TEXT_AREA_INPUT
from reflex_components_ui.themes import LiteralAccentColor, LiteralRadius

LiteralTextAreaSize = Literal["1", "2", "3"]
LiteralTextAreaResize = Literal["none", "vertical", "horizontal", "both"]


class TextAreaInput(UIComponent, elements.Textarea):
    """The textarea of a text area."""

    tag = "textarea"

    styles: ClassVar[ComponentStyles] = TEXT_AREA_INPUT

    @classmethod
    @functools.cache
    def _style_props(cls) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Get the props that are read as styles rather than rendered.

        Returns:
            The layout props and the variants. The rows of a textarea are
            its lines, an attribute, and not the rows of a grid.
        """
        layout_props, variants = super()._style_props()  # pyright: ignore[reportAttributeAccessIssue]
        return tuple(prop for prop in layout_props if prop != "rows"), variants

    def _post_init(self, *args, **kwargs):
        """Initialize the textarea, with the look its box gives it.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component. ``box`` holds the
                size and the variant of the box.
        """
        # What the style table reads as variants.
        self._size, self._variant = kwargs.pop("box")
        super()._post_init(*args, **kwargs)


class TextArea(UIComponent, elements.Textarea):
    """The input part of a TextArea, may be used by itself."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = TEXT_AREA

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

        The size, the variant, the resize behavior, the color, the radius
        and the styles are the ones of the box, and every other prop is
        given to the textarea inside it: its attributes, its ``id`` and its
        event triggers. A ``padding`` is the one of the textarea.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The component.
        """
        own = control_props(props, elements.Textarea)
        padding = props.pop("padding", None)
        if padding is not None:
            own["style"] = {"padding": padding}
        # Marked for the rule of the thumb of its scrollbar.
        own.setdefault("custom_attrs", {})["data-rx-text-area-input"] = ""
        control: Component = TextAreaInput.create(
            *children, box=(props.get("size"), props.get("variant")), **own
        )
        if own.get("value") is not None and own.get("on_change") is not None:
            # create a debounced input if the user requests full control to avoid typing jank
            control = DebouncedControl.create(control)  # pyright: ignore[reportArgumentType]
        return super().create(control, **props)


text_area = TextArea.create
