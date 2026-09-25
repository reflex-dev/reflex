"""Tests for the I18nState and set_locale event helper."""

import contextlib
from typing import TYPE_CHECKING, cast

import pytest
from reflex_base.config import get_config
from reflex_i18n import I18nConfig, I18nPlugin, PathPrefixRouting
from reflex_i18n.config import set_active_i18n_config
from reflex_i18n.runtime import get_locale
from reflex_i18n.state import I18nState, _locale_scope, _resolve_locale, set_locale

from reflex.istate.data import PageData
from reflex.state import State

if TYPE_CHECKING:
    from reflex.state import BaseState


@pytest.fixture(autouse=True)
def i18n_config():
    """Activate an i18n config for the duration of the test.

    Yields:
        The active config.
    """
    config = I18nConfig(locales=["en", "de", "fr"], default_locale="en")
    set_active_i18n_config(config)
    yield config
    set_active_i18n_config(None)


def test_resolve_locale_prefers_cookie():
    assert _resolve_locale("de", "fr-FR,fr;q=0.9") == "de"


def test_resolve_locale_ignores_invalid_cookie():
    assert _resolve_locale("es", "fr-FR,fr;q=0.9") == "fr"


def test_resolve_locale_uses_accept_language():
    assert _resolve_locale("", "de-DE,de;q=0.9") == "de"


def test_resolve_locale_falls_back_to_default():
    assert _resolve_locale("", "ja,ko") == "en"


def test_resolve_locale_without_config():
    set_active_i18n_config(None)
    assert _resolve_locale("", "de") == "en"
    assert _resolve_locale("de", "") == "de"


def test_set_locale_returns_client_and_server_events():
    events = set_locale("de")
    assert isinstance(events, list)
    assert len(events) == 2
    # The first switches the client (run_script), the second updates state.
    assert "switchLocale" in repr(events[0])
    assert "set_locale" in repr(events[1])


def test_set_locale_handler_validates_locale():
    state = I18nState()
    with pytest.raises(ValueError, match="not configured"):
        state.set_locale("es")


def test_set_locale_handler_sets_cookie():
    state = I18nState()
    state.set_locale("de")
    assert state.locale_cookie == "de"


@pytest.mark.asyncio
async def test_locale_scope_noop_without_plugin(monkeypatch: pytest.MonkeyPatch):
    # The scope is gated on the app's plugins (so an app sharing the process
    # with an i18n app stays untouched), not on the active i18n config.
    monkeypatch.setattr(get_config(), "plugins", [])

    scope = await _locale_scope(cast("BaseState", object()))
    assert isinstance(scope, contextlib.nullcontext)


def test_locale_depends_on_the_route_locale():
    # The route-derived locale must be a dependency of its own: it is not a
    # function of the cookie, and depending on the root state's router var
    # instead would give every app in the process an i18n edge.
    deps = I18nState.computed_vars["locale"]._deps(objclass=I18nState)
    assert deps[I18nState.get_full_name()] == {"locale_cookie", "_route_locale"}


async def _root_on(path: str, cookie: str) -> State:
    """Build a root state on a given page, with a locale cookie set.

    Args:
        path: The page path the client is on.
        cookie: The locale chosen by the user, if any.

    Returns:
        The root state.
    """
    root = State()
    root.rx_router_page = PageData(path=path)
    (await root.get_state(I18nState)).locale_cookie = cookie
    return root


@pytest.mark.asyncio
async def test_locale_scope_prefers_the_route_with_url_routing(
    monkeypatch: pytest.MonkeyPatch,
):
    # Regression: with URL routing the path owns the locale, so navigating to
    # another prefix must retranslate cached dynamic content even though the
    # cookie never changed.
    monkeypatch.setattr(
        get_config(),
        "plugins",
        [
            I18nPlugin(
                locales=["en", "de"], default_locale="en", routing=PathPrefixRouting()
            )
        ],
    )
    root = await _root_on("/de/pricing", cookie="en")
    i18n_state = await root.get_state(I18nState)
    assert i18n_state.locale == "en"

    with await _locale_scope(root):
        assert get_locale() == "de"
    # The cached computed var was invalidated, not just the contextvar set.
    assert i18n_state.locale == "de"


@pytest.mark.asyncio
async def test_locale_scope_uses_the_cookie_without_url_routing(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        get_config(), "plugins", [I18nPlugin(locales=["en", "de"], default_locale="en")]
    )
    root = await _root_on("/pricing", cookie="de")

    with await _locale_scope(root):
        assert get_locale() == "de"
