from __future__ import annotations

from typing import List

from reflex import constants
from reflex.base import Base
from reflex.components import Component
from reflex.utils import imports
from reflex.vars import ImportVar, Var


class CommonMarginProps(Base):
    """Many radix-themes elements accept shorthand margin props."""

    # Margin: "0" - "9"
    m: Var[str]

    # Margin horizontal: "0" - "9"
    mx: Var[str]

    # Margin vertical: "0" - "9"
    my: Var[str]

    # Margin top: "0" - "9"
    mt: Var[str]

    # Margin right: "0" - "9"
    mr: Var[str]

    # Margin bottom: "0" - "9"
    mb: Var[str]

    # Margin left: "0" - "9"
    ml: Var[str]


class RadixThemesComponent(Component):
    library = "@radix-ui/themes@^2.0.0"

    @classmethod
    def create(cls, *children, **props) -> Component:
        component = super().create(*children, **props)
        component.alias = "RadixThemes" + component.tag
        return component

    def _get_app_wrap_components(self) -> dict[tuple[int, str], Component]:
        return {
            **super()._get_app_wrap_components(),
            (45, "RadixThemesColorModeProvider"): RadixThemesColorModeProvider.create(),
        }


class Theme(RadixThemesComponent):
    tag = "Theme"

    # Whether to apply the themes background color to the theme node.
    has_background: Var[bool]

    # Override light or dark mode theme: "inherit" | "light" | "dark"
    appearance: Var[str]

    # The color used for default buttons, typography, backgrounds, etc
    accent_color: Var[str]

    # The shade of gray
    gray_color: Var[str]

    # Whether panel backgrounds are transparent: "solid" | "transparent" (default)
    panel_background: Var[str]

    # Border radius: "none" | "small" | "medium" | "large" | "full"
    border_radius: Var[str]

    # Scale of all theme items: "90%" | "95%" | "100%" | "105%" | "110%"
    scaling: Var[str]

    def _get_imports(self) -> imports.ImportDict:
        return {
            **super()._get_imports(),
            "": {ImportVar(tag="@radix-ui/themes/styles.css", install=False)},
        }


class ThemePanel(RadixThemesComponent):
    """Visual editor for creating and editing themes.

    Include as a child component of Theme to use in your app.
    """

    tag = "ThemePanel"

    default_open: Var[bool]


class RadixThemesColorModeProvider(Component):
    library = "/components/reflex/radix_themes_color_mode_provider.js"
    tag = "RadixThemesColorModeProvider"
    is_default = True

    lib_dependencies: List[str] = [
        constants.Packages.NEXT_THEMES,
    ]
