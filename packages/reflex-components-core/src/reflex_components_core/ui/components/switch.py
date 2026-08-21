"""A switch styled with Tailwind classes on the native checkbox element."""

from __future__ import annotations

from typing import ClassVar

from reflex_components_core.el.elements import forms
from reflex_components_core.ui.base import UIComponent

# The thumb is the ::before pseudo-element, translated when checked.
SWITCH_CLASS_NAME = (
    "peer appearance-none inline-flex h-5 w-9 shrink-0 items-center "
    "rounded-full border border-transparent bg-input shadow-xs "
    "transition-colors outline-none cursor-pointer "
    "before:content-[''] before:block before:size-4 before:rounded-full "
    "before:bg-background before:shadow-sm before:transition-transform "
    "before:translate-x-0.5 checked:before:translate-x-4 "
    "checked:bg-primary "
    "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] "
    "disabled:cursor-not-allowed disabled:opacity-50"
)


class Switch(forms.CheckboxInput, UIComponent):
    """A themable toggle switch built on the native checkbox element."""

    _slot: ClassVar[str | None] = "switch"

    @classmethod
    def create(cls, *children, **props):
        """Create a switch.

        Args:
            *children: Unused; switches render no children.
            **props: The props of the component.

        Returns:
            The switch component.
        """
        props["type"] = "checkbox"
        props.setdefault("role", "switch")
        cls._apply_class_name(SWITCH_CLASS_NAME, props)
        return super().create(*children, **props)


switch = Switch.create
