"""A group of checkboxes: native inputs that share a name."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar, Literal

from reflex_base.components.component import ComponentNamespace, field
from reflex_base.components.tags import CommonTag
from reflex_base.event import EventHandler, JavascriptInputEvent
from reflex_base.vars.base import Var
from reflex_base.vars.object import ObjectVar
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_ui.components._group import (
    GroupInput,
    GroupRoot,
    group_name,
    has_value,
)
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.checkbox import CHECKBOX_GROUP_ITEM
from reflex_components_ui.styles.control import GROUP
from reflex_components_ui.themes import LiteralAccentColor


def checked_values_event(
    e: ObjectVar[JavascriptInputEvent],
) -> tuple[Var[list[str]]]:
    """Get the values of the checked checkboxes of a group from a change in it.

    Args:
        e: The change of one of the checkboxes, as it reaches their group.

    Returns:
        The value of each checked checkbox that has the name of the changed
        one, in the order of the checkboxes.
    """
    return (
        Var(
            f"Array.from({e!s}.currentTarget.querySelectorAll("
            '"input[type=checkbox]:checked"))'
            f".filter((input) => input.name === {e!s}.target.name)"
            ".map((input) => input.value)",
            _var_type=list[str],
        ),
    )


class CheckboxGroupRoot(GroupRoot):
    """Root element for a CheckboxGroup component."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = GROUP

    size: Var[Responsive[Literal["1", "2", "3"]]] = field(
        doc="Use the size prop to control the checkbox size."
    )

    variant: Var[Literal["classic", "surface", "soft"]] = field(
        doc='Variant of button: "classic" | "surface" | "soft"'
    )

    color_scheme: Var[LiteralAccentColor] = field(doc="Override theme color for button")

    high_contrast: Var[bool] = field(
        doc="Uses a higher contrast color for the component."
    )

    default_value: Var[Sequence[str]] = field(
        doc="determines which checkboxes, if any, are checked by default."
    )

    value: Var[Sequence[str]] = field(
        doc="The controlled value of the checked checkboxes. Should be used in conjunction with on_value_change."
    )

    name: Var[str] = field(
        doc="used to assign a name to the entire group of checkboxes"
    )

    disabled: Var[bool] = field(doc="Whether the checkbox group is disabled")

    required: Var[bool] = field(
        doc="When true, every checkbox in the group must be checked before the owning form can be submitted."
    )

    orientation: Var[Literal["horizontal", "vertical"]] = field(
        doc="The orientation of the component."
    )

    dir: Var[Literal["ltr", "rtl"]] = field(
        doc="The reading direction of the checkbox group. If omitted, inherits globally from DirectionProvider or assumes LTR (left-to-right) reading mode."
    )

    loop: Var[bool] = field(
        doc="When true, keyboard navigation will loop from last item to first, and vice versa."
    )

    on_value_change: EventHandler[checked_values_event] = field(
        doc="Fired when the set of checked checkboxes changes."
    )

    _rename_props: ClassVar[dict[str, str]] = {"onValueChange": "onChange"}

    _holds = staticmethod(has_value)

    def _bind(self) -> None:
        """Name the group: a change says which checkboxes it is about by it."""
        self._name = group_name(self.name, "checkbox")

    def _exclude_props(self) -> list[str]:
        """Keep the props that are the ones of the items off the element.

        Returns:
            The props read as styles, what the group hands its items, and
            what says how the arrow keys move through a group of Radix: the
            checkboxes of this one are reached with Tab, as any checkbox is.
        """
        return [
            *super()._exclude_props(),
            "size",
            "variant",
            "high_contrast",
            "value",
            "default_value",
            "disabled",
            "name",
            "required",
            "orientation",
            "loop",
        ]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the group.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, with the role of a group.
        """
        return super()._render(props).add_props(role="group")


class CheckboxGroupItem(GroupInput):
    """An item in the CheckboxGroup component."""

    styles: ClassVar[ComponentStyles] = CHECKBOX_GROUP_ITEM

    _type: ClassVar[str] = "checkbox"

    value: Var[str] = field(
        doc="specifies the value associated with a particular checkbox option."
    )

    disabled: Var[bool] = field(
        doc="Use the native disabled attribute to create a disabled checkbox."
    )

    required: Var[bool] = field(
        doc="When true, indicates that the user must check the checkbox item before the owning form can be submitted."
    )


class CheckboxGroup(ComponentNamespace):
    """CheckboxGroup components namespace."""

    root = staticmethod(CheckboxGroupRoot.create)
    item = staticmethod(CheckboxGroupItem.create)


checkbox_group = CheckboxGroup()
