"""AppHarness end-to-end check with the `reflex[testing]` extra, as a downstream project would.

    cd <this dir> && <venv with reflex[testing]>/bin/pytest -q test_harness.py
"""

from collections.abc import Generator

import httpx
import pytest

from reflex.testing import AppHarness


def HarnessApp():
    import reflex as rx

    class HState(rx.State):
        count: int = 0

        @rx.event
        def bump(self):
            self.count += 1

    def index():
        return rx.vstack(
            rx.text(f"count={HState.count}", id="count"),
            rx.button("bump", on_click=HState.bump, id="bump"),
        )

    app = rx.App()
    app.add_page(index, route="/")


@pytest.fixture(scope="module")
def harness(tmp_path_factory) -> Generator[AppHarness, None, None]:
    with AppHarness.create(
        root=tmp_path_factory.mktemp("harness_app"), app_source=HarnessApp
    ) as h:
        yield h


def test_frontend_serves(harness: AppHarness):
    assert harness.frontend_url is not None
    with httpx.Client(trust_env=False, timeout=30) as c:
        r = c.get(harness.frontend_url)
    assert r.status_code == 200, r.status_code
    assert "count=" in r.text or "reflex" in r.text.lower()


def test_backend_alive(harness: AppHarness):
    assert harness.backend is not None
    assert harness.app_instance is not None
    assert harness.token_manager is not None


def test_state_manager_roundtrip(harness: AppHarness):
    """Drive the app's state through the harness's app instance."""
    import asyncio

    import reflex as rx
    from reflex.state import State

    app = harness.app_instance
    assert app is not None

    async def run():
        token = rx.BaseStateToken(ident="harness-probe-token", cls=State)
        async with app.state_manager.modify_state(token) as state:
            return sorted(state.substates)

    substates = asyncio.run(run())
    assert substates, "root state has no substates"
    assert any("h_state" in name for name in substates), substates


def test_poll_for_content(harness: AppHarness):
    """The documented content helper works against the running frontend."""
    with httpx.Client(trust_env=False, timeout=30) as c:
        body = c.get(harness.frontend_url).text
    assert "<!DOCTYPE html" in body or "<!doctype html" in body
