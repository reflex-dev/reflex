"""Framework state backing localization.

Registered as a substate of the root state when this module is imported (which
the :class:`~reflex_i18n.plugin.I18nPlugin` triggers). Holds the client's
chosen locale in a cookie and exposes the resolved locale for server-side
translation of dynamic content.
"""

from __future__ import annotations

import contextlib

from reflex_base.event.processor.scope import register_event_scope_provider
from reflex_base.plugins.base import get_plugin
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var, VarData, computed_var
from reflex_base.vars.function import FunctionStringVar, ReflexCallable

from reflex.event import EventType, event, run_script
from reflex.istate.storage import Cookie
from reflex.state import BaseState, State, _override_base_method

from .config import LOCALE_COOKIE_NAME, get_active_i18n_config
from .runtime import negotiate_locale, use_locale

# Switches the client-side locale, without a round trip to the server.
_SWITCH_LOCALE = FunctionStringVar.create(
    "switchLocale",
    _var_type=ReflexCallable[[str], None],
    _var_data=VarData(imports={"$/utils/i18n": [ImportVar(tag="switchLocale")]}),
)


def _resolve_locale(locale_cookie: str, accept_language: str) -> str:
    """Resolve a locale: chosen cookie, then Accept-Language, then default.

    Args:
        locale_cookie: The user's chosen locale, or empty if none.
        accept_language: The raw ``Accept-Language`` header value.

    Returns:
        The resolved locale.
    """
    config = get_active_i18n_config()
    if config is None:
        return locale_cookie or "en"
    if locale_cookie and locale_cookie in config.locales:
        return locale_cookie
    return negotiate_locale(accept_language, config.locales, config.default_locale)


def _locale_from_path(path: str) -> str | None:
    """The locale a URL path names, when URL-based routing is enabled.

    Args:
        path: The page path the client is on.

    Returns:
        The locale owned by the path, or None if this app does not route
        locales through the URL.
    """
    from .plugin import I18nPlugin

    plugin = get_plugin(I18nPlugin)
    config = get_active_i18n_config()
    if plugin is None or plugin.routing is None or config is None:
        return None
    return plugin.routing.locale_of(path, config.locales, config.default_locale)


class I18nState(State):
    """Substate holding the active locale for the current client."""

    # The locale explicitly chosen by the user, persisted client-side. Empty
    # until the user picks one, so Accept-Language keeps driving the default.
    locale_cookie: str = Cookie("", name=LOCALE_COOKIE_NAME)

    # The locale the current URL names, written per event by _locale_scope when
    # the plugin routes locales through the path (empty otherwise). A var of
    # this state rather than a dependency on the root state's router var: that
    # would attach an i18n edge to every app sharing the process.
    _route_locale: str = ""

    @classmethod
    @_override_base_method
    def is_user_defined(cls) -> bool:
        """Whether this is a user-authored state.

        Returns:
            False: this is a framework state, so it is excluded from telemetry
            and auto-setter generation.
        """
        return False

    @computed_var(
        cache=True,
        backend=True,
        auto_deps=False,
        deps=["locale_cookie", "_route_locale"],
    )
    def locale(self) -> str:
        """The locale in effect for this client (server-side).

        Returns:
            The resolved locale.
        """
        # With URL routing the path owns the locale, so navigating between
        # prefixes retranslates dynamic content. accept-language is read for the
        # initial cookie-mode value but is fixed per session, so it is not a
        # dependency.
        return self._route_locale or _resolve_locale(
            self.locale_cookie, self.router.headers.accept_language
        )

    @event
    def set_locale(self, locale: str) -> None:
        """Set the client's chosen locale.

        Args:
            locale: The locale to switch to.

        Raises:
            ValueError: If the locale is not configured.
        """
        config = get_active_i18n_config()
        if config is not None and locale not in config.locales:
            msg = (
                f"Locale {locale!r} is not configured. Configured locales: "
                f"{list(config.locales)}."
            )
            raise ValueError(msg)
        self.locale_cookie = locale


def set_locale(locale: str | Var[str]) -> EventType:
    """Switch the app's locale (static content instantly, dynamic on next delta).

    Args:
        locale: The locale to switch to.

    Returns:
        The client-side and server-side switch events.
    """
    return [
        run_script(_SWITCH_LOCALE.call(locale)),
        I18nState.set_locale(locale),
    ]


async def _locale_scope(
    root_state: BaseState,
) -> contextlib.AbstractContextManager[None]:
    """Per-event locale context, or a no-op when this app has no i18n plugin.

    Args:
        root_state: The client's root state instance.

    Returns:
        A context manager activating the client's locale.
    """
    from .plugin import I18nPlugin

    # Gate on the CURRENT app's plugins rather than the module-global active
    # config: the provider is registered process-wide once i18n is imported,
    # but an app not using i18n (possible when several apps share a process)
    # must be a no-op so it never touches I18nState.
    if get_plugin(I18nPlugin) is None:
        return contextlib.nullcontext()
    i18n_state = await root_state.get_state(I18nState)
    # Record the URL's locale so translated computed vars are invalidated when
    # the visitor navigates to another prefix.
    route_locale = _locale_from_path(i18n_state.router.page.path)
    if route_locale is not None and route_locale != i18n_state._route_locale:
        i18n_state._route_locale = route_locale
    # I18nState.locale is the single source of truth, so what gettext returns
    # and what dynamic translations depend on can never disagree.
    return use_locale(i18n_state.locale)


register_event_scope_provider(_locale_scope)

# The implicit dependency of gettext-family calls on I18nState.locale (so
# translated computed vars recompute when the locale changes) is registered in
# .runtime, next to those functions, so it takes effect as soon as the app
# imports gettext — independently of when this module is imported.
