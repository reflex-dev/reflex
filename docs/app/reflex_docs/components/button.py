from typing import Callable, Literal

import reflex as rx
from reflex_site_shared.components.icons import get_icon

LiteralButtonVariant = Literal[
    "primary", "success", "destructive", "secondary", "muted"
]

default_class_name = "text-sm font-medium rounded-control cursor-pointer inline-flex items-center justify-center px-4 py-2 relative transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:opacity-50"


variant_styles = {
    "primary": {
        "class_name": "bg-primary text-primary-foreground hover:bg-primary-hover",
    },
    "success": {
        "class_name": "bg-success-9 hover:bg-success-10 text-white",
    },
    "destructive": {
        "class_name": "bg-destructive hover:bg-destructive/90 text-white",
    },
    "muted": {
        "class_name": "bg-muted hover:bg-accent-hover text-muted-foreground",
    },
    "secondary": {
        "class_name": "bg-muted hover:bg-accent-hover text-foreground",
    },
}


def button(
    text: str,
    variant: LiteralButtonVariant = "primary",
    onclick: Callable | None = None,
    style: dict | None = None,
    class_name: str = "",
    *children,
    **props,
) -> rx.Component:
    return rx.el.button(
        text,
        *children,
        onclick=onclick,
        style=style if style is not None else {},
        class_name=default_class_name
        + " "
        + variant_styles[variant]["class_name"]
        + " "
        + class_name,
        **props,
    )


def button_with_icon(
    text: str,
    icon: str,
    variant: LiteralButtonVariant = "primary",
    onclick: Callable | None = None,
    style: dict | None = None,
    class_name: str = "",
    *children,
    **props,
) -> rx.Component:
    return rx.el.button(
        get_icon(icon, class_name="[&>svg]:size-5"),
        text,
        *children,
        onclick=onclick,
        style=style if style is not None else {},
        class_name=default_class_name
        + " "
        + variant_styles[variant]["class_name"]
        + " "
        + class_name,
        **props,
    )
