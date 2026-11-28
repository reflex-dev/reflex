"""A group of radio buttons: native inputs that share a name."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any, ClassVar, Literal

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.components.tags import CommonTag
from reflex_base.event import EventHandler, input_event
from reflex_base.utils import types
from reflex_base.vars.base import LiteralVar, Var
from reflex_base.vars.sequence import StringVar
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.core.cond import cond
from reflex_components_core.core.foreach import foreach

from reflex_components_ui.base import UIComponent
from reflex_components_ui.components._group import (
    descendants,
    either,
    group_name,
    is_value,
    literal,
)
from reflex_components_ui.layout.flex import Flex
from reflex_components_ui.props import LiteralSpacing
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.radio import (
    RADIO,
    RADIO_GROUP,
    RADIO_GROUP_ITEM,
    RADIO_GROUP_ITEM_INNER,
)
from reflex_components_ui.themes import LiteralAccentColor
from reflex_components_ui.typography.text import Text

LiteralFlexDirection = Literal["row", "column", "row-reverse", "column-reverse"]


class RadioGroupItemLabel(Text):
    """The label around an item that is given children."""

    def add_style(self) -> dict[str, Any]:
        """Lay the radio button and its text out in a row.

        Returns:
            The styles Radix Themes gives the label of an item.
        """
        return RADIO_GROUP_ITEM


class RadioGroupItemInner(UIComponent):
    """The children of an item, beside its radio button."""

    tag = "span"

    styles: ClassVar[ComponentStyles] = RADIO_GROUP_ITEM_INNER


class RadioGroupItem(UIComponent):
    """An item in the group that can be checked."""

    tag = "input"

    styles: ClassVar[ComponentStyles] = RADIO

    value: Var[str] = field(
        doc="The value of the radio item to check. Should be used in conjunction with on_change."
    )

    disabled: Var[bool] = field(
        doc="When true, prevents the user from interacting with the radio item."
    )

    required: Var[bool] = field(
        doc="When true, indicates that the user must check the radio item before the owning form can be submitted."
    )

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an item: a radio button, in a label when it has children.

        Args:
            *children: What is shown beside the radio button.
            **props: The props of the item. With children, its styles are
                those of the label.

        Returns:
            The radio button, or the label that holds it.
        """
        if not children:
            return super().create(**props)
        fields = cls.get_fields()
        triggers = cls.get_event_triggers()
        own = {
            key: props.pop(key)
            for key in list(props)
            if key in fields
            or key in triggers
            or key.startswith(("on_", "aria_", "data_"))
        }
        return RadioGroupItemLabel.create(
            super().create(**own),
            RadioGroupItemInner.create(*children),
            as_="label",
            **props,
        )

    def _post_init(self, *args, **kwargs):
        """Initialize the item, with the look of a group of its own.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        # What the style table reads as variants, and the attributes the
        # group gives its items: both are set by the group around the item.
        self._size: Any = None
        self._variant: Any = None
        self._high_contrast: Any = None
        self._group: dict[str, Any] = {}
        super()._post_init(*args, **kwargs)

    def _join(self, group: RadioGroupRoot) -> None:
        """Take from a group what Radix hands its items through a context.

        Args:
            group: The group the item is in.
        """
        self._size = group.size
        self._variant = group.variant
        self._high_contrast = group.high_contrast
        attributes: dict[str, Any] = {"name": group._name}
        disabled = either(group.disabled, self.disabled)
        if disabled is not None:
            attributes["disabled"] = disabled
        required = either(group.required, self.required)
        if required is not None:
            attributes["required"] = required
        if group.value is not None:
            # An input React keeps checked says who changes it: the group.
            attributes["checked"] = is_value(group.value, self.value)
            attributes["read_only"] = True
        elif group.default_value is not None:
            checked = is_value(group.default_value, self.value)
            if checked is not False:
                attributes["default_checked"] = checked
        self._group = attributes
        self._merge_styles()

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in the item, those its group gives it included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        for value in self._group.values():
            if isinstance(value, Var):
                yield value

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the radio button.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, with the type of the input and what its group gives it.
        """
        return super()._render(props).add_props(type="radio", **self._group)


class RadioGroupRoot(UIComponent):
    """A set of interactive radio buttons where only one can be selected at a time."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = RADIO_GROUP

    size: Var[Responsive[Literal["1", "2", "3"]]] = field(
        default=LiteralVar.create("2"),
        doc='The size of the radio group: "1" | "2" | "3"',
    )

    variant: Var[Literal["classic", "surface", "soft"]] = field(
        default=LiteralVar.create("classic"), doc="The variant of the radio group"
    )

    color_scheme: Var[LiteralAccentColor] = field(doc="The color of the radio group")

    high_contrast: Var[bool] = field(
        doc="Whether to render the radio group with higher contrast color against background"
    )

    value: Var[str] = field(
        doc="The controlled value of the radio item to check. Should be used in conjunction with on_change."
    )

    default_value: Var[str] = field(
        doc="The initial value of checked radio item. Should be used in conjunction with on_change."
    )

    disabled: Var[bool] = field(doc="Whether the radio group is disabled")

    name: Var[str] = field(
        doc="The name of the group. Submitted with its owning form as part of a name/value pair."
    )

    required: Var[bool] = field(doc="Whether the radio group is required")

    on_change: EventHandler[input_event] = field(
        doc="Fired when the value of the radio group changes."
    )

    def _post_init(self, *args, **kwargs):
        """Initialize the group, and give its items what they share.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        super()._post_init(*args, **kwargs)
        # The browser takes radio buttons for a group by their name.
        self._name = group_name(self.name, "radio")
        for label in descendants(self, RadioGroupItemLabel, RadioGroupRoot):
            label.size = self.size
            label._merge_styles()
        for item in descendants(self, RadioGroupItem, RadioGroupRoot):
            item._join(self)

    def _exclude_props(self) -> list[str]:
        """Keep the props that are the ones of the items off the element.

        Returns:
            The props read as styles, and what the group hands its items.
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
        ]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the group.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, with the role of a group of radio buttons and whether
            one of them has to be checked.
        """
        tag = super()._render(props).add_props(role="radiogroup")
        if self.required is not None and literal(self.required) is not False:
            tag = tag.add_props(**{"aria-required": self.required})
        return tag


class HighLevelRadioGroup(UIComponent):
    """High level wrapper for the RadioGroup component."""

    items: Var[Sequence[str]] = field(doc="The items of the radio group.")

    direction: Var[LiteralFlexDirection] = field(
        default=LiteralVar.create("row"), doc="The direction of the radio group."
    )

    spacing: Var[LiteralSpacing] = field(
        default=LiteralVar.create("2"),
        doc="The gap between the items of the radio group.",
    )

    size: Var[Literal["1", "2", "3"]] = field(
        default=LiteralVar.create("2"), doc="The size of the radio group."
    )

    variant: Var[Literal["classic", "surface", "soft"]] = field(
        default=LiteralVar.create("classic"), doc="The variant of the radio group"
    )

    color_scheme: Var[LiteralAccentColor] = field(doc="The color of the radio group")

    high_contrast: Var[bool] = field(
        doc="Whether to render the radio group with higher contrast color against background"
    )

    value: Var[str] = field(
        doc="The controlled value of the radio item to check. Should be used in conjunction with on_change."
    )

    default_value: Var[str] = field(
        doc="The initial value of checked radio item. Should be used in conjunction with on_change."
    )

    disabled: Var[bool] = field(doc="Whether the radio group is disabled")

    name: Var[str] = field(
        doc="The name of the group. Submitted with its owning form as part of a name/value pair."
    )

    required: Var[bool] = field(doc="Whether the radio group is required")

    @classmethod
    def create(
        cls,
        items: Var[Sequence[str | int | float | list | dict | bool | None]],
        **props,
    ) -> Component:
        """Create a radio group component.

        Args:
            items: The items of the radio group.
            **props: Additional properties to apply to the accordion item.

        Returns:
            The created radio group component.

        Raises:
            TypeError: If the type of items is invalid.
        """
        direction = props.pop("direction", "row")
        spacing = props.pop("spacing", "2")
        size = props.pop("size", "2")
        variant = props.pop("variant", "classic")
        color_scheme = props.pop("color_scheme", None)
        default_value = props.pop("default_value", "")

        if not isinstance(items, (list, Var)) or (
            isinstance(items, Var)
            and not types.typehint_issubclass(items._var_type, list)
        ):
            items_type = type(items) if not isinstance(items, Var) else items._var_type
            msg = f"The radio group component takes in a list, got {items_type} instead"
            raise TypeError(msg)

        default_value = LiteralVar.create(default_value)

        # convert only non-strings to json(JSON.stringify) so quotes are not rendered
        # for string literal types.
        if isinstance(default_value, str) or (
            isinstance(default_value, Var) and default_value._var_type is str
        ):
            default_value = LiteralVar.create(default_value)
        else:
            default_value = LiteralVar.create(default_value).to_string()

        def radio_group_item(value: Var) -> Component:
            item_value = cond(
                value.js_type() == "string",
                value,
                value.to_string(),
            ).to(StringVar)

            return Text.create(
                Flex.create(
                    RadioGroupItem.create(
                        value=item_value,
                        disabled=props.get("disabled", LiteralVar.create(False)),
                    ),
                    item_value,
                    spacing="2",
                ),
                size=size,
                as_="label",
            )

        children = [
            foreach(
                items,
                radio_group_item,
            )
        ]

        return RadioGroupRoot.create(
            Flex.create(
                *children,
                direction=direction,
                spacing=spacing,
            ),
            size=size,
            variant=variant,
            color_scheme=color_scheme,
            default_value=default_value,
            **props,
        )


class RadioGroup(ComponentNamespace):
    """RadioGroup components namespace."""

    root = staticmethod(RadioGroupRoot.create)
    item = staticmethod(RadioGroupItem.create)
    __call__ = staticmethod(HighLevelRadioGroup.create)


radio = radio_group = RadioGroup()
