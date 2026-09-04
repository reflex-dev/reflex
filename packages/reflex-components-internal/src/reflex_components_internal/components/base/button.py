"""Custom button component."""

from typing import Literal

from reflex_components_core.core.cond import cond
from reflex_components_core.el.elements.forms import Button as BaseButton

from reflex.components.component import ComponentNamespace
from reflex.vars.base import Var
from reflex_components_internal.components.component import CoreComponent
from reflex_components_internal.components.icons.others import spinner

LiteralButtonVariant = Literal[
    "primary",
    "primary-bordered",
    "destructive",
    "outline",
    "outline-shadow",
    "secondary",
    "ghost",
    "ghost-highlight",
    "link",
    "dark",
]
LiteralButtonSize = Literal[
    "xs", "sm", "md", "lg", "xl", "icon-xs", "icon-sm", "icon-md", "icon-lg", "icon-xl"
]

DEFAULT_CLASS_NAME = "inline-flex items-center justify-center whitespace-nowrap text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:border disabled:border-secondary-4/80 disabled:bg-secondary-3 disabled:text-secondary-8 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 cursor-pointer box-border"

BUTTON_VARIANTS = {
    "variant": {
        "primary": "bg-primary-9 text-primary-contrast hover:bg-primary-10",
        "primary-bordered": "bg-primary-9 text-primary-contrast hover:bg-primary-10 shadow-button-bordered disabled:shadow-none",
        "destructive": "bg-destructive-9 hover:bg-destructive-10 text-primary-contrast",
        "outline": "border border-secondary-a4 bg-secondary-1 hover:bg-secondary-3 text-secondary-12",
        "outline-shadow": "dark:shadow-[0_1px_0_0_rgba(255,255,255,0.08)_inset] bg-white hover:bg-secondary-2 dark:bg-secondary-3 dark:hover:bg-secondary-4 text-secondary-12 shadow-button-outline disabled:shadow-none",
        "secondary": "bg-secondary-4 text-secondary-12 hover:bg-secondary-5",
        "ghost": "hover:bg-secondary-3 text-secondary-11",
        "ghost-highlight": "text-secondary-12 hover:text-primary-9",
        "link": "text-secondary-12 underline-offset-4 hover:underline",
        "dark": "bg-secondary-12 text-secondary-1 hover:bg-secondary-12/80",
    },
    "size": {
        "xs": "px-1.5 h-7 rounded-ui-xs gap-1.5",
        "sm": "px-2 h-8 rounded-ui-sm gap-2",
        "md": "px-2.5 h-9 rounded-ui-md gap-2",
        "lg": "px-3 h-10 rounded-ui-lg gap-2.5",
        "xl": "px-3.5 h-12 rounded-ui-xl gap-3",
        "icon-xs": "size-7 rounded-ui-xs",
        "icon-sm": "size-8 rounded-ui-sm",
        "icon-md": "size-9 rounded-ui-md",
        "icon-lg": "size-10 rounded-ui-lg",
        "icon-xl": "size-12 rounded-ui-xl",
    },
}


class ClassNames:
    """Class names for button components."""

    DEFAULT = DEFAULT_CLASS_NAME
    VARIANTS = BUTTON_VARIANTS

    @staticmethod
    def for_button(variant: str = "primary", size: str = "md") -> str:
        """Return combined class string for the given variant and size."""
        return f"{ClassNames.DEFAULT} {ClassNames.VARIANTS['variant'][variant]} {ClassNames.VARIANTS['size'][size]}"


class Button(BaseButton, CoreComponent):
    """A custom button component."""

    # Button variant. Defaults to "primary".
    variant: Var[LiteralButtonVariant]

    # Button size. Defaults to "md".
    size: Var[LiteralButtonSize]

    # The loading state of the button
    loading: Var[bool]

    @classmethod
    def create(cls, *children, **props) -> BaseButton:
        """Create the button component.

        Returns:
            The component.
        """
        variant = props.pop("variant", "primary")
        cls.validate_variant(variant)

        size = props.pop("size", "md")
        cls.validate_size(size)

        loading = props.pop("loading", False)
        disabled = props.pop("disabled", False)

        button_classes = f"{DEFAULT_CLASS_NAME} {BUTTON_VARIANTS['variant'][variant]} {BUTTON_VARIANTS['size'][size]}"

        cls.set_class_name(button_classes, props)

        children_list = list(children)

        if isinstance(loading, Var):
            props["disabled"] = cond(loading, True, disabled)
            children_list.insert(0, cond(loading, spinner()))
        else:
            props["disabled"] = True if loading else disabled
            children_list.insert(0, spinner()) if loading else None

        return super().create(*children_list, **props)

    @staticmethod
    def validate_variant(variant: LiteralButtonVariant):
        """Validate the button variant."""
        if variant not in BUTTON_VARIANTS["variant"]:
            available_variants = ", ".join(BUTTON_VARIANTS["variant"].keys())
            message = (
                f"Invalid variant: {variant}. Available variants: {available_variants}"
            )
            raise ValueError(message)

    @staticmethod
    def validate_size(size: LiteralButtonSize):
        """Validate the button size."""
        if size not in BUTTON_VARIANTS["size"]:
            available_sizes = ", ".join(BUTTON_VARIANTS["size"].keys())
            message = f"Invalid size: {size}. Available sizes: {available_sizes}"
            raise ValueError(message)

    def _exclude_props(self) -> list[str]:
        return [
            *super()._exclude_props(),
            "size",
            "variant",
            "loading",
        ]


class ButtonNamespace(ComponentNamespace):
    """Namespace for Button components."""

    create = staticmethod(Button.create)
    class_names = ClassNames
    __call__ = staticmethod(Button.create)


button = ButtonNamespace()
