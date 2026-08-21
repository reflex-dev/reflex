"""A form label styled with Tailwind classes."""

from __future__ import annotations

from typing import ClassVar

from reflex_components_core.el.elements import forms
from reflex_components_core.ui.base import UIComponent

LABEL_CLASS_NAME = (
    "flex items-center gap-2 text-sm leading-none font-medium select-none "
    "peer-disabled:cursor-not-allowed peer-disabled:opacity-50"
)


class Label(forms.Label, UIComponent):
    """A label for a form control."""

    _slot: ClassVar[str | None] = "label"

    @classmethod
    def create(cls, *children, **props):
        """Create a label.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The label component.
        """
        cls._apply_class_name(LABEL_CLASS_NAME, props)
        return super().create(*children, **props)


label = Label.create
