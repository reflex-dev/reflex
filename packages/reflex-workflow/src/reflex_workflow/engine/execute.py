"""Running a claimed step and committing its result."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import datetime
import logging
import time
from typing import TYPE_CHECKING, Any

from sqlalchemy import Interval, case, func, insert, literal, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from reflex_workflow import model
from reflex_workflow.engine import handles, notify, rows
from reflex_workflow.engine.runtime import Runtime
from reflex_workflow.model import (
    REGISTRY,
    Call,
    Child,
    Every,
    FanOut,
    Schedule,
    Step,
    Wait,
    WakeIn,
    Workflow,
    as_call,
    check_owner,
)

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement

logger = logging.getLogger(__name__)

# A step that returns another step runs it straight away.
NO_DELAY = datetime.timedelta()


@dataclasses.dataclass(frozen=True, slots=True)
class Scheduled:
    """What a step's return value means for the row.

    Attributes:
        call: The step to run when the delay passes, or on timeout while waiting.
        delay: How long until that step runs; None means never on its own.
        waiting_for: The step a delivered event runs, when the row is waiting.
        repeat: The schedule the step repeats on, if it does.
        children: The runs to start, when the step fanned out to them.
    """

    call: Call[Any] | None
    delay: datetime.timedelta | None
    waiting_for: str | None = None
    repeat: Schedule | None = None
    children: tuple[Child, ...] | None = None


def resolve(cls: type[Workflow], transition: object) -> Scheduled:
    """Turn a step's return value into what the row should do next.

    Args:
        cls: The workflow class.
        transition: What the step returned.

    Returns:
        The scheduling the transition asks for.

    Raises:
        TypeError: If the return value is not a valid transition.
    """
    if transition is None:
        return Scheduled(None, None)
    if isinstance(transition, Wait):
        if transition.on_timeout is not None:
            check_owner(cls, transition.on_timeout)
        if transition.then.name not in cls.__workflow_steps__:
            msg = f"{transition.then!r} is not a step of {cls.__qualname__}."
            raise TypeError(msg)
        return Scheduled(
            transition.on_timeout, transition.timeout, transition.then.name
        )
    if isinstance(transition, FanOut):
        check_owner(cls, transition.then)
        # No delay parks the row: next_step is set, but nothing wakes it until
        # the last child does.
        return Scheduled(transition.then, None, None, None, transition.children)
    if isinstance(transition, Every):
        check_owner(cls, transition.call)
        return Scheduled(transition.call, None, None, transition.schedule)
    if isinstance(transition, WakeIn):
        call, delay = transition.call, transition.delay
    elif isinstance(transition, (Call, Step)):
        call, delay = as_call(transition), datetime.timedelta()
    else:
        msg = (
            "A step must return a step call, wake_in(...), wait_for(...), "
            f"every(...), or None; got {transition!r}."
        )
        raise TypeError(msg)
    check_owner(cls, call)
    return Scheduled(call, delay)


async def invoke(
    row: Workflow, current: str, stored: dict[str, Any] | None
) -> Scheduled:
    """Call the row's scheduled step with its stored arguments.

    Args:
        row: The detached row.
        current: Name of the step to call.
        stored: The step's arguments as stored in ``next_args``.

    Returns:
        The scheduling its return value asks for.

    Raises:
        LookupError: If the row names a step its class no longer has.
    """
    cls = type(row)
    step = cls.__workflow_steps__.get(current)
    if step is None:
        msg = f"{current!r} is not a step of {cls.__qualname__}."
        raise LookupError(msg)
    stored = stored or {}
    result = await step.fn(row, *stored.get("args", ()), **stored.get("kwargs", {}))
    return resolve(cls, result)


def repeats(cls: type[Workflow], interval: datetime.timedelta) -> ColumnElement[Any]:
    """Build the next time on a fixed schedule, counting from the last one.

    Counting from ``wake_at`` rather than from now keeps the schedule on its grid
    however long the step took. Occurrences missed while nothing ran collapse into
    one, because the count skips ahead to the first time still in the future.

    Args:
        cls: The workflow class.
        interval: How long between runs.

    Returns:
        The next time to run.
    """
    anchor = func.coalesce(cls.wake_at, func.now())
    elapsed = func.extract("epoch", func.now() - anchor) / interval.total_seconds()
    return anchor + literal(interval, Interval) * func.greatest(1, func.ceil(elapsed))


def schedule(cls: type[Workflow], scheduled: Scheduled) -> dict[str, Any]:
    """Turn scheduling into the row columns that express it.

    Args:
        cls: The workflow class.
        scheduled: What the step asked for.

    Returns:
        Values for the scheduling columns; a schedule the database cannot work out
        on its own leaves ``wake_at`` for the caller to fill in.
    """
    call, delay, repeat = scheduled.call, scheduled.delay, scheduled.repeat
    if scheduled.children is not None:
        # Filled in once the children are in, because how many were actually
        # started is what the row waits for.
        wake_at = None
    elif isinstance(repeat, datetime.timedelta):
        wake_at = repeats(cls, repeat)
    elif repeat is not None:
        wake_at = None
    else:
        wake_at = func.now() + delay if call is not None and delay is not None else None
    return {
        "next_step": call.step.name if call is not None else None,
        "next_args": call.encode() if call is not None else None,
        "wake_at": wake_at,
        "waiting_for": scheduled.waiting_for,
    }


def stop() -> dict[str, Any]:
    """Build the columns that leave a row doing nothing.

    Returns:
        Values that clear everything scheduled.
    """
    return {
        "next_step": None,
        "next_args": None,
        "wake_at": None,
        "waiting_for": None,
    }


def is_finished(values: dict[str, Any]) -> bool:
    """Report whether the columns a step committed leave the run with nothing to do.

    Args:
        values: The scheduling columns being written.

    Returns:
        Whether the run is over.
    """
    return values["next_step"] is None and values["waiting_for"] is None


async def start_children(
    session: AsyncSession, row: Workflow, children: tuple[Child, ...]
) -> int:
    """Start a run's children, skipping the ones that are already there.

    Args:
        session: The transaction the parent is committing in.
        row: The parent row.
        children: The runs to start.

    Returns:
        How many were started by this call.
    """
    parent = row.as_parent()
    started = 0
    for entry in children:
        stmt = handles.insertion(entry.row, entry.first, parent)
        started += (await session.execute(stmt)).first() is not None
    return started


async def finish_child(session: AsyncSession, parent: dict[str, Any]) -> None:
    """Count one child as done, and wake the parent when it was the last.

    The count and the wake-up are one statement, so two children finishing at
    the same moment cannot both read "one left" and leave the parent asleep.

    Args:
        session: The transaction the child is committing in.
        parent: The table and primary key the child points at.

    Raises:
        LookupError: If the parent's table is no longer a workflow.
    """
    cls = REGISTRY.get(parent["table"])
    if cls is None:
        msg = f"{parent['table']!r} is not a workflow table."
        raise LookupError(msg)
    remaining = cls.children_left - 1
    await session.execute(
        update(cls)
        .where(*rows.pk_filter(cls, parent["pk"]), cls.children_left.is_not(None))
        .values(
            children_left=remaining,
            # The last one to finish is the one that makes the parent due.
            wake_at=case((remaining <= 0, func.now()), else_=cls.wake_at),
            wf_version=cls.wf_version + 1,
        )
        .execution_options(synchronize_session=False)
    )


async def record_attempt(
    session: AsyncSession,
    cls: type[Workflow],
    pk: list[Any],
    attempt: dict[str, Any],
) -> None:
    """Write what this attempt did, in the transaction that commits it.

    An attempt and its record land together, so history never shows a step that
    did not happen and never misses one that did.

    Args:
        session: The transaction the step is committing in.
        cls: The workflow class.
        pk: The row's primary key values.
        attempt: The step, number, outcome, error and duration.
    """
    if model.ATTEMPTS is None:
        return
    await session.execute(
        insert(model.ATTEMPTS).values(
            workflow=cls.__tablename__,
            run=list(pk),
            finished_at=func.now(),
            **attempt,
        )
    )


async def keep_lease(
    runtime: Runtime, cls: type[Workflow], pk: list[Any], version: int
) -> None:
    """Extend a claim while its step runs, so a slow step isn't claimed twice.

    Args:
        runtime: The running engine.
        cls: The workflow class.
        pk: The row's primary key values.
        version: The row version the claim is for.
    """
    stmt = (
        update(cls)
        .where(*rows.pk_filter(cls, pk), cls.wf_version == version)
        .values(claimed_until=func.now() + runtime.lease)
        .execution_options(synchronize_session=False)
    )
    while True:
        await asyncio.sleep(runtime.lease.total_seconds() / 3)
        try:
            async with runtime.session_factory() as session, session.begin():
                await session.execute(stmt)
        except Exception:
            logger.exception(
                "reflex_workflow could not extend a lease on %s", cls.__qualname__
            )


async def execute(
    runtime: Runtime, cls: type[Workflow], pk: list[Any], version: int
) -> str:
    """Run a claimed row's step and commit its result if the row hasn't moved.

    Args:
        runtime: The running engine.
        cls: The workflow class.
        pk: The row's primary key values.
        version: The row version that was claimed.

    Returns:
        The outcome: ok, retry, failed, stale, fenced, or missing.
    """
    factory = runtime.session_factory
    async with factory() as session:
        row = await session.get(cls, tuple(pk) if len(pk) > 1 else pk[0])
        if row is None:
            return "missing"
        if row.wf_version != version:
            return "stale"
        session.expunge(row)

    # A buffered event for the step the row waits on takes precedence over its
    # timeout, which is what ``next_step`` holds while waiting.
    waiting_for, pending = row.waiting_for, row.pending_event
    event = (
        pending
        if waiting_for is not None
        and pending is not None
        and pending.get("step") == waiting_for
        else None
    )
    current = waiting_for if event is not None else row.next_step
    if current is None:
        return "stale"
    stored = event["args"] if event is not None else row.next_args
    attempts = row.attempts
    columns = rows.user_columns(cls)
    before = rows.snapshot(row, columns)
    spec = cls.__workflow_steps__.get(current)
    repeat: Schedule | None = None
    scheduled: Scheduled | None = None
    began = time.monotonic()
    lease = asyncio.create_task(keep_lease(runtime, cls, pk, version))
    try:
        scheduled = await invoke(row, current, stored)
    except Exception as err:
        attempts += 1
        error = f"{type(err).__name__}: {err}"[:2000]
        if spec is not None and attempts <= spec.retries:
            values: dict[str, Any] = {
                "next_step": current,
                "next_args": stored,
                "wake_at": func.now() + spec.backoff * 2 ** (attempts - 1),
                "waiting_for": None,
            }
            outcome = "retry"
        else:
            values = stop()
            outcome = "failed"
        values |= {"attempts": attempts, "last_error": error}
        recorded = error
    else:
        repeat = scheduled.repeat
        after = rows.snapshot(row, columns)
        values = {key: after[key] for key in columns if after[key] != before[key]}
        values |= schedule(cls, scheduled)
        values |= {"attempts": 0, "last_error": None}
        recorded = None
        outcome = "ok"
    finally:
        lease.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await lease

    # An unconsumed event stays only while the row can still take it: it is for
    # the wait this step just armed, or the row is still stepping toward one. The
    # column is left alone when nothing was buffered, so a delivery that landed
    # while this step ran survives.
    if event is not None:
        values["pending_event"] = None
    elif pending is not None:
        waiting = values["waiting_for"]
        wanted = (
            pending["step"] == waiting
            if waiting is not None
            else values["next_step"] is not None
        )
        if not wanted:
            values["pending_event"] = None

    parent = row.parent
    async with factory() as session:
        try:
            # A schedule the database cannot express is worked out here, against
            # the database clock, so every time the engine writes comes from one.
            if callable(repeat):
                now = (await session.execute(select(func.now()))).scalar_one()
                try:
                    values["wake_at"] = repeat(now)
                except Exception as err:
                    error = f"{type(err).__name__}: {err}"[:2000]
                    values |= stop() | {"last_error": error}
                    outcome = "failed"
            # The children go in first so the row can record how many of them it
            # is waiting for; a fenced parent rolls all of it back together.
            if scheduled is not None and scheduled.children is not None:
                started = await start_children(session, row, scheduled.children)
                values["children_left"] = started
                if not started:
                    values["wake_at"] = func.now()
            stmt = (
                update(cls)
                .where(*rows.pk_filter(cls, pk), cls.wf_version == version)
                .values(**values, claimed_until=None, wf_version=version + 1)
                .returning(cls.wf_version)
                .execution_options(synchronize_session=False)
            )
            committed = (await session.execute(stmt)).first()
            if committed is None:
                await session.rollback()
                return "fenced"
            await record_attempt(
                session,
                cls,
                pk,
                {
                    "step": current,
                    "attempt": attempts + 1 if outcome == "ok" else attempts,
                    "outcome": outcome,
                    "error": recorded,
                    "took_ms": int((time.monotonic() - began) * 1000),
                },
            )
            # Finishing is what a parent counts, so it is part of the same
            # commit: a child cannot be done without its parent hearing of it.
            if parent is not None and is_finished(values):
                await finish_child(session, parent)
                await notify.announce(session, parent["table"])
            # A step that asked for the next one now leaves work another worker
            # could take; one scheduled for later waits for a timer anyway.
            if scheduled is not None and scheduled.delay == NO_DELAY:
                await notify.announce(session, cls.__tablename__)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    runtime.wake.set()
    return outcome
