"""Base classes for radix-themes components."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from reflex_base.components.component import Component, field
from reflex_base.components.tags import Tag
from reflex_base.utils.imports import ImportDict, ImportVar
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

LiteralAlign = Literal["start", "center", "end", "baseline", "stretch"]
LiteralJustify = Literal["start", "center", "end", "between"]
LiteralSpacing = Literal["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
LiteralVariant = Literal["classic", "solid", "soft", "surface", "outline", "ghost"]
LiteralAppearance = Literal["inherit", "light", "dark"]
LiteralGrayColor = Literal["gray", "mauve", "slate", "sage", "olive", "sand", "auto"]
LiteralPanelBackground = Literal["solid", "translucent"]
LiteralRadius = Literal["none", "small", "medium", "large", "full"]
LiteralScaling = Literal["90%", "95%", "100%", "105%", "110%"]
LiteralAccentColor = Literal[
    "tomato",
    "red",
    "ruby",
    "crimson",
    "pink",
    "plum",
    "purple",
    "violet",
    "iris",
    "indigo",
    "blue",
    "cyan",
    "teal",
    "jade",
    "green",
    "grass",
    "brown",
    "orange",
    "sky",
    "mint",
    "lime",
    "yellow",
    "amber",
    "gold",
    "bronze",
    "gray",
]


class CommonMarginProps(Component):
    """Many radix-themes elements accept shorthand margin props."""

    m: Var[LiteralSpacing] = field(doc='Margin: "0" - "9" # noqa: ERA001')

    mx: Var[LiteralSpacing] = field(doc='Margin horizontal: "0" - "9"')

    my: Var[LiteralSpacing] = field(doc='Margin vertical: "0" - "9"')

    mt: Var[LiteralSpacing] = field(doc='Margin top: "0" - "9"')

    mr: Var[LiteralSpacing] = field(doc='Margin right: "0" - "9"')

    mb: Var[LiteralSpacing] = field(doc='Margin bottom: "0" - "9"')

    ml: Var[LiteralSpacing] = field(doc='Margin left: "0" - "9"')


class CommonPaddingProps(Component):
    """Many radix-themes elements accept shorthand padding props."""

    p: Var[Responsive[LiteralSpacing]] = field(doc='Padding: "0" - "9" # noqa: ERA001')

    px: Var[Responsive[LiteralSpacing]] = field(doc='Padding horizontal: "0" - "9"')

    py: Var[Responsive[LiteralSpacing]] = field(doc='Padding vertical: "0" - "9"')

    pt: Var[Responsive[LiteralSpacing]] = field(doc='Padding top: "0" - "9"')

    pr: Var[Responsive[LiteralSpacing]] = field(doc='Padding right: "0" - "9"')

    pb: Var[Responsive[LiteralSpacing]] = field(doc='Padding bottom: "0" - "9"')

    pl: Var[Responsive[LiteralSpacing]] = field(doc='Padding left: "0" - "9"')


class RadixLoadingProp(Component):
    """Base class for components that can be in a loading state."""

    loading: Var[bool] = field(
        doc="If set, show an rx.spinner instead of the component children."
    )


class RadixThemesComponent(Component):
    """Base class for all @radix-ui/themes components."""

    library = "@radix-ui/themes@3.3.0"

    # "Fake" prop color_scheme is used to avoid shadowing CSS prop "color".
    _rename_props: ClassVar[dict[str, str]] = {"colorScheme": "color"}

    @classmethod
    def create(
        cls,
        *children,
        **props,
    ) -> Component:
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
            component.library = RadixThemesComponent.get_fields()[
                "library"
            ].default_value()
        component.alias = "RadixThemes" + (component.tag or type(component).__name__)
        return component

    @staticmethod
    def _get_app_wrap_components() -> dict[tuple[int, str], Component]:
        return {
            (45, "RadixThemesColorModeProvider"): RadixThemesColorModeProvider.create(),
        }


class RadixThemesTriggerComponent(RadixThemesComponent):
    """Base class for Trigger, Close, Cancel, and Accept components.

    These components trigger some action in an overlay component that depends on the
    on_click event, and thus if a child is provided and has on_click specified, it
    will overtake the internal action, unless it is wrapped in some inert component,
    in this case, a Flex.
    """

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create a new RadixThemesTriggerComponent instance.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The new RadixThemesTriggerComponent instance.
        """
        from .layout.flex import Flex

        for child in children:
            if "on_click" in getattr(child, "event_triggers", {}):
                children = (Flex.create(*children),)
                break
        return super().create(*children, **props)


class Theme(RadixThemesComponent):
    """A theme provider for radix components.

    This should be applied as `App.theme` to apply the theme to all radix
    components in the app with the given settings.

    It can also be used in a normal page to apply specified properties to all
    child elements as an override of the main theme.
    """

    tag = "Theme"

    has_background: Var[bool] = field(
        doc="Whether to apply the themes background color to the theme node. Defaults to True."
    )

    appearance: Var[LiteralAppearance] = field(
        doc='Override light or dark mode theme: "inherit" | "light" | "dark". Defaults to "inherit".'
    )

    accent_color: Var[LiteralAccentColor] = field(
        doc="The color used for default buttons, typography, backgrounds, etc"
    )

    gray_color: Var[LiteralGrayColor] = field(
        doc='The shade of gray, defaults to "auto".'
    )

    panel_background: Var[LiteralPanelBackground] = field(
        doc='Whether panel backgrounds are translucent: "solid" | "translucent" (default)'
    )

    radius: Var[LiteralRadius] = field(
        doc='Element border radius: "none" | "small" | "medium" | "large" | "full". Defaults to "medium".'
    )

    scaling: Var[LiteralScaling] = field(
        doc='Scale of all theme items: "90%" | "95%" | "100%" | "105%" | "110%". Defaults to "100%"'
    )

    @classmethod
    def create(
        cls,
        *children,
        color_mode: LiteralAppearance | None = None,
        theme_panel: bool = False,
        **props,
    ) -> Component:
        """Create a new Radix Theme specification.

        Args:
            *children: Child components.
            color_mode: Map to appearance prop.
            theme_panel: Whether to include a panel for editing the theme.
            **props: Component properties.

        Returns:
            A new component instance.
        """
        if color_mode is not None:
            props["appearance"] = color_mode
        if theme_panel:
            children = [ThemePanel.create(), *children]
        return super().create(*children, **props)

    def add_imports(self) -> ImportDict | list[ImportDict]:
        """Add imports for the Theme component.

        Returns:
            The import dict.
        """
        return {
            "$/utils/theme": [ImportVar(tag="theme", is_default=True)],
        }

    def _render(self, props: dict[str, Any] | None = None) -> Tag:
        tag = super()._render(props)
        return tag.add_props(
            css=Var(
                _js_expr="{...theme.styles.global[':root'], ...theme.styles.global.body}"
            ),
        ).remove_props("appearance")


class ThemePanel(RadixThemesComponent):
    """Visual editor for creating and editing themes.

    Include as a child component of Theme to use in your app.
    """

    tag = "ThemePanel"

    default_open: Var[bool] = field(doc="Whether the panel is open. Defaults to False.")

    def add_imports(self) -> dict[str, str]:
        """Add imports for the ThemePanel component.

        Returns:
            The import dict.
        """
        return {"react": "useEffect"}


class RadixThemesColorModeProvider(Component):
    """React-themes integration for radix themes components."""

    library = "$/components/reflex/radix_themes_color_mode_provider"
    tag = "RadixThemesColorModeProvider"
    is_default = True


theme = Theme.create
theme_panel = ThemePanel.create
