"""Wrapper around react-debounce-input."""

from __future__ import annotations

from typing import Any, Type

from reflex.components.component import Component
from reflex.constants import EventTriggers
from reflex.event import EventHandler, no_args_event_spec
from reflex.vars import VarData
from reflex.vars.base import Var

DEFAULT_DEBOUNCE_TIMEOUT = 300


class DebounceInput(Component):
    """The DebounceInput component is used to buffer input events on the client side.

    It is intended to wrap various form controls and should be used whenever a
    fully-controlled input is needed to prevent lost input data when the backend
    is experiencing high latency.
    """

    library = "react-debounce-input@3.3.0"
    tag = "DebounceInput"

    # Minimum input characters before triggering the on_change event
    min_length: Var[int]

    # Time to wait between end of input and triggering on_change
    debounce_timeout: Var[int] = Var.create(DEFAULT_DEBOUNCE_TIMEOUT)

    # If true, notify when Enter key is pressed
    force_notify_by_enter: Var[bool]

    # If true, notify when form control loses focus
    force_notify_on_blur: Var[bool]

    # If provided, create a fully-controlled input
    value: Var[str | int | float]

    # The ref to attach to the created input
    input_ref: Var[str]

    # The element to wrap
    element: Var[Type[Component]]

    # Fired when the input value changes
    on_change: EventHandler[no_args_event_spec]

    @classmethod
    def create(cls, *children: Component, **props: Any) -> Component:
        """Create a DebounceInput component.

        Carry first child props directly on this tag.

        Since react-debounce-input wants to create and manage the underlying
        input component itself, we carry all props, events, and styles from
        the child, and then neuter the child's render method so it produces no output.

        Args:
            children: The child component to wrap.
            props: The component props.

        Returns:
            The DebounceInput component.

        Raises:
            RuntimeError: unless exactly one child element is provided.
            ValueError: if the child element does not have an on_change handler.
        """
        if len(children) != 1:
            raise RuntimeError(
                "Provide a single child for DebounceInput, such as rx.input() or "
                "rx.text_area()",
            )

        child = children[0]
        if "on_change" not in child.event_triggers:
            raise ValueError("DebounceInput child requires an on_change handler")

        # Carry known props and event_triggers from the child.
        props_from_child = {
            p: getattr(child, p)
            for p in cls.get_props()
            if getattr(child, p, None) is not None
        }
        props[EventTriggers.ON_CHANGE] = child.event_triggers.pop(
            EventTriggers.ON_CHANGE
        )
        props = {**props_from_child, **props}

        # Carry all other child props directly via custom_attrs
        other_props = {
            p: getattr(child, p)
            for p in child.get_props()
            if p not in props_from_child and getattr(child, p) is not None
        }
        props.setdefault("custom_attrs", {}).update(other_props, **child.custom_attrs)

        # Carry base Component props.
        props.setdefault("style", {}).update(child.style)
        if child.class_name is not None:
            props["class_name"] = f"{props.get('class_name', '')} {child.class_name}"
        for field in ("key", "special_props"):
            if getattr(child, field) is not None:
                props[field] = getattr(child, field)
        child_ref = child.get_ref()
        if props.get("input_ref") is None and child_ref:
            props["input_ref"] = Var(_js_expr=child_ref, _var_type=str)
            props["id"] = child.id

        # Set the child element to wrap, including any imports/hooks from the child.
        props.setdefault(
            "element",
            Var(
                _js_expr=str(child.alias or child.tag),
                _var_type=Type[Component],
                _var_data=VarData(
                    imports=child._get_imports(),
                    hooks=child._get_all_hooks(),
                ),
            ),
        )

        component = super().create(**props)
        component._get_style = child._get_style
        component.event_triggers.update(child.event_triggers)
        component.children = child.children
        component._rename_props = child._rename_props  # pyright: ignore[reportAttributeAccessIssue]
        outer_get_all_custom_code = component._get_all_custom_code
        component._get_all_custom_code = lambda: outer_get_all_custom_code().union(
            child._get_all_custom_code()
        )
        return component

    def _render(self):
        return super()._render().remove_props("ref")


debounce_input = DebounceInput.create
