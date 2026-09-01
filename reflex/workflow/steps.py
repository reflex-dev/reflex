"""Recorded substeps: memoized side effects inside one durable handler.

A handler is the unit of retry. When it makes three external calls and fails
after the second, a bare retry repeats all three -- and the first two already
happened. ``rx.step`` fixes the granularity: it runs a callable once, records
the result durably the moment it returns, and on any later attempt of the same
handler returns the recorded result instead of running the callable again. A
crash between substeps costs the work since the last recorded one, not the
whole handler.

The recorded value is what ``rx.step`` returns on every attempt -- including
the first. Results round-trip through JSON serialization before they are
handed back, so the type a handler sees is identical whether the substep ran
or was replayed from the journal; a difference there would be a bug that only
appears during retries, which is the worst possible place.
"""

from __future__ import annotations

import asyncio
import inspect
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING, Any

from reflex_base.utils.exceptions import WorkflowRuntimeError

from reflex.workflow.serde import to_run_data

if TYPE_CHECKING:
    from collections.abc import Callable

    from reflex.workflow.store import RunStore


class SubstepJournal:
    """The recorded substeps of one claimed attempt.

    Attributes:
        recorded: Results already recorded for this step, by key.
    """

    __slots__ = (
        "_clock",
        "_counts",
        "_epoch",
        "_loop",
        "_notify",
        "_ordinal",
        "_run_id",
        "_store",
        "_sync_timeout",
        "recorded",
    )

    def __init__(
        self,
        *,
        store: RunStore,
        run_id: str,
        ordinal: int,
        epoch: int,
        recorded: dict[str, Any],
        clock: Callable[[], float],
        notify: Callable[[str], None],
        loop: asyncio.AbstractEventLoop,
        sync_timeout: float,
    ):
        """Initialize the journal for one attempt.

        Args:
            store: The durable run store.
            run_id: The run being executed.
            ordinal: The mailbox slot being executed.
            epoch: The claim fence of this attempt.
            recorded: Results recorded by earlier attempts of this step.
            clock: Epoch-seconds time source.
            notify: Receives each newly recorded key, for the observer.
            loop: The kernel's event loop, for calls from sync handlers.
            sync_timeout: Seconds a sync handler waits for the loop to record
                before giving up.
        """
        self._store = store
        self._run_id = run_id
        self._ordinal = ordinal
        self._epoch = epoch
        self.recorded = recorded
        self._counts: dict[str, int] = {}
        self._clock = clock
        self._notify = notify
        self._loop = loop
        self._sync_timeout = sync_timeout

    def allocate_key(self, name: str) -> str:
        """Assign the memoization key for the next occurrence of a name.

        A handler that loops calls the same name repeatedly, so occurrences
        after the first are numbered. Re-executing the handler replays the
        same sequence of calls and therefore allocates the same keys, which is
        what lets a retry line its calls up against the journal.

        Args:
            name: The substep name as written in the handler.

        Returns:
            The key identifying this occurrence.
        """
        count = self._counts.get(name, 0) + 1
        self._counts[name] = count
        return name if count == 1 else f"{name}#{count}"

    async def record(self, key: str, value: Any) -> Any:
        """Serialize and durably record one substep result.

        Args:
            key: The memoization key.
            value: The value the substep produced.

        Returns:
            The recorded form of the value.

        Raises:
            WorkflowRuntimeError: If the value cannot be serialized, or this
                attempt has been fenced and must stop.
        """
        try:
            payload = to_run_data({"value": value})["value"]
        except Exception as err:
            msg = (
                f"The result of step {key!r} could not be serialized: {err} "
                "A substep result must be JSON-compatible data, because it is "
                "recorded durably and replayed to later attempts."
            )
            raise WorkflowRuntimeError(msg) from err
        accepted = await self._store.record_substep(
            self._run_id, self._ordinal, self._epoch, key, payload, self._clock()
        )
        if not accepted:
            msg = (
                f"Step {key!r} could not be recorded because this attempt no "
                "longer owns the run: its lease was reclaimed by another "
                "worker. Stopping here prevents a duplicated side effect."
            )
            raise WorkflowRuntimeError(msg)
        self.recorded[key] = payload
        self._notify(key)
        return payload

    def record_from_thread(self, key: str, value: Any) -> Any:
        """Record a result from a sync handler's worker thread.

        Args:
            key: The memoization key.
            value: The value the substep produced.

        Returns:
            The recorded form of the value.
        """
        future = asyncio.run_coroutine_threadsafe(self.record(key, value), self._loop)
        try:
            # Bounded: a loop that stopped consuming -- a shutdown, a wedge --
            # must fail this thread's step, not pin the thread forever. An
            # unkillable thread makes the whole process refuse to exit.
            return future.result(timeout=self._sync_timeout)
        except TimeoutError:
            future.cancel()
            msg = (
                f"Recording step {key!r} did not complete within "
                f"{self._sync_timeout:.0f}s. The worker is shutting down or "
                "stalled; the attempt stops so another worker can take over."
            )
            raise WorkflowRuntimeError(msg) from None


_journal: ContextVar[SubstepJournal | None] = ContextVar(
    "reflex_workflow_substep_journal", default=None
)


def bind_journal(journal: SubstepJournal) -> Token[SubstepJournal | None]:
    """Install the journal for the duration of one attempt.

    Args:
        journal: The attempt's journal.

    Returns:
        The token that restores the previous journal.
    """
    return _journal.set(journal)


def unbind_journal(token: Token[SubstepJournal | None]) -> None:
    """Restore the journal that was in place before an attempt.

    Args:
        token: The token returned by ``bind_journal``.
    """
    _journal.reset(token)


def _require_journal() -> SubstepJournal:
    """Read the current attempt's journal.

    Returns:
        The journal.

    Raises:
        WorkflowRuntimeError: If called outside a durable handler.
    """
    journal = _journal.get()
    if journal is None:
        msg = (
            "rx.step() records work against the run it belongs to, and there "
            "is no durable handler running. Call it from inside a "
            "@rx.event(durable=True) handler."
        )
        raise WorkflowRuntimeError(msg)
    return journal


async def _run_step(
    journal: SubstepJournal,
    key: str,
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Any:
    """Execute one substep in an async handler.

    Args:
        journal: The attempt's journal.
        key: The memoization key.
        fn: The callable producing the result.
        args: Positional arguments for the callable.
        kwargs: Keyword arguments for the callable.

    Returns:
        The recorded result.
    """
    value = fn(*args, **kwargs)
    if inspect.isawaitable(value):
        value = await value
    return await journal.record(key, value)


def step(name: str, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    """Run a callable once per handler, however many times the handler runs.

    The first attempt executes ``fn`` and records its result durably; every
    later attempt of the same handler -- a retry, or a recovery after a crash
    -- returns the recorded result without executing ``fn`` again. That makes
    it the right wrapper for any side effect a retry must not repeat::

        @rx.event(durable=True, effect="idempotent_write", retry=rx.Retry(max_attempts=5))
        async def fulfil(self):
            charge = await rx.step("charge", charge_card, self.amount)
            label = await rx.step("label", create_shipping_label, self.order_id)
            return rx.complete(result={"charge": charge, "label": label})

    If ``create_shipping_label`` fails and the handler retries, the card is
    not charged again: the ``"charge"`` step replays its recorded result.

    In an ``async def`` handler the call returns an awaitable. In a sync
    handler it blocks and returns the value directly -- same name, same
    semantics, no ceremony.

    The result must be JSON-compatible data (models are reduced the same way
    run state is), and what you get back is that recorded form on every
    attempt, including the first, so replays are indistinguishable.

    Args:
        name: Names the substep. A name reused in a loop is numbered by
            occurrence, so each iteration is its own recorded step.
        fn: The callable to run once. May be sync or async in an async
            handler; sync in a sync handler.
        args: Positional arguments passed to the callable.
        kwargs: Keyword arguments passed to the callable.

    Returns:
        An awaitable of the recorded result in an async handler; the recorded
        result itself in a sync handler.

    Raises:
        WorkflowRuntimeError: If called outside a durable handler, or a sync
            handler passes an async callable.
    """
    journal = _require_journal()
    key = journal.allocate_key(name)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        if key in journal.recorded:
            return journal.recorded[key]
        if inspect.iscoroutinefunction(fn):
            msg = (
                f"Step {name!r} passes an async callable from a sync handler. "
                "Make the handler `async def`, or pass a sync callable."
            )
            raise WorkflowRuntimeError(msg) from None
        return journal.record_from_thread(key, fn(*args, **kwargs))
    if key in journal.recorded:
        return _replay(journal.recorded[key])
    return _run_step(journal, key, fn, args, kwargs)


async def _replay(value: Any) -> Any:  # noqa: RUF029
    """Hand back an already recorded result as an awaitable.

    An async handler awaits every ``rx.step`` call, so a replayed result must
    arrive in the same shape as an executed one.

    Args:
        value: The recorded payload.

    Returns:
        The payload.
    """
    return value


def substep_results() -> dict[str, Any]:
    """Read the substep results recorded so far for the current step.

    Returns:
        Recorded payloads by key.
    """
    return dict(_require_journal().recorded)
