"""Scheduling runs from application code: starting them and advancing them."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy import true as sqlalchemy_true
from sqlalchemy.dialects.postgresql import insert as pg_insert

from reflex_workflow.engine import execute, notify, rows
from reflex_workflow.engine.runtime import current
from reflex_workflow.model import (
    WORKFLOW_COLUMNS,
    Call,
    StepRef,
    Workflow,
    as_call,
    check_call,
    remember,
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
    # What the caller set, rather than what reads as None: an attribute never
    # assigned is left out so its column default applies, and one assigned None
    # is written as None, which is what the caller asked for and what adding the
    # row to a session would have stored.
    assigned = row.__dict__
    values: dict[str, Any] = {
        attr.columns[0].key: assigned[attr.key]
        for attr in mapper.column_attrs
        if attr.key not in WORKFLOW_COLUMNS and attr.key in assigned
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
            and_(
                or_(
                    cls.recent_event_keys.is_(None),
                    ~cls.recent_event_keys.contains([key]),
                ),
                # A key held in the buffer counts as taken while it is there,
                # so a resend does not queue behind itself. It is remembered
                # for good only once the run actually takes it.
                or_(
                    cls.pending_event.is_(None),
                    cls.pending_event["key"].astext.is_distinct_from(key),
                ),
            )
            if key is not None
            else sqlalchemy_true()
        )
        remembered = (
            {"recent_event_keys": remember(cls, key)} if key is not None else {}
        )
        # Carried with the buffered event rather than remembered now: an event
        # held for a wait the run never arms is discarded, and remembering its
        # key here would refuse the resend that is the caller's only way back.
        buffering = {"step": call.step.name, "args": call.encode()}
        if key is not None:
            buffering["key"] = key
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
            .values(pending_event=buffering)
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
                        # The lease is left alone, as ``run`` leaves it: a run
                        # finished here has none, and one whose step was
                        # cancelled mid-flight still holds the lease that keeps
                        # the step started here from running beside it.
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

        A step already running keeps its lease, as it does through ``run``, so a
        run started again straight afterwards waits for the cancelled step to be
        done rather than acting beside it.

        A cancelled run counts as finished to the run that fanned it out, as one
        that gave up does, so a parent waiting on it carries on rather than
        waiting for a child that will never report.

        Returns:
            How many runs were cancelled.
        """
        runtime = current()
        cls = self.cls
        pk_cols = rows.mapper(cls).primary_key
        # Locked as they are picked, so nothing finishes between being read and
        # being cancelled: a child that did would be counted by its own commit
        # and again by this one, and its parent would join early.
        #
        # Materialized, so the update writes the rows this locked rather than
        # whatever matches the predicate by the time it runs under a snapshot of
        # its own -- a run that started matching in between would be cancelled
        # without being read here, its parent never told, and that parent would
        # wait for a child that could no longer report. Joined rather than
        # listed back as keys: a backlog of more than about sixty-five thousand
        # rows is more parameters than a statement can carry.
        stopping = (
            select(*pk_cols, cls.parent.label("was"))
            .where(
                *self.where,
                or_(cls.next_step.is_not(None), cls.waiting_for.is_not(None)),
            )
            .with_for_update()
            .cte("stopping")
            .prefix_with("MATERIALIZED")
        )
        async with runtime.session_factory() as session, session.begin():
            stopped = (
                await session.execute(
                    update(cls)
                    .where(*(column == stopping.c[column.key] for column in pk_cols))
                    .values(
                        next_step=None,
                        next_args=None,
                        wake_at=None,
                        waiting_for=None,
                        pending_event=None,
                        children_left=None,
                        # The parent stops being named, so a child cancelled
                        # here cannot also be counted when its step lands.
                        parent=execute.unjoin(cls),
                        wf_version=cls.wf_version + 1,
                    )
                    # The pointer as it was before this cleared it, which is who
                    # to tell; what the row holds now no longer names anyone.
                    .returning(stopping.c.was)
                    .execution_options(synchronize_session=False)
                )
            ).all()
            woken = set()
            for (parent,) in stopped:
                if parent is None or parent.get("fan_out") is None:
                    continue
                await execute.finish_child(session, parent)
                woken.add(parent["table"])
            for table in sorted(woken):
                await notify.announce(session, table)
        if stopped:
            runtime.wake.set()
        return len(stopped)
