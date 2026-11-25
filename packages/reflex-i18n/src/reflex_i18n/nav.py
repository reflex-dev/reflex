"""Navigation helpers for URL-based locale routing (``rx.i18n.*``)."""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any

from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import LiteralVar, Var, VarData

from .component import LanguageSwitcher
from .config import check_configured_locale, get_active_i18n_config, source_locale
from .runtime import get_locale

if TYPE_CHECKING:
    from reflex_base.components.component import Component
    from reflex_base.vars.object import ObjectVar
    from reflex_base.vars.sequence import StringVar


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

    Like any Reflex route, the path is relative to ``frontend_path``, which
    ``rx.link`` and ``rx.redirect`` prepend.

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


def localized_url(route: str) -> str:
    """The URL path for a route in the locale the current page is built in.

    For links in a layout shared by every locale: on a page compiled for
    ``/de/...`` it points to the German address. Like ``gettext``, it uses the
    default locale outside a page, e.g. in a ``@rx.memo`` component.

    Args:
        route: The base route (``"/pricing"`` or ``"pricing"``).

    Returns:
        The localized URL path (unchanged if URL routing is off).
    """
    return locale_url(get_locale() or source_locale(), route)


@functools.cache
def _alternate_urls() -> ObjectVar[dict[str, str]]:
    """The current page's address in each locale, as a client-side var.

    Returns:
        The ``useAlternateUrls`` hook's locale to URL map.
    """
    return Var(
        _js_expr="i18nAlternateUrls",
        _var_data=VarData(
            imports={"$/utils/i18n": [ImportVar(tag="useAlternateUrls")]},
            hooks={"const i18nAlternateUrls = useAlternateUrls()": None},
        ),
    ).to(dict[str, str])


def alternate_url(locale: str | Var[str]) -> StringVar:
    """The current page's URL in a locale, for a language switcher of your own.

    With URL routing it is the page's address in that locale; without it, the
    page itself (switch with ``rx.i18n.set_locale`` there). The query string
    and fragment are kept, as in :func:`language_switcher`.

    Args:
        locale: A configured locale.

    Returns:
        The URL as a client-side var.
    """
    if get_active_i18n_config() is None:
        # Without an I18nPlugin the app has a single locale and URL.
        return LiteralVar.create("").to(str)
    if isinstance(locale, str):
        check_configured_locale(locale)
    return _alternate_urls()[locale].to(str)


def language_switcher(**props: Any) -> Component:
    """A crawlable language switcher: one ``<a>`` link per locale.

    Args:
        props: Props forwarded to the switcher's ``<nav>`` element.

    Returns:
        The language-switcher component.
    """
    return LanguageSwitcher.create(**props)
