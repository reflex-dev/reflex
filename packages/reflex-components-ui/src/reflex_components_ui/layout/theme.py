"""A theme: an element whose subtree has an accent, a gray, a radius and so on."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from typing import Any, ClassVar

from reflex_base.components.component import Component, field
from reflex_base.components.dynamic import is_rendering_dynamic_component
from reflex_base.components.tags import CommonTag
from reflex_base.plugins import get_plugin
from reflex_base.utils.exceptions import ConfigError
from reflex_base.utils.imports import ImportDict
from reflex_base.vars.base import Var

from reflex_components_ui.base import MISSING_PLUGIN_ERROR, UIComponent, add_styles
from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.style.emit import Emitted, style_object
from reflex_components_ui.styles.theme import APP_THEME, APPEARANCE
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
    literal_option,
    theme_styles,
)


class Appearance(UIComponent):
    """What carries the class of an appearance around a theme element.

    Radix Themes and Tailwind select on the classes ``light`` and ``dark``, so
    their components inside a theme follow its appearance through them. The
    class cannot be on the theme element: the stylesheet of Radix Themes sets
    its plain gray scale on an element with either class, over the gray of the
    theme. This element has no box, so the theme element is laid out as a
    child of what is around both.
    """

    tag = "div"

    styles: ClassVar[ComponentStyles] = APPEARANCE

    @classmethod
    def _display_name(cls) -> str:
        """Get the name an app refers to the component by.

        Returns:
            ``rx.ui.theme``, which is what an app wrote.
        """
        return "rx.ui.theme"


# The fields of the element that are options of its theme.
_OPTIONS = (*OPTIONS, "has_background")


class ThemeElement(UIComponent):
    """A block whose content follows a theme of its own.

    An option that is left out is inherited from the theme around the element.
    """

    tag = "div"

    # The radius is an option of the theme, for what is inside the element.
    _own_radius: ClassVar[bool] = False

    accent_color: Var[LiteralAccentColor] = field(
        is_javascript_property=False,
        doc="The color of the components that stand out.",
    )

    gray_color: Var[LiteralGrayColor] = field(
        is_javascript_property=False,
        doc='The gray of text, borders and surfaces. "auto" is the gray that matches the accent color.',
    )

    radius: Var[LiteralRadius] = field(
        is_javascript_property=False,
        doc='How round corners are: "none" | "small" | "medium" | "large" | "full".',
    )

    scaling: Var[LiteralScaling] = field(
        is_javascript_property=False,
        doc='The size of everything: "90%" | "95%" | "100%" | "105%" | "110%".',
    )

    appearance: Var[LiteralAppearance] = field(
        is_javascript_property=False,
        doc='"light" or "dark" to keep one whatever the color mode, "inherit" to follow it.',
    )

    panel_background: Var[LiteralPanelBackground] = field(
        is_javascript_property=False,
        doc='Whether panels such as cards are see-through: "solid" | "translucent".',
    )

    has_background: Var[bool] = field(
        is_javascript_property=False,
        doc="Whether the element paints the background of the theme. Defaults to True when it sets an appearance.",
    )

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a theme around the children.

        Args:
            *children: The children of the theme.
            **props: The options of the theme and the props of its element.

        Returns:
            The theme element, inside the element that carries the class of
            its appearance when it has one of its own.
        """
        element = super().create(*children, **props)
        appearance = literal_option(props.get("appearance"))
        if appearance is None or (
            appearance.__class__ is str and appearance == "inherit"
        ):
            return element
        # Bound to state, the class is `inherit` when the appearance is: no
        # stylesheet selects on it.
        return Appearance.create(element, class_name=appearance)

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

    def _own_styles(self) -> Emitted:
        """Get the StyleX source of the element's own styles.

        Returns:
            What the module that renders the element declares for them.
        """
        # The generated stub of the base class leaves its private methods out.
        return self._emit()  # pyright: ignore [reportAttributeAccessIssue]

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
        style = style_object(self._own_styles())
        if style is None:
            return self._resolve_theme_styles(plugin, None)
        statement, name = style
        theme = self._resolve_theme_styles(plugin, name)
        return dataclasses.replace(theme, declarations=(statement, *theme.declarations))

    def _resolve_theme_styles(self, plugin: UIPlugin, style: str | None) -> ThemeStyles:
        """Work out the StyleX themes of the options of the element.

        Args:
            plugin: The configured plugin.
            style: The compiled style of the element itself.

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
            style=style,
        )

    def add_imports(self) -> ImportDict:
        """Import the StyleX themes of the element.

        Returns:
            The imports, beside the ones every rx.ui component has.
        """
        return self._theme_styles().import_dict()

    def add_custom_code(self) -> list[str]:
        """Declare what the class names of the theme are read from.

        Returns:
            The declaration of the element's own style, which the others
            name, then the ones of its theme.
        """
        declaration = self._own_styles().declaration
        declarations = self._theme_styles().declarations
        return [*declarations] if declaration is None else [declaration, *declarations]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the element with its themes and its style.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, with the class names of its theme joined to the ones of
            its style, which wins where both set a property.
        """
        tag = Component._render(self, props)
        theme = self._theme_styles()
        return add_styles(
            tag, dataclasses.replace(self._own_styles(), classes=theme.classes)
        )


class AppTheme(ThemeElement):
    """The element around an app, which carries the theme of the plugin."""

    styles: ClassVar[ComponentStyles] = APP_THEME

    def _resolve_theme_styles(self, plugin: UIPlugin, style: str | None) -> ThemeStyles:
        """Work out the StyleX themes of the theme of the app.

        Args:
            plugin: The configured plugin.
            style: The compiled style of the element itself.

        Returns:
            What the element needs: every option of the theme is set.
        """
        return app_theme_styles(plugin.theme, style)


theme = ThemeElement.create
