"""Progress."""

from __future__ import annotations

from typing import Any

from reflex.components.component import Component, ComponentNamespace
from reflex.components.core.colors import color
from reflex.components.radix.primitives.accordion import DEFAULT_ANIMATION_DURATION
from reflex.components.radix.primitives.base import RadixPrimitiveComponentWithClassName
from reflex.components.radix.themes.base import LiteralAccentColor, LiteralRadius
from reflex.vars.base import Var


class ProgressComponent(RadixPrimitiveComponentWithClassName):
    """A Progress component."""

    library = "@radix-ui/react-progress@1.1.8"


class ProgressRoot(ProgressComponent):
    """The Progress Root component."""

    tag = "Root"
    alias = "RadixProgressRoot"

    # Override theme radius for progress bar: "none" | "small" | "medium" | "large" | "full"
    radius: Var[LiteralRadius]

    def add_style(self) -> dict[str, Any] | None:
        """Add style to the component.

        Returns:
            The style of the component.
        """
        if self.radius is not None:
            self.custom_attrs["data-radius"] = self.radius

        return {
            "position": "relative",
            "overflow": "hidden",
            "background": color("gray", 3, alpha=True),
            "border_radius": "max(var(--radius-2), var(--radius-full))",
            "width": "100%",
            "height": "20px",
            "boxShadow": f"inset 0 0 0 1px {color('gray', 5, alpha=True)}",
        }

    def _exclude_props(self) -> list[str]:
        return ["radius"]


class ProgressIndicator(ProgressComponent):
    """The Progress bar indicator."""

    tag = "Indicator"

    alias = "RadixProgressIndicator"

    # The current progress value.
    value: Var[int | None]

    # The maximum progress value.
    max: Var[int | None]

    # The color scheme of the progress indicator.
    color_scheme: Var[LiteralAccentColor]

    def add_style(self) -> dict[str, Any] | None:
        """Add style to the component.

        Returns:
            The style of the component.
        """
        if self.color_scheme is not None:
            self.custom_attrs["data-accent-color"] = self.color_scheme

        return {
            "background_color": color("accent", 9),
            "width": "100%",
            "height": "100%",
            "transition": f"transform {DEFAULT_ANIMATION_DURATION}ms linear",
            "&[data_state='loading']": {
                "transition": f"transform {DEFAULT_ANIMATION_DURATION}ms linear",
            },
            "transform": f"translateX(calc(-100% + ({self.value} / {self.max} * 100%)))",
            "boxShadow": "inset 0 0 0 1px var(--gray-a5)",
        }

    def _exclude_props(self) -> list[str]:
        return ["color_scheme"]


class Progress(ProgressRoot):
    """The high-level Progress component."""

    # Override theme color for progress bar indicator
    color_scheme: Var[LiteralAccentColor]

    # The current progress value.
    value: Var[int | None]

    # The maximum progress value.
    max: Var[int | None]

    @classmethod
    def create(cls, **props) -> Component:
        """High-level API for progress bar.

        Args:
            **props: The props of the progress bar.

        Returns:
            The progress bar.
        """
        progress_indicator_props = {}
        if "color_scheme" in props:
            progress_indicator_props["color_scheme"] = props.pop("color_scheme")

        return ProgressRoot.create(
            ProgressIndicator.create(
                value=props.pop("value", 0),
                max=props.pop("max", 100),
                **progress_indicator_props,
            ),
            **props,
        )


class ProgressNamespace(ComponentNamespace):
    """High-level API for progress bar."""

    root = staticmethod(ProgressRoot.create)
    indicator = staticmethod(ProgressIndicator.create)
    __call__ = staticmethod(Progress.create)


progress = ProgressNamespace()
