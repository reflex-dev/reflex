"""Test cases for the FastAPI lifespan integration."""

from typing import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness

from .utils import SessionStorage


def LifespanApp():
    """App with lifespan tasks and context."""
    import asyncio
    from contextlib import asynccontextmanager

    import reflex as rx

    lifespan_task_global = 0
    lifespan_context_global = 0

    @asynccontextmanager
    async def lifespan_context(app, inc: int = 1):
        global lifespan_context_global
        print(f"Lifespan context entered: {app}.")
        lifespan_context_global += inc  # pyright: ignore[reportUnboundVariable]
        try:
            yield
        finally:
            print("Lifespan context exited.")
            lifespan_context_global += inc

    async def lifespan_task(inc: int = 1):
        global lifespan_task_global
        print("Lifespan global started.")
        try:
            while True:
                lifespan_task_global += inc  # pyright: ignore[reportUnboundVariable]
                await asyncio.sleep(0.1)
        except asyncio.CancelledError as ce:
            print(f"Lifespan global cancelled: {ce}.")
            lifespan_task_global = 0

    class LifespanState(rx.State):
        @rx.var
        def task_global(self) -> int:
            return lifespan_task_global

        @rx.var
        def context_global(self) -> int:
            return lifespan_context_global

        def tick(self, date):
            pass

    def index():
        return rx.vstack(
            rx.text(LifespanState.task_global, id="task_global"),
            rx.text(LifespanState.context_global, id="context_global"),
            rx.moment(interval=100, on_change=LifespanState.tick),
        )

    app = rx.App()
    app.register_lifespan_task(lifespan_task)
    app.register_lifespan_task(lifespan_context, inc=2)
    app.add_page(index)


@pytest.fixture()
def lifespan_app(tmp_path) -> Generator[AppHarness, None, None]:
    """Start LifespanApp app at tmp_path via AppHarness.

    Args:
        tmp_path: pytest tmp_path fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=LifespanApp,  # type: ignore
    ) as harness:
        yield harness


@pytest.mark.asyncio
async def test_lifespan(lifespan_app: AppHarness):
    """Test the lifespan integration.

    Args:
        lifespan_app: harness for LifespanApp app
    """
    assert lifespan_app.app_module is not None, "app module is not found"
    assert lifespan_app.app_instance is not None, "app is not running"
    driver = lifespan_app.frontend()

    ss = SessionStorage(driver)
    assert AppHarness._poll_for(lambda: ss.get("token") is not None), "token not found"

    context_global = driver.find_element(By.ID, "context_global")
    task_global = driver.find_element(By.ID, "task_global")

    assert context_global.text == "2"
    assert lifespan_app.app_module.lifespan_context_global == 2  # type: ignore

    original_task_global_text = task_global.text
    original_task_global_value = int(original_task_global_text)
    lifespan_app.poll_for_content(task_global, exp_not_equal=original_task_global_text)
    assert lifespan_app.app_module.lifespan_task_global > original_task_global_value  # type: ignore
    assert int(task_global.text) > original_task_global_value

    # Kill the backend
    assert lifespan_app.backend is not None
    lifespan_app.backend.should_exit = True
    if lifespan_app.backend_thread is not None:
        lifespan_app.backend_thread.join()

    # Check that the lifespan tasks have been cancelled
    assert lifespan_app.app_module.lifespan_task_global == 0
    assert lifespan_app.app_module.lifespan_context_global == 4
