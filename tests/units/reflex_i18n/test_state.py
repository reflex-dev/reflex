"""Tests for the I18nState and set_locale event helper."""

import contextlib
from typing import TYPE_CHECKING, cast

import pytest
from reflex_base import constants
from reflex_base.config import get_config
from reflex_base.utils import console
from reflex_i18n import I18nConfig, I18nPlugin, PathPrefixRouting
from reflex_i18n.config import set_active_i18n_config
from reflex_i18n.runtime import get_locale
from reflex_i18n.state import (
    I18nState,
    _locale_scope,
    _page_path,
    _resolve_locale,
    set_locale,
)

from reflex.istate.data import RouterData
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


def test_resolve_locale_falls_back_to_fallback_locale():
    set_active_i18n_config(
        I18nConfig(locales=["de", "en"], default_locale="de", fallback_locale="en")
    )
    assert _resolve_locale("", "ja,ko") == "en"
    assert _resolve_locale("", "de-AT") == "de"
    assert _resolve_locale("", "") == "en"


def test_resolve_locale_without_config():
    set_active_i18n_config(None)
    assert _resolve_locale("", "de") == "en"
    assert _resolve_locale("de", "") == "de"


def test_set_locale_returns_client_and_server_events():
    events = set_locale("de")
    assert isinstance(events, list)
    assert len(events) == 2
    # The first switches the client (run_script), the second updates state.
    # The helper sends the server event itself, so the provider must not.
    assert 'switchLocale("de", ({ ["notifyServer"] : false }))' in repr(events[0])
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


async def _root_on(
    path: str, cookie: str, accept_language: str = "", url_path: str | None = None
) -> State:
    """Build a root state on a given page, with a locale cookie set.

    Args:
        path: The route of the page the client is on.
        cookie: The locale chosen by the user, if any.
        accept_language: The client's Accept-Language header.
        url_path: The browser's path below frontend_path, if not the route.

    Returns:
        The root state.
    """
    root = State()
    root.router = RouterData.from_router_data({
        constants.RouteVar.PATH: path,
        constants.RouteVar.ORIGIN: path if url_path is None else url_path,
        constants.RouteVar.HEADERS: {"accept-language": accept_language},
    })
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
@pytest.mark.parametrize("frontend_path", ["", "/app"])
async def test_locale_scope_takes_an_unknown_pages_locale_from_the_url(
    monkeypatch: pytest.MonkeyPatch, frontend_path: str
):
    # Regression: an unknown page's route id is "/404", while the provider reads
    # the locale from the browser's path, so a localized error page mixed the
    # default locale's dynamic text with the URL locale's static text.
    monkeypatch.setattr(get_config(), "frontend_path", frontend_path)
    monkeypatch.setattr(
        get_config(),
        "plugins",
        [
            I18nPlugin(
                locales=["en", "de"], default_locale="en", routing=PathPrefixRouting()
            )
        ],
    )
    root = await _root_on("/404", cookie="en", url_path="/de/missing")

    with await _locale_scope(root):
        assert get_locale() == "de"


@pytest.mark.parametrize(
    ("url_path", "expected"),
    [
        ("/app/de/pricing", "/de/pricing"),
        ("/app", "/"),
        ("/app/", "/"),
        ("/application/de", "/application/de"),
    ],
)
def test_page_path_strips_the_frontend_path(
    monkeypatch: pytest.MonkeyPatch, url_path: str, expected: str
):
    monkeypatch.setattr(get_config(), "frontend_path", "/app")
    assert _page_path(url_path) == expected


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


@pytest.mark.asyncio
async def test_locale_scope_keeps_a_session_locale_a_deploy_removed(
    monkeypatch: pytest.MonkeyPatch,
):
    # A session resolved its locale before the config dropped it; its events
    # must keep working rather than fail the configured-locale check.
    root = await _root_on("/pricing", cookie="fr")
    assert (await root.get_state(I18nState)).locale == "fr"
    monkeypatch.setattr(
        get_config(), "plugins", [I18nPlugin(locales=["en", "de"], default_locale="en")]
    )

    with await _locale_scope(root):
        assert get_locale() == "fr"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("routing", "expected"),
    [(None, "fr"), (PathPrefixRouting(), "de")],
    ids=["cookie", "url"],
)
async def test_locale_scope_reads_the_router_fields_directly(
    monkeypatch: pytest.MonkeyPatch, routing: PathPrefixRouting | None, expected: str
):
    # The scope runs on every event, so it must not compose a RouterData view,
    # whose deprecated page accessor also logs a warning.
    monkeypatch.setattr(
        get_config(),
        "plugins",
        [I18nPlugin(locales=["en", "de", "fr"], default_locale="en", routing=routing)],
    )
    root = await _root_on("/de/pricing", cookie="", accept_language="fr")
    built: list[RouterData] = []
    deprecations: list[str] = []

    def build_router(**fields) -> RouterData:
        router = RouterData(**fields)
        built.append(router)
        return router

    monkeypatch.setattr("reflex.state.RouterData", build_router)
    monkeypatch.setattr(
        console,
        "deprecate",
        lambda *, feature_name, **_: deprecations.append(feature_name),
    )

    with await _locale_scope(root):
        assert get_locale() == expected
    assert built == []
    assert deprecations == []
