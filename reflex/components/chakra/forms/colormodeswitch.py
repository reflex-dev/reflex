"""A switch component for toggling color_mode.

To style components based on color mode, use style props with `color_mode_cond`:

```
rx.text(
    "Hover over me",
    _hover={
        "background": rx.color_mode_cond(
            light="var(--chakra-colors-gray-200)",
            dark="var(--chakra-colors-gray-700)",
        ),
    },
)
```
"""
from __future__ import annotations

from reflex.components.chakra import ChakraComponent
from reflex.components.chakra.media.icon import Icon
from reflex.components.component import BaseComponent
from reflex.components.core.cond import Cond, color_mode_cond
from reflex.style import LIGHT_COLOR_MODE, color_mode, toggle_color_mode

from .button import Button
from .switch import Switch

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
    """Switch for toggling chakra light / dark mode via toggle_color_mode."""

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
            is_checked=color_mode != LIGHT_COLOR_MODE,
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
            The switch component.
        """
        return Button.create(
            *children,
            on_click=toggle_color_mode,
            **props,
        )


class ColorModeScript(ChakraComponent):
    """Chakra color mode script."""

    tag = "ColorModeScript"
    initialColorMode = LIGHT_COLOR_MODE
