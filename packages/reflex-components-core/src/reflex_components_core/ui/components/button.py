"""A button styled with Tailwind classes on the native button element."""

from __future__ import annotations

from typing import ClassVar, Literal

from reflex_base.components.component import field
from reflex_base.vars.base import Var

from reflex_components_core.core.cond import cond
from reflex_components_core.el.elements import forms
from reflex_components_core.ui.base import UIComponent
from reflex_components_core.ui.components.spinner import spinner
from reflex_components_core.ui.styling import variant_class

LiteralButtonVariant = Literal[
    "primary", "secondary", "destructive", "outline", "ghost", "link"
]
LiteralButtonSize = Literal["sm", "md", "lg", "icon", "icon-sm", "icon-lg"]

BUTTON_CLASS_NAME = (
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md "
    "text-sm font-medium transition-all outline-none cursor-pointer shrink-0 "
    "disabled:pointer-events-none disabled:opacity-50 "
    "[&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4 "
    "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] "
    "aria-invalid:border-destructive aria-invalid:ring-destructive/20"
)

BUTTON_VARIANTS: dict[str, str] = {
    "primary": "bg-primary text-primary-foreground shadow-xs hover:bg-primary/90",
    "secondary": "bg-secondary text-secondary-foreground shadow-xs hover:bg-secondary/80",
    "destructive": (
        "bg-destructive text-destructive-foreground shadow-xs "
        "hover:bg-destructive/90 focus-visible:ring-destructive/20"
    ),
    "outline": (
        "border border-input bg-background shadow-xs "
        "hover:bg-accent hover:text-accent-foreground"
    ),
    "ghost": "hover:bg-accent hover:text-accent-foreground",
    "link": "text-primary underline-offset-4 hover:underline",
}

BUTTON_SIZES: dict[str, str] = {
    "sm": "h-8 rounded-md gap-1.5 px-3",
    "md": "h-9 px-4 py-2",
    "lg": "h-10 rounded-md px-6",
    "icon": "size-9",
    "icon-sm": "size-8",
    "icon-lg": "size-10",
}


class Button(forms.Button, UIComponent):
    """A themable button built on the native button element."""

    _slot: ClassVar[str | None] = "button"

    variant: Var[LiteralButtonVariant] = field(
        doc='Visual style of the button. Defaults to "primary".'
    )

    size: Var[LiteralButtonSize] = field(doc='Size of the button. Defaults to "md".')

    loading: Var[bool] = field(doc="Show a spinner and disable the button while true.")

    @classmethod
    def create(cls, *children, **props):
        """Create a button.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The button component.
        """
        variant = variant_class(
            props.pop("variant", None),
            BUTTON_VARIANTS,
            default="primary",
            prop="variant",
            component="rx.ui.button",
        )
        size = variant_class(
            props.pop("size", None),
            BUTTON_SIZES,
            default="md",
            prop="size",
            component="rx.ui.button",
        )
        default_class_name: str | list = (
            f"{BUTTON_CLASS_NAME} {variant} {size}"
            if isinstance(variant, str) and isinstance(size, str)
            else [BUTTON_CLASS_NAME, variant, size]
        )
        cls._apply_class_name(default_class_name, props)

        loading = props.pop("loading", None)
        children_list = list(children)
        if loading is not None:
            disabled = props.pop("disabled", False)
            if isinstance(loading, Var):
                props["disabled"] = cond(loading, True, disabled)
                children_list.insert(0, cond(loading, spinner()))
            elif loading:
                props["disabled"] = True
                children_list.insert(0, spinner())
            else:
                props["disabled"] = disabled
        return super().create(*children_list, **props)

    def _exclude_props(self) -> list[str]:
        return [
            *super()._exclude_props(),
            "variant",
            "size",
            "loading",
        ]


button = Button.create
