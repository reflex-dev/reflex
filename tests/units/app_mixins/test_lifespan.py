"""Unit tests for lifespan app mixin behavior."""

from __future__ import annotations

import asyncio
import contextlib

import pytest
from reflex_base.utils.exceptions import InvalidLifespanTaskTypeError

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
