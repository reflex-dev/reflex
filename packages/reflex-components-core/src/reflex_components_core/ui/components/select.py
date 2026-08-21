"""A select styled with Tailwind classes on the native select element."""

from __future__ import annotations

from typing import Any, ClassVar

from reflex_base.components.component import field
from reflex_base.vars.base import Var

from reflex_components_core.core.foreach import foreach
from reflex_components_core.el.elements import forms
from reflex_components_core.el.elements.inline import Span
from reflex_components_core.ui._icons import chevron_down
from reflex_components_core.ui.base import UIComponent

# The visual box lives on the wrapper so the chevron can share it; the inner
# select is transparent and fills the wrapper via a stacked grid cell.
SELECT_WRAPPER_CLASS_NAME = (
    "relative inline-grid w-fit grid-cols-1 items-center rounded-md "
    "border border-input bg-transparent shadow-xs text-sm "
    "transition-[color,box-shadow] "
    "focus-within:border-ring focus-within:ring-ring/50 focus-within:ring-[3px] "
    "has-[select:disabled]:cursor-not-allowed has-[select:disabled]:opacity-50 "
    "has-[select[aria-invalid=true]]:border-destructive"
)

SELECT_CLASS_NAME = (
    "col-start-1 row-start-1 h-9 w-full min-w-0 appearance-none rounded-md "
    "bg-transparent pl-3 pr-8 outline-none cursor-pointer "
    "disabled:cursor-not-allowed"
)

SELECT_ICON_CLASS_NAME = (
    "col-start-1 row-start-1 justify-self-end mr-3 size-4 "
    "pointer-events-none text-muted-foreground"
)


class Select(forms.Select, UIComponent):
    """A themable select built on the native select element.

    Pass ``items`` for the common case; otherwise compose ``rx.el.option``
    children. The returned component is a wrapper span carrying the visual
    styles (and the user ``class_name``) around the native select, which
    has a ``data-slot="select"`` attribute for CSS targeting.
    """

    _slot: ClassVar[str | None] = "select"

    items: Var[list[str]] = field(doc="Values to render as options, in order.")

    placeholder: Var[str] = field(
        doc="Text shown before a selection is made, as a hidden disabled option."
    )

    @classmethod
    def create(
        cls,
        *children,
        items: list[str] | Var[list[str]] | None = None,
        placeholder: str | None = None,
        **props,
    ):
        """Create a select.

        Args:
            *children: Option elements, used when items is not given.
            items: Values to render as options.
            placeholder: Text shown before a selection is made.
            **props: The props of the component.

        Returns:
            The select component, wrapped with its indicator icon.
        """
        unstyled = props.pop("unstyled", False)
        wrapper_props: dict[str, Any] = {
            "data_slot": "select-wrapper",
            "unstyled": unstyled,
        }
        user_class_name = props.pop("class_name", None)
        if user_class_name is not None:
            wrapper_props["class_name"] = user_class_name
        if "key" in props:
            wrapper_props["key"] = props.pop("key")

        children_list = list(children)
        if placeholder is not None:
            if "value" not in props:
                props.setdefault("default_value", "")
            children_list.insert(
                0,
                forms.Option.create(placeholder, value="", disabled=True, hidden=True),
            )
        if items is not None:
            if isinstance(items, Var):
                children_list.append(
                    foreach(items, lambda item: forms.Option.create(item, value=item))
                )
            else:
                children_list.extend(
                    forms.Option.create(item, value=item) for item in items
                )

        props["unstyled"] = unstyled
        cls._apply_class_name(SELECT_CLASS_NAME, props)
        select = super().create(*children_list, **props)

        cls._apply_class_name(SELECT_WRAPPER_CLASS_NAME, wrapper_props)
        # An unstyled select keeps the native indicator, so skip the icon.
        icon = [] if unstyled else [chevron_down(class_name=SELECT_ICON_CLASS_NAME)]
        return Span.create(select, *icon, **wrapper_props)

    def _exclude_props(self) -> list[str]:
        return [
            *super()._exclude_props(),
            "items",
            "placeholder",
        ]


select = Select.create
