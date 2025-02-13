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

from typing import Any, Dict, List, Literal, Optional, Union, get_args

from reflex.components.component import BaseComponent
from reflex.components.core.cond import color_mode_cond, cond
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


def color_mode_icon(
    light_component: BaseComponent | None = None,
    dark_component: BaseComponent | None = None,
):
    """Create a color mode icon component.

    Args:
        light_component: The component to render in light mode.
        dark_component: The component to render in dark mode.

    Returns:
        The color mode icon component.
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
def _find(const: List[str], var: Any):
    return LiteralArrayVar.create(const).contains(var)


def _set_var_default(
    props: dict, position: Any, prop: str, default1: str, default2: str = ""
):
    props.setdefault(
        prop, cond(_find(position_map[prop], position), default1, default2)
    )


def _set_static_default(props: dict, position: Any, prop: str, default: str):
    if prop in position:
        props.setdefault(prop, default)


class ColorModeIconButton(IconButton):
    """Icon Button for toggling light / dark mode via toggle_color_mode."""

    # The position of the icon button. Follow document flow if None.
    position: Optional[Union[LiteralPosition, Var[LiteralPosition]]] = None

    # Allow picking the "system" value for the color mode.
    allow_system: bool = False

    @classmethod
    def create(
        cls,
        **props,
    ):
        """Create an icon button component that calls toggle_color_mode on click.

        Args:
            **props: The props to pass to the component.

        Returns:
            The button component.
        """
        position: str | Var = props.pop("position", None)
        allow_system = props.pop("allow_system", False)

        # position is used to set nice defaults for positioning the icon button
        if isinstance(position, Var):
            _set_var_default(props, position, "position", "fixed", position)  # pyright: ignore [reportArgumentType]
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

            def color_mode_item(_color_mode: Literal["light", "dark", "system"]):
                return dropdown_menu.item(
                    _color_mode.title(), on_click=set_color_mode(_color_mode)
                )

            return dropdown_menu.root(
                dropdown_menu.trigger(
                    super().create(
                        color_mode_icon(),
                    ),
                    **props,
                ),
                dropdown_menu.content(
                    color_mode_item("light"),
                    color_mode_item("dark"),
                    color_mode_item("system"),
                ),
            )
        return IconButton.create(
            color_mode_icon(),
            on_click=toggle_color_mode,
            **props,
        )

    def _exclude_props(self) -> list[str]:
        return ["position", "allow_system"]


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

    icon = staticmethod(color_mode_icon)
    button = staticmethod(ColorModeIconButton.create)
    switch = staticmethod(ColorModeSwitch.create)


color_mode = color_mode_var_and_namespace = ColorModeNamespace(
    _js_expr=color_mode._js_expr,
    _var_type=color_mode._var_type,
    _var_data=color_mode._get_default_value(),
)
