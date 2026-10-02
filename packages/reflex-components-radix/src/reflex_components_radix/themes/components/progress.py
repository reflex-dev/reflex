"""Progress from Radix Themes."""

from typing import Literal

from reflex_base.components.component import Component, field
from reflex_base.style import Style
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_radix.themes.base import LiteralAccentColor, RadixThemesComponent


class Progress(RadixThemesComponent):
    """A progress bar component."""

    tag = "Progress"

    value: Var[int] = field(doc="The value of the progress bar: 0 to max (default 100)")

    max: Var[int] = field(doc="The maximum progress value.")

    size: Var[Responsive[Literal["1", "2", "3"]]] = field(
        doc='The size of the progress bar: "1" | "2" | "3"'
    )

    variant: Var[Literal["classic", "surface", "soft"]] = field(
        doc='The variant of the progress bar: "classic" | "surface" | "soft"'
    )

    color_scheme: Var[LiteralAccentColor] = field(
        doc="The color theme of the progress bar"
    )

    high_contrast: Var[bool] = field(
        doc="Whether to render the progress bar with higher contrast color against background"
    )

    radius: Var[Literal["none", "small", "medium", "large", "full"]] = field(
        doc='Override theme radius for progress bar: "none" | "small" | "medium" | "large" | "full"'
    )

    duration: Var[str] = field(
        doc="The duration of the progress bar animation. Once the duration times out, the progress bar will start an indeterminate animation."
    )

    fill_color: Var[str] = field(doc="The color of the progress bar fill animation.")

    @staticmethod
    def _color_selector(color: str) -> Style:
        """Return a style object with the correct color and css selector.

        Args:
            color: Color of the fill part.

        Returns:
            Style: Style object with the correct css selector and color.
        """
        return Style({".rt-ProgressIndicator": {"background_color": color}})

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a Progress component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The Progress Component.
        """
        props.setdefault("width", "100%")
        if "fill_color" in props:
            color = props.get("fill_color", "")
            style = props.get("style", {})
            style = style | cls._color_selector(color)
            props["style"] = style

        return super().create(*children, **props)


progress = Progress.create
