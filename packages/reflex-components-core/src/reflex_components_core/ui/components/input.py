"""A text input styled with Tailwind classes on the native input element."""

from __future__ import annotations

from typing import ClassVar

from reflex_components_core.el.elements import forms
from reflex_components_core.ui.base import UIComponent

INPUT_CLASS_NAME = (
    "flex h-9 w-full min-w-0 rounded-md border border-input bg-transparent "
    "px-3 py-1 text-base md:text-sm shadow-xs transition-[color,box-shadow] "
    "outline-none placeholder:text-muted-foreground "
    "selection:bg-primary selection:text-primary-foreground "
    "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 "
    "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] "
    "aria-invalid:border-destructive aria-invalid:ring-destructive/20 "
    "file:inline-flex file:h-7 file:border-0 file:bg-transparent "
    "file:text-sm file:font-medium file:text-foreground"
)


class Input(forms.Input, UIComponent):
    """A themable input built on the native input element."""

    _slot: ClassVar[str | None] = "input"

    @classmethod
    def create(cls, *children, **props):
        """Create an input.

        Args:
            *children: Unused; inputs render no children.
            **props: The props of the component.

        Returns:
            The input component.
        """
        cls._apply_class_name(INPUT_CLASS_NAME, props)
        return super().create(*children, **props)


input = Input.create
