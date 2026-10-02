"""Navigation helpers for URL-based locale routing (``rx.i18n.*``)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .component import LanguageSwitcher

if TYPE_CHECKING:
    from reflex_base.components.component import Component


def _base_path(route: str) -> str:
    """Normalize a route to a base URL path.

    Args:
        route: A route key (``"index"``, ``"pricing"``) or path (``"/pricing"``).

    Returns:
        The URL path (``"/"`` for the index, else ``"/<route>"``).
    """
    if route in ("", "/", "index"):
        return "/"
    return route if route.startswith("/") else f"/{route}"


def locale_url(locale: str, route: str) -> str:
    """The URL path for a route in a given locale (for custom links).

    Args:
        locale: The target locale.
        route: The base route (``"/pricing"`` or ``"pricing"``).

    Returns:
        The localized URL path (unchanged if URL routing is off).
    """
    from reflex_base.plugins.base import get_plugin

    from .plugin import I18nPlugin

    path = _base_path(route)
    plugin = get_plugin(I18nPlugin)
    if plugin is None or plugin.routing is None:
        return path
    return plugin.routing.localize(path, locale, plugin.default_locale)


def language_switcher(**props: Any) -> Component:
    """A crawlable language switcher: one ``<a>`` link per locale.

    Args:
        props: Props forwarded to the switcher's ``<nav>`` element.

    Returns:
        The language-switcher component.
    """
    return LanguageSwitcher.create(**props)
