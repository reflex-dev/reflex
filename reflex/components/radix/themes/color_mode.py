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
from typing import Literal, get_args

from reflex.components.component import BaseComponent
from reflex.components.core.cond import Cond, color_mode_cond, cond
from reflex.components.lucide.icon import Icon
from reflex.style import LIGHT_COLOR_MODE, color_mode, toggle_color_mode
from reflex.vars import BaseVar, Var

from .components.button import Button
from .components.icon_button import IconButton
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
    """Button for toggling light / dark mode via toggle_color_mode."""

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


LiteralPosition = Literal["top-left", "top-right", "bottom-left", "bottom-right"]


class ColorModeIconButton(IconButton):
    """Icon Button for toggling light / dark mode via toggle_color_mode."""

    @classmethod
    def create(
        cls,
        light_component: BaseComponent | None = None,
        dark_component: BaseComponent | None = None,
        position: LiteralPosition | None = None,
        **props,
    ):
        """Create a icon button component that calls toggle_color_mode on click.

        Args:
            light_component: The component to display when color mode is light.
            dark_component: The component to display when color mode is dark.
            position: The position of the icon button. Follow document flow if None.
            **props: The props to pass to the component.

        Returns:
            The button component.
        """
        pos_values = get_args(LiteralPosition)

        def find(const, var):
            return Var.create_safe(const).contains(var)

        if isinstance(position, Var):
            props.setdefault(
                "position",
                cond(find(pos_values, position), "fixed", ""),
            )
            props.setdefault(
                "bottom",
                cond(find(["bottom-left", "bottom-right"], position), "2rem", ""),
            )
            props.setdefault(
                "top", cond(find(["top-left", "top-right"], position), "2rem", "")
            )
            props.setdefault(
                "left",
                cond(find(["top-left", "bottom-left"], position), "2rem", ""),
            )
            props.setdefault(
                "right",
                cond(find(["top-right", "bottom-right"], position), "2rem", ""),
            )
        elif position is not None:
            if position in pos_values:
                # position only set nice defaults for positioning, it will not enforce them
                props.setdefault("position", "fixed")

                if "bottom" in position:
                    props.setdefault("bottom", "2rem")
                if "top" in position:
                    props.setdefault("top", "2rem")
                if "left" in position:
                    props.setdefault("left", "2rem")
                if "right" in position:
                    props.setdefault("right", "2rem")

        props.setdefault("background", "transparent")
        props.setdefault("color", "inherit")
        props.setdefault("z_index", "20")

        return super().create(
            ColorModeIcon.create(
                light_component=light_component, dark_component=dark_component
            ),
            on_click=toggle_color_mode,
            **props,
        )


class ColorModeNamespace(BaseVar):
    """Namespace for color mode components."""

    icon = staticmethod(ColorModeIcon.create)
    switch = staticmethod(ColorModeSwitch.create)
    button = staticmethod(ColorModeButton.create)
    icon_button = staticmethod(ColorModeIconButton.create)


color_mode_var_and_namespace = ColorModeNamespace(**dataclasses.asdict(color_mode))
