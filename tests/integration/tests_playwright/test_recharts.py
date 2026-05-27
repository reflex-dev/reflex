"""Integration test that recharts charts render at runtime.

Regression coverage for https://github.com/reflex-dev/reflex/issues/6561: any page
rendering a ``rx.recharts`` chart crashed with ``TypeError`` and an infinite React
Router route-reload loop. recharts default-imports CommonJS ``es-toolkit/compat/*``
shims from its core utils; the bundler emitted the CJS interop helper into a chunk
that loaded after the lazy route chunk. The bug only surfaced at runtime in a real
(esp. production / Rolldown) build, which this test exercises via ``app_harness_env``.
"""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def RechartsApp():
    """App with an area chart on the index route (the issue's reproduction)."""
    import reflex as rx

    @rx.page("/")
    def index():
        return rx.box(
            rx.heading("recharts"),
            rx.recharts.area_chart(
                rx.recharts.area(data_key="value"),
                rx.recharts.x_axis(data_key="name"),
                data=[
                    {"name": "A", "value": 1},
                    {"name": "B", "value": 3},
                    {"name": "C", "value": 2},
                ],
                width=500,
                height=300,
            ),
            id="page",
        )

    app = rx.App()  # noqa: F841


@pytest.fixture(scope="module")
def recharts_app(
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start RechartsApp in both dev and prod mode.

    Args:
        app_harness_env: AppHarness (dev) or AppHarnessProd (prod), from conftest.
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        Running AppHarness instance.
    """
    name = f"recharts_{app_harness_env.__name__.lower()}"
    with app_harness_env.create(
        root=tmp_path_factory.mktemp(name),
        app_name=name,
        app_source=RechartsApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_recharts_renders_without_error(recharts_app: AppHarness, page: Page):
    """The chart's SVG renders and the page raises no JS error or reload loop.

    Args:
        recharts_app: AppHarness running the recharts test app.
        page: Playwright page.
    """
    assert recharts_app.frontend_url is not None

    page_errors: list[str] = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

    page.goto(recharts_app.frontend_url)

    # Under #6561 the route module fails to load and React Router reloads forever,
    # so the chart never appears and this assertion times out.
    expect(page.locator(".recharts-surface")).to_be_visible()
    assert not page_errors, f"Frontend raised unexpected errors: {page_errors}"
