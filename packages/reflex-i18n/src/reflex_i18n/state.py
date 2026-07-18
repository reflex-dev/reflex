"""Framework state backing localization.

Registered as a substate of the root state when this module is imported (which
the :class:`~reflex_i18n.plugin.I18nPlugin` triggers). Holds the client's
chosen locale in a cookie and exposes the resolved locale for server-side
translation of dynamic content.
"""

from __future__ import annotations

import contextlib

from reflex_base.event.processor.scope import register_event_scope_provider
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var, VarData, computed_var
from reflex_base.vars.dep_tracking import register_implicit_dependency
from reflex_base.vars.function import FunctionVar

from reflex.event import EventType, run_script
from reflex.istate.storage import Cookie
from reflex.state import BaseState, State

from .config import LOCALE_COOKIE_NAME, get_active_i18n_config
from .runtime import gettext, negotiate_locale, ngettext, pgettext, use_locale


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


class I18nState(State):
    """Substate holding the active locale for the current client."""

    # The locale explicitly chosen by the user, persisted client-side. Empty
    # until the user picks one, so Accept-Language keeps driving the default.
    locale_cookie: str = Cookie("", name=LOCALE_COOKIE_NAME)

    @computed_var(cache=True, backend=True, auto_deps=False, deps=["locale_cookie"])
    def locale(self) -> str:
        """The locale in effect for this client (server-side).

        Returns:
            The resolved locale.
        """
        # Depends only on locale_cookie (not router): accept-language is read
        # for the initial value but is fixed per session, and depending on
        # router would dirty this substate on every navigation.
        return _resolve_locale(self.locale_cookie, self.router.headers.accept_language)

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
    switch_client = run_script(
        Var(
            _js_expr="switchLocale",
            _var_data=VarData(
                imports={"$/utils/i18n": [ImportVar(tag="switchLocale")]}
            ),
        )
        .to(FunctionVar)
        .call(locale)
    )
    # The State metaclass turns set_locale into an EventHandler at runtime;
    # pyright still sees the plain method, hence the ignore.
    return [switch_client, I18nState.set_locale(locale)]  # pyright: ignore[reportCallIssue]


async def _locale_scope(
    root_state: BaseState,
) -> contextlib.AbstractContextManager[None]:
    """Per-event locale context, or a no-op when this app has no i18n plugin.

    Args:
        root_state: The client's root state instance.

    Returns:
        A context manager activating the client's locale.
    """
    from reflex_base.config import get_config

    from .plugin import I18nPlugin

    # Gate on the CURRENT app's plugins rather than the module-global active
    # config: the provider is registered process-wide once i18n is imported,
    # but a given app (e.g. a non-i18n app loaded later in the same process,
    # as in the test suite) must be a no-op so it never touches I18nState.
    if not any(isinstance(plugin, I18nPlugin) for plugin in get_config().plugins):
        return contextlib.nullcontext()
    i18n_state = await root_state.get_state(I18nState)
    locale = _resolve_locale(
        i18n_state.locale_cookie, i18n_state.router.headers.accept_language
    )
    return use_locale(locale)


register_event_scope_provider(_locale_scope)

# A computed var that calls gettext/ngettext/pgettext reads the active locale
# from a contextvar, which the bytecode dependency tracker cannot see. Register
# these functions so referencing one implies a dependency on I18nState.locale,
# making translated computed vars recompute (and re-push) when the locale
# changes.
register_implicit_dependency(
    (gettext, ngettext, pgettext),
    lambda: I18nState.locale,
)
