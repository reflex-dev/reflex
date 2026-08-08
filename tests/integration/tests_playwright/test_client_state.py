"""Integration tests for experimental client state vars."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def ClientStateLateMountApp():
    """App reproducing late-mounted global ClientStateVar synchronization."""
    import asyncio

    import reflex as rx
    from reflex.experimental import ClientStateVar

    flag = ClientStateVar.create("flag", default="")

    class State(rx.State):
        mounted: bool = False

        @rx.event(background=True)
        async def go(self):
            async with self:
                self.mounted = False
            yield flag.push("busy")
            await asyncio.sleep(0.2)
            async with self:
                self.mounted = True
            await asyncio.sleep(0.2)
            yield flag.push("")

    def index() -> rx.Component:
        return rx.el.div(
            rx.el.button("go", on_click=State.go, id="go"),
            rx.el.div(flag.value, id="always"),
            rx.cond(State.mounted, rx.el.div(flag.value, id="late")),
        )

    app = rx.App()
    app.add_page(index, route="/")


@pytest.fixture(scope="module")
def client_state_late_mount_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Run the client state late-mount repro app.

    Args:
        tmp_path_factory: Pytest fixture for creating temporary directories.

    Yields:
        The running harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("client_state_late_mount_app"),
        app_source=ClientStateLateMountApp,
    ) as harness:
        yield harness


def test_late_mounted_global_client_state_rerenders_on_default_push(
    client_state_late_mount_app: AppHarness, page: Page
) -> None:
    """A late-mounted consumer should update when the shared value returns to default.

    Args:
        client_state_late_mount_app: Running app harness.
        page: Playwright page.
    """
    assert client_state_late_mount_app.frontend_url is not None
    page.goto(client_state_late_mount_app.frontend_url)

    expect(page.locator("#always")).to_have_text("")
    expect(page.locator("#late")).to_have_count(0)

    page.click("#go")

    expect(page.locator("#always")).to_have_text("busy")
    expect(page.locator("#late")).to_have_text("busy")
    expect(page.locator("#always")).to_have_text("")
    expect(page.locator("#late")).to_have_text("")
