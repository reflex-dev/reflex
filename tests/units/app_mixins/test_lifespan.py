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
