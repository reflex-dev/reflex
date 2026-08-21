"""A radio group styled with Tailwind classes on native radio inputs."""

from __future__ import annotations

from typing import Any, ClassVar

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.vars.base import Var, get_unique_variable_name

from reflex_components_core.core.foreach import foreach
from reflex_components_core.el.elements import forms
from reflex_components_core.el.elements.typography import Div
from reflex_components_core.ui.base import UIComponent
from reflex_components_core.ui.components.label import label

RADIO_GROUP_CLASS_NAME = "grid gap-3"

# The dot is the ::before pseudo-element, scaled in when checked.
RADIO_CLASS_NAME = (
    "peer appearance-none aspect-square size-4 shrink-0 rounded-full "
    "border border-input bg-background shadow-xs transition-shadow outline-none "
    "cursor-pointer grid place-content-center "
    "before:content-[''] before:size-2 before:rounded-full before:scale-0 "
    "before:bg-primary before:transition-transform "
    "checked:border-primary checked:before:scale-100 "
    "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] "
    "aria-invalid:border-destructive aria-invalid:ring-destructive/20 "
    "disabled:cursor-not-allowed disabled:opacity-50"
)


class RadioGroupItem(forms.CheckboxInput, UIComponent):
    """A single radio input styled for the radio group."""

    _slot: ClassVar[str | None] = "radio-group-item"

    @classmethod
    def create(cls, *children, **props):
        """Create a radio item.

        Args:
            *children: Unused; radio inputs render no children.
            **props: The props of the component.

        Returns:
            The radio item component.
        """
        props["type"] = "radio"
        cls._apply_class_name(RADIO_CLASS_NAME, props)
        return super().create(*children, **props)


class RadioGroup(Div, UIComponent):
    """A group of radio inputs built on native form controls.

    Pass ``items`` for the common case; each item renders a radio with a
    label. For full control, compose ``rx.ui.radio_group.item`` (and your own
    labels) as children, sharing the same ``name``.
    """

    _slot: ClassVar[str | None] = "radio-group"

    items: Var[list[str]] = field(
        doc="Values to render as labeled radio items, in order."
    )

    @classmethod
    def create(
        cls,
        *children,
        items: list[str] | Var[list[str]] | None = None,
        value: str | Var[str] | None = None,
        on_change: Any = None,
        name: str | Var[str] | None = None,
        disabled: bool | Var[bool] | None = None,
        **props,
    ):
        """Create a radio group.

        Args:
            *children: Custom children, used when items is not given.
            items: Values to render as labeled radio items.
            value: The controlled selected value.
            on_change: Event handler called with the newly selected value.
            name: Shared input name; auto-generated when omitted.
            disabled: Disable all generated radio items.
            **props: The props of the component.

        Returns:
            The radio group component.
        """
        props.setdefault("role", "radiogroup")
        cls._apply_class_name(RADIO_GROUP_CLASS_NAME, props)

        children_list = list(children)
        if items is not None:
            if name is None:
                name = f"radio-group-{get_unique_variable_name()}"

            def make_item(item: str | Var[str]) -> Component:
                item_props: dict[str, Any] = {"value": item, "name": name}
                if value is not None:
                    item_props["checked"] = value == item
                if on_change is not None:
                    item_props["on_change"] = on_change(item)
                if disabled is not None:
                    item_props["disabled"] = disabled
                return label(RadioGroupItem.create(**item_props), item)

            if isinstance(items, Var):
                children_list.append(foreach(items, make_item))
            else:
                children_list.extend(make_item(item) for item in items)
        return super().create(*children_list, **props)


class RadioGroupNamespace(ComponentNamespace):
    """Namespace for radio group components."""

    root = staticmethod(RadioGroup.create)
    item = staticmethod(RadioGroupItem.create)
    __call__ = staticmethod(RadioGroup.create)


radio_group = RadioGroupNamespace()
