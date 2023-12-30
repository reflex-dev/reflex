"""Radix accordion components."""

from typing import Literal

from reflex.components.component import Component
from reflex.components.radix.primitives.base import RadixPrimitiveComponent
from reflex.components.radix.themes.components.icons import Icon
from reflex.style import Style
from reflex.utils import imports
from reflex.vars import Var

LiteralAccordionType = Literal["single", "multiple"]
LiteralAccordionDir = Literal["ltr", "rtl"]
LiteralAccordionOrientation = Literal["vertical", "horizontal"]


DEFAULT_ANIMATION_DURATION = 250


class AccordionComponent(RadixPrimitiveComponent):
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

    def _apply_theme(self, theme: Component):
        self.style = Style(
            {
                "border_radius": "6px",
                "background_color": "var(--accent-6)",
                "box_shadow": "0 2px 10px var(--black-a4)",
                **self.style,
            }
        )


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
                "overflow": "hidden",
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
                    "box_shadow": "0 0 0 2px var(--accent-7)",
                },
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
                "display": "flex",
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
                "font_family": "inherit",
                "padding": "0 20px",
                "height": "45px",
                "flex": 1,
                "display": "flex",
                "align_items": "center",
                "justify_content": "space-between",
                "font_size": "15px",
                "line_height": 1,
                "color": "var(--accent-11)",
                "box_shadow": "0 1px 0 var(--accent-6)",
                "&:hover": {
                    "background_color": "var(--gray-2)",
                },
                "& > .AccordionChevron": {
                    "color": "var(--accent-10)",
                    "transition": f"transform {DEFAULT_ANIMATION_DURATION}ms cubic-bezier(0.87, 0, 0.13, 1)",
                },
                "&[data-state='open'] > .AccordionChevron": {
                    "transform": "rotate(180deg)",
                },
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
                "overflow": "hidden",
                "fontSize": "15px",
                "color": "var(--accent-11)",
                "backgroundColor": "var(--accent-2)",
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
            ),
        ),
        AccordionContent.create(
            content,
        ),
        value=value,
        **props,
    )


accordion = AccordionRoot.create
