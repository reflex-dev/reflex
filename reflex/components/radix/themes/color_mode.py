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
from reflex.components.radix.themes.components.switch import Switch
from reflex.style import LIGHT_COLOR_MODE, color_mode, toggle_color_mode
from reflex.utils import console
from reflex.vars import BaseVar, Var

from .components.icon_button import IconButton

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


LiteralPosition = Literal["top-left", "top-right", "bottom-left", "bottom-right"]

position_values = get_args(LiteralPosition)

position_map = {
    "position": position_values,
    "left": ["top-left", "bottom-left"],
    "right": ["top-right", "bottom-right"],
    "top": ["top-left", "top-right"],
    "bottom": ["bottom-left", "bottom-right"],
}


# needed to inverse contains for find
def _find(const, var):
    return Var.create_safe(const, _var_is_string=False).contains(var)


def _set_var_default(props, position, prop, default1, default2=""):
    props.setdefault(
        prop, cond(_find(position_map[prop], position), default1, default2)
    )


def _set_static_default(props, position, prop, default):
    if prop in position:
        props.setdefault(prop, default)


class ColorModeIconButton(IconButton):
    """Icon Button for toggling light / dark mode via toggle_color_mode."""

    @classmethod
    def create(
        cls,
        *children,
        position: LiteralPosition | None = None,
        **props,
    ):
        """Create a icon button component that calls toggle_color_mode on click.

        Args:
            *children: The children of the component.
            position: The position of the icon button. Follow document flow if None.
            **props: The props to pass to the component.

        Returns:
            The button component.
        """
        if children:
            console.deprecate(
                feature_name="passing children to color_mode.button",
                reason=", use color_mode_cond and toggle_color_mode instead to build a custom color_mode component",
                deprecation_version="0.5.0",
                removal_version="0.6.0",
            )

        # position is used to set nice defaults for positioning the icon button
        if isinstance(position, Var):
            _set_var_default(props, position, "position", "fixed", position)
            _set_var_default(props, position, "bottom", "2rem")
            _set_var_default(props, position, "top", "2rem")
            _set_var_default(props, position, "left", "2rem")
            _set_var_default(props, position, "right", "2rem")
        elif position is not None:
            if position in position_values:
                props.setdefault("position", "fixed")
                _set_static_default(props, position, "bottom", "2rem")
                _set_static_default(props, position, "top", "2rem")
                _set_static_default(props, position, "left", "2rem")
                _set_static_default(props, position, "right", "2rem")
            else:
                props["position"] = position

        props.setdefault("background", "transparent")
        props.setdefault("color", "inherit")
        props.setdefault("z_index", "20")
        props.setdefault(":hover", {"cursor": "pointer"})

        return super().create(
            ColorModeIcon.create(),
            on_click=toggle_color_mode,
            **props,
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


class ColorModeNamespace(BaseVar):
    """Namespace for color mode components."""

    icon = staticmethod(ColorModeIcon.create)
    button = staticmethod(ColorModeIconButton.create)
    switch = staticmethod(ColorModeSwitch.create)


color_mode = color_mode_var_and_namespace = ColorModeNamespace(
    **dataclasses.asdict(color_mode)
)
