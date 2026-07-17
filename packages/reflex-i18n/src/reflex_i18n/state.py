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
    """Resolve a locale from a chosen-locale cookie and Accept-Language.

    Resolution order: the chosen-locale cookie, then the best match for the
    ``Accept-Language`` header, then the configured default.

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
        """The locale in effect for this client.

        Server-side only: the client tracks its own locale via the i18n
        provider. Exists so user computed vars that translate dynamic content
        can depend on it and recompute when the locale changes.

        Depends only on ``locale_cookie`` (not ``router``): the accept-language
        header is read for the initial value but never changes within a
        session, and tracking ``router`` here would add this substate to the
        root state's potentially-dirty set on every navigation.

        Returns:
            The resolved locale.
        """
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
    """Switch the app's locale for static and dynamic content.

    Switches client-side translated (``rx.t``) content immediately and writes
    the locale cookie, then updates the server so dynamic (state) content is
    retranslated on the next delta.

    Args:
        locale: The locale to switch to.

    Returns:
        The events performing the client-side and server-side switch.
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
    """Build the per-event locale context for a client.

    Reads the client's resolved locale from state and returns a context
    manager activating it, so server-side ``gettext`` translates into it
    during handler execution and delta resolution.

    Args:
        root_state: The client's root state instance.

    Returns:
        A context manager activating the client's locale, or a no-op when
        i18n is not configured.
    """
    if get_active_i18n_config() is None:
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
