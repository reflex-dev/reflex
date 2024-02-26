"""A switch component for toggling color_mode.

To style components based on color mode, use style props with `color_mode_cond`:

```
rx.text(
    "Hover over me",
    _hover={
        "background": rx.color_mode_cond(
            light="var(--accent-2)",
            dark="var(--accent-4)",
        ),
    },
)
```
"""
from __future__ import annotations

import dataclasses

from reflex.components.component import BaseComponent
from reflex.components.core.cond import Cond, color_mode_cond
from reflex.components.lucide.icon import Icon
from reflex.style import LIGHT_COLOR_MODE, color_mode, toggle_color_mode
from reflex.vars import BaseVar

from .components.button import Button
from .components.switch import Switch

DEFAULT_LIGHT_ICON: Icon = Icon.create(tag="sun")
DEFAULT_DARK_ICON: Icon = Icon.create(tag="moon")


class ColorModeIcon(Cond):
    """Displays the current color mode as an icon."""

    @classmethod
    def create(
        cls,
        light_component: BaseComponent | None = None,
        dark_component: BaseComponent | None = None,
    ):
        """Create an icon component based on color_mode.

        Args:
            light_component: the component to display when color mode is default
            dark_component: the component to display when color mode is dark (non-default)

        Returns:
            The conditionally rendered component
        """
        return color_mode_cond(
            light=light_component or DEFAULT_LIGHT_ICON,
            dark=dark_component or DEFAULT_DARK_ICON,
        )


class ColorModeSwitch(Switch):
    """Switch for toggling light / dark mode via toggle_color_mode."""

    @classmethod
    def create(cls, *children, **props):
        """Create a switch component bound to color_mode.

        Args:
            *children: The children of the component.
            **props: The props to pass to the component.

        Returns:
            The switch component.
        """
        return Switch.create(
            *children,
            checked=color_mode != LIGHT_COLOR_MODE,
            on_change=toggle_color_mode,
            **props,
        )


class ColorModeButton(Button):
    """Button for toggling chakra light / dark mode via toggle_color_mode."""

    @classmethod
    def create(cls, *children, **props):
        """Create a button component that calls toggle_color_mode on click.

        Args:
            *children: The children of the component.
            **props: The props to pass to the component.

        Returns:
            The button component.
        """
        return Button.create(
            *children,
            on_click=toggle_color_mode,
            **props,
        )


class ColorModeNamespace(BaseVar):
    """Namespace for color mode components."""

    icon = staticmethod(ColorModeIcon.create)
    switch = staticmethod(ColorModeSwitch.create)
    button = staticmethod(ColorModeButton.create)


color_mode_var_and_namespace = ColorModeNamespace(**dataclasses.asdict(color_mode))
