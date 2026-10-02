"""Unit tests for lifespan app mixin behavior."""

from __future__ import annotations

import asyncio
import contextlib

import pytest
from reflex_base.utils.exceptions import InvalidLifespanTaskTypeError
from starlette.applications import Starlette

from reflex.app_mixins.lifespan import LifespanMixin


def test_register_lifespan_task_can_be_used_as_decorator():
    """Bare decorator registers the task and preserves the name binding."""
    mixin = LifespanMixin()

    @mixin.register_lifespan_task
    def polling_task() -> str:
        return "ok"

    assert polling_task() == "ok"
    assert polling_task in mixin.get_lifespan_tasks()


def test_register_lifespan_task_with_kwargs_can_be_used_as_decorator():
    """Decorator-with-kwargs registers a partial that applies the kwargs."""
    mixin = LifespanMixin()

    @mixin.register_lifespan_task(timeout=10)
    def check_for_updates(timeout: int) -> int:
        return timeout

    assert check_for_updates(timeout=4) == 4

    (registered_task,) = mixin.get_lifespan_tasks()
    assert not isinstance(registered_task, asyncio.Task)
    assert registered_task() == 10


@pytest.mark.asyncio
async def test_register_lifespan_task_rejects_kwargs_for_asyncio_task():
    """Registering kwargs against an asyncio.Task raises a clear error."""
    mixin = LifespanMixin()
    task = asyncio.create_task(asyncio.sleep(0), name="scheduled-lifespan-task")

    try:
        with pytest.raises(
            InvalidLifespanTaskTypeError,
            match=r"of type asyncio\.Task cannot be registered with kwargs",
        ):
            mixin.register_lifespan_task(task, timeout=10)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_lifespan_task_app_param_receives_reflex_app_instance():
    """Lifespan tasks should receive the Reflex app instance, not Starlette."""
    mixin = LifespanMixin()
    received: dict[str, object] = {}

    def lifespan_task(app):
        """Record the app argument injected by the lifespan runner."""
        received["app"] = app

    mixin.register_lifespan_task(lifespan_task)

    async with mixin._run_lifespan_tasks(Starlette()):
        await asyncio.sleep(0)

    assert received["app"] is mixin


@pytest.mark.asyncio
async def test_lifespan_task_starlette_app_param_receives_starlette_instance():
    """Lifespan tasks should receive the Starlette app when requested."""
    mixin = LifespanMixin()
    received: dict[str, object] = {}
    starlette_app = Starlette()

    def lifespan_task(starlette_app):
        """Record the Starlette app argument injected by the lifespan runner.

        Args:
            starlette_app: Starlette app object injected by the lifespan runner.
        """
        received["starlette_app"] = starlette_app

    mixin.register_lifespan_task(lifespan_task)

    async with mixin._run_lifespan_tasks(starlette_app):
        await asyncio.sleep(0)

    assert received["starlette_app"] is starlette_app


@pytest.mark.asyncio
async def test_lifespan_task_both_app_and_starlette_app_params_are_injected():
    """Lifespan tasks should receive both app and starlette_app when declared."""
    mixin = LifespanMixin()
    received: dict[str, object] = {}
    starlette_app = Starlette()

    def lifespan_task(app, starlette_app):
        """Record both injected app objects from the lifespan runner.

        Args:
            app: Reflex app object injected by the lifespan runner.
            starlette_app: Starlette app object injected by the lifespan runner.
        """
        received["app"] = app
        received["starlette_app"] = starlette_app

    mixin.register_lifespan_task(lifespan_task)

    async with mixin._run_lifespan_tasks(starlette_app):
        await asyncio.sleep(0)

    assert received["app"] is mixin
    assert received["starlette_app"] is starlette_app


@pytest.mark.asyncio
async def test_lifespan_shutdown_closes_health_redis(mocker):
    """Lifespan shutdown releases the cached health-check redis client."""
    close = mocker.patch(
        "reflex.utils.prerequisites.close_health_redis", new_callable=mocker.AsyncMock
    )
    mixin = LifespanMixin()

    async with mixin._run_lifespan_tasks(Starlette()):
        close.assert_not_awaited()

    close.assert_awaited_once()


async def _run_coroutine_lifespan_task(task) -> list[dict]:
    """Run a coroutine lifespan task through startup and shutdown.

    Args:
        task: The coroutine function to register as a lifespan task.

    Returns:
        The contexts passed to the event loop exception handler.
    """
    loop = asyncio.get_running_loop()
    reported: list[dict] = []
    previous_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda _, context: reported.append(context))
    try:
        mixin = LifespanMixin()
        mixin.register_lifespan_task(task)
        async with mixin._run_lifespan_tasks(Starlette()):
            lifespan_tasks = [
                t
                for t in asyncio.all_tasks()
                if t.get_name().startswith("reflex_lifespan_task|")
            ]
            # Let tasks that end on their own finish before shutdown starts.
            await asyncio.wait(lifespan_tasks, timeout=0.01)
        await asyncio.gather(*lifespan_tasks, return_exceptions=True)
    finally:
        loop.set_exception_handler(previous_handler)
    return reported


@pytest.mark.asyncio
async def test_lifespan_shutdown_cancellation_is_not_reported_as_error():
    """Cancelling a running coroutine lifespan task at shutdown is not an error."""

    async def run_forever():
        await asyncio.Event().wait()

    assert await _run_coroutine_lifespan_task(run_forever) == []


@pytest.mark.asyncio
async def test_lifespan_coroutine_task_exception_is_reported():
    """An exception raised by a coroutine lifespan task reaches the loop handler."""

    async def fail():  # noqa: RUF029
        msg = "lifespan task failed"
        raise ValueError(msg)

    reported = await _run_coroutine_lifespan_task(fail)

    assert [type(context["exception"]) for context in reported] == [ValueError]


@pytest.mark.asyncio
async def test_lifespan_task_self_cancellation_is_reported():
    """A coroutine lifespan task cancelled before shutdown still reaches the loop handler."""

    async def cancel_itself():  # noqa: RUF029
        raise asyncio.CancelledError

    reported = await _run_coroutine_lifespan_task(cancel_itself)

    assert [type(context["exception"]) for context in reported] == [
        asyncio.CancelledError
    ]
