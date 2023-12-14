"""Progress."""

from typing import Optional

from reflex.components.component import Component
from reflex.components.radix.primitives.base import RadixPrimitiveComponent
from reflex.style import Style
from reflex.vars import Var


class ProgressComponent(RadixPrimitiveComponent):
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

    def _apply_theme(self, theme: Component | None):
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

    def _apply_theme(self, theme: Component | None):
        self.style = Style(
            {
                "background-color": "white",
                "width": "var(--data-max - --data-value)%",
                "height": "100%",
                "transition": f"transform 660ms cubic-bezier(0.65, 0, 0.35, 1)",
            }
        )


progress_root = ProgressRoot.create
progress_indicator = ProgressIndicator.create


def progress(**props):
    return progress_root(
        progress_indicator(
            style=Style(
                # {
                #     "transform": f"`translateX(50))`",
                # }
            )
        ),
        **props,
    )
