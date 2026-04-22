"""Theme switcher component."""

from reflex_components_core.core.cond import cond
from reflex_components_core.el.elements.forms import Button
from reflex_components_core.el.elements.typography import Div

from reflex.components.component import Component, memo
from reflex.style import LiteralColorMode, color_mode, set_color_mode
from reflex_components_internal.components.icons.hugeicon import hi
from reflex_components_internal.utils.twmerge import cn


def theme_switcher_item(mode: LiteralColorMode, icon: str) -> Component:
    """Create a theme switcher item button for a specific mode.

    Returns:
        The component.
    """
    active_cn = "text-secondary-11 shadow-small bg-secondary-1"
    unactive_cn = "hover:text-secondary-11 text-secondary-9"
    return Button.create(
        hi(icon, class_name="shrink-0", size=14),
        on_click=set_color_mode(mode),
        class_name=(
            "flex items-center cursor-pointer justify-center rounded-ui-xs transition-color size-6",
            cond(mode == color_mode, active_cn, unactive_cn),
        ),
        aria_label=f"Switch to {mode} mode",
    )


def theme_switcher(class_name: str = "") -> Component:
    """Theme switcher component.

    Returns:
        The component.
    """
    return Div.create(
        theme_switcher_item("system", "ComputerIcon"),
        theme_switcher_item("light", "Sun01Icon"),
        theme_switcher_item("dark", "Moon02Icon"),
        class_name=cn(
            "flex flex-row items-center bg-secondary-3 p-1 rounded-ui-md w-fit",
            class_name,
        ),
    )


@memo
def memoized_theme_switcher(class_name: str = "") -> Component:
    """Memoized theme switcher component.

    Returns:
        The component.
    """
    return theme_switcher(class_name=class_name)
