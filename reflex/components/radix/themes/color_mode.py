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

from typing import Dict, List, Literal, get_args

from reflex.components.component import BaseComponent
from reflex.components.core.cond import Cond, color_mode_cond, cond
from reflex.components.lucide.icon import Icon
from reflex.components.radix.themes.components.dropdown_menu import dropdown_menu
from reflex.components.radix.themes.components.switch import Switch
from reflex.style import (
    LIGHT_COLOR_MODE,
    color_mode,
    resolved_color_mode,
    set_color_mode,
    toggle_color_mode,
)
from reflex.vars.base import Var
from reflex.vars.sequence import LiteralArrayVar

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

position_values: List[str] = list(get_args(LiteralPosition))

position_map: Dict[str, List[str]] = {
    "position": position_values,
    "left": ["top-left", "bottom-left"],
    "right": ["top-right", "bottom-right"],
    "top": ["top-left", "top-right"],
    "bottom": ["bottom-left", "bottom-right"],
}


# needed to inverse contains for find
def _find(const: List[str], var):
    return LiteralArrayVar.create(const).contains(var)


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
        position: LiteralPosition | None = None,
        allow_system: bool = False,
        **props,
    ):
        """Create a icon button component that calls toggle_color_mode on click.

        Args:
            position: The position of the icon button. Follow document flow if None.
            allow_system: Allow picking the "system" value for the color mode.
            **props: The props to pass to the component.

        Returns:
            The button component.
        """
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

        if allow_system:

            def color_mode_item(_color_mode):
                return dropdown_menu.item(
                    _color_mode.title(), on_click=set_color_mode(_color_mode)
                )

            return dropdown_menu.root(
                dropdown_menu.trigger(
                    super().create(
                        ColorModeIcon.create(),
                        **props,
                    )
                ),
                dropdown_menu.content(
                    color_mode_item("light"),
                    color_mode_item("dark"),
                    color_mode_item("system"),
                ),
            )
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
            checked=resolved_color_mode != LIGHT_COLOR_MODE,
            on_change=toggle_color_mode,
            **props,
        )


class ColorModeNamespace(Var):
    """Namespace for color mode components."""

    icon = staticmethod(ColorModeIcon.create)
    button = staticmethod(ColorModeIconButton.create)
    switch = staticmethod(ColorModeSwitch.create)


color_mode = color_mode_var_and_namespace = ColorModeNamespace(
    _js_expr=color_mode._js_expr,
    _var_type=color_mode._var_type,
    _var_data=color_mode.get_default_value(),
)
