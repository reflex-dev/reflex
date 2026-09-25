"""The client components backing i18n (provider, per-route locale, hreflang)."""

from __future__ import annotations

from typing import Any

from reflex_base.components.component import Component
from reflex_base.vars.base import Var

# Outside the ErrorBoundary (55) so error fallback UI can translate too.
_PROVIDER_PRIORITY = 58


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
    """A language switcher: one ``<a>`` per locale (crawlable with URL routing)."""

    library = "$/utils/i18n"

    tag = "LanguageSwitcher"

    @staticmethod
    def _get_app_wrap_components() -> dict[tuple[int, str], Component]:
        """Pull in the provider so the switcher can read and set the locale.

        Returns:
            The provider app wrap.
        """
        # A page may use the switcher without any rx.t or rx.i18n formatting
        # var, neither of which would then drag the provider in.
        return {(_PROVIDER_PRIORITY, "I18nProvider"): I18nProvider.create()}
