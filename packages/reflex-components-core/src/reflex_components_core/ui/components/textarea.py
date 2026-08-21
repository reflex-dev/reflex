"""A textarea styled with Tailwind classes on the native textarea element."""

from __future__ import annotations

from typing import ClassVar

from reflex_components_core.el.elements import forms
from reflex_components_core.ui.base import UIComponent

TEXTAREA_CLASS_NAME = (
    "flex field-sizing-content min-h-16 w-full rounded-md border border-input "
    "bg-transparent px-3 py-2 text-base md:text-sm shadow-xs "
    "transition-[color,box-shadow] outline-none placeholder:text-muted-foreground "
    "disabled:cursor-not-allowed disabled:opacity-50 "
    "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] "
    "aria-invalid:border-destructive aria-invalid:ring-destructive/20"
)


class Textarea(forms.Textarea, UIComponent):
    """A themable multi-line text input built on the native textarea element."""

    _slot: ClassVar[str | None] = "textarea"

    @classmethod
    def create(cls, *children, **props):
        """Create a textarea.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The textarea component.
        """
        cls._apply_class_name(TEXTAREA_CLASS_NAME, props)
        return super().create(*children, **props)


textarea = Textarea.create
