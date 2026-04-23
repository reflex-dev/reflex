"""Custom button component."""

from typing import Literal

import reflex as rx
from reflex.vars.base import Var

LiteralButtonVariant = Literal["primary", "destructive", "outline", "ghost"]
LiteralButtonSize = Literal[
    "xs", "sm", "md", "lg", "icon-xs", "icon-sm", "icon-md", "icon-lg"
]


class Button(rx.Component):
    """A custom button component."""

    library = "$/public/components/GradientButton"

    tag = "GradientButton"

    # Button variant. Defaults to "primary".
    variant: Var[LiteralButtonVariant]

    # Button size. Defaults to "md".
    size: Var[LiteralButtonSize]

    # Whether to use a native button element. Defaults to True. If False, the button will be rendered as a div element.
    native_button: Var[bool] = rx.Var.create(True)

    def add_imports(self) -> rx.ImportDict:
        """Add imports to the component.

        Returns:
            The component.
        """
        return {
            "clsx-for-tailwind": "cn",
        }


button = Button.create
