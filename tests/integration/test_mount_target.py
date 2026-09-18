"""Integration tests for the ``mount_target`` config option.

Builds the app in prod mode with ``mount_target`` set, then serves a
hand-written host HTML page that loads the bundle's entry script and contains
``<div id="reflex-root">`` so we can verify the app mounts inside it instead of
taking over ``<html>``/``<body>``.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect
from reflex_base import constants as base_constants

import reflex.constants
from reflex.testing import AppHarnessProd
from reflex.utils.prerequisites import get_web_dir


def MountTargetApp():
    import reflex as rx

    class S(rx.State):
        n: int = 0
        last_loaded_path: str = ""

        @rx.event
        def inc(self):
            self.n += 1

        @rx.event
        def on_load_about(self):
            self.last_loaded_path = self.router.url.path

        @rx.event
        def on_load_counter(self):
            self.n += 1
            self.last_loaded_path = self.router.url.path

    def index():
        return rx.box(
            rx.text("count: ", S.n, id="count"),
            rx.button("inc", on_click=S.inc, id="inc"),
            rx.link("about", href="/about", id="link-about"),
            rx.link("counter", href="/counter", id="link-counter"),
            id="index-marker",
        )

    @rx.page(route="/about", on_load=S.on_load_about)
    def about():
        return rx.box(
            rx.text("about page"),
            rx.text("loaded: ", S.last_loaded_path, id="loaded-path"),
            rx.link("home", href="/", id="link-home"),
            id="about-marker",
        )

    @rx.page(route="/counter", on_load=S.on_load_counter)
    def counter():
        return rx.box(
            rx.text("count: ", S.n, id="count"),
            rx.text("loaded: ", S.last_loaded_path, id="loaded-path"),
            id="counter-marker",
        )

    app = rx.App()
    app.add_page(index)

    # Set plugins after rx.App() because App.__post_init__ reloads the config
    # from rxconfig.py and would wipe any earlier mutation.
    config = rx.config.get_config()
    config.plugins = [rx.plugins.EmbedPlugin(mount_target="#reflex-root")]


@pytest.fixture(scope="module")
def mount_target_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarnessProd, None, None]:
    """Start MountTargetApp in prod mode with mount_target set.

    Args:
        tmp_path_factory: Pytest fixture.

    Yields:
        Running harness.
    """
    with AppHarnessProd.create(
        root=tmp_path_factory.mktemp("mount_target_app"),
        app_source=MountTargetApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def _static_dir(harness: AppHarnessProd) -> Path:
    return harness.app_path / get_web_dir() / reflex.constants.Dirs.STATIC


def _write_host(static_dir: Path, name: str = "host.html") -> None:
    entry_src = "/" + base_constants.Embed.ENTRY_PATH
    host_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>host</title></head>
<body>
  <div data-host-marker="yes">host content above</div>
  <div id="reflex-root"></div>
  <div data-host-marker="yes">host content below</div>
  <script type="module" src="{entry_src}"></script>
</body>
</html>
"""
    (static_dir / name).write_text(host_html)


def test_app_mounts_into_host_container(mount_target_app: AppHarnessProd, page: Page):
    """A host HTML page with #reflex-root receives the mounted app."""
    static = _static_dir(mount_target_app)
    _write_host(static)

    base = mount_target_app.frontend_url
    assert base is not None
    page.goto(f"{base.rstrip('/')}/host.html")

    expect(page.locator("#reflex-root #count")).to_contain_text("count:")
    expect(page.locator('[data-host-marker="yes"]')).to_have_count(2)


def test_in_widget_navigation_keeps_host_url(
    mount_target_app: AppHarnessProd, page: Page
):
    """Clicking a Reflex link routes inside the widget; host URL stays put."""
    static = _static_dir(mount_target_app)
    _write_host(static)

    base = mount_target_app.frontend_url
    assert base is not None
    host_url = f"{base.rstrip('/')}/host.html"
    page.goto(host_url)

    expect(page.locator("#reflex-root #index-marker")).to_be_visible()

    page.locator("#reflex-root #link-about").click()

    expect(page.locator("#reflex-root #about-marker")).to_be_visible()
    # Host URL must not have changed despite the in-widget navigation.
    assert page.url == host_url
    # The about page's on_load handler writes the path it observed; the
    # backend's route matcher only resolves the on_load if router_data.pathname
    # is the in-widget URL "/about" (not the host's "/host.html").
    expect(page.locator("#reflex-root #loaded-path")).to_have_text("loaded: /about")


def test_on_load_fires_for_embedded_route(mount_target_app: AppHarnessProd, page: Page):
    """An on_load handler tied to a non-index route fires after navigation."""
    static = _static_dir(mount_target_app)
    _write_host(static)

    base = mount_target_app.frontend_url
    assert base is not None
    page.goto(f"{base.rstrip('/')}/host.html")

    expect(page.locator("#reflex-root #count")).to_have_text("count: 0")
    page.locator("#reflex-root #link-counter").click()
    expect(page.locator("#reflex-root #counter-marker")).to_be_visible()
    expect(page.locator("#reflex-root #count")).to_have_text("count: 1")
    expect(page.locator("#reflex-root #loaded-path")).to_have_text("loaded: /counter")
