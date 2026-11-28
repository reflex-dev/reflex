"""A segmented control: a row of native radio buttons, drawn as one control."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar, Literal, cast

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.components.tags import CommonTag
from reflex_base.event import EventHandler, input_event
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var, VarData
from reflex_base.vars.sequence import ArrayVar
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.core.foreach import Foreach

from reflex_components_ui.base import Part, UIComponent
from reflex_components_ui.components._group import (
    GroupInput,
    GroupRoot,
    group_name,
    is_value,
)
from reflex_components_ui.constants import WEB_DIR
from reflex_components_ui.props import style_before
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.segmented_control import (
    COUNT,
    INDEX,
    INDEX_OF_VALUE,
    PLACED,
    SEGMENTED_CONTROL,
    SEGMENTED_CONTROL_ITEM,
    chosen,
)
from reflex_components_ui.themes import LiteralAccentColor

# The `onKeyDown` of the control: the arrow keys move the focus between the
# items without choosing one, as in Radix, which is all its JavaScript.
_ROVING_KEY_DOWN = Var(
    "rovingKeyDown",
    _var_data=VarData(
        imports={
            f"$/{WEB_DIR}/behaviors/roving-focus.js": [ImportVar(tag="rovingKeyDown")]
        }
    ),
)


class SegmentedControlInput(GroupInput, Part):
    """The radio button of an item, which is not seen."""

    _type: ClassVar[str] = "radio"

    value: Var[str] = field(doc="The value of the item.")

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the radio button.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, of no form: a segmented control has no name, and the
            name that groups its radio buttons is not for a form to submit.
        """
        return super()._render(props).add_props(form="")


class SegmentedControlRoot(GroupRoot):
    """Root element for a SegmentedControl component."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = SEGMENTED_CONTROL

    size: Var[Responsive[Literal["1", "2", "3"]]] = field(
        doc='The size of the segmented control: "1" | "2" | "3"'
    )

    variant: Var[Literal["classic", "surface"]] = field(
        doc='Variant of button: "classic" | "surface"'
    )

    type: Var[Literal["single", "multiple"]] = field(
        doc='The type of the segmented control, either "single" for selecting one option or "multiple" for selecting multiple options.'
    )

    color_scheme: Var[LiteralAccentColor] = field(doc="Override theme color for button")

    radius: Var[Literal["none", "small", "medium", "large", "full"]] = field(
        doc='The radius of the segmented control: "none" | "small" | "medium" | "large" | "full"'
    )

    default_value: Var[str | Sequence[str]] = field(
        doc="The default value of the segmented control."
    )

    value: Var[str | Sequence[str]] = field(
        doc="The current value of the segmented control."
    )

    on_change: EventHandler[input_event] = field(
        doc="Handles the `onChange` event for the SegmentedControl component."
    )

    # What a group hands its items, and a segmented control does not have.
    high_contrast: ClassVar[None] = None
    disabled: ClassVar[None] = None
    required: ClassVar[None] = None

    _holds = staticmethod(is_value)

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create a SegmentedControlRoot.

        What marks the chosen item is as wide as one item and moved to it,
        so the control counts its items: while compiling when they are its
        children, and in the browser when a ``foreach`` renders them.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The SegmentedControlRoot component.
        """
        placement: dict[str, Any] = {COUNT: len(children)}
        if len(children) == 1 and isinstance(children[0], Foreach):
            foreach = children[0]
            values = cast("ArrayVar", foreach.iterable)
            placement[COUNT] = values.length()
            selected = props.get("value", props.get("default_value"))
            item = foreach.render_fn(foreach.iterable[0])  # pyright: ignore[reportIndexIssue]
            if selected is not None and isinstance(item, SegmentedControlItem):
                # For the items after the ones the style table places.
                index = Var(
                    f"({values.map(lambda element: _value_of(foreach, element))!s}"
                    f".indexOf({Var.create(selected)!s}))",
                    _var_type=int,
                    _var_data=VarData.merge(
                        values._get_all_var_data(),
                        Var.create(selected)._get_all_var_data(),
                    ),
                )
                placement[INDEX_OF_VALUE] = index
        elif len(children) > PLACED:
            placement[INDEX] = {
                chosen(position): position - 1
                for position in range(PLACED + 1, len(children) + 1)
            }
        props.setdefault("custom_attrs", {}).setdefault("onKeyDown", _ROVING_KEY_DOWN)
        style_before(props, placement)
        return super().create(
            *children, Part.create(part="indicator", tag="div"), **props
        )

    def _bind(self) -> None:
        """Name the items: the browser takes radio buttons for a group by it."""
        self._name = group_name(None, "segmented")

    def _exclude_props(self) -> list[str]:
        """Keep the props that are the ones of the items off the element.

        Returns:
            The props read as styles, and what the control hands its items.
            The type is one of them: as in Radix Themes, one item is chosen
            whatever it says.
        """
        return [
            *super()._exclude_props(),
            "size",
            "variant",
            "type",
            "value",
            "default_value",
        ]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the control.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, with the role of a group of radio buttons.
        """
        return super()._render(props).add_props(role="radiogroup")


def _value_of(foreach: Foreach, element: Var) -> Var:
    """Get the value of the item a ``foreach`` renders for an element.

    Args:
        foreach: The ``foreach`` that renders the items of a control.
        element: One of the elements it iterates over.

    Returns:
        The value of the item.
    """
    return cast("SegmentedControlItem", foreach.render_fn(element)).children[0].value  # pyright: ignore[reportAttributeAccessIssue]


class SegmentedControlItem(UIComponent):
    """An item in the SegmentedControl component."""

    tag = "label"

    styles: ClassVar[ComponentStyles] = SEGMENTED_CONTROL_ITEM

    value: Var[str] = field(doc="The value of the item.")

    _valid_parents: ClassVar[list[str]] = ["SegmentedControlRoot"]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an item: a label around its radio button and its text.

        Args:
            *children: What the item shows.
            **props: The props of the item. Its styles are those of the
                label, and everything else is given to the radio button.

        Returns:
            The label.
        """
        own = {
            key: props.pop(key)
            for key in list(props)
            if key in ("value", "id") or key.startswith(("on_", "aria_", "data_"))
        }
        return super().create(
            SegmentedControlInput.create(part="input", **own),
            Part.create(part="separator", tag="span"),
            Part.create(
                Part.create(*children, part="active", tag="span"),
                Part.create(
                    *children,
                    part="inactive",
                    tag="span",
                    custom_attrs={"aria-hidden": True},
                ),
                part="label",
                tag="span",
            ),
            **props,
        )

    def _exclude_props(self) -> list[str]:
        """Keep the value off the label: it is the one of the radio button.

        Returns:
            The props read as styles, and the value.
        """
        return [*super()._exclude_props(), "value"]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the item.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, marked for the rule that hides the line beside the
            chosen item.
        """
        return super()._render(props).add_props(**{"data-rx-segmented-item": ""})


class SegmentedControl(ComponentNamespace):
    """SegmentedControl components namespace."""

    root = staticmethod(SegmentedControlRoot.create)
    item = staticmethod(SegmentedControlItem.create)


segmented_control = SegmentedControl()
