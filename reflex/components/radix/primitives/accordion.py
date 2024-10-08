"""Radix accordion components."""

from __future__ import annotations

from typing import Any, List, Literal, Optional, Union

from reflex.components.component import Component, ComponentNamespace
from reflex.components.core.colors import color
from reflex.components.core.cond import cond
from reflex.components.lucide.icon import Icon
from reflex.components.radix.primitives.base import RadixPrimitiveComponent
from reflex.components.radix.themes.base import LiteralAccentColor, LiteralRadius
from reflex.event import EventHandler
from reflex.style import Style
from reflex.vars import get_uuid_string_var
from reflex.vars.base import LiteralVar, Var

LiteralAccordionType = Literal["single", "multiple"]
LiteralAccordionDir = Literal["ltr", "rtl"]
LiteralAccordionOrientation = Literal["vertical", "horizontal"]
LiteralAccordionVariant = Literal["classic", "soft", "surface", "outline", "ghost"]

DEFAULT_ANIMATION_DURATION = 250
DEFAULT_ANIMATION_EASING = "cubic-bezier(0.87, 0, 0.13, 1)"


def _inherited_variant_selector(
    variant: Var[LiteralAccordionVariant] | LiteralAccordionVariant,
    *selectors: str,
) -> str:
    """Create a multi CSS selector for targeting variant against the given selectors.

    Args:
        variant: The variant to target.
        selectors: The selectors to apply the variant to (default &)

    Returns:
        A CSS selector that is more specific on elements that directly set the variant.
    """
    if not selectors:
        selectors = ("&",)
    # Prefer the `data-variant` that is set directly on the selector,
    # but also inherit the `data-variant` from any parent element.
    return ", ".join(
        [
            f"{selector}[data-variant='{variant}'], *:where([data-variant='{variant}']) {selector}"
            for selector in selectors
        ]
    )


class AccordionComponent(RadixPrimitiveComponent):
    """Base class for all @radix-ui/accordion components."""

    library = "@radix-ui/react-accordion@^1.1.2"

    # The color scheme of the component.
    color_scheme: Var[LiteralAccentColor]

    # The variant of the component.
    variant: Var[LiteralAccordionVariant]

    def add_style(self):
        """Add style to the component."""
        if self.color_scheme is not None:
            self.custom_attrs["data-accent-color"] = self.color_scheme
        if self.variant is not None:
            self.custom_attrs["data-variant"] = self.variant

    def _exclude_props(self) -> list[str]:
        return ["color_scheme", "variant"]


class AccordionRoot(AccordionComponent):
    """An accordion component."""

    tag = "Root"

    alias = "RadixAccordionRoot"

    # The type of accordion (single or multiple).
    type: Var[LiteralAccordionType]

    # The value of the item to expand.
    value: Var[Union[str, List[str]]]

    # The default value of the item to expand.
    default_value: Var[Union[str, List[str]]]

    # Whether or not the accordion is collapsible.
    collapsible: Var[bool]

    # Whether or not the accordion is disabled.
    disabled: Var[bool]

    # The reading direction of the accordion when applicable.
    dir: Var[LiteralAccordionDir]

    # The orientation of the accordion.
    orientation: Var[LiteralAccordionOrientation]

    # The radius of the accordion corners.
    radius: Var[LiteralRadius]

    # The time in milliseconds to animate open and close
    duration: Var[int] = LiteralVar.create(DEFAULT_ANIMATION_DURATION)

    # The easing function to use for the animation.
    easing: Var[str] = LiteralVar.create(DEFAULT_ANIMATION_EASING)

    # Whether to show divider lines between items.
    show_dividers: Var[bool]

    _valid_children: List[str] = ["AccordionItem"]

    # Fired when the opened the accordions changes.
    on_value_change: EventHandler[lambda e0: [e0]]

    def _exclude_props(self) -> list[str]:
        return super()._exclude_props() + [
            "radius",
            "duration",
            "easing",
            "show_dividers",
        ]

    def add_style(self):
        """Add style to the component.

        Returns:
            The style of the component.
        """
        if self.radius is not None:
            self.custom_attrs["data-radius"] = self.radius
        if self.variant is None:
            # The default variant is classic
            self.custom_attrs["data-variant"] = "classic"

        style = {
            "border_radius": "var(--radius-4)",
            "box_shadow": f"0 2px 10px {color('black', 1, alpha=True)}",
            "&[data-variant='classic']": {
                "background_color": color("accent", 9),
                "box_shadow": f"0 2px 10px {color('black', 4, alpha=True)}",
            },
            "&[data-variant='soft']": {
                "background_color": color("accent", 3),
            },
            "&[data-variant='outline']": {
                "border": f"1px solid {color('accent', 6)}",
            },
            "&[data-variant='surface']": {
                "border": f"1px solid {color('accent', 6)}",
                "background_color": "var(--accent-surface)",
            },
            "&[data-variant='ghost']": {
                "background_color": "none",
                "box_shadow": "None",
            },
            "--animation-duration": f"{self.duration}ms",
            "--animation-easing": self.easing,
        }
        if self.show_dividers is not None:
            style["--divider-px"] = cond(self.show_dividers, "1px", "0")
        else:
            style["&[data-variant='outline']"]["--divider-px"] = "1px"
            style["&[data-variant='surface']"]["--divider-px"] = "1px"
        return Style(style)


class AccordionItem(AccordionComponent):
    """An accordion component."""

    tag = "Item"

    alias = "RadixAccordionItem"

    # A unique identifier for the item.
    value: Var[str]

    # When true, prevents the user from interacting with the item.
    disabled: Var[bool]

    _valid_children: List[str] = [
        "AccordionHeader",
        "AccordionTrigger",
        "AccordionContent",
    ]

    _valid_parents: List[str] = ["AccordionRoot"]

    @classmethod
    def create(
        cls,
        *children,
        header: Optional[Component | Var] = None,
        content: Optional[Component | Var] = None,
        **props,
    ) -> Component:
        """Create an accordion item.

        Args:
            *children: The list of children to use if header and content are not provided.
            header: The header of the accordion item.
            content: The content of the accordion item.
            **props: Additional properties to apply to the accordion item.

        Returns:
            The accordion item.
        """
        # The item requires a value to toggle (use a random unique name if not provided).
        value = props.pop("value", get_uuid_string_var())

        if "AccordionItem" not in (
            cls_name := props.pop("class_name", "AccordionItem")
        ):
            cls_name = f"{cls_name} AccordionItem"

        color_scheme = props.get("color_scheme")
        variant = props.get("variant")

        if (header is not None) and (content is not None):
            children = [
                AccordionHeader.create(
                    AccordionTrigger.create(
                        header,
                        AccordionIcon.create(
                            color_scheme=color_scheme,
                            variant=variant,
                        ),
                        color_scheme=color_scheme,
                        variant=variant,
                    ),
                    color_scheme=color_scheme,
                    variant=variant,
                ),
                AccordionContent.create(
                    content,
                    color_scheme=color_scheme,
                    variant=variant,
                ),
            ]

        return super().create(*children, value=value, **props, class_name=cls_name)

    def add_style(self) -> dict[str, Any] | None:
        """Add style to the component.

        Returns:
            The style of the component.
        """
        divider_style = f"var(--divider-px) solid {color('gray', 6, alpha=True)}"
        return {
            "overflow": "hidden",
            "width": "100%",
            "margin_top": "1px",
            "border_top": divider_style,
            "&:first-child": {
                "margin_top": 0,
                "border_top": 0,
                "border_top_left_radius": "var(--radius-4)",
                "border_top_right_radius": "var(--radius-4)",
            },
            "&:last-child": {
                "border_bottom_left_radius": "var(--radius-4)",
                "border_bottom_right_radius": "var(--radius-4)",
            },
            "&:focus-within": {
                "position": "relative",
                "z_index": 1,
            },
            _inherited_variant_selector("ghost", "&:first-child"): {
                "border_radius": 0,
                "border_top": divider_style,
            },
            _inherited_variant_selector("ghost", "&:last-child"): {
                "border_radius": 0,
                "border_bottom": divider_style,
            },
        }


class AccordionHeader(AccordionComponent):
    """An accordion component."""

    tag = "Header"

    alias = "RadixAccordionHeader"

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the Accordion header component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The Accordion header Component.
        """
        if "AccordionHeader" not in (
            cls_name := props.pop("class_name", "AccordionHeader")
        ):
            cls_name = f"{cls_name} AccordionHeader"

        return super().create(*children, class_name=cls_name, **props)

    def add_style(self) -> dict[str, Any] | None:
        """Add style to the component.

        Returns:
            The style of the component.
        """
        return {"display": "flex"}


class AccordionTrigger(AccordionComponent):
    """An accordion component."""

    tag = "Trigger"

    alias = "RadixAccordionTrigger"

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the Accordion trigger component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The Accordion trigger Component.
        """
        if "AccordionTrigger" not in (
            cls_name := props.pop("class_name", "AccordionTrigger")
        ):
            cls_name = f"{cls_name} AccordionTrigger"

        return super().create(*children, class_name=cls_name, **props)

    def add_style(self) -> dict[str, Any] | None:
        """Add style to the component.

        Returns:
            The style of the component.
        """
        return {
            "color": color("accent", 11),
            "font_size": "1.1em",
            "line_height": 1,
            "justify_content": "space-between",
            "align_items": "center",
            "flex": 1,
            "display": "flex",
            "padding": "var(--space-3) var(--space-4)",
            "width": "100%",
            "box_shadow": f"0 var(--divider-px) 0 {color('gray', 6, alpha=True)}",
            "&[data-state='open'] > .AccordionChevron": {
                "transform": "rotate(180deg)",
            },
            "&:hover": {
                "background_color": color("accent", 4),
            },
            "& > .AccordionChevron": {
                "transition": f"transform var(--animation-duration) var(--animation-easing)",
            },
            _inherited_variant_selector("classic"): {
                "color": "var(--accent-contrast)",
                "&:hover": {
                    "background_color": color("accent", 10),
                },
                "& > .AccordionChevron": {
                    "color": "var(--accent-contrast)",
                },
            },
        }


class AccordionIcon(Icon):
    """An accordion icon component."""

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the Accordion icon component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The Accordion icon Component.
        """
        if "AccordionChevron" not in (
            cls_name := props.pop("class_name", "AccordionChevron")
        ):
            cls_name = f"{cls_name} AccordionChevron"

        return super().create(tag="chevron_down", class_name=cls_name, **props)


class AccordionContent(AccordionComponent):
    """An accordion component."""

    tag = "Content"

    alias = "RadixAccordionContent"

    def add_imports(self) -> dict:
        """Add imports to the component.

        Returns:
            The imports of the component.
        """
        return {"@emotion/react": "keyframes"}

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the Accordion content component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The Accordion content Component.
        """
        if "AccordionContent" not in (
            cls_name := props.pop("class_name", "AccordionContent")
        ):
            cls_name = f"{cls_name} AccordionContent"

        return super().create(*children, class_name=cls_name, **props)

    def add_custom_code(self) -> list[str]:
        """Add custom code to the component.

        Returns:
            The custom code of the component.
        """
        return [
            """
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
        ]

    def add_style(self) -> dict[str, Any] | None:
        """Add style to the component.

        Returns:
            The style of the component.
        """
        slideDown = LiteralVar.create(
            f"${{slideDown}} var(--animation-duration) var(--animation-easing)",
        )

        slideUp = LiteralVar.create(
            f"${{slideUp}} var(--animation-duration) var(--animation-easing)",
        )

        return {
            "overflow": "hidden",
            "color": color("accent", 11),
            "padding_x": "var(--space-4)",
            # Apply before and after content to avoid height animation jank.
            "&:before, &:after": {
                "content": "' '",
                "display": "block",
                "height": "var(--space-3)",
            },
            "&[data-state='open']": {"animation": slideDown},
            "&[data-state='closed']": {"animation": slideUp},
            _inherited_variant_selector("classic"): {
                "color": "var(--accent-contrast)",
            },
        }


class Accordion(ComponentNamespace):
    """Accordion component."""

    content = staticmethod(AccordionContent.create)
    header = staticmethod(AccordionHeader.create)
    item = staticmethod(AccordionItem.create)
    icon = staticmethod(AccordionIcon.create)
    root = staticmethod(AccordionRoot.create)
    trigger = staticmethod(AccordionTrigger.create)


accordion = Accordion()
