"""A loading spinner built from a single element and Tailwind classes."""

from __future__ import annotations

from typing import ClassVar

from reflex_components_core.el.elements.inline import Span
from reflex_components_core.ui.base import UIComponent

SPINNER_CLASS_NAME = (
    "inline-block size-4 shrink-0 animate-spin rounded-full "
    "border-2 border-current border-t-transparent"
)


class Spinner(Span, UIComponent):
    """An indeterminate loading indicator."""

    _slot: ClassVar[str | None] = "spinner"

    @classmethod
    def create(cls, *children, **props):
        """Create a spinner.

        Size and color follow the surrounding text by default; override with
        Tailwind classes like ``size-6`` or ``text-primary``.

        Args:
            *children: Unused; spinners render no children.
            **props: The props of the component.

        Returns:
            The spinner component.
        """
        props.setdefault("role", "status")
        props.setdefault("aria_label", "Loading")
        cls._apply_class_name(SPINNER_CLASS_NAME, props)
        return super().create(*children, **props)


spinner = Spinner.create
