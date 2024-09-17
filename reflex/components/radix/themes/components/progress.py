"""Progress from Radix Themes."""

from typing import Literal

from reflex.components.component import Component
from reflex.components.core.breakpoints import Responsive
from reflex.style import Style
from reflex.vars.base import Var

from ..base import LiteralAccentColor, RadixThemesComponent


class Progress(RadixThemesComponent):
    """A progress bar component."""

    tag = "Progress"

    # The value of the progress bar: 0 to max (default 100)
    value: Var[int]

    # The maximum progress value.
    max: Var[int]

    # The size of the progress bar: "1" | "2" | "3"
    size: Var[Responsive[Literal["1", "2", "3"]]]

    # The variant of the progress bar: "classic" | "surface" | "soft"
    variant: Var[Literal["classic", "surface", "soft"]]

    # The color theme of the progress bar
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the progress bar with higher contrast color against background
    high_contrast: Var[bool]

    # Override theme radius for progress bar: "none" | "small" | "medium" | "large" | "full"
    radius: Var[Literal["none", "small", "medium", "large", "full"]]

    # The duration of the progress bar animation. Once the duration times out, the progress bar will start an indeterminate animation.
    duration: Var[str]

    # The color of the progress bar fill animation.
    fill_color: Var[str]

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
