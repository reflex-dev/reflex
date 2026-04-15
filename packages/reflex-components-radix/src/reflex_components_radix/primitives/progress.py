"""Progress."""

from __future__ import annotations

from typing import Any

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.vars.base import Var
from reflex_components_core.core.colors import color

from reflex_components_radix.primitives.accordion import DEFAULT_ANIMATION_DURATION
from reflex_components_radix.primitives.base import RadixPrimitiveComponentWithClassName
from reflex_components_radix.themes.base import LiteralAccentColor, LiteralRadius


class ProgressComponent(RadixPrimitiveComponentWithClassName):
    """A Progress component."""

    library = "@radix-ui/react-progress@1.1.8"


class ProgressRoot(ProgressComponent):
    """The Progress Root component."""

    tag = "Root"
    alias = "RadixProgressRoot"

    radius: Var[LiteralRadius] = field(
        doc='Override theme radius for progress bar: "none" | "small" | "medium" | "large" | "full"'
    )

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

    value: Var[int | None] = field(doc="The current progress value.")

    max: Var[int | None] = field(doc="The maximum progress value.")

    color_scheme: Var[LiteralAccentColor] = field(
        doc="The color scheme of the progress indicator."
    )

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

    color_scheme: Var[LiteralAccentColor] = field(
        doc="Override theme color for progress bar indicator"
    )

    value: Var[int | None] = field(doc="The current progress value.")

    max: Var[int | None] = field(doc="The maximum progress value.")

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
