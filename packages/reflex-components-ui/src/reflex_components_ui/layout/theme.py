"""A theme: an element whose subtree has an accent, a gray, a radius and so on."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, ClassVar

from reflex_base.components.component import Component, field
from reflex_base.components.dynamic import is_rendering_dynamic_component
from reflex_base.components.tags import CommonTag
from reflex_base.plugins import get_plugin
from reflex_base.utils.exceptions import ConfigError
from reflex_base.utils.imports import ImportDict
from reflex_base.vars.base import Var
from reflex_base.vars.sequence import LiteralStringVar

from reflex_components_ui.base import (
    MISSING_PLUGIN_ERROR,
    ComponentStyles,
    UIComponent,
)
from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style.emit import props_call
from reflex_components_ui.styles.theme import APP_THEME
from reflex_components_ui.themes import (
    OPTIONS,
    LiteralAccentColor,
    LiteralAppearance,
    LiteralGrayColor,
    LiteralPanelBackground,
    LiteralRadius,
    LiteralScaling,
    ThemeError,
    ThemeStyles,
    app_theme_styles,
    theme_styles,
)


# The fields of the element that are options of its theme.
_OPTIONS = (*OPTIONS, "has_background")


class ThemeElement(UIComponent):
    """A block whose content follows a theme of its own.

    An option that is left out is inherited from the theme around the element.
    """

    tag = "div"

    accent_color: LiteralAccentColor | Var[LiteralAccentColor] | None = field(
        default=None,
        is_javascript_property=False,
        doc="The color of the components that stand out.",
    )

    gray_color: LiteralGrayColor | Var[LiteralGrayColor] | None = field(
        default=None,
        is_javascript_property=False,
        doc='The gray of text, borders and surfaces. "auto" is the gray that matches the accent color.',
    )

    radius: LiteralRadius | Var[LiteralRadius] | None = field(
        default=None,
        is_javascript_property=False,
        doc='How round corners are: "none" | "small" | "medium" | "large" | "full".',
    )

    scaling: LiteralScaling | Var[LiteralScaling] | None = field(
        default=None,
        is_javascript_property=False,
        doc='The size of everything: "90%" | "95%" | "100%" | "105%" | "110%".',
    )

    appearance: LiteralAppearance | Var[LiteralAppearance] | None = field(
        default=None,
        is_javascript_property=False,
        doc='"light" or "dark" to keep one whatever the color mode, "inherit" to follow it.',
    )

    panel_background: (
        LiteralPanelBackground | Var[LiteralPanelBackground] | None
    ) = field(
        default=None,
        is_javascript_property=False,
        doc='Whether panels such as cards are see-through: "solid" | "translucent".',
    )

    has_background: bool | Var[bool] | None = field(
        default=None,
        is_javascript_property=False,
        doc="Whether the element paints the background of the theme. Defaults to True when it sets an appearance.",
    )

    @classmethod
    def _display_name(cls) -> str:
        """Get the name an app refers to the component by.

        Returns:
            ``rx.ui.theme``.
        """
        return "rx.ui.theme"

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in this component.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            The Vars of every component, then the options bound to state: they
            are no props of the element, so nothing else reports the state
            they read.
        """
        yield from super()._get_vars(
            include_children=include_children, ignore_ids=ignore_ids
        )
        for option in _OPTIONS:
            value = getattr(self, option)
            if isinstance(value, Var):
                yield value

    def _theme_styles(self) -> ThemeStyles:
        """Work out the StyleX themes of the element.

        Returns:
            What the element needs to carry its theme.

        Raises:
            ThemeError: If the element is rendered from state.
            ConfigError: If the plugin that compiles the styles is not configured.
        """
        if is_rendering_dynamic_component():
            msg = (
                f"{self._display_name()}: a theme rendered from state cannot be "
                "applied: its code is evaluated in the browser and never "
                "reaches the StyleX compiler. Render the theme in a page, and "
                "what comes from state inside it."
            )
            raise ThemeError(msg)
        plugin = get_plugin(UIPlugin)
        if plugin is None:
            raise ConfigError(MISSING_PLUGIN_ERROR)
        return self._resolve_theme_styles(plugin)

    def _resolve_theme_styles(self, plugin: UIPlugin) -> ThemeStyles:
        """Work out the StyleX themes of the options of the element.

        Args:
            plugin: The configured plugin.

        Returns:
            What the element needs to carry its theme.
        """
        return theme_styles(
            self._display_name(),
            accent_color=self.accent_color,
            gray_color=self.gray_color,
            radius=self.radius,
            scaling=self.scaling,
            appearance=self.appearance,
            panel_background=self.panel_background,
            has_background=self.has_background,
            app_theme=plugin.theme,
        )

    def add_imports(self) -> ImportDict:
        """Import the StyleX themes of the element.

        Returns:
            The imports, beside the ones every rx.ui component has.
        """
        return self._theme_styles().import_dict()

    def add_custom_code(self) -> list[str]:
        """Declare the maps an option bound to state is looked up in.

        Returns:
            The declarations, beside the one of the element's own style.
        """
        return list(self._theme_styles().declarations)

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the element with its themes and its style.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, with one ``stylex.props`` spread.
        """
        tag = Component._render(self, props)
        theme = self._theme_styles()
        style = self._stylex()
        refs = theme.refs if style is None else (*theme.refs, style.ref)
        own = tag.props.get("className")
        if own is None or isinstance(own, LiteralStringVar):
            names = theme.class_name
            if own is not None and own._var_value:
                names = f"{names} {own._var_value}" if names else own._var_value
            return tag.remove_props("className").set(
                special_props=[
                    *tag.special_props,
                    Var(props_call(refs, names), _var_data=theme.var_data),
                ]
            )
        return tag.add_props(
            class_name=Var(
                # Parenthesized: the expression may be a conditional.
                f'({own!s}) + " " + {props_call(refs, theme.class_name)}.className',
                _var_type=str,
                _var_data=own._get_all_var_data(),
            )._replace(merge_var_data=theme.var_data)
        )


class AppTheme(ThemeElement):
    """The element around an app, which carries the theme of the plugin."""

    styles: ClassVar[ComponentStyles] = APP_THEME

    def _resolve_theme_styles(self, plugin: UIPlugin) -> ThemeStyles:
        """Work out the StyleX themes of the theme of the app.

        Args:
            plugin: The configured plugin.

        Returns:
            What the element needs: every option of the theme is set.
        """
        return app_theme_styles(plugin.theme)


theme = ThemeElement.create
