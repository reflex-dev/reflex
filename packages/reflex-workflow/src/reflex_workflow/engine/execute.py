"""Running a claimed step and committing its result."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import datetime
import logging
import time
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Interval,
    String,
    case,
    func,
    insert,
    literal,
    null,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

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
    check_call,
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
            check_call(cls, transition.on_timeout)
        if cls.__workflow_steps__.get(transition.then.name) is not transition.then:
            msg = f"{transition.then!r} is not a step of {cls.__qualname__}."
            raise TypeError(msg)
        return Scheduled(
            transition.on_timeout, transition.timeout, transition.then.name
        )
    if isinstance(transition, FanOut):
        check_call(cls, transition.then)
        # No delay parks the row: next_step is set, but nothing wakes it until
        # the last child does.
        return Scheduled(transition.then, None, None, None, transition.children)
    if isinstance(transition, Every):
        check_call(cls, transition.call)
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
    check_call(cls, call)
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


def backoff_for(spec: Step[Any, Any], attempts: int) -> datetime.timedelta:
    """Return how long to put off an attempt that failed.

    Each retry waits twice as long as the one before it, up to the step's cap.
    Doubling without one passes what a timestamp can hold, and what a timedelta
    can hold before that, so a step with many retries would stop being retried
    and start failing to record that it had.

    Args:
        spec: The step being retried.
        attempts: How many attempts have failed, this one included.

    Returns:
        The delay before the next attempt.
    """
    limit = spec.max_backoff
    if spec.backoff <= NO_DELAY or spec.backoff >= limit:
        return min(spec.backoff, limit)
    # Held to what fits inside the cap rather than to a count of doublings: the
    # doubling that passes a cap near the largest timedelta would overflow on
    # its way to being capped.
    fits = limit // spec.backoff
    return spec.backoff * min(2 ** min(attempts - 1, fits.bit_length()), fits)


def after_failure(
    spec: Step[Any, Any] | None,
    current: str,
    stored: dict[str, Any] | None,
    attempts: int,
) -> tuple[dict[str, Any], str]:
    """Build the columns that record an attempt having failed.

    Args:
        spec: The step that failed, when its class still declares it.
        current: The step's name.
        stored: The arguments it was called with.
        attempts: How many attempts have failed, this one included.

    Returns:
        The scheduling columns, and the outcome to record.
    """
    if spec is not None and attempts <= spec.retries:
        return {
            "next_step": current,
            "next_args": stored,
            "wake_at": func.now() + backoff_for(spec, attempts),
            "waiting_for": None,
        }, "retry"
    return stop(), "failed"


def settle_event(cls: type[Workflow], values: dict[str, Any], took: bool) -> None:
    """Decide what becomes of an event held for a wait, as the commit finds it.

    An unconsumed event stays only while the row can still take it: it is for the
    wait this step just armed, or the row is still stepping toward one. Judged
    against the column rather than what was read, since a delivery may have
    landed while the step ran.

    Args:
        cls: The workflow class.
        values: The columns being written, which this adds ``pending_event`` to.
        took: Whether this attempt ran the held event itself.
    """
    waiting = values["waiting_for"]
    if took or (waiting is None and values["next_step"] is None):
        values["pending_event"] = null()
    elif waiting is not None:
        values["pending_event"] = case(
            (cls.pending_event["step"].astext == waiting, cls.pending_event),
            else_=null(),
        )
        # An event already held for the wait being armed makes the row due now,
        # rather than leaving it behind every run with a nearer deadline.
        values["wake_at"] = case(
            (cls.pending_event["step"].astext == waiting, func.now()),
            else_=values["wake_at"],
        )


def is_finished(values: dict[str, Any]) -> bool:
    """Report whether the columns a step committed leave the run with nothing to do.

    Args:
        values: The scheduling columns being written.

    Returns:
        Whether the run is over.
    """
    return values["next_step"] is None and values["waiting_for"] is None


async def start_children(
    session: AsyncSession, row: Workflow, children: tuple[Child, ...], fan_out: int
) -> int:
    """Start a run's children, skipping the ones that are already there.

    Args:
        session: The transaction the parent is committing in.
        row: The parent row.
        children: The runs to start.
        fan_out: The version the parent commits this fan-out at. A child counts
            toward its parent only while the parent is still at that version,
            so one that finishes after the parent moved on is not counted.

    Returns:
        How many were started by this call.
    """
    parent = {**row.as_parent(), "fan_out": fan_out}
    started = 0
    tables: set[str] = set()
    for entry in children:
        stmt = handles.insertion(entry.row, entry.first, parent)
        if (await session.execute(stmt)).first() is not None:
            started += 1
            tables.add(type(entry.row).__tablename__)
    for table in sorted(tables):
        await notify.announce(session, table)
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
        .where(
            *rows.pk_filter(cls, parent["pk"]),
            # Still joining the fan-out this child belongs to, and still owed a
            # child: a child run again after it finished, or one whose parent was
            # moved on and may have fanned out again, counts for nothing. The
            # version is left alone so every child of the fan-out still matches;
            # nothing else can touch a parked parent, and its claim bumps it.
            # A pointer without the fan-out's version predates children naming
            # it, and no longer knows which join it counts toward: it counts
            # toward none, rather than possibly toward the wrong one.
            cls.wf_version == parent.get("fan_out"),
            cls.children_left > 0,
        )
        .values(
            children_left=remaining,
            # The last one to finish is the one that makes the parent due.
            wake_at=case((remaining <= 0, func.now()), else_=cls.wake_at),
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
            run=rows.json_pk(pk),
            finished_at=func.now(),
            **attempt,
        )
    )


@dataclasses.dataclass(slots=True)
class Lease:
    """The lease a running step holds on its row, as it last wrote it.

    Attributes:
        until: When it runs out; the value is also what identifies it, since
            every claim and renewal writes a new one.
    """

    until: datetime.datetime | None


async def release(
    runtime: Runtime, cls: type[Workflow], pk: list[Any], lease: Lease
) -> None:
    """Give back the lease of a step whose commit was fenced.

    An event applied while a step runs moves the run on but leaves the step's
    lease in place, so nothing else runs the row while the step might still be
    acting. Once it is done the lease is its own to give back, and only its own:
    a worker that took the row over has written a lease of its own.

    Args:
        runtime: The running engine.
        cls: The workflow class.
        pk: The row's primary key values.
        lease: The lease the step held.
    """
    async with runtime.session_factory() as session, session.begin():
        released = (
            await session.execute(
                update(cls)
                .where(*rows.pk_filter(cls, pk), cls.claimed_until == lease.until)
                .values(claimed_until=None)
                .returning(cls.wf_version)
                .execution_options(synchronize_session=False)
            )
        ).first()
        if released is not None:
            await notify.announce(session, cls.__tablename__)
    if released is not None:
        runtime.wake.set()


async def keep_lease(
    runtime: Runtime, cls: type[Workflow], pk: list[Any], version: int, lease: Lease
) -> None:
    """Extend a claim while its step runs, so a slow step isn't claimed twice.

    Args:
        runtime: The running engine.
        cls: The workflow class.
        pk: The row's primary key values.
        version: The row version the claim is for.
        lease: The lease the step holds, updated with each renewal.
    """
    # Most steps are done before the first renewal is due, so the statement is
    # built only once one is.
    await asyncio.sleep(runtime.lease.total_seconds() / 3)
    stmt = (
        update(cls)
        .where(*rows.pk_filter(cls, pk), cls.wf_version == version)
        .values(claimed_until=func.now() + runtime.lease)
        .returning(cls.claimed_until)
        .execution_options(synchronize_session=False)
    )
    while True:
        try:
            async with runtime.session_factory() as session, session.begin():
                renewed = (await session.execute(stmt)).scalar_one_or_none()
            if renewed is not None:
                lease.until = renewed
        except Exception:
            logger.exception(
                "reflex_workflow could not extend a lease on %s", cls.__qualname__
            )
        await asyncio.sleep(runtime.lease.total_seconds() / 3)


def unjoin(cls: type[Workflow]) -> ColumnElement[Any]:
    """Build the parent pointer a child keeps once it has been counted.

    The pointer stops naming the fan-out it counted toward, while still naming
    the run it belongs to, which is all ``children()`` reads it for.

    Args:
        cls: The child's workflow class.

    Returns:
        The new value for ``parent``.
    """
    return cls.parent.op("-", return_type=JSONB)(literal("fan_out", String))


async def abandon(
    runtime: Runtime,
    cls: type[Workflow],
    pk: list[Any],
    version: int,
    spec: Step[Any, Any] | None,
    current: str,
    stored: dict[str, Any] | None,
    attempts: int,
    parent: dict[str, Any] | None,
    took_event: bool,
    began: float,
    err: Exception,
) -> str:
    """Record an attempt whose step ran but whose commit could not land.

    A step's body can finish and its commit still be refused: an argument json
    cannot hold, a value too long for its column, a child that breaks a
    constraint. That commit is rolled back, so none of the step's own changes
    are kept and the row is still at the version this attempt claimed. The
    failure is then written on its own, fenced the same way the commit would
    have been. Without it nothing counts the attempt: the row keeps its
    schedule, is claimed again once the lease runs out, and runs the step's
    body again after every lease for good.

    Args:
        runtime: The running engine.
        cls: The workflow class.
        pk: The row's primary key values.
        version: The row version the attempt claimed.
        spec: The step that was running, when its class still declares it.
        current: The step's name.
        stored: The arguments it was called with.
        attempts: How many attempts had failed before this one.
        parent: The run this one was fanned out by, when it was.
        took_event: Whether this attempt ran an event held for a wait.
        began: When the attempt started, on the monotonic clock.
        err: What stopped the commit.

    Returns:
        The outcome: retry, failed, or fenced.
    """
    attempts += 1
    error = f"{type(err).__name__}: {err}"[:2000]
    values, outcome = after_failure(spec, current, stored, attempts)
    values |= {"attempts": attempts, "last_error": error}
    settle_event(cls, values, took=took_event)
    joining = parent is not None and parent.get("fan_out") is not None
    done = is_finished(values)
    if joining and done:
        values["parent"] = unjoin(cls)
    async with runtime.session_factory() as session, session.begin():
        committed = (
            await session.execute(
                update(cls)
                .where(*rows.pk_filter(cls, pk), cls.wf_version == version)
                .values(**values, claimed_until=None, wf_version=version + 1)
                .returning(cls.wf_version)
                .execution_options(synchronize_session=False)
            )
        ).first()
        if committed is None:
            return "fenced"
        await record_attempt(
            session,
            cls,
            pk,
            {
                "step": current,
                "attempt": attempts,
                "outcome": outcome,
                "error": error,
                "took_ms": int((time.monotonic() - began) * 1000),
            },
        )
        # A run that gave up is as done as one that finished, so the parent it
        # was fanned out by hears of it either way.
        if joining and done and parent is not None:
            await finish_child(session, parent)
            await notify.announce(session, parent["table"])
    runtime.wake.set()
    return outcome


async def execute(
    runtime: Runtime,
    cls: type[Workflow],
    pk: list[Any],
    version: int,
    held: Lease | None = None,
) -> str:
    """Run a claimed row's step and commit its result if the row hasn't moved.

    Args:
        runtime: The running engine.
        cls: The workflow class.
        pk: The row's primary key values.
        version: The row version that was claimed.
        held: The lease the claim wrote, which renewals keep up to date. Given
            it, a claim moved on before its step started gives that lease back
            at once rather than leaving the row held until it runs out, and
            whoever holds this can give it back on the step's behalf.

    Returns:
        The outcome: ok, retry, failed, stale, fenced, or missing.
    """
    factory = runtime.session_factory
    until = held.until if held is not None else None
    held = held if held is not None else Lease(None)
    async with factory() as session:
        # Every column, deferred ones too: the step runs on a detached row, which
        # cannot load one it reads later.
        row = await session.get(
            cls, tuple(pk) if len(pk) > 1 else pk[0], options=[undefer("*")]
        )
        if row is None:
            return "missing"
        if row.wf_version != version:
            # Moved on before the step started, so nothing of this claim will
            # run and nothing will come back to give its lease up. Only its own:
            # a worker that took the row over has written a lease of its own,
            # which this leaves alone.
            if until is not None:
                await release(runtime, cls, pk, held)
            return "stale"
        columns = rows.user_columns(cls)
        before = rows.snapshot(row, columns)
        if until is None:
            held.until = row.claimed_until
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
    claimed = attempts = row.attempts
    spec = cls.__workflow_steps__.get(current)
    repeat: Schedule | None = None
    scheduled: Scheduled | None = None
    began = time.monotonic()
    lease = asyncio.create_task(keep_lease(runtime, cls, pk, version, held))
    try:
        scheduled = await invoke(row, current, stored)
        # Inside the try with the step itself: what a step asks for can be as
        # wrong as what it did -- an argument json cannot hold, a step of
        # another class -- and either way it is this attempt that failed.
        repeat = scheduled.repeat
        after = rows.snapshot(row, columns)
        values: dict[str, Any] = {
            key: after[key] for key in columns if after[key] != before[key]
        }
        values |= schedule(cls, scheduled)
        values |= {"attempts": 0, "last_error": None}
        recorded = None
        outcome = "ok"
        attempt = attempts + 1
    except Exception as err:
        # Nothing the step asked for stands, so nothing it asked for is done.
        repeat, scheduled = None, None
        attempts += 1
        recorded = f"{type(err).__name__}: {err}"[:2000]
        values, outcome = after_failure(spec, current, stored, attempts)
        values |= {"attempts": attempts, "last_error": recorded}
        attempt = attempts
    finally:
        lease.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await lease

    settle_event(cls, values, took=event is not None)
    parent = row.parent
    joining = parent is not None and parent.get("fan_out") is not None
    try:
        async with factory() as session:
            try:
                # A schedule the database cannot express is worked out here,
                # against the database clock, so every time the engine writes
                # comes from one.
                if callable(repeat):
                    now = (await session.execute(select(func.now()))).scalar_one()
                    try:
                        values["wake_at"] = repeat(now)
                    except Exception as err:
                        error = f"{type(err).__name__}: {err}"[:2000]
                        values |= stop() | {
                            "last_error": error,
                            "pending_event": null(),
                        }
                        outcome = "failed"
                        recorded = error
                # The children go in first so the row can record how many of them
                # it is waiting for; a fenced parent rolls all of it back together.
                if scheduled is not None and scheduled.children is not None:
                    started = await start_children(
                        session, row, scheduled.children, version + 1
                    )
                    values["children_left"] = started
                    if not started:
                        values["wake_at"] = func.now()
                done = is_finished(values)
                if joining and done:
                    # Counted once: the pointer stops naming the fan-out as this
                    # commit lands, so a child that is run again cannot release
                    # its parent a second time while its siblings are still going.
                    values["parent"] = unjoin(cls)
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
                    await release(runtime, cls, pk, held)
                    return "fenced"
                await record_attempt(
                    session,
                    cls,
                    pk,
                    {
                        "step": current,
                        "attempt": attempt,
                        "outcome": outcome,
                        "error": recorded,
                        "took_ms": int((time.monotonic() - began) * 1000),
                    },
                )
                # Finishing is what a parent counts, so it is part of the same
                # commit: a child cannot be done without its parent hearing of it.
                if joining and done and parent is not None:
                    await finish_child(session, parent)
                    await notify.announce(session, parent["table"])
                # A step that asked for the next one now leaves work another
                # worker could take; one scheduled for later waits for a timer.
                if scheduled is not None and scheduled.delay == NO_DELAY:
                    await notify.announce(session, cls.__tablename__)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    except Exception as err:
        logger.exception(
            "reflex_workflow could not commit a step of %s", cls.__qualname__
        )
        return await abandon(
            runtime,
            cls,
            pk,
            version,
            spec,
            current,
            stored,
            claimed,
            parent,
            took_event=event is not None,
            began=began,
            err=err,
        )
    runtime.wake.set()
    return outcome
