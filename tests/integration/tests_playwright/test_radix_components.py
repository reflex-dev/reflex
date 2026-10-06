"""Playwright integration tests for Radix primitive components."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def ProgressApp():
    """App with a stateful primitive Progress component."""
    from reflex_components_radix.primitives.progress import progress

    import reflex as rx

    class ProgressState(rx.State):
        value: int = 25

        @rx.event
        def advance(self):
            self.value = 50

    app = rx.App()

    @app.add_page
    def index():
        return rx.vstack(
            progress(value=ProgressState.value, max=100, id="progress"),
            rx.button("Advance", on_click=ProgressState.advance),
        )


@pytest.fixture(scope="module")
def progress_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Run the primitive Progress app with AppHarness."""
    with AppHarness.create(
        root=tmp_path_factory.mktemp("radix_progress"),
        app_source=ProgressApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_progress_aria_value_updates(progress_app: AppHarness, page: Page) -> None:
    """The Root exposes and updates its current value through ARIA."""
    assert progress_app.frontend_url is not None

    page.goto(progress_app.frontend_url)
    progressbar = page.get_by_role("progressbar")
    expect(progressbar).to_have_attribute("id", "progress")
    expect(progressbar).to_have_attribute("aria-valuenow", "25")
    expect(progressbar).to_have_attribute("aria-valuemax", "100")

    page.get_by_role("button", name="Advance").click()
    expect(progressbar).to_have_attribute("aria-valuenow", "50")
