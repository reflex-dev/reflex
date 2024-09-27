"""Mixin that allow tasks to run during the whole app lifespan."""

from __future__ import annotations

import asyncio
import contextlib
import functools
import inspect
from typing import Callable, Coroutine, Set, Union

from fastapi import FastAPI

from reflex.utils import console

from .mixin import AppMixin


class LifespanMixin(AppMixin):
    """A Mixin that allow tasks to run during the whole app lifespan."""

    # Lifespan tasks that are planned to run.
    lifespan_tasks: Set[Union[asyncio.Task, Callable]] = set()

    @contextlib.asynccontextmanager
    async def _run_lifespan_tasks(self, app: FastAPI):
        running_tasks = []
        try:
            async with contextlib.AsyncExitStack() as stack:
                for task in self.lifespan_tasks:
                    console.debug(f"Running lifespan task: {task}")
                    if isinstance(task, asyncio.Task):
                        running_tasks.append(task)
                    else:
                        signature = inspect.signature(task)
                        if "app" in signature.parameters:
                            task = functools.partial(task, app=app)
                        _t = task()
                        if isinstance(_t, contextlib._AsyncGeneratorContextManager):
                            await stack.enter_async_context(_t)
                        elif isinstance(_t, Coroutine):
                            running_tasks.append(asyncio.create_task(_t))
                yield
        finally:
            for task in running_tasks:
                task.cancel(msg="lifespan_cleanup")

    def register_lifespan_task(self, task: Callable | asyncio.Task, **task_kwargs):
        """Register a task to run during the lifespan of the app.

        Args:
            task: The task to register.
            task_kwargs: The kwargs of the task.
        """
        if task_kwargs:
            task = functools.partial(task, **task_kwargs)  # type: ignore
        self.lifespan_tasks.add(task)  # type: ignore
        console.debug(f"Registered lifespan task: {task}")
