"""A button."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from reflex_base.components.component import Component, field
from reflex_base.components.tags import CommonTag
from reflex_base.vars.base import LiteralVar, Var, VarData
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.el import elements

from reflex_components_ui.base import Part, UIComponent
from reflex_components_ui.components.spinner import leaves, while_loading
from reflex_components_ui.props import LiteralVariant
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.button import BUTTON
from reflex_components_ui.themes import LiteralAccentColor, LiteralRadius

LiteralButtonSize = Literal["1", "2", "3", "4"]


def _either(first: Var | None, second: Var | None) -> Var | None:
    """Combine two flags, either of which may be left out.

    Args:
        first: A flag.
        second: Another one.

    Returns:
        Whether one of them is set, or None when neither is given.
    """
    if first is None or second is None:
        return second if first is None else first
    if isinstance(first, LiteralVar) and isinstance(second, LiteralVar):
        return LiteralVar.create(bool(first._var_value or second._var_value))
    return Var(
        f"({first!s} || {second!s})",
        _var_type=bool,
        _var_data=VarData.merge(first._get_all_var_data(), second._get_all_var_data()),
    )


class BaseButton(UIComponent, elements.Button):
    """What a button and an icon button share."""

    tag = "button"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )

    size: Var[Responsive[LiteralButtonSize]] = field(doc='Button size "1" - "4"')

    color_scheme: Var[LiteralAccentColor] = field(doc="Override theme color for button")

    high_contrast: Var[bool] = field(
        doc="Whether to render the button with higher contrast color against background"
    )

    radius: Var[LiteralRadius] = field(
        doc='Override theme radius for button: "none" | "small" | "medium" | "large" | "full"'
    )

    loading: Var[bool] = field(
        doc="If set, show an rx.spinner instead of the component children."
    )

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a button, with a spinner over its children while it loads.

        Args:
            *children: The children of the button.
            **props: The props of the button.

        Returns:
            The button.
        """
        loading = props.get("loading")
        if loading is not None and not props.get("as_child"):
            # As Radix Themes renders it: the children keep their place
            # without being shown, and are still read out.
            children = while_loading(
                loading,
                [
                    Part.create(
                        *children,
                        part="content",
                        tag="span",
                        custom_attrs={"aria-hidden": True},
                    ),
                    Part.create(*children, part="label", tag="span"),
                    Part.create(
                        Part.create(*leaves(), part="spinner", tag="span"),
                        part="overlay",
                        tag="span",
                    ),
                ],
                children,
            )
        return super().create(*children, **props)

    def _exclude_props(self) -> list[str]:
        """Keep the props that are not attributes off the element.

        Returns:
            The props read as styles, and the one that shows the spinner.
        """
        return [*super()._exclude_props(), "loading"]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the button, disabled while it loads.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag: a disabled button says so in ``data-disabled`` too,
            which is what its styles select on, so that an element rendered
            in its place with ``as_child`` looks disabled as well.
        """
        tag = super()._render(props)
        disabled = _either(self.disabled, self.loading)
        if disabled is None:
            return tag
        if isinstance(disabled, LiteralVar):
            if not disabled._var_value:
                return tag
            return tag.add_props(disabled=True, **{"data-disabled": True})
        return tag.add_props(
            disabled=disabled,
            **{
                "data-disabled": Var(
                    f"({disabled!s} || undefined)",
                    _var_data=disabled._get_all_var_data(),
                )
            },
        )


class Button(BaseButton):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    styles: ClassVar[ComponentStyles] = BUTTON

    variant: Var[LiteralVariant] = field(
        doc='Variant of button: "solid" | "soft" | "outline" | "ghost"'
    )


button = Button.create
