"""A typed handle on one run.

``rx.workflows.start()`` returns an admission result: a disposition and, when
one exists, a run id. That is the honest answer to "what happened to my
submission", but it is not what a caller does next. Next they wait for the
run, look at its result, signal it, or cancel it -- and doing any of that from
a bare string means finding the right module-level function and passing the id
back into it every time.

A handle carries the id and the operations that belong to it, so the calling
code reads as one object rather than a string plus a namespace.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Generic, TypeVar, overload

from reflex_base.utils.exceptions import WorkflowRuntimeError
from reflex_base.workflow import DurationLike, parse_duration

from reflex.workflow.records import TERMINAL_RUN_STATUSES, RunStatus

if TYPE_CHECKING:
    from reflex_base.workflow import ChannelDelivery

    from reflex.workflow.records import RunSnapshot

DEFAULT_POLL_INTERVAL: float = 0.05

ResultT = TypeVar("ResultT")
T = TypeVar("T")


class RunHandle(Generic[ResultT]):
    """One run, and the things a caller does with it.

    Attributes:
        run_id: The run this handle refers to.
        disposition: How admission handled the submission that produced it.
    """

    __slots__ = ("disposition", "run_id")

    def __init__(self, run_id: str, disposition: str = "started"):
        """Bind a handle to a run.

        Args:
            run_id: The run's identity.
            disposition: How admission handled the submission.
        """
        self.run_id = run_id
        self.disposition = disposition

    def __repr__(self) -> str:
        """Describe the handle.

        Returns:
            A short representation naming the run.
        """
        return f"RunHandle({self.run_id!r}, {self.disposition!r})"

    @property
    def started(self) -> bool:
        """Whether this submission created the run rather than finding one.

        Returns:
            True when a new run was admitted.
        """
        return self.disposition == "started"

    async def snapshot(self) -> RunSnapshot | None:
        """Read the run's current state.

        Returns:
            The snapshot, or None if the run is unknown to this store.
        """
        from reflex.workflow.runtime import workflows

        return await workflows.get_run(self.run_id)

    async def status(self) -> RunStatus | None:
        """Read just the run's status.

        Returns:
            The status, or None if the run is unknown.
        """
        snapshot = await self.snapshot()
        return None if snapshot is None else snapshot.status

    @overload
    async def result(
        self,
        *,
        as_type: type[T],
        timeout: DurationLike = "30s",
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> T: ...

    @overload
    async def result(
        self,
        *,
        as_type: None = None,
        timeout: DurationLike = "30s",
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> ResultT: ...

    async def result(
        self,
        *,
        as_type: type[Any] | None = None,
        timeout: DurationLike = "30s",
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> Any:
        """Wait for the run to finish and return what it produced.

        Meant for scripts and tests, where waiting is the point. A durable
        handler should never call this: blocking one run's step on another
        run's completion ties up a worker slot for as long as the other run
        takes. Compose with ``rx.parallel`` instead, which is what child runs
        and joins are for.

        A result crosses the store as plain JSON data, so it comes back as
        dicts and lists whatever the handler passed to ``rx.complete``. Pass
        ``as_type`` to get the shape back::

            receipt = await handle.result(as_type=Receipt)
            receipt.total

        That is a real validation, not a cast: a result that does not fit the
        declared type raises here, naming the run, rather than becoming an
        ``AttributeError`` further along in the caller.

        Args:
            as_type: Type to validate and coerce the result into.
            timeout: How long to wait before giving up.
            poll_interval: Seconds between checks.

        Returns:
            The run's result, coerced to ``as_type`` when one was given.

        Raises:
            WorkflowRuntimeError: If the run is unknown, does not finish in
                time, finishes in any state other than completed, or produced
                a result that does not fit ``as_type``.
        """
        snapshot = await self.wait(timeout=timeout, poll_interval=poll_interval)
        if snapshot.status is not RunStatus.COMPLETED:
            detail = f": {snapshot.error}" if snapshot.error else ""
            msg = (
                f"Run {self.run_id} finished {snapshot.status.value}, not "
                f"COMPLETED{detail}"
            )
            raise WorkflowRuntimeError(msg)
        if as_type is None:
            return snapshot.result
        from pydantic import TypeAdapter, ValidationError

        try:
            return TypeAdapter(as_type).validate_python(snapshot.result)
        except ValidationError as error:
            msg = (
                f"Run {self.run_id} completed with a result that does not fit "
                f"{getattr(as_type, '__name__', as_type)}: {error}"
            )
            raise WorkflowRuntimeError(msg) from error

    async def wait(
        self,
        *,
        timeout: DurationLike = "30s",
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> RunSnapshot:
        """Wait for the run to reach a terminal state.

        Args:
            timeout: How long to wait before giving up.
            poll_interval: Seconds between checks.

        Returns:
            The final snapshot, whatever the outcome.

        Raises:
            WorkflowRuntimeError: If the run is unknown or is still running
                when the timeout expires.
        """
        deadline = asyncio.get_running_loop().time() + parse_duration(timeout)
        while True:
            snapshot = await self.snapshot()
            if snapshot is None:
                msg = f"Run {self.run_id} is not in this store."
                raise WorkflowRuntimeError(msg)
            if snapshot.status in TERMINAL_RUN_STATUSES:
                return snapshot
            if asyncio.get_running_loop().time() >= deadline:
                msg = (
                    f"Run {self.run_id} was still {snapshot.status.value} after "
                    f"{timeout}. Workers may not be running, or the run is "
                    "waiting on something that has not happened yet."
                )
                raise WorkflowRuntimeError(msg)
            await asyncio.sleep(poll_interval)

    async def signal(self, delivery: ChannelDelivery, *, key: str | None = None) -> str:
        """Deliver a payload to a channel this run is waiting on.

        Args:
            delivery: The addressed payload, e.g. ``MyFlow.approved(answer)``.
            key: Sender idempotency key; a repeated key is a no-op.

        Returns:
            What the store did with the delivery.
        """
        from reflex.workflow.runtime import workflows

        return await workflows.signal(self.run_id, delivery, key=key)

    async def cancel(self) -> bool:
        """Request cancellation of the run.

        Returns:
            True if intent was recorded on a nonterminal run.
        """
        from reflex.workflow.runtime import workflows

        return await workflows.cancel(self.run_id)
