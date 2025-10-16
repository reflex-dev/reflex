"""Mixin that allow tasks to run during the whole app lifespan."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import functools
import inspect
import time
from collections.abc import Callable, Coroutine

from starlette.applications import Starlette

from reflex.utils import console
from reflex.utils.exceptions import InvalidLifespanTaskTypeError

from .mixin import AppMixin


@dataclasses.dataclass
class LifespanMixin(AppMixin):
    """A Mixin that allow tasks to run during the whole app lifespan."""

    # Lifespan tasks that are planned to run.
    lifespan_tasks: set[asyncio.Task | Callable] = dataclasses.field(
        default_factory=set
    )

    @contextlib.asynccontextmanager
    async def _run_lifespan_tasks(self, app: Starlette):
        running_tasks = []
        try:
            async with contextlib.AsyncExitStack() as stack:
                for task in self.lifespan_tasks:
                    run_msg = f"Started lifespan task: {task.__name__} as {{type}}"  # pyright: ignore [reportAttributeAccessIssue]
                    if isinstance(task, asyncio.Task):
                        running_tasks.append(task)
                    else:
                        task_name = task.__name__
                        signature = inspect.signature(task)
                        if "app" in signature.parameters:
                            task = functools.partial(task, app=app)
                        t_ = task()
                        if isinstance(t_, contextlib._AsyncGeneratorContextManager):
                            await stack.enter_async_context(t_)
                            console.debug(run_msg.format(type="asynccontextmanager"))
                        elif isinstance(t_, Coroutine):
                            task_ = asyncio.create_task(
                                t_,
                                name=f"reflex_lifespan_task|{task_name}|{time.time()}",
                            )
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
        # Disassociate sid / token pairings so they can be reconnected properly.
        try:
            event_namespace = self.event_namespace  # pyright: ignore[reportAttributeAccessIssue]
        except AttributeError:
            pass
        else:
            try:
                if event_namespace:
                    await event_namespace._token_manager.disconnect_all()
            except Exception as e:
                console.error(f"Error during lifespan cleanup: {e}")
        # Flush any pending writes from the state manager.
        try:
            state_manager = self.state_manager  # pyright: ignore[reportAttributeAccessIssue]
        except AttributeError:
            pass
        else:
            await state_manager.close()

    def register_lifespan_task(self, task: Callable | asyncio.Task, **task_kwargs):
        """Register a task to run during the lifespan of the app.

        Args:
            task: The task to register.
            **task_kwargs: The kwargs of the task.

        Raises:
            InvalidLifespanTaskTypeError: If the task is a generator function.
        """
        if inspect.isgeneratorfunction(task) or inspect.isasyncgenfunction(task):
            msg = f"Task {task.__name__} of type generator must be decorated with contextlib.asynccontextmanager."
            raise InvalidLifespanTaskTypeError(msg)

        task_name = task.__name__  # pyright: ignore [reportAttributeAccessIssue]
        if task_kwargs:
            original_task = task
            task = functools.partial(task, **task_kwargs)  # pyright: ignore [reportArgumentType]
            functools.update_wrapper(task, original_task)  # pyright: ignore [reportArgumentType]
        self.lifespan_tasks.add(task)
        console.debug(f"Registered lifespan task: {task_name}")
