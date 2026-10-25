"""Tests for the i18n client components."""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from reflex_base.registry import RegistrationContext
from reflex_base.utils.format import format_event_handler
from reflex_i18n import I18nPlugin, PathPrefixRouting, language_switcher, t
from reflex_i18n.config import set_active_i18n_config
from reflex_i18n.plugin import _reset_provider
from reflex_i18n.registry import clear_messages
from reflex_i18n.state import I18nState

import reflex as rx
from reflex.compiler import compiler

CompileApp = Callable[[PathPrefixRouting | None], tuple[str, str]]


@pytest.fixture(autouse=True)
def clean_i18n() -> Iterator[None]:
    """Keep the test's plugin, messages and provider from leaking into others.

    Yields:
        None
    """
    yield
    _reset_provider()
    clear_messages()
    set_active_i18n_config(None)


@pytest.fixture
def compile_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> CompileApp:
    """Compile an app translating client-side and showing the language switcher.

    Args:
        tmp_path: The app directory.
        monkeypatch: Fixture for changing the app directory.
        mocker: Fixture for configuring the app and capturing compiled code.

    Returns:
        A function compiling the app with the given plugin routing (None for
        cookie mode), returning the compiled memo modules and app root, and
        the wire name of ``I18nState.set_locale``.
    """
    monkeypatch.chdir(tmp_path)
    memos = mocker.spy(compiler, "compile_memo_components")
    root = mocker.spy(compiler, "compile_app_root")

    def compile_(routing: PathPrefixRouting | None) -> tuple[str, str]:
        with RegistrationContext():
            plugin = I18nPlugin(locales=["en", "de"], routing=routing)
            config = rx.Config(app_name="i18n_test", plugins=[plugin])
            mocker.patch("reflex_base.config._get_config", return_value=config)
            app = rx.App()
            app.add_page(lambda: rx.el.div(t("Hello"), language_switcher()), route="/")
            compiler.compile_app(app, dry_run=True, use_rich=False)
            handler = format_event_handler(I18nState.event_handlers["set_locale"])
        memo_files, _ = memos.spy_return
        code = "".join(code for _, code in (*memo_files, root.spy_return))
        return code, handler

    return compile_


def test_cookie_mode_provider_reports_switch_to_server(compile_app: CompileApp):
    code, handler = compile_app(None)
    assert "onLocaleChange" in code
    assert f'ReflexEvent("{handler}"' in code


def test_url_routing_provider_reports_nothing(compile_app: CompileApp):
    code, _ = compile_app(PathPrefixRouting())
    assert "I18nProvider" in code
    assert "onLocaleChange" not in code


def test_provider_follows_a_newly_configured_plugin(compile_app: CompileApp):
    # An earlier app in this process (e.g. another test harness) left its
    # cookie-mode provider cached.
    compile_app(None)
    code, _ = compile_app(PathPrefixRouting())
    assert "onLocaleChange" not in code
