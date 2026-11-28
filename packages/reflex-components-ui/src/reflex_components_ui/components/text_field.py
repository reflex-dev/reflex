"""A text field: a box around a native input, with slots for icons and buttons."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.components.tags import CommonTag
from reflex_base.event import EventHandler, input_event, key_event
from reflex_base.utils.imports import ImportVar
from reflex_base.utils.types import is_optional, safe_issubclass, value_inside_optional
from reflex_base.vars.base import Var, VarData
from reflex_base.vars.number import ternary_operation
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.core.debounce import DebounceInput
from reflex_components_core.el import elements

from reflex_components_ui.base import UIComponent
from reflex_components_ui.components._group import literal
from reflex_components_ui.constants import WEB_DIR
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.text_field import (
    TEXT_FIELD,
    TEXT_FIELD_INPUT,
    TEXT_FIELD_SLOT,
)
from reflex_components_ui.themes import LiteralAccentColor, LiteralRadius

LiteralTextFieldSize = Literal["1", "2", "3"]
LiteralTextFieldVariant = Literal["classic", "surface", "soft"]

# The `onPointerDown` of a box with slots: a pointer on a slot or on the edge
# of the box gives the input the focus, which is all the JavaScript of a text
# field.
_FOCUS_FIELD = Var(
    "focusField",
    _var_data=VarData(
        imports={f"$/{WEB_DIR}/behaviors/text-field.js": [ImportVar(tag="focusField")]}
    ),
)

# The props of the box of a text field or a text area. Every other one is a
# prop of the control inside it.
_BOX_PROPS = frozenset((
    "size",
    "variant",
    "resize",
    "color_scheme",
    "radius",
    "class_name",
    "style",
))


def control_props(props: dict[str, Any], element: type[Component]) -> dict[str, Any]:
    """Take the props of the control out of the props of its box.

    Args:
        props: The props a text field or a text area is created with, which
            keeps the ones of the box.
        element: The element class of the control.

    Returns:
        The props of the control: its attributes, its ``id`` and its event
        triggers.
    """
    fields = element.get_fields()
    return {
        key: props.pop(key)
        for key in list(props)
        if key not in _BOX_PROPS
        and (
            key in fields
            or key.startswith(("on_", "aria_", "data_"))
            or key == "custom_attrs"
        )
    }


class DebouncedControl(DebounceInput):
    """An input or a text area that keeps what is typed while state catches up.

    The value of a control bound to state comes back from the state after
    each change, later than the next key. This is the wrapper Reflex puts
    around every input a state controls, with the class names of the
    control's styles.
    """

    @classmethod
    def create(cls, control: UIComponent) -> Component:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Wrap a control that has a value and an ``on_change``.

        Args:
            control: The input or the text area.

        Returns:
            The control inside the wrapper.
        """
        component = super().create(control)
        component._control = control  # pyright: ignore[reportAttributeAccessIssue]
        return component

    def _render(self) -> CommonTag:
        """Render the wrapper with the class names of the control's styles.

        Returns:
            The tag.
        """
        control: UIComponent = self._control  # pyright: ignore[reportAttributeAccessIssue]
        return (
            super()._render().add_props(class_name=control._render().props["className"])
        )


class TextFieldInput(UIComponent, elements.Input):
    """The input of a text field."""

    tag = "input"

    styles: ClassVar[ComponentStyles] = TEXT_FIELD_INPUT

    def _post_init(self, *args, **kwargs):
        """Initialize the input, with the look its box gives it.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component. ``box`` holds the
                size and the variant of the box.
        """
        # What the style table reads as variants.
        self._size, self._variant = kwargs.pop("box")
        super()._post_init(*args, **kwargs)


class TextFieldRoot(UIComponent, elements.Input):
    """Captures user input with an optional slot for buttons and icons."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = TEXT_FIELD

    size: Var[Responsive[LiteralTextFieldSize]] = field(doc='Text field size "1" - "3"')

    variant: Var[LiteralTextFieldVariant] = field(
        doc='Variant of text field: "classic" | "surface" | "soft"'
    )

    color_scheme: Var[LiteralAccentColor] = field(
        doc="Override theme color for text field"
    )

    radius: Var[LiteralRadius] = field(
        doc='Override theme radius for text field: "none" | "small" | "medium" | "large" | "full"'
    )

    auto_complete: Var[str] = field(
        doc='The autocomplete hint, e.g. "off", "on" or "email". True and False become "on" and "off".'
    )

    default_value: Var[str] = field(
        doc="The value of the input when initially rendered."
    )

    disabled: Var[bool] = field(doc="Disables the input")

    max_length: Var[int] = field(
        doc="Specifies the maximum number of characters allowed in the input"
    )

    min_length: Var[int] = field(
        doc="Specifies the minimum number of characters required in the input"
    )

    name: Var[str] = field(doc="Name of the input, used when sending form data")

    placeholder: Var[str] = field(doc="Placeholder text in the input")

    read_only: Var[bool] = field(doc="Indicates whether the input is read-only")

    required: Var[bool] = field(doc="Indicates that the input is required")

    type: Var[str] = field(doc="Specifies the type of input")

    value: Var[str | int | float] = field(doc="Value of the input")

    list: Var[str] = field(doc="References a datalist for suggested options")

    on_change: EventHandler[input_event] = field(
        doc="Fired when the value of the textarea changes."
    )

    on_focus: EventHandler[input_event] = field(
        doc="Fired when the textarea is focused."
    )

    on_blur: EventHandler[input_event] = field(
        doc="Fired when the textarea is blurred."
    )

    on_key_down: EventHandler[key_event] = field(
        doc="Fired when a key is pressed down."
    )

    on_key_up: EventHandler[key_event] = field(doc="Fired when a key is released.")

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an Input component.

        The size, the variant, the color, the radius and the styles are the
        ones of the box, and every other prop is given to the input inside
        it: its attributes, its ``id`` and its event triggers.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The component.
        """
        # React drops a bool autoComplete, the DOM takes a string
        auto_complete = props.get("auto_complete")
        if isinstance(auto_complete, bool):
            props["auto_complete"] = "on" if auto_complete else "off"
        elif isinstance(auto_complete, Var) and safe_issubclass(
            value_inside_optional(auto_complete._var_type), bool
        ):
            props["auto_complete"] = ternary_operation(
                auto_complete, Var.create("on"), Var.create("off")
            )

        value = props.get("value")

        # React expects an empty string(instead of null) for controlled inputs.
        if value is not None and is_optional(
            (value_var := Var.create(value))._var_type
        ):
            value_var_is_not_none = value_var != Var.create(None)
            value_var_is_not_undefined = value_var != Var(_js_expr="undefined")
            props["value"] = ternary_operation(
                value_var_is_not_none & value_var_is_not_undefined,
                value,
                Var.create(""),
            )

        own = control_props(props, elements.Input)
        # Marked for the rules of the fields of a date, and without the spell
        # check of the browser unless it is asked for, as in Radix Themes.
        own.setdefault("custom_attrs", {})["data-rx-text-field-input"] = ""
        own.setdefault("spell_check", False)
        control: Component = TextFieldInput.create(
            box=(props.get("size"), props.get("variant")), **own
        )
        if own.get("value") is not None and own.get("on_change") is not None:
            # create a debounced input if the user requests full control to avoid typing jank
            control = DebouncedControl.create(control)  # pyright: ignore[reportArgumentType]
        if children:
            _place_slots(children)
            props.setdefault("custom_attrs", {})["onPointerDown"] = _FOCUS_FIELD
        return super().create(control, *children, **props)


def _place_slots(children: tuple[Any, ...]) -> None:
    """Say which side each slot of a text field is on.

    A slot is on the side it names, and one that names none is on the left,
    or on the right when a slot before it is not: two slots without a side
    are one on each.

    Args:
        children: The children of the text field.
    """
    left_before = False
    for child in children:
        if isinstance(child, TextFieldSlot):
            side = literal(child.side)
            if side is None:
                child._set_side("right" if left_before else "left")
            left_before = left_before or child._side != "right"


class TextFieldSlot(UIComponent):
    """Contains icons or buttons associated with an Input."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = TEXT_FIELD_SLOT

    color_scheme: Var[LiteralAccentColor] = field(
        doc="Override theme color for text field slot"
    )

    side: Var[Literal["left", "right"]] = field(
        doc="Which side of the input the slot should be placed on"
    )

    def _post_init(self, *args, **kwargs):
        """Initialize the slot, on the side it names.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        # What the style table reads as a variant: the text field sets the
        # side of a slot that names none.
        self._side: Any = kwargs.get("side")
        super()._post_init(*args, **kwargs)

    def _set_side(self, side: str) -> None:
        """Put a slot that names no side on one.

        Args:
            side: The side.
        """
        self._side = side
        self._merge_styles()  # pyright: ignore[reportAttributeAccessIssue]

    def _exclude_props(self) -> list[str]:
        """Keep the side off the element as a prop: it is rendered as data.

        Returns:
            The props read as styles, and the side.
        """
        return [*super()._exclude_props(), "side"]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the slot.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, with the side the slot is on: the box around it reads
            it to leave no room on that side of the input.
        """
        return (
            super()
            ._render(props)
            .add_props(**{"data-side": "left" if self._side is None else self._side})
        )


class TextField(ComponentNamespace):
    """TextField components namespace."""

    slot = staticmethod(TextFieldSlot.create)
    __call__ = staticmethod(TextFieldRoot.create)


input = text_field = TextField()
