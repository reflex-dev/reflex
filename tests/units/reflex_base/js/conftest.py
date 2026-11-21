"""Fixtures for importing JavaScript modules from Python."""

import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from reflex_base.registry import RegistrationContext

import reflex as rx

# The source of js_app/party.js.
PARTY_SOURCE = """
import confetti from "canvas-confetti";
export function celebrate(count) {}
export async function load() {}
export const arrow = () => 1;
export const notAFunction = 5;
export default function () {}
"""


@pytest.fixture
def app_package(
    tmp_path: Path, clean_registration_context: RegistrationContext
) -> Generator[Path, None, None]:
    """Put an app package and another package, each with JavaScript modules, on sys.path.

    The app's config names ``js_app``; ``js_vendor`` stands for a third-party
    package.

    Args:
        tmp_path: pytest tmp_path fixture.
        clean_registration_context: a fresh registry for the app's config and
            the imported modules.

    Yields:
        The app package's directory.
    """
    clean_registration_context._set_config(rx.Config(app_name="js_app"))
    app = tmp_path / "js_app"
    vendor = tmp_path / "js_vendor"
    for package in (app, vendor):
        package.mkdir()
        (package / "__init__.py").write_text("")
    (app / "party.js").write_text(PARTY_SOURCE)
    (app / "typed.ts").write_text("export function typed(n: number) {}\n")
    (vendor / "widget.js").write_text("export function widget() {}\n")
    sys.path.insert(0, str(tmp_path))
    yield app
    sys.path.remove(str(tmp_path))
    for name in [
        n for n in sys.modules if n.partition(".")[0] in ("js_app", "js_vendor")
    ]:
        del sys.modules[name]
