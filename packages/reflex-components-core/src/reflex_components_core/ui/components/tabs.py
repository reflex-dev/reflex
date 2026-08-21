"""Tabs built from buttons and divs with WAI-ARIA tab semantics.

Tab state lives client side by default (via a useState hook), or can be
driven from Reflex state with the ``value``/``on_change`` props.
"""

from __future__ import annotations

from typing import Any, ClassVar

from reflex_base.components.component import BaseComponent, ComponentNamespace, field
from reflex_base.event import EventChain, EventHandler, no_args_event_spec
from reflex_base.vars.base import LiteralVar, Var, get_unique_variable_name
from reflex_base.vars.client_state import ClientStateVar

from reflex_components_core.core.cond import cond
from reflex_components_core.el.elements import forms
from reflex_components_core.el.elements.typography import Div
from reflex_components_core.ui.base import UIComponent

TABS_CLASS_NAME = "flex flex-col gap-2"

TABS_LIST_CLASS_NAME = (
    "bg-muted text-muted-foreground inline-flex h-9 w-fit items-center "
    "justify-center rounded-lg p-[3px] gap-1"
)

TABS_TRIGGER_CLASS_NAME = (
    "inline-flex flex-1 items-center justify-center gap-1.5 whitespace-nowrap "
    "rounded-md border border-transparent px-2 py-1 h-[calc(100%-1px)] "
    "text-sm font-medium text-muted-foreground transition-[color,box-shadow] "
    "outline-none cursor-pointer "
    "disabled:pointer-events-none disabled:opacity-50 "
    "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] "
    "data-[state=active]:bg-background data-[state=active]:text-foreground "
    "data-[state=active]:shadow-sm "
    "[&_svg]:pointer-events-none [&_svg]:shrink-0 "
    "[&_svg:not([class*='size-'])]:size-4"
)

TABS_CONTENT_CLASS_NAME = "flex-1 outline-none data-[state=inactive]:hidden"

# Roving focus for the tablist: arrows move focus and select the tab.
_TABS_KEYDOWN_HANDLER = Var(
    "((event) => {"
    " const tabs = Array.from(event.currentTarget.querySelectorAll('[role=\"tab\"]:not([disabled])'));"
    " const index = tabs.indexOf(event.target.closest('[role=\"tab\"]'));"
    " if (index < 0) return;"
    " let next = null;"
    ' if (event.key === "ArrowRight") next = tabs[(index + 1) % tabs.length];'
    ' else if (event.key === "ArrowLeft") next = tabs[(index - 1 + tabs.length) % tabs.length];'
    ' else if (event.key === "Home") next = tabs[0];'
    ' else if (event.key === "End") next = tabs[tabs.length - 1];'
    " if (next) { event.preventDefault(); next.focus(); next.click(); }"
    "})"
)


def _static_value(value: Any) -> str | None:
    """Extract the compile-time string from a possibly-Var value.

    Args:
        value: A string, a literal Var, or None.

    Returns:
        The static string, or None if the value is dynamic or unset.
    """
    if isinstance(value, str):
        return value
    literal = getattr(value, "_var_value", None)
    return literal if isinstance(literal, str) else None


class TabsTrigger(forms.Button, UIComponent):
    """A button that activates its associated tab content."""

    _slot: ClassVar[str | None] = "tabs-trigger"

    value: Var[str] = field(doc="The value of the tab this trigger activates.")

    @classmethod
    def create(cls, *children, **props):
        """Create a tabs trigger.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The tabs trigger component.
        """
        props.setdefault("type", "button")
        props.setdefault("role", "tab")
        cls._apply_class_name(TABS_TRIGGER_CLASS_NAME, props)
        return super().create(*children, **props)

    def _exclude_props(self) -> list[str]:
        return [
            *super()._exclude_props(),
            "value",
        ]


class TabsList(Div, UIComponent):
    """The container of tab triggers."""

    _slot: ClassVar[str | None] = "tabs-list"

    @classmethod
    def create(cls, *children, **props):
        """Create a tabs list.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The tabs list component.
        """
        props.setdefault("role", "tablist")
        custom_attrs = props.setdefault("custom_attrs", {})
        custom_attrs.setdefault("onKeyDown", _TABS_KEYDOWN_HANDLER)
        cls._apply_class_name(TABS_LIST_CLASS_NAME, props)
        return super().create(*children, **props)


class TabsContent(Div, UIComponent):
    """The content panel associated with a tab."""

    _slot: ClassVar[str | None] = "tabs-content"

    value: Var[str] = field(doc="The value of the tab this content belongs to.")

    @classmethod
    def create(cls, *children, **props):
        """Create a tabs content panel.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The tabs content component.
        """
        props.setdefault("role", "tabpanel")
        props.setdefault("tab_index", 0)
        cls._apply_class_name(TABS_CONTENT_CLASS_NAME, props)
        return super().create(*children, **props)

    def _exclude_props(self) -> list[str]:
        return [
            *super()._exclude_props(),
            "value",
        ]


def _walk_tab_parts(
    component: BaseComponent,
) -> list[TabsTrigger | TabsContent]:
    """Collect tab triggers and contents, without descending into nested tabs.

    Args:
        component: The component to walk.

    Returns:
        The tab parts in document order.
    """
    parts: list[TabsTrigger | TabsContent] = []
    for child in component.children:
        if isinstance(child, (TabsTrigger, TabsContent)):
            parts.append(child)
        if isinstance(child, Tabs) or not isinstance(child, BaseComponent):
            continue
        parts.extend(_walk_tab_parts(child))
    return parts


class Tabs(Div, UIComponent):
    """A set of tab panels shown one at a time.

    Compose ``tabs.list`` with ``tabs.trigger`` children and matching
    ``tabs.content`` panels, all sharing string values. Without ``value``
    the selection is kept client side, starting from ``default_value``.
    """

    _slot: ClassVar[str | None] = "tabs"

    default_value: Var[str] = field(doc="Initial selected tab for client-managed tabs.")

    value: Var[str] = field(doc="The controlled selected tab value.")

    on_change: EventHandler[no_args_event_spec] = field(
        doc="Event handler called with the newly selected tab value."
    )

    @classmethod
    def create(cls, *children, **props):
        """Create the tabs root, wiring triggers and content panels.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The tabs component.

        Raises:
            ValueError: If a trigger or content is missing a value.
        """
        tabs_uid = get_unique_variable_name()
        value = props.pop("value", None)
        default_value = props.pop("default_value", None)
        on_change = props.pop("on_change", None)
        cls._apply_class_name(TABS_CLASS_NAME, props)
        component = super().create(*children, **props)

        parts = _walk_tab_parts(component)
        triggers = [part for part in parts if isinstance(part, TabsTrigger)]
        contents = [part for part in parts if isinstance(part, TabsContent)]

        if isinstance(default_value, Var):
            msg = "The default_value prop must be a static string, not a Var."
            raise ValueError(msg)
        if default_value is None:
            static_values = [
                static_value
                for trigger in triggers
                if (static_value := _static_value(trigger.value)) is not None
            ]
            default_value = static_values[0] if static_values else ""

        set_current = None
        if value is not None:
            current = LiteralVar.create(value).to(str)
        else:
            client_value = ClientStateVar.create(
                f"tabs_{tabs_uid}", default=default_value
            )
            current = client_value.value.to(str)
            set_current = client_value.set_value

        for trigger in triggers:
            part_value = trigger.value
            if part_value is None:
                msg = "Each rx.ui.tabs.trigger requires a value prop."
                raise ValueError(msg)
            selected = current == part_value
            trigger.custom_attrs.setdefault(
                "data-state", cond(selected, "active", "inactive")
            )
            trigger.custom_attrs.setdefault("aria-selected", selected)
            if getattr(trigger, "tab_index", None) is None:
                trigger.tab_index = cond(selected, 0, -1)  # pyright: ignore[reportAttributeAccessIssue]
            if "on_click" not in trigger.event_triggers:
                on_select: list[Any] = []
                if set_current is not None:
                    on_select.append(set_current(part_value))
                if on_change is not None:
                    on_select.append(on_change(part_value))
                if len(on_select) == 1 and isinstance(on_select[0], Var):
                    trigger.event_triggers["on_click"] = on_select[0]
                elif on_select:
                    trigger.event_triggers["on_click"] = EventChain.create(
                        value=on_select,
                        args_spec=no_args_event_spec,
                        key="on_click",
                    )

        for content in contents:
            part_value = content.value
            if part_value is None:
                msg = "Each rx.ui.tabs.content requires a value prop."
                raise ValueError(msg)
            content.custom_attrs.setdefault(
                "data-state",
                cond(current == part_value, "active", "inactive"),
            )

        return component

    def _exclude_props(self) -> list[str]:
        return [
            *super()._exclude_props(),
            "default_value",
            "value",
            "on_change",
        ]


class TabsNamespace(ComponentNamespace):
    """Namespace for tabs components."""

    root = staticmethod(Tabs.create)
    list = staticmethod(TabsList.create)
    trigger = staticmethod(TabsTrigger.create)
    content = staticmethod(TabsContent.create)
    __call__ = staticmethod(Tabs.create)


tabs = TabsNamespace()
