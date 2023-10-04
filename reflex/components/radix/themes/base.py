from __future__ import annotations

from typing import List

from reflex import constants
from reflex.base import Base
from reflex.components import Component
from reflex.vars import Var


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
            (20, "RadixThemesTheme"): RadixThemesTheme.create(),
        }


class RadixThemesTheme(Component):
    library = "/components/reflex/radix_themes.js"
    tag = "RadixThemesTheme"
    is_default = True

    lib_dependencies: List[str] = [
        RadixThemesComponent().library,
    ]

    def _get_app_wrap_components(self) -> dict[tuple[int, str], Component]:
        return {
            **super()._get_app_wrap_components(),
            (45, "RadixThemesColorModeProvider"): RadixThemesColorModeProvider.create(),
        }


class RadixThemesColorModeProvider(Component):
    library = "/components/reflex/radix_themes_color_mode_provider.js"
    tag = "RadixThemesColorModeProvider"
    is_default = True

    lib_dependencies: List[str] = [
        constants.Packages.NEXT_THEMES,
    ]
