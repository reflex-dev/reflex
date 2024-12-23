"""Mixin that allow tasks to run during the whole app lifespan."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import functools
import inspect
from typing import Callable, Coroutine, Set, Union

from fastapi import FastAPI

from reflex.utils import console
from reflex.utils.exceptions import InvalidLifespanTaskType

from .mixin import AppMixin


@dataclasses.dataclass
class LifespanMixin(AppMixin):
    """A Mixin that allow tasks to run during the whole app lifespan."""

    # Lifespan tasks that are planned to run.
    lifespan_tasks: Set[Union[asyncio.Task, Callable]] = dataclasses.field(
        default_factory=set
    )

    @contextlib.asynccontextmanager
    async def _run_lifespan_tasks(self, app: FastAPI):
        running_tasks = []
        try:
            async with contextlib.AsyncExitStack() as stack:
                for task in self.lifespan_tasks:
                    run_msg = f"Started lifespan task: {task.__name__} as {{type}}"  # type: ignore
                    if isinstance(task, asyncio.Task):
                        running_tasks.append(task)
                    else:
                        signature = inspect.signature(task)
                        if "app" in signature.parameters:
                            task = functools.partial(task, app=app)
                        _t = task()
                        if isinstance(_t, contextlib._AsyncGeneratorContextManager):
                            await stack.enter_async_context(_t)
                            console.debug(run_msg.format(type="asynccontextmanager"))
                        elif isinstance(_t, Coroutine):
                            task_ = asyncio.create_task(_t)
                            task_.add_done_callback(lambda t: t.result())
                            running_tasks.append(task_)
                            console.debug(run_msg.format(type="coroutine"))
                        else:
                            console.debug(run_msg.format(type="function"))
                yield
        finally:
            for task in running_tasks:
                console.debug(f"Canceling lifespan task: {task}")
                task.cancel(msg="lifespan_cleanup")

    def register_lifespan_task(self, task: Callable | asyncio.Task, **task_kwargs):
        """Register a task to run during the lifespan of the app.

        Args:
            task: The task to register.
            task_kwargs: The kwargs of the task.

        Raises:
            InvalidLifespanTaskType: If the task is a generator function.
        """
        if inspect.isgeneratorfunction(task) or inspect.isasyncgenfunction(task):
            raise InvalidLifespanTaskType(
                f"Task {task.__name__} of type generator must be decorated with contextlib.asynccontextmanager."
            )

        if task_kwargs:
            original_task = task
            task = functools.partial(task, **task_kwargs)  # type: ignore
            functools.update_wrapper(task, original_task)  # type: ignore
        self.lifespan_tasks.add(task)  # type: ignore
        console.debug(f"Registered lifespan task: {task.__name__}")  # type: ignore
