"""Scheduling runs from application code: starting them and advancing them."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from sqlalchemy import func, or_, select, text, update
from sqlalchemy import true as sqlalchemy_true
from sqlalchemy.dialects.postgresql import insert as pg_insert

from reflex_workflow.engine import execute, notify, rows
from reflex_workflow.engine.runtime import current
from reflex_workflow.model import (
    EVENT_KEY_HISTORY,
    WORKFLOW_COLUMNS,
    Call,
    StepRef,
    Workflow,
    as_call,
    check_call,
)

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement

W = TypeVar("W", bound=Workflow)


def insertion(row: Workflow, first: Call[Any], parent: dict[str, Any] | None = None):
    """Build the statement that starts one run.

    Args:
        row: A transient instance of a workflow class.
        first: The first step call.
        parent: The run fanning this one out, when it has one.

    Returns:
        An insert that does nothing if the row is already there, returning its key.
    """
    cls = type(row)
    check_call(cls, first)
    mapper = rows.mapper(cls)
    values: dict[str, Any] = {
        attr.columns[0].key: value
        for attr in mapper.column_attrs
        if attr.key not in WORKFLOW_COLUMNS
        and (value := getattr(row, attr.key)) is not None
    }
    values.update(
        next_step=first.step.name,
        next_args=first.encode(),
        wake_at=func.now(),
        attempts=0,
        last_error=None,
        claimed_until=None,
        parent=parent,
        wf_version=0,
    )
    return (
        pg_insert(cls)
        .values(values)
        .on_conflict_do_nothing()
        .returning(*mapper.primary_key)
    )


async def start(row: W, first: Call[W]) -> bool:
    """Insert a row and schedule its first step, unless it already exists.

    A row the database keyed itself is given its key here, so the caller can
    address the run it just started without a key of its own to look it up by.

    Args:
        row: A transient instance of a workflow class.
        first: The first step call.

    Returns:
        Whether a new run was started.
    """
    runtime = current()
    stmt = insertion(row, first)
    async with runtime.session_factory() as session, session.begin():
        inserted = (await session.execute(stmt)).first()
        if inserted is not None:
            await notify.announce(session, type(row).__tablename__)
    if inserted is None:
        return False
    for key, value in zip(rows.pk_keys(type(row)), inserted, strict=True):
        setattr(row, key, value)
    runtime.wake.set()
    return True


def remember(cls: type[Workflow], key: str) -> ColumnElement[Any]:
    """Add an event key to a row's recent keys, dropping the oldest.

    Args:
        cls: The workflow class.
        key: The key to remember.

    Returns:
        The new value for ``recent_event_keys``, newest first.
    """
    keys = func.jsonb_build_array(key).op("||")(
        func.coalesce(cls.recent_event_keys, func.jsonb_build_array())
    )
    # The cap is a constant, so the jsonpath holds no user input.
    return func.jsonb_path_query_array(
        keys, text(f"'$[0 to {EVENT_KEY_HISTORY - 1}]'::jsonpath")
    )


@dataclasses.dataclass(frozen=True, slots=True)
class RunHandle(Generic[W]):
    """Runs of one workflow class matching a SQL condition."""

    cls: type[W]
    where: tuple[ColumnElement[bool], ...]

    async def get(self) -> W | None:
        """Load the first matching row.

        Returns:
            The row, or None when nothing matches.
        """
        async with current().session_factory() as session:
            return (
                (await session.execute(select(self.cls).where(*self.where)))
                .scalars()
                .first()
            )

    async def all(self) -> list[W]:
        """Load every matching row.

        Returns:
            The rows, in no particular order.
        """
        async with current().session_factory() as session:
            return list(
                (await session.execute(select(self.cls).where(*self.where)))
                .scalars()
                .all()
            )

    async def run(self, call: StepRef[W]) -> int:
        """Run a step now on every matching row.

        This preempts whatever the row was scheduled to do: a step that hasn't run
        yet is replaced, one already in flight will not commit, a wait is
        abandoned along with any event held for it, and children of a fan-out it
        was joining no longer count toward it.

        A step already running keeps its lease, so the step asked for here waits
        for it rather than starting beside it, and starts as soon as it is done.
        A step that outlives its lease is the exception the engine makes
        everywhere: past it the row is claimable again, here as anywhere else.

        Args:
            call: The step call, e.g. ``Expense.decide("approve")``, or a step
                that takes no arguments.

        Returns:
            How many runs were scheduled.
        """
        runtime = current()
        cls = self.cls
        call = as_call(call)
        check_call(cls, call)
        stmt = (
            update(cls)
            .where(*self.where)
            .values(
                next_step=call.step.name,
                next_args=call.encode(),
                wake_at=func.now(),
                waiting_for=None,
                pending_event=None,
                children_left=None,
                attempts=0,
                last_error=None,
                wf_version=cls.wf_version + 1,
            )
            .returning(cls.wf_version)
            .execution_options(synchronize_session=False)
        )
        async with runtime.session_factory() as session, session.begin():
            updated = len((await session.execute(stmt)).all())
            if updated:
                await notify.announce(session, cls.__tablename__)
        if updated:
            runtime.wake.set()
        return updated

    async def deliver(
        self, call: Call[W], *, key: str | None = None, restart: bool = False
    ) -> int:
        """Deliver an event to matching runs.

        A run waiting for this step runs it now with the delivered arguments. A run
        that has not reached its wait yet keeps the event and applies it when the
        wait arms; if it ends up waiting for something else, or stops, the event is
        discarded. A repeat of a ``key`` the run has already taken changes nothing,
        so a resent reply records one decision.

        Args:
            call: The step call the event carries, e.g. ``Expense.decide("approve")``.
            key: Identifies the event; repeats of it are ignored.
            restart: Whether a run that has finished takes the event too, by
                starting again with this step: for a run that lives as long as
                its events keep coming, such as a conversation that closed when
                it went quiet.

        Returns:
            How many runs accepted the event.
        """
        runtime = current()
        cls = self.cls
        check_call(cls, call)
        fresh = (
            or_(
                cls.recent_event_keys.is_(None),
                ~cls.recent_event_keys.contains([key]),
            )
            if key is not None
            else sqlalchemy_true()
        )
        remembered = (
            {"recent_event_keys": remember(cls, key)} if key is not None else {}
        )
        # Buffering must not bump the version: the step that is about to arm the
        # wait is still running, and its commit has to land. It runs first, so a
        # run the event is applied to below is not buffered as well.
        buffered = (
            update(cls)
            .where(
                *self.where,
                cls.waiting_for.is_(None),
                cls.pending_event.is_(None),
                cls.next_step.is_not(None),
                fresh,
            )
            .values(
                pending_event={"step": call.step.name, "args": call.encode()},
                **remembered,
            )
            .returning(cls.wf_version)
            .execution_options(synchronize_session=False)
        )
        applied = (
            update(cls)
            .where(
                *self.where,
                cls.waiting_for == call.step.name,
                # A wait ends once. An event already held for this one is on its
                # way to being run, so a second is neither applied over it nor
                # buffered behind it: the wait has its answer.
                cls.pending_event.is_(None),
                fresh,
            )
            .values(
                next_step=call.step.name,
                next_args=call.encode(),
                wake_at=func.now(),
                waiting_for=None,
                pending_event=None,
                attempts=0,
                last_error=None,
                # A timeout step for this wait may still be running: the new
                # version fences its commit, and its lease stays, so the event's
                # step does not run beside it. It gives the lease back as soon
                # as it is done.
                wf_version=cls.wf_version + 1,
                **remembered,
            )
            .returning(cls.wf_version)
            .execution_options(synchronize_session=False)
        )
        async with runtime.session_factory() as session, session.begin():
            accepted = len((await session.execute(buffered)).all())
            accepted += len((await session.execute(applied)).all())
            if restart:
                # A finished run matches neither of the above: nothing is
                # scheduled and it waits for nothing.
                restarted = (
                    update(cls)
                    .where(
                        *self.where,
                        cls.next_step.is_(None),
                        cls.waiting_for.is_(None),
                        fresh,
                    )
                    .values(
                        next_step=call.step.name,
                        next_args=call.encode(),
                        wake_at=func.now(),
                        pending_event=None,
                        children_left=None,
                        attempts=0,
                        last_error=None,
                        claimed_until=None,
                        wf_version=cls.wf_version + 1,
                        **remembered,
                    )
                    .returning(cls.wf_version)
                    .execution_options(synchronize_session=False)
                )
                accepted += len((await session.execute(restarted)).all())
            if accepted:
                await notify.announce(session, cls.__tablename__)
        if accepted:
            runtime.wake.set()
        return accepted

    async def cancel(self) -> int:
        """Stop every matching run where it stands.

        A run that has not started its next step will not, one already running
        will not commit, a wait is abandoned along with any event held for it,
        and nothing is scheduled in their place. What the runs have already done
        stays; this ends them rather than undoing them.

        A cancelled run counts as finished to the run that fanned it out, as one
        that gave up does, so a parent waiting on it carries on rather than
        waiting for a child that will never report.

        Returns:
            How many runs were cancelled.
        """
        runtime = current()
        cls = self.cls
        async with runtime.session_factory() as session, session.begin():
            stopping = (
                await session.execute(
                    select(*rows.mapper(cls).primary_key, cls.parent).where(
                        *self.where,
                        or_(cls.next_step.is_not(None), cls.waiting_for.is_not(None)),
                    )
                )
            ).all()
            if not stopping:
                return 0
            cancelled = len(
                (
                    await session.execute(
                        update(cls)
                        .where(
                            *self.where,
                            or_(
                                cls.next_step.is_not(None),
                                cls.waiting_for.is_not(None),
                            ),
                        )
                        .values(
                            next_step=None,
                            next_args=None,
                            wake_at=None,
                            waiting_for=None,
                            pending_event=None,
                            children_left=None,
                            claimed_until=None,
                            # The parent stops being named, so a child cancelled
                            # here cannot also be counted when its step lands.
                            parent=execute.unjoin(cls),
                            wf_version=cls.wf_version + 1,
                        )
                        .returning(cls.wf_version)
                        .execution_options(synchronize_session=False)
                    )
                ).all()
            )
            woken = set()
            for *_pk, parent in stopping:
                if parent is None or parent.get("fan_out") is None:
                    continue
                await execute.finish_child(session, parent)
                woken.add(parent["table"])
            for table in sorted(woken):
                await notify.announce(session, table)
        if cancelled:
            runtime.wake.set()
        return cancelled
