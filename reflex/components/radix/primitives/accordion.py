"""Radix accordion components."""

from typing import Literal

from reflex.components.component import Component
from reflex.components.radix.primitives.base import RadixPrimitiveComponent
from reflex.components.radix.themes.components.icons import Icon
from reflex.components.radix.themes.layout import Box
from reflex.components.core import match, cond
from reflex.components.base import Fragment
from reflex.style import Style
from reflex.utils import imports
from reflex.vars import Var

LiteralAccordionType = Literal["single", "multiple"]
LiteralAccordionDir = Literal["ltr", "rtl"]
LiteralAccordionOrientation = Literal["vertical", "horizontal"]

DEFAULT_ANIMATION_DURATION = 250


# Helper methods


def get_theme_accordion_root(variant: Var[str], color: Var[str]):
    """Get the theme for the accordion root component.

    Args:
        variant: The variant of the accordion.
        color: The color of the accordion.

    Returns:
        The theme for the accordion root component.
    """
    return match(
        (
            "classic",
            {
                "border_radius": "6px",
                "background_color": cond(
                    color == "primary", "var(--accent-9)", "var(--slate-9)"
                ),
                "box_shadow": "0 2px 10px var(--black-a4)",
            },
        ),
        (
            "soft",
            {
                "border_radius": "6px",
                "background_color": cond(
                    color == "primary", "var(--accent-3)", "var(--slate-3)"
                ),
                "box_shadow": "0 2px 10px var(--black-a1)",
            },
        ),
        {},
    )


def get_theme_accordion_item(variant: str):
    """Get the theme for the accordion item component.

    Args:
        variant: The variant of the accordion.

    Returns:
        The theme for the accordion item component.
    """
    return {
        "overflow": "hidden",
        "width": "100%",
        "margin_top": "1px",
        "&:first-child": {
            "margin_top": 0,
            "border_top_left_radius": "4px",
            "border_top_right_radius": "4px",
        },
        "&:last-child": {
            "border_bottom_left_radius": "4px",
            "border_bottom_right_radius": "4px",
        },
        "&:focus-within": {
            "position": "relative",
            "z_index": 1,
        },
    }


def get_theme_accordion_header(variant: str):
    """Get the theme for the accordion header component.

    Args:
        variant: The variant of the accordion.

    Returns:
        The theme for the accordion header component.
    """
    return {
        "display": "flex",
    }


def get_theme_accordion_trigger(variant: str, color: str):
    """Get the theme for the accordion trigger component.

    Args:
        variant: The variant of the accordion.
        color: The color of the accordion.

    Returns:
        The theme for the accordion trigger component.
    """
    if variant == "classic":
        return {
            "font_family": "inherit",
            "width": "100%",
            "padding": "0 20px",
            "height": "45px",
            "flex": 1,
            "display": "flex",
            "align_items": "center",
            "justify_content": "space-between",
            "font_size": "15px",
            "line_height": 1,
            "color": "var(--accent-9-contrast)"
            if color == "primary"
            else "var(--slate-9-contrast)",
            "box_shadow": "0 1px 0 var(--accent-6)",
            "&:hover": {
                "background_color": "var(--accent-10)"
                if color == "primary"
                else "var(--slate-10)",
            },
            "& > .AccordionChevron": {
                "color": "var(--accent-9-contrast)"
                if color == "primary"
                else "var(--slate-9-contrast)",
                "transition": f"transform {DEFAULT_ANIMATION_DURATION}ms cubic-bezier(0.87, 0, 0.13, 1)",
            },
            "&[data-state='open'] > .AccordionChevron": {
                "transform": "rotate(180deg)",
            },
        }
    if variant == "soft":
        return {
            "font_family": "inherit",
            "width": "100%",
            "padding": "0 20px",
            "height": "45px",
            "flex": 1,
            "display": "flex",
            "align_items": "center",
            "justify_content": "space-between",
            "font_size": "15px",
            "line_height": 1,
            "color": "var(--accent-11)" if color == "primary" else "var(--slate-11)",
            "box_shadow": "0 1px 0 var(--accent-6)",
            "&:hover": {
                "background_color": "var(--accent-4)"
                if color == "primary"
                else "var(--slate-4)",
            },
            "& > .AccordionChevron": {
                "color": "var(--accent-11)"
                if color == "primary"
                else "var(--slate-11)",
                "transition": f"transform {DEFAULT_ANIMATION_DURATION}ms cubic-bezier(0.87, 0, 0.13, 1)",
            },
            "&[data-state='open'] > .AccordionChevron": {
                "transform": "rotate(180deg)",
            },
        }
    if variant == "outline":
        return {
            "font_family": "inherit",
            "width": "100%",
            "padding": "0 20px",
            "height": "45px",
            "flex": 1,
            "display": "flex",
            "align_items": "center",
            "justify_content": "space-between",
            "font_size": "15px",
            "line_height": 1,
            "color": "var(--accent-11)" if color == "primary" else "var(--slate-11)",
            "box_shadow": "0 1px 0 var(--accent-6)",
            "&:hover": {
                "background_color": "var(--accent-4)"
                if color == "primary"
                else "var(--slate-4)",
            },
            "& > .AccordionChevron": {
                "color": "var(--accent-11)"
                if color == "primary"
                else "var(--slate-11)",
                "transition": f"transform {DEFAULT_ANIMATION_DURATION}ms cubic-bezier(0.87, 0, 0.13, 1)",
            },
            "&[data-state='open'] > .AccordionChevron": {
                "transform": "rotate(180deg)",
            },
        }
    if variant == "surface":
        return {
            "font_family": "inherit",
            "width": "100%",
            "padding": "0 20px",
            "height": "45px",
            "flex": 1,
            "display": "flex",
            "align_items": "center",
            "justify_content": "space-between",
            "font_size": "15px",
            "line_height": 1,
            "color": "var(--accent-11)" if color == "primary" else "var(--slate-11)",
            "box_shadow": "0 1px 0 var(--accent-6)",
            "&:hover": {
                "background_color": "var(--accent-4)"
                if color == "primary"
                else "var(--slate-4)",
            },
            "& > .AccordionChevron": {
                "color": "var(--accent-11)"
                if color == "primary"
                else "var(--slate-11)",
                "transition": f"transform {DEFAULT_ANIMATION_DURATION}ms cubic-bezier(0.87, 0, 0.13, 1)",
            },
            "&[data-state='open'] > .AccordionChevron": {
                "transform": "rotate(180deg)",
            },
        }
    if variant == "ghost":
        return {
            "font_family": "inherit",
            "width": "100%",
            "padding": "0 20px",
            "height": "45px",
            "flex": 1,
            "display": "flex",
            "align_items": "center",
            "justify_content": "space-between",
            "font_size": "15px",
            "line_height": 1,
            "color": "var(--accent-11)" if color == "primary" else "var(--slate-11)",
            "box_shadow": "0 1px 0 var(--accent-6)",
            "&:hover": {
                "background_color": "var(--accent-4)"
                if color == "primary"
                else "var(--slate-4)",
            },
            "& > .AccordionChevron": {
                "color": "var(--accent-11)"
                if color == "primary"
                else "var(--slate-11)",
                "transition": f"transform {DEFAULT_ANIMATION_DURATION}ms cubic-bezier(0.87, 0, 0.13, 1)",
            },
            "&[data-state='open'] > .AccordionChevron": {
                "transform": "rotate(180deg)",
            },
        }


def get_theme_accordion_content(variant: str, color: str):
    """Get the theme for the accordion content component.

    Args:
        variant: The variant of the accordion.
        color: The color of the accordion.

    Returns:
        The theme for the accordion content component.
    """
    if variant == "classic":
        return {
            "overflow": "hidden",
            "font_size": "10px",
            "color": "var(--accent-9-contrast)"
            if color == "primary"
            else "var(--slate-9-contrast)",
            "background_color": "var(--accent-9)"
            if color == "primary"
            else "var(--slate-9)",
            "padding": "15px, 20px",
            "&[data-state='open']": {
                "animation": Var.create(
                    f"${{slideDown}} {DEFAULT_ANIMATION_DURATION}ms cubic-bezier(0.87, 0, 0.13, 1)",
                    _var_is_string=True,
                ),
            },
            "&[data-state='closed']": {
                "animation": Var.create(
                    f"${{slideUp}} {DEFAULT_ANIMATION_DURATION}ms cubic-bezier(0.87, 0, 0.13, 1)",
                    _var_is_string=True,
                ),
            },
        }
    elif variant == "soft":
        return {
            "overflow": "hidden",
            "font_size": "10px",
            "color": "var(--accent-11)" if color == "primary" else "var(--slate-11)",
            "background_color": "var(--accent-3)"
            if color == "primary"
            else "var(--slate-3)",
            "padding": "15px, 20px",
            "&[data-state='open']": {
                "animation": Var.create(
                    f"${{slideDown}} {DEFAULT_ANIMATION_DURATION}ms cubic-bezier(0.87, 0, 0.13, 1)",
                    _var_is_string=True,
                ),
            },
            "&[data-state='closed']": {
                "animation": Var.create(
                    f"${{slideUp}} {DEFAULT_ANIMATION_DURATION}ms cubic-bezier(0.87, 0, 0.13, 1)",
                    _var_is_string=True,
                ),
            },
        }
    elif variant == "outline":
        return {
            "overflow": "hidden",
            "font_size": "10px",
            "color": "var(--accent-11)" if color == "primary" else "var(--slate-11)",
            "padding": "15px, 20px",
            "&[data-state='open']": {
                "animation": Var.create(
                    f"${{slideDown}} {DEFAULT_ANIMATION_DURATION}ms cubic-bezier(0.87, 0, 0.13, 1)",
                    _var_is_string=True,
                ),
            },
            "&[data-state='closed']": {
                "animation": Var.create(
                    f"${{slideUp}} {DEFAULT_ANIMATION_DURATION}ms cubic-bezier(0.87, 0, 0.13, 1)",
                    _var_is_string=True,
                ),
            },
        }
    elif variant == "surface":
        return {
            "overflow": "hidden",
            "font_size": "10px",
            "color": "var(--accent-11)" if color == "primary" else "var(--slate-11)",
            "background_color": "var(--accent-3)"
            if color == "primary"
            else "var(--slate-3)",
            "padding": "15px, 20px",
            "&[data-state='open']": {
                "animation": Var.create(
                    f"${{slideDown}} {DEFAULT_ANIMATION_DURATION}ms cubic-bezier(0.87, 0, 0.13, 1)",
                    _var_is_string=True,
                ),
            },
            "&[data-state='closed']": {
                "animation": Var.create(
                    f"${{slideUp}} {DEFAULT_ANIMATION_DURATION}ms cubic-bezier(0.87, 0, 0.13, 1)",
                    _var_is_string=True,
                ),
            },
        }
    elif variant == "ghost":
        return {
            "overflow": "hidden",
            "font_size": "10px",
            "color": "var(--accent-11)" if color == "primary" else "var(--slate-11)",
            "padding": "15px, 20px",
            "&[data-state='open']": {
                "animation": Var.create(
                    f"${{slideDown}} {DEFAULT_ANIMATION_DURATION}ms cubic-bezier(0.87, 0, 0.13, 1)",
                    _var_is_string=True,
                ),
            },
            "&[data-state='closed']": {
                "animation": Var.create(
                    f"${{slideUp}} {DEFAULT_ANIMATION_DURATION}ms cubic-bezier(0.87, 0, 0.13, 1)",
                    _var_is_string=True,
                ),
            },
        }


class AccordionComponent(Component):
    """Base class for all @radix-ui/accordion components."""

    library = "@radix-ui/react-accordion@^1.1.2"


class AccordionRoot(AccordionComponent):
    """An accordion component."""

    tag = "Root"

    alias = "RadixAccordionRoot"

    # The type of accordion (single or multiple).
    type_: Var[LiteralAccordionType]

    # The value of the item to expand.
    value: Var[str]

    # The default value of the item to expand.
    default_value: Var[str]

    # Whether or not the accordion is collapsible.
    collapsible: Var[bool]

    # Whether or not the accordion is disabled.
    disabled: Var[bool]

    # The reading direction of the accordion when applicable.
    dir: Var[LiteralAccordionDir]

    # The orientation of the accordion.
    orientation: Var[LiteralAccordionOrientation]

    variant: Literal["classic", "soft", "surface", "outline", "ghost"] = "classic"

    color: Literal["primary", "accent"] = "primary"

    def _apply_theme(self, theme: Component):

        self.style = Var.create(Style(
            {
                "& .AccordionItem": get_theme_accordion_item(variant=self.variant),
                "& .AccordionHeader": get_theme_accordion_header(variant=self.variant),
                "& .AccordionTrigger": get_theme_accordion_trigger(
                    variant=self.variant, color=self.color
                ),
                "& .AccordionContent": get_theme_accordion_content(
                    variant=self.variant, color=self.color
                ),
                **self.style,
            }
        ))

        self.style= Var.create(self.style._merge(get_theme_accordion_root(variant=self.variant, color=self.color))) # type: ignore 

    @classmethod
    def create(cls, *children, **props) -> Component:
        return super().create(*children, **props)


class AccordionItem(AccordionComponent):
    """An accordion component."""

    tag = "Item"

    alias = "RadixAccordionItem"

    # A unique identifier for the item.
    value: Var[str]

    # When true, prevents the user from interacting with the item.
    disabled: Var[bool]

    def _apply_theme(self, theme: Component):
        self.style = Style(
            {
                **self.style,
            }
        )


class AccordionHeader(AccordionComponent):
    """An accordion component."""

    tag = "Header"

    alias = "RadixAccordionHeader"

    def _apply_theme(self, theme: Component):
        self.style = Style(
            {
                **self.style,
            }
        )


class AccordionTrigger(AccordionComponent):
    """An accordion component."""

    tag = "Trigger"

    alias = "RadixAccordionTrigger"

    def _apply_theme(self, theme: Component):
        self.style = Style(
            {
                **self.style,
            }
        )


class AccordionContent(AccordionComponent):
    """An accordion component."""

    tag = "Content"

    alias = "RadixAccordionContent"

    def _apply_theme(self, theme: Component):
        self.style = Style(
            {
                **self.style,
            }
        )

    def _get_imports(self):
        return {
            **super()._get_imports(),
            "@emotion/react": [imports.ImportVar(tag="keyframes")],
        }

    def _get_custom_code(self) -> str:
        return """
const slideDown = keyframes`
from {
  height: 0;
}
to {
  height: var(--radix-accordion-content-height);
}
`
const slideUp = keyframes`
from {
  height: var(--radix-accordion-content-height);
}
to {
  height: 0;
}
`
"""


def accordion_item(header: Component, content: Component, **props) -> Component:
    """Create an accordion item.

    Args:
        header: The header of the accordion item.
        content: The content of the accordion item.
        **props: Additional properties to apply to the accordion item.

    Returns:
        The accordion item.
    """
    # The item requires a value to toggle (use the header as the default value).
    value = props.pop("value", str(header))

    return AccordionItem.create(
        AccordionHeader.create(
            AccordionTrigger.create(
                header,
                Icon.create(
                    tag="chevron_down",
                    class_name="AccordionChevron",
                ),
                class_name="AccordionTrigger",
            ),
        ),
        AccordionContent.create(
            content,
            class_name="AccordionContent",
        ),
        value=value,
        **props,
        class_name="AccordionItem",
    )


accordion = AccordionRoot.create
accordion_root = AccordionRoot.create
accordion_header = AccordionHeader.create
accordion_trigger = AccordionTrigger.create
accordion_content = AccordionContent.create
