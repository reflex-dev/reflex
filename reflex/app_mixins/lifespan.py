"""Mixin that allow tasks to run during the whole app lifespan."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import functools
import inspect
import time
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, TypeVar, overload

from reflex_base.utils import console
from reflex_base.utils.exceptions import InvalidLifespanTaskTypeError
from starlette.applications import Starlette

from .mixin import AppMixin

if TYPE_CHECKING:
    from typing_extensions import deprecated

_LifespanTaskT = TypeVar("_LifespanTaskT", bound="Callable | asyncio.Task")


def _get_task_name(task: asyncio.Task | Callable) -> str:
    """Get a display name for a lifespan task.

    Args:
        task: The task to get the name for.

    Returns:
        The name of the task.
    """
    if isinstance(task, asyncio.Task):
        return task.get_name()
    return task.__name__  # pyright: ignore[reportAttributeAccessIssue]


@dataclasses.dataclass
class LifespanMixin(AppMixin):
    """A Mixin that allow tasks to run during the whole app lifespan.

    Attributes:
        lifespan_tasks: Set of lifespan tasks that are planned to run (deprecated).
    """

    _lifespan_tasks: dict[asyncio.Task | Callable, None] = dataclasses.field(
        default_factory=dict, init=False, repr=False
    )
    _lifespan_tasks_started: bool = dataclasses.field(
        default=False, init=False, repr=False
    )

    if TYPE_CHECKING:
        # Static deprecation warning for IDE/type checkers.
        @property
        @deprecated("Use get_lifespan_tasks method instead.")
        def lifespan_tasks(self) -> frozenset[asyncio.Task | Callable]:
            """Get a copy of registered lifespan tasks (deprecated)."""
            ...

    else:

        @property
        def lifespan_tasks(self) -> frozenset[asyncio.Task | Callable]:
            """Get a copy of registered lifespan tasks.

            Returns:
                A frozenset of registered lifespan tasks.
            """
            # Runtime deprecation warning prints to the console when accessed.
            console.deprecate(
                feature_name="LifespanMixin.lifespan_tasks",
                reason="Use get_lifespan_tasks method instead to get a copy of registered lifespan tasks.",
                deprecation_version="0.9.0",
                removal_version="1.0",
            )
            return frozenset(self._lifespan_tasks)

    def get_lifespan_tasks(self) -> tuple[asyncio.Task | Callable, ...]:
        """Get a copy of currently registered lifespan tasks.

        Returns:
            A tuple of registered lifespan tasks.
        """
        return tuple(self._lifespan_tasks)

    @contextlib.asynccontextmanager
    async def _run_lifespan_tasks(self, app: Starlette):
        self._lifespan_tasks_started = True
        running_tasks = []
        try:
            async with contextlib.AsyncExitStack() as stack:
                for task in self._lifespan_tasks:
                    task_name = _get_task_name(task)
                    run_msg = f"Started lifespan task: {task_name} as {{type}}"
                    if isinstance(task, asyncio.Task):
                        running_tasks.append(task)
                    else:
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

    @overload
    def register_lifespan_task(
        self, task: _LifespanTaskT, **task_kwargs
    ) -> _LifespanTaskT: ...

    @overload
    def register_lifespan_task(
        self, task: None = None, **task_kwargs
    ) -> Callable[[_LifespanTaskT], _LifespanTaskT]: ...

    def register_lifespan_task(
        self,
        task: Callable | asyncio.Task | None = None,
        **task_kwargs,
    ):
        """Register a task to run during the lifespan of the app.

        Supports three call shapes:
            - `app.register_lifespan_task(fn, **kwargs)` — direct call.
            - `@app.register_lifespan_task` — bare decorator.
            - `@app.register_lifespan_task(**kwargs)` — parameterized decorator.

        Args:
            task: The task to register, or None to return a decorator.
            **task_kwargs: The kwargs of the task.

        Returns:
            The original task when called with a task, or a decorator when
            called without one.

        Raises:
            InvalidLifespanTaskTypeError: If the task is a generator function.
            RuntimeError: If lifespan tasks are already running.
        """
        if task is None:
            return functools.partial(self.register_lifespan_task, **task_kwargs)

        if self._lifespan_tasks_started:
            msg = (
                f"Cannot register lifespan task {_get_task_name(task)!r} after "
                "lifespan has started. Register all tasks before the app starts."
            )
            raise RuntimeError(msg)
        if inspect.isgeneratorfunction(task) or inspect.isasyncgenfunction(task):
            msg = f"Task {task.__name__} of type generator must be decorated with contextlib.asynccontextmanager."
            raise InvalidLifespanTaskTypeError(msg)

        task_name = _get_task_name(task)
        registered_task = task
        if task_kwargs:
            if isinstance(task, asyncio.Task):
                msg = f"Task {task_name!r} of type asyncio.Task cannot be registered with kwargs."
                raise InvalidLifespanTaskTypeError(msg)
            registered_task = functools.partial(task, **task_kwargs)
            functools.update_wrapper(registered_task, task)
        self._lifespan_tasks[registered_task] = None
        console.debug(f"Registered lifespan task: {task_name}")
        return task
