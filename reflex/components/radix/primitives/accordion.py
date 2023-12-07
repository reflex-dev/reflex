"""Radix accordion components."""

from typing import Literal

from reflex.components.component import Component
from reflex.components.tags import Tag
from reflex.style import Style
from reflex.utils import format, imports
from reflex.vars import Var

LiteralAccordionType = Literal["single", "multiple"]
LiteralAccordionDir = Literal["ltr", "rtl"]
LiteralAccordionOrientation = Literal["vertical", "horizontal"]


DEFAULT_ANIMATION_DURATION = 250


class AccordionComponent(Component):
    """Base class for all @radix-ui/accordion components."""

    library = "@radix-ui/react-accordion@^1.1.2"

    # Change the default rendered element for the one passed as a child.
    as_child: Var[bool]

    def _render(self) -> Tag:
        return (
            super()
            ._render()
            .add_props(
                **{
                    "class_name": format.to_title_case(self.tag or ""),
                }
            )
        )


class AccordionRoot(AccordionComponent):
    """An accordion component."""

    tag = "Root"

    alias = "RadixAccordionRoot"

    style: Style = Style(
        {
            "borderRadius": "6px",
            "width": "300px",
            "backgroundColor": "var(--accent-6)",
            "boxShadow": "0 2px 10px var(--black-a4)",
        }
    )

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


class AccordionItem(AccordionComponent):
    """An accordion component."""

    tag = "Item"

    alias = "RadixAccordionItem"

    style: Style = Style(
        {
            "overflow": "hidden",
            "marginTop": "1px",
            "&:first-child": {
                "marginTop": 0,
                "borderTopLeftRadius": "4px",
                "borderTopRightRadius": "4px",
            },
            "&:last-child": {
                "borderBottomLeftRadius": "4px",
                "borderBottomRightRadius": "4px",
            },
            "&:focus-within": {
                "position": "relative",
                "zIndex": 1,
                "boxShadow": "0 0 0 2px var(--accent-7)",
            },
        }
    )

    # A unique identifier for the item.
    value: Var[str]

    # When true, prevents the user from interacting with the item.
    disabled: Var[bool]


class AccordionHeader(AccordionComponent):
    """An accordion component."""

    tag = "Header"

    alias = "RadixAccordionHeader"

    style: Style = Style(
        {
            "display": "flex",
        }
    )


class AccordionTrigger(AccordionComponent):
    """An accordion component."""

    tag = "Trigger"

    alias = "RadixAccordionTrigger"

    style: Style = Style(
        {
            "fontFamily": "inherit",
            "backgroundColor": "transparent",
            "padding": "0 20px",
            "height": "45px",
            "flex": 1,
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "space-between",
            "fontSize": "15px",
            "lineHeight": 1,
            "color": "var(--accent-11)",
            "boxShadow": "0 1px 0 var(--accent-6)",
            "&:hover": {
                "backgroundColor": "var(--gray-2)",
            },
            "&[data-state='open'] > .AccordionChevron": {
                "transform": "rotate(180deg)",
            },
        }
    )


class AccordionContent(AccordionComponent):
    """An accordion component."""

    tag = "Content"

    alias = "RadixAccordionContent"

    style: Style = Style(
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


# TODO: Remove this once the radix-icons PR is merged in.
class ChevronDownIcon(Component):
    """A chevron down icon."""

    library = "@radix-ui/react-icons"

    tag = "ChevronDownIcon"

    style: Style = Style(
        {
            "color": "var(--accent-10)",
            "transition": f"transform {DEFAULT_ANIMATION_DURATION}ms cubic-bezier(0.87, 0, 0.13, 1)",
        }
    )
