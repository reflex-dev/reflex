"""The client components backing i18n (provider, per-route locale, hreflang)."""

from __future__ import annotations

from typing import Any

from reflex_base.components.component import Component
from reflex_base.vars.base import Var


class I18nProvider(Component):
    """Provides the active locale and message catalog via React context.

    Implemented in the static web template ``utils/i18n.js``; pulled into the
    app shell automatically (via ``VarData.app_wraps``) whenever ``rx.t`` is
    used.
    """

    library = "$/utils/i18n"

    tag = "I18nProvider"


class LocaleRoute(Component):
    """Wraps a per-locale route with a fixed locale + static catalog.

    The static catalog import makes the language available synchronously during
    prerender (unlike the provider's default dynamic import).
    """

    library = "$/utils/i18n"

    tag = "LocaleRoute"

    # The locale this route renders in.
    locale: Var[str]

    # The statically-imported catalog module for ``locale``.
    catalog: Var[Any]


class HreflangLinks(Component):
    """App-wrap emitting ``hreflang`` alternates + canonical for the route.

    Reads the current path and its config from ``$/i18n/index.js`` (no props).
    """

    library = "$/utils/i18n"

    tag = "HreflangLinks"


class LanguageSwitcher(Component):
    """A crawlable language switcher: one ``<a>`` link per locale."""

    library = "$/utils/i18n"

    tag = "LanguageSwitcher"
