"""Claiming due rows so exactly one worker runs each step at a time."""

from __future__ import annotations

from collections.abc import Collection
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from reflex_workflow import model
from reflex_workflow.engine import rows
from reflex_workflow.engine.runtime import Runtime
from reflex_workflow.model import Limit, Workflow

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement

# How many groups one pass considers, as a multiple of the rows it wants. Groups
# are taken longest-waiting first, so one passed over this time is nearer the
# front of the next pass.
GROUPS_PER_PASS = 4


def claimable(
    cls: type[Workflow], steps: Collection[str] | None = None
) -> tuple[ColumnElement[bool], ...]:
    """Build the condition that selects rows a worker may take.

    Args:
        cls: The workflow class.
        steps: The steps this worker may run, when it serves only some lanes.

    Returns:
        The conditions: due or holding an event, runnable here, and not leased.
    """
    due_now = and_(cls.next_step.is_not(None), cls.wake_at <= func.now())
    # A row waiting for an event is due as soon as one is buffered for it, and
    # what it will run then is the step it waits on, not the one in next_step.
    event_ready = and_(
        cls.waiting_for.is_not(None),
        cls.pending_event["step"].astext == cls.waiting_for,
    )
    if steps is not None:
        due_now = and_(due_now, cls.next_step.in_(steps))
        event_ready = and_(event_ready, cls.waiting_for.in_(steps))
    return (
        or_(due_now, event_ready),
        or_(cls.claimed_until.is_(None), cls.claimed_until < func.now()),
    )


def due(cls: type[Workflow], limit: int, steps: Collection[str] | None):
    """Select the oldest due rows, locking them against other workers.

    Args:
        cls: The workflow class.
        limit: Most rows to take.
        steps: The steps this worker may run, or None for all of them.

    Returns:
        A select of primary keys.
    """
    return (
        select(*rows.mapper(cls).primary_key)
        .where(*claimable(cls, steps))
        .order_by(cls.wake_at.nullsfirst())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )


def lease(
    runtime: Runtime,
    cls: type[Workflow],
    picked: Any,
    steps: Collection[str] | None,
):
    """Build the update that leases the picked rows.

    Args:
        runtime: The running engine; its lease is how long the claim lasts.
        cls: The workflow class.
        picked: A select of the primary keys to claim.
        steps: The steps this worker may run, or None for all of them.

    Returns:
        The update, returning each claimed key and its new version.
    """
    pk_cols = rows.mapper(cls).primary_key
    # Materialized so the pick runs exactly once. Inlined as `pk IN (...)`, the
    # planner may rescan it for every candidate row, and each rescan skips the
    # rows the update has already taken and locks the next ones: a stale estimate
    # of how much is due then claims the whole table, whatever the limit says.
    chosen = picked.cte("chosen").prefix_with("MATERIALIZED")
    # The lock and the predicate are on the same row, so a row another worker
    # claimed or advanced meanwhile is re-checked against its latest version.
    return (
        update(cls)
        .where(
            *(column == chosen.c[column.key] for column in pk_cols),
            *claimable(cls, steps),
        )
        .values(
            claimed_until=func.now() + runtime.lease,
            wf_version=cls.wf_version + 1,
        )
        .returning(*pk_cols, cls.wf_version)
        .execution_options(synchronize_session=False)
    )


async def waiting_groups(
    runtime: Runtime,
    cls: type[Workflow],
    group: Any,
    most: int,
    steps: Collection[str] | None,
) -> list[Any]:
    """Return the groups with work waiting, the longest-waiting first.

    Args:
        runtime: The running engine.
        cls: The workflow class.
        group: The column that says which group a row belongs to.
        most: How many groups to return.
        steps: The steps this worker may run, or None for all of them.

    Returns:
        The group values to try this pass.
    """
    stmt = (
        select(group)
        .where(*claimable(cls, steps))
        .group_by(group)
        .order_by(func.min(cls.wake_at).nullsfirst())
        .limit(most)
    )
    async with runtime.session_factory() as session:
        return list((await session.execute(stmt)).scalars().all())


def bucket_key(cls: type[Workflow], value: Any) -> str:
    """Name the rate bucket of one group of one workflow.

    Args:
        cls: The workflow class.
        value: The group.

    Returns:
        The bucket's key.
    """
    return f"{cls.__tablename__}:{value}"


async def take_tokens(
    session: AsyncSession, cls: type[Workflow], spec: Limit, value: Any, want: int
) -> int:
    """Refill a group's bucket and take up to ``want`` tokens from it.

    The bucket fills continuously at the declared rate and holds at most one
    period's worth, so a group that has been quiet may start a burst, and one
    that has been busy waits. The refill, the read and the spend are one
    transaction, which the caller has already locked this group against.

    Args:
        session: The transaction the claim is happening in.
        cls: The workflow class.
        spec: The workflow's limit, whose rate and period size the bucket.
        value: Which group to spend for.
        want: Most tokens to take.

    Returns:
        How many tokens were taken, which is how many rows may be claimed.

    Raises:
        TypeError: If nothing has mapped a table for the buckets to live in.
    """
    bucket, rate, per = model.BUCKET, spec.rate, spec.per
    if rate is None or per is None:
        return want
    if bucket is None:
        msg = (
            f"{cls.__qualname__} declares a rate, so a rate bucket table must be "
            "mapped: class WorkflowRate(Base, RateBucket): __tablename__ = ..."
        )
        raise TypeError(msg)
    key = bucket_key(cls, value)
    a_second = rate / per.total_seconds()
    refilled = func.least(
        float(rate),
        bucket.tokens
        + func.extract("epoch", func.now() - bucket.updated_at) * a_second,
    )
    # A group first seen now starts with a full period's worth.
    stmt = (
        pg_insert(bucket)
        .values(key=key, tokens=float(rate), updated_at=func.now())
        .on_conflict_do_update(
            index_elements=[bucket.key],
            set_={"tokens": refilled, "updated_at": func.now()},
        )
        .returning(bucket.tokens)
    )
    available = int((await session.execute(stmt)).scalar_one())
    spend = max(0, min(want, available))
    if spend:
        await session.execute(
            update(bucket)
            .where(bucket.key == key)
            .values(tokens=bucket.tokens - spend)
            .execution_options(synchronize_session=False)
        )
    return spend


async def refund_tokens(
    session: AsyncSession, cls: type[Workflow], value: Any, unused: int
) -> None:
    """Give back tokens a claim took but found no rows to spend on.

    Args:
        session: The transaction the claim is happening in, which already holds
            the group's lock.
        cls: The workflow class.
        value: Which group the tokens were taken for.
        unused: How many to give back.
    """
    bucket = model.BUCKET
    if bucket is None:
        return
    await session.execute(
        update(bucket)
        .where(bucket.key == bucket_key(cls, value))
        .values(tokens=bucket.tokens + unused)
        .execution_options(synchronize_session=False)
    )


async def claim_group(
    runtime: Runtime,
    cls: type[Workflow],
    spec: Limit,
    group: Any,
    value: Any,
    limit: int,
    steps: Collection[str] | None,
) -> list[tuple[list[Any], int]]:
    """Claim one group's due rows, within what it may run and how often it may start.

    Claimers of the same group take the same advisory lock first, so neither the
    count of what is already running nor the group's tokens are read while another
    worker is committing its own claim. The lock is held for the length of this
    transaction only, and two different groups do not wait for each other.

    Args:
        runtime: The running engine.
        cls: The workflow class.
        spec: The workflow's limit.
        group: The column that says which group a row belongs to.
        value: Which group to claim for.
        limit: Most rows to claim.
        steps: The steps this worker may run, or None for all of them.

    Returns:
        (pk, version) for each claimed row.
    """
    pk_cols = rows.mapper(cls).primary_key
    gate = func.hashtext(f"{cls.__tablename__}:{value}")
    running = (
        select(func.count())
        .select_from(cls)
        .where(group == value, cls.claimed_until > func.now())
    )
    async with runtime.session_factory() as session, session.begin():
        await session.execute(select(func.pg_advisory_xact_lock(gate)))
        free = limit
        if spec.at_most is not None:
            busy = (await session.execute(running)).scalar_one()
            free = min(free, spec.at_most - busy)
        if free > 0:
            free = await take_tokens(session, cls, spec, value, free)
        if free <= 0:
            return []
        picked = (
            select(*pk_cols)
            .where(*claimable(cls, steps), group == value)
            .order_by(cls.wake_at.nullsfirst())
            .limit(free)
            .with_for_update(skip_locked=True)
        )
        claimed = (await session.execute(lease(runtime, cls, picked, steps))).all()
        # Tokens were taken before the claim knew how many rows it would find;
        # the ones it could not use go back rather than throttling later work.
        if spec.rate is not None and len(claimed) < free:
            await refund_tokens(session, cls, value, free - len(claimed))
    return [(list(pk), version) for *pk, version in claimed]


async def claim(
    runtime: Runtime,
    cls: type[Workflow],
    limit: int,
    steps: Collection[str] | None = None,
) -> list[tuple[list[Any], int]]:
    """Claim up to ``limit`` due rows of one workflow table.

    A claim is a lease: ``claimed_until`` is set, and the row can't be claimed again
    until it passes. Each claim also bumps ``wf_version``, so a worker whose lease
    was taken over can neither renew nor commit with the version it claimed. All
    times come from the database clock.

    A workflow that declares a limit is claimed a group at a time, longest-waiting
    group first, so no group runs more at once than it is allowed however many
    workers are asking, and a group at its limit does not spend the pass.

    Args:
        runtime: The running engine; its lease is how long the claim lasts.
        cls: The workflow class.
        limit: Most rows to claim.
        steps: The steps this worker may run, when it serves only some lanes.

    Returns:
        (pk, version) for each claimed row, the version being this claim's.

    Raises:
        TypeError: If the workflow's limit names a column it does not have.
    """
    spec = cls.__workflow_limit__
    if spec is None:
        async with runtime.session_factory() as session, session.begin():
            claimed = (
                await session.execute(
                    lease(runtime, cls, due(cls, limit, steps), steps)
                )
            ).all()
        return [(list(pk), version) for *pk, version in claimed]

    group = getattr(cls, spec.by, None)
    if group is None:
        msg = f"{cls.__qualname__} has no column {spec.by!r} to limit by."
        raise TypeError(msg)
    taken: list[tuple[list[Any], int]] = []
    groups = await waiting_groups(runtime, cls, group, limit * GROUPS_PER_PASS, steps)
    for value in groups:
        free = limit - len(taken)
        if free <= 0:
            break
        taken += await claim_group(runtime, cls, spec, group, value, free, steps)
    return taken
