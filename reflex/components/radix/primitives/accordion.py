"""Radix accordion components."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from reflex.components.component import Component, ComponentNamespace
from reflex.components.core.match import Match
from reflex.components.lucide.icon import Icon
from reflex.components.radix.primitives.base import RadixPrimitiveComponent
from reflex.components.radix.themes.base import LiteralAccentColor
from reflex.style import (
    Style,
    convert_dict_to_style_and_format_emotion,
    format_as_emotion,
)
from reflex.utils import imports
from reflex.vars import BaseVar, Var, VarData, get_uuid_string_var

LiteralAccordionType = Literal["single", "multiple"]
LiteralAccordionDir = Literal["ltr", "rtl"]
LiteralAccordionOrientation = Literal["vertical", "horizontal"]
LiteralAccordionRootVariant = Literal["classic", "soft", "surface", "outline", "ghost"]
LiteralAccordionRootColorScheme = Literal["primary", "accent"]

DEFAULT_ANIMATION_DURATION = 250


def get_theme_accordion_root(variant: Var[str], color_scheme: Var[str]) -> BaseVar:
    """Get the theme for the accordion root component.

    Args:
        variant: The variant of the accordion.
        color_scheme: The color of the accordion.

    Returns:
        The theme for the accordion root component.
    """
    return Match.create(  # type: ignore
        variant,
        (
            "soft",
            convert_dict_to_style_and_format_emotion(
                {
                    "border_radius": "6px",
                    "background_color": f"var(--{color_scheme}-3)",
                    "box_shadow": "0 2px 10px var(--black-a1)",
                }
            ),
        ),
        (
            "outline",
            convert_dict_to_style_and_format_emotion(
                {
                    "border_radius": "6px",
                    "border": f"1px solid var(--{color_scheme}-6)",
                    "box_shadow": "0 2px 10px var(--black-a1)",
                }
            ),
        ),
        (
            "surface",
            convert_dict_to_style_and_format_emotion(
                {
                    "border_radius": "6px",
                    "border": f"1px solid var(--{color_scheme}-6)",
                    "background_color": f"var(--{color_scheme}-3)",
                    "box_shadow": "0 2px 10px var(--black-a1)",
                }
            ),
        ),
        (
            "ghost",
            convert_dict_to_style_and_format_emotion(
                {
                    "border_radius": "6px",
                    "background_color": "none",
                    "box_shadow": "None",
                }
            ),
        ),
        convert_dict_to_style_and_format_emotion(
            {
                "border_radius": "6px",
                "background_color": f"var(--{color_scheme}-9)",
                "box_shadow": "0 2px 10px var(--black-a4)",
            }
        ),
        # defaults to classic
    )


def get_theme_accordion_item():
    """Get the theme for the accordion item component.

    Returns:
        The theme for the accordion item component.
    """
    return convert_dict_to_style_and_format_emotion(
        {
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
    )


def get_theme_accordion_header() -> dict[str, str]:
    """Get the theme for the accordion header component.

    Returns:
        The theme for the accordion header component.
    """
    return {
        "display": "flex",
    }


def get_theme_accordion_trigger(variant: str | Var, color_scheme: str | Var) -> BaseVar:
    """Get the theme for the accordion trigger component.

    Args:
        variant: The variant of the accordion.
        color_scheme: The color of the accordion.

    Returns:
        The theme for the accordion trigger component.
    """
    return Match.create(  # type: ignore
        variant,
        (
            "soft",
            convert_dict_to_style_and_format_emotion(
                {
                    "color": f"var(--{color_scheme}-11)",
                    "&:hover": {
                        "background_color": f"var(--{color_scheme}-4)",
                    },
                    "& > .AccordionChevron": {
                        "color": f"var(--{color_scheme}-11)",
                        "transition": f"transform {DEFAULT_ANIMATION_DURATION}ms cubic-bezier(0.87, 0, 0.13, 1)",
                    },
                    "&[data-state='open'] > .AccordionChevron": {
                        "transform": "rotate(180deg)",
                    },
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
                }
            ),
        ),
        (
            "outline",
            "surface",
            "ghost",
            convert_dict_to_style_and_format_emotion(
                {
                    "color": f"var(--{color_scheme}-11)",
                    "&:hover": {
                        "background_color": f"var(--{color_scheme}-4)",
                    },
                    "& > .AccordionChevron": {
                        "color": f"var(--{color_scheme}-11)",
                        "transition": f"transform {DEFAULT_ANIMATION_DURATION}ms cubic-bezier(0.87, 0, 0.13, 1)",
                    },
                    "&[data-state='open'] > .AccordionChevron": {
                        "transform": "rotate(180deg)",
                    },
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
                }
            ),
        ),
        # defaults to classic
        convert_dict_to_style_and_format_emotion(
            {
                "color": f"var(--{color_scheme}-9-contrast)",
                "box_shadow": f"var(--{color_scheme}-11)",
                "&:hover": {
                    "background_color": f"var(--{color_scheme}-10)",
                },
                "& > .AccordionChevron": {
                    "color": f"var(--{color_scheme}-9-contrast)",
                    "transition": f"transform {DEFAULT_ANIMATION_DURATION}ms cubic-bezier(0.87, 0, 0.13, 1)",
                },
                "&[data-state='open'] > .AccordionChevron": {
                    "transform": "rotate(180deg)",
                },
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
            }
        ),
    )


def get_theme_accordion_content(variant: str | Var, color_scheme: str | Var) -> BaseVar:
    """Get the theme for the accordion content component.

    Args:
        variant: The variant of the accordion.
        color_scheme: The color of the accordion.

    Returns:
        The theme for the accordion content component.
    """
    return Match.create(  # type: ignore
        variant,
        (
            "outline",
            "ghost",
            convert_dict_to_style_and_format_emotion(
                {
                    "overflow": "hidden",
                    "font_size": "10px",
                    "color": f"var(--{color_scheme}-11)",
                    "padding": "15px 20px",
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
            ),
        ),
        convert_dict_to_style_and_format_emotion(
            {
                "overflow": "hidden",
                "font_size": "10px",
                "color": Match.create(
                    variant,
                    ("classic", f"var(--{color_scheme}-9-contrast)"),
                    f"var(--{color_scheme}-11)",
                ),
                "background_color": Match.create(
                    variant,
                    ("classic", f"var(--{color_scheme}-9)"),
                    f"var(--{color_scheme}-3)",
                ),
                "padding": "15px 20px",
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
        ),
    )


class AccordionComponent(RadixPrimitiveComponent):
    """Base class for all @radix-ui/accordion components."""

    library = "@radix-ui/react-accordion@^1.1.2"


class AccordionRoot(AccordionComponent):
    """An accordion component."""

    tag = "Root"

    alias = "RadixAccordionRoot"

    # The type of accordion (single or multiple).
    type: Var[LiteralAccordionType]

    # The value of the item to expand.
    value: Var[Optional[Union[str, List[str]]]]

    # The default value of the item to expand.
    default_value: Var[Optional[Union[str, List[str]]]]

    # Whether or not the accordion is collapsible.
    collapsible: Var[bool]

    # Whether or not the accordion is disabled.
    disabled: Var[bool]

    # The reading direction of the accordion when applicable.
    dir: Var[LiteralAccordionDir]

    # The orientation of the accordion.
    orientation: Var[LiteralAccordionOrientation]

    # The variant of the accordion.
    variant: Var[LiteralAccordionRootVariant] = "classic"  # type: ignore

    # The color scheme of the accordion.
    color_scheme: Var[LiteralAccentColor]  # type: ignore

    # dynamic themes of the accordion generated at compile time.
    _dynamic_themes: Var[dict] = Var.create({})  # type: ignore

    # The var_data associated with the component.
    _var_data: VarData = VarData()  # type: ignore

    _valid_children: List[str] = ["AccordionItem"]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the Accordion root component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The Accordion root Component.
        """
        comp = super().create(*children, **props)

        if comp.color_scheme is not None and not comp.color_scheme._var_state:  # type: ignore
            # mark the vars of color string literals as strings so they can be formatted properly when performing a var operation.
            comp.color_scheme._var_is_string = True  # type: ignore

        if comp.variant is not None and not comp.variant._var_state:  # type: ignore
            # mark the vars of variant string literals as strings so they are formatted properly in the match condition.
            comp.variant._var_is_string = True  # type: ignore

        return comp

    def _get_style(self) -> dict:
        """Get the style for the component.

        Returns:
            The dictionary of the component style as value and the style notation as key.
        """
        return {"css": self._dynamic_themes._merge(format_as_emotion(self.style))}  # type: ignore

    def _apply_theme(self, theme: Component):
        global_color_scheme = getattr(theme, "accent_color", None)

        if global_color_scheme is None and self.color_scheme is None:
            raise ValueError(
                "`color_scheme` cannot be None. Either set the `color_scheme` prop on the accordion "
                "component or set the `accent_color` prop in your global theme."
            )

        # prepare the color_scheme var to be used in an f-string(strip off the wrapping curly brace)
        color_scheme = Var.create(
            self.color_scheme if self.color_scheme is not None else global_color_scheme
        )._replace(  # type: ignore
            _var_is_string=False
        )

        accordion_theme_root = get_theme_accordion_root(
            variant=self.variant, color_scheme=color_scheme
        )
        accordion_theme_content = get_theme_accordion_content(
            variant=self.variant, color_scheme=color_scheme
        )
        accordion_theme_trigger = get_theme_accordion_trigger(
            variant=self.variant, color_scheme=color_scheme
        )

        # extract var_data from dynamic themes.
        self._var_data = (
            self._var_data.merge(  # type: ignore
                accordion_theme_trigger._var_data,
                accordion_theme_content._var_data,
                accordion_theme_root._var_data,
            )
            or self._var_data
        )

        self._dynamic_themes = Var.create(  # type: ignore
            convert_dict_to_style_and_format_emotion(
                {
                    "& .AccordionItem": get_theme_accordion_item(),
                    "& .AccordionHeader": get_theme_accordion_header(),
                    "& .AccordionTrigger": accordion_theme_trigger,
                    "& .AccordionContent": accordion_theme_content,
                }
            )
        )._merge(  # type: ignore
            accordion_theme_root
        )

    def _get_imports(self):
        return imports.merge_imports(
            super()._get_imports(),
            self._var_data.imports if self._var_data else {},
            {"@emotion/react": [imports.ImportVar(tag="keyframes")]},
        )

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            "on_value_change": lambda e0: [e0],
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

    def _exclude_props(self) -> list[str]:
        return ["color_scheme", "variant"]


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

    def _apply_theme(self, theme: Component):
        self.style = Style(
            {
                **self.style,
            }
        )

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
            header: The header of the accordion item.
            content: The content of the accordion item.
            *children: The list of children to use if header and content are not provided.
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

        if (header is not None) and (content is not None):
            children = [
                AccordionHeader.create(
                    AccordionTrigger.create(
                        header,
                        AccordionIcon.create(),
                    ),
                ),
                AccordionContent.create(content),
            ]

        return super().create(*children, value=value, **props, class_name=cls_name)


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

    def _apply_theme(self, theme: Component):
        self.style = Style({**self.style})


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

    def _apply_theme(self, theme: Component):
        self.style = Style({**self.style})


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

    def _apply_theme(self, theme: Component):
        self.style = Style({**self.style})

    # def _get_imports(self):
    #     return {
    #         **super()._get_imports(),
    #         "@emotion/react": [imports.ImportVar(tag="keyframes")],
    #     }


class Accordion(ComponentNamespace):
    """Accordion component."""

    content = staticmethod(AccordionContent.create)
    header = staticmethod(AccordionHeader.create)
    item = staticmethod(AccordionItem.create)
    icon = staticmethod(AccordionIcon.create)
    root = staticmethod(AccordionRoot.create)
    trigger = staticmethod(AccordionTrigger.create)


accordion = Accordion()
