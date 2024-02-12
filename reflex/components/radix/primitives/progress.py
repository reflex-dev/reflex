"""Progress."""

from __future__ import annotations

from typing import Optional

from reflex.components.component import Component
from reflex.components.radix.primitives.base import RadixPrimitiveComponentWithClassName
from reflex.style import Style
from reflex.vars import Var


class ProgressComponent(RadixPrimitiveComponentWithClassName):
    """A Progress component."""

    library = "@radix-ui/react-progress@^1.0.3"


class ProgressRoot(ProgressComponent):
    """The Progress Root component."""

    tag = "Root"
    alias = "RadixProgressRoot"

    # The current progress value.
    value: Var[Optional[int]]

    # The maximum progress value.
    max: Var[int]

    def _apply_theme(self, theme: Component):
        self.style = Style(
            {
                "position": "relative",
                "overflow": "hidden",
                "background": "black",
                "border_radius": "99999px",
                "width": "300px",
                "height": "25px",
                **self.style,
            }
        )


class ProgressIndicator(ProgressComponent):
    """The Progress bar indicator."""

    tag = "Indicator"

    alias = "RadixProgressIndicator"

    # The current progress value.
    value: Var[Optional[int]]

    def _apply_theme(self, theme: Component):
        self.style = Style(
            {
                "background-color": "white",
                "width": "100%",
                "height": "100%",
                "transition": f"transform 660ms linear",
                "&[data_state='loading']": {
                    "transition": f"transform 660ms linear",
                },
                "transform": f"translateX(-{100 - self.value}%)",  # type: ignore
            }
        )


progress_root = ProgressRoot.create
progress_indicator = ProgressIndicator.create


def progress(**props):
    """High level API for progress bar.

    Args:
        **props: The props of the progress bar

    Returns:
        The progress bar.
    """
    return progress_root(
        progress_indicator(value=props.get("value")),
        **props,
    )
