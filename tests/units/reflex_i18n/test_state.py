"""Tests for the I18nState and set_locale event helper."""

import contextlib
from typing import TYPE_CHECKING, cast

import pytest
from reflex_i18n import I18nConfig
from reflex_i18n.config import set_active_i18n_config
from reflex_i18n.state import I18nState, _locale_scope, _resolve_locale, set_locale

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
async def test_locale_scope_noop_without_config():
    set_active_i18n_config(None)

    scope = await _locale_scope(cast("BaseState", object()))
    assert isinstance(scope, contextlib.nullcontext)
