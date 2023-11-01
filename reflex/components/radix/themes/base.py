"""Base classes for radix-themes components."""

from __future__ import annotations

from reflex.components import Component
from reflex.components.literals.radix import LiteralSize, LiteralAppearance, LiteralAccentColor,  LiteralGrayColor, LiteralPanelBackground, LiteralRadius, LiteralScaling
from reflex.utils import imports
from reflex.vars import ImportVar, Var

class CommonMarginProps(Component):
    """Many radix-themes elements accept shorthand margin props."""

    # Margin: "0" - "9"
    m: Var[LiteralSize]

    # Margin horizontal: "0" - "9"
    mx: Var[LiteralSize]

    # Margin vertical: "0" - "9"
    my: Var[LiteralSize]

    # Margin top: "0" - "9"
    mt: Var[LiteralSize]

    # Margin right: "0" - "9"
    mr: Var[LiteralSize]

    # Margin bottom: "0" - "9"
    mb: Var[LiteralSize]

    # Margin left: "0" - "9"
    ml: Var[LiteralSize]


class RadixThemesComponent(Component):
    """Base class for all @radix-ui/themes components."""

    library = "@radix-ui/themes@^2.0.0"

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a new component instance.

        Will prepend "RadixThemes" to the component tag to avoid conflicts with
        other UI libraries for common names, like Text and Button.

        Args:
            *children: Child components.
            **props: Component properties.

        Returns:
            A new component instance.
        """
        component = super().create(*children, **props)
        if component.library is None:
            component.library = RadixThemesComponent.__fields__["library"].default
        component.alias = "RadixThemes" + (
            component.tag or component.__class__.__name__
        )
        return component

    def _get_app_wrap_components(self) -> dict[tuple[int, str], Component]:
        return {
            **super()._get_app_wrap_components(),
            (45, "RadixThemesColorModeProvider"): RadixThemesColorModeProvider.create(),
        }

    def _get_style(self) -> dict:
        return {"style": self.style}


class Theme(RadixThemesComponent):
    """A theme provider for radix components.

    This should be applied as `App.theme` to apply the theme to all radix
    components in the app with the given settings.

    It can also be used in a normal page to apply specified properties to all
    child elements as an override of the main theme.
    """

    tag = "Theme"

    # Whether to apply the themes background color to the theme node.
    has_background: Var[bool]

    # Override light or dark mode theme: "inherit" | "light" | "dark"
    appearance: Var[LiteralAppearance]

    # The color used for default buttons, typography, backgrounds, etc
    accent_color: Var[LiteralAccentColor]

    # The shade of gray
    gray_color: Var[LiteralGrayColor]

    # Whether panel backgrounds are transparent: "solid" | "transparent" (default)
    panel_background: Var[LiteralPanelBackground]

    # Element border radius: "none" | "small" | "medium" | "large" | "full"
    radius: Var[LiteralRadius]

    # Scale of all theme items: "90%" | "95%" | "100%" | "105%" | "110%"
    scaling: Var[LiteralScaling]

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
    """Next-themes integration for radix themes components."""

    library = "/components/reflex/radix_themes_color_mode_provider.js"
    tag = "RadixThemesColorModeProvider"
    is_default = True
