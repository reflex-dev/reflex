"""Progress."""

from __future__ import annotations

from typing import Optional, Union

from reflex.components.component import Component, ComponentNamespace
from reflex.components.core.colors import color
from reflex.components.radix.primitives.accordion import DEFAULT_ANIMATION_DURATION
from reflex.components.radix.primitives.base import RadixPrimitiveComponentWithClassName
from reflex.components.radix.themes.base import LiteralAccentColor
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
                "background": "var(--gray-a3)",
                "border_radius": "99999px",
                "width": "100%",
                "height": "20px",
                "boxShadow": "inset 0 0 0 1px var(--gray-a5)",
                **self.style,
            }
        )


class ProgressIndicator(ProgressComponent):
    """The Progress bar indicator."""

    tag = "Indicator"

    alias = "RadixProgressIndicator"

    # The current progress value.
    value: Var[Optional[int]]

    # The maximum progress value.
    max: Var[Optional[int]]

    # The color scheme of the progress indicator.
    color_scheme: Var[LiteralAccentColor]

    def _apply_theme(self, theme: Component):
        global_color_scheme = getattr(theme, "accent_color", None)

        if global_color_scheme is None and self.color_scheme is None:
            raise ValueError(
                "`color_scheme` cannot be None. Either set the `color_scheme` prop on the progress indicator "
                "component or set the `accent_color` prop in your global theme."
            )

        color_scheme = color(
            self.color_scheme if self.color_scheme is not None else global_color_scheme,  # type: ignore
            9,
        )

        self.style = Style(
            {
                "background-color": color_scheme,
                "width": "100%",
                "height": "100%",
                f"transition": f"transform {DEFAULT_ANIMATION_DURATION}ms linear",
                "&[data_state='loading']": {
                    "transition": f"transform {DEFAULT_ANIMATION_DURATION}ms linear",
                },
                "transform": f"translateX(calc(-100% + ({self.value} / {self.max} * 100%)))",  # type: ignore
                "boxShadow": "inset 0 0 0 1px var(--gray-a5)",
            }
        )

    def _exclude_props(self) -> list[str]:
        return ["color_scheme"]


class Progress(ComponentNamespace):
    """High-level API for progress bar."""

    root = staticmethod(ProgressRoot.create)
    indicator = staticmethod(ProgressIndicator.create)

    @staticmethod
    def __call__(
        width: Optional[str] = "100%",
        color_scheme: Optional[Union[Var, LiteralAccentColor]] = None,
        **props,
    ) -> Component:
        """High-level API for progress bar.

        Args:
            width: The width of the progress bar.
            **props: The props of the progress bar.
            color_scheme: The color scheme of the progress indicator.

        Returns:
            The progress bar.
        """
        style = props.setdefault("style", {})
        style.update({"width": width})

        progress_indicator_props = (
            {"color_scheme": color_scheme} if color_scheme is not None else {}
        )

        return ProgressRoot.create(
            ProgressIndicator.create(
                value=props.get("value"),
                max=props.get("max", 100),
                **progress_indicator_props,  # type: ignore
            ),
            **props,
        )


progress = Progress()
