"""A checkbox styled with Tailwind classes on the native input element."""

from __future__ import annotations

from typing import ClassVar

from reflex_components_core.el.elements import forms
from reflex_components_core.ui.base import UIComponent

# The check mark is drawn with a clip-path polygon on the ::before
# pseudo-element, so no icon assets or fonts are required.
CHECKBOX_CLASS_NAME = (
    "peer appearance-none size-4 shrink-0 rounded-[4px] border border-input "
    "bg-background shadow-xs transition-shadow outline-none cursor-pointer "
    "grid place-content-center "
    "before:content-[''] before:size-2.5 before:scale-0 before:transition-transform "
    "before:bg-primary-foreground "
    "before:[clip-path:polygon(14%_44%,0_59%,42%_100%,100%_19%,86%_5%,42%_71%)] "
    "checked:bg-primary checked:border-primary checked:before:scale-100 "
    "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] "
    "aria-invalid:border-destructive aria-invalid:ring-destructive/20 "
    "disabled:cursor-not-allowed disabled:opacity-50"
)


class Checkbox(forms.CheckboxInput, UIComponent):
    """A themable checkbox built on the native input element."""

    _slot: ClassVar[str | None] = "checkbox"

    @classmethod
    def create(cls, *children, **props):
        """Create a checkbox.

        Args:
            *children: Unused; checkboxes render no children.
            **props: The props of the component.

        Returns:
            The checkbox component.
        """
        props["type"] = "checkbox"
        cls._apply_class_name(CHECKBOX_CLASS_NAME, props)
        return super().create(*children, **props)


checkbox = Checkbox.create
