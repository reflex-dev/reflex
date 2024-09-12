"""Progress from Radix Themes."""

from typing import Literal

from reflex.components.component import Component
from reflex.components.core.breakpoints import Responsive
from reflex.ivars.base import ImmutableVar

from ..base import LiteralAccentColor, RadixThemesComponent


class Progress(RadixThemesComponent):
    """A progress bar component."""

    tag = "Progress"

    # The value of the progress bar: 0 to max (default 100)
    value: ImmutableVar[int]

    # The maximum progress value.
    max: ImmutableVar[int]

    # The size of the progress bar: "1" | "2" | "3"
    size: ImmutableVar[Responsive[Literal["1", "2", "3"]]]

    # The variant of the progress bar: "classic" | "surface" | "soft"
    variant: ImmutableVar[Literal["classic", "surface", "soft"]]

    # The color theme of the progress bar
    color_scheme: ImmutableVar[LiteralAccentColor]

    # Whether to render the progress bar with higher contrast color against background
    high_contrast: ImmutableVar[bool]

    # Override theme radius for progress bar: "none" | "small" | "medium" | "large" | "full"
    radius: ImmutableVar[Literal["none", "small", "medium", "large", "full"]]

    # The duration of the progress bar animation. Once the duration times out, the progress bar will start an indeterminate animation.
    duration: ImmutableVar[str]

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
        return super().create(*children, **props)


progress = Progress.create
