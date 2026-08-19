"""Run store backed by PostgreSQL.

SQLite is a fine local tier, but it takes one writer at a time, which caps a
deployment at one worker process per database file. Postgres is where the
engine earns the comparison: many workers claim from the same mailbox
concurrently, each taking a different run because a claim locks the frontier
row with ``FOR UPDATE ... SKIP LOCKED`` rather than locking the whole store.

The semantics are the ones ``reflex.workflow.conformance`` fixes; this module
is a second implementation of them, not a second definition. Anything this
store does differently from ``SqliteRunStore`` is a dialect difference, and the
conformance suite is what proves it.
"""

from __future__ import annotations

import asyncio
import dataclasses
from typing import TYPE_CHECKING, Any, Final

from reflex_base.utils.exceptions import WorkflowRuntimeError
from reflex_base.workflow import DEFAULT_LEASE_DURATION

from reflex.workflow.records import (
    CLAIMABLE_STEP_STATUSES,
    TERMINAL_RUN_STATUSES,
    TERMINAL_STEP_STATUSES,
    HistoryEvent,
    HistoryEventType,
    RunRecord,
    RunStatus,
    StepRecord,
    StepStatus,
)
from reflex.workflow.store import Claim, StaleClaimError

try:
    import psycopg
    import psycopg_pool
    from psycopg.rows import dict_row
    from psycopg.sql import SQL, Composed, Identifier
    from psycopg.types.json import Jsonb
except ImportError as exc:  # pragma: no cover - depends on the environment
    msg = (
        "reflex.workflow.postgres needs psycopg with its pool extra. "
        "Install it with: pip install 'psycopg[binary,pool]'"
    )
    raise WorkflowRuntimeError(msg) from exc

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from psycopg import AsyncConnection
    from psycopg.rows import DictRow

    from reflex.workflow.records import RunQuery
    from reflex.workflow.store import DeliveryDisposition, StepCompletion

    Connection = AsyncConnection[DictRow]

DEFAULT_POOL_SIZE: Final = 10

_SCHEMA: Final = """
CREATE TABLE IF NOT EXISTS workflow_runs (
    run_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    definition_digest TEXT NOT NULL,
    status TEXT NOT NULL,
    state JSONB NOT NULL,
    state_version BIGINT NOT NULL,
    next_ordinal INTEGER NOT NULL,
    result JSONB,
    error JSONB,
    flow_key TEXT,
    parent_run_id TEXT,
    parent_ordinal INTEGER,
    request_key TEXT,
    labels JSONB,
    deadline DOUBLE PRECISION,
    cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_steps (
    run_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    handler_id TEXT NOT NULL,
    status TEXT NOT NULL,
    args JSONB NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    recoveries INTEGER NOT NULL DEFAULT 0,
    due_at DOUBLE PRECISION NOT NULL DEFAULT 0,
    epoch BIGINT NOT NULL DEFAULT 0,
    lease_expires_at DOUBLE PRECISION NOT NULL DEFAULT 0,
    wait_key TEXT,
    join_expected INTEGER NOT NULL DEFAULT 0,
    join_arrived INTEGER NOT NULL DEFAULT 0,
    error JSONB,
    origin TEXT NOT NULL,
    queue TEXT NOT NULL DEFAULT 'default',
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (run_id, ordinal)
);
CREATE TABLE IF NOT EXISTS workflow_history (
    run_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    type TEXT NOT NULL,
    at DOUBLE PRECISION NOT NULL,
    data JSONB NOT NULL,
    PRIMARY KEY (run_id, seq)
);
CREATE TABLE IF NOT EXISTS workflow_dedupe (
    workflow_id TEXT NOT NULL,
    request_key TEXT NOT NULL,
    run_id TEXT NOT NULL,
    PRIMARY KEY (workflow_id, request_key)
);
CREATE TABLE IF NOT EXISTS workflow_schedules (
    key TEXT PRIMARY KEY,
    at DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_substeps (
    run_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    key TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (run_id, ordinal, key)
);
CREATE TABLE IF NOT EXISTS workflow_inbox (
    run_id TEXT NOT NULL,
    wait_key TEXT NOT NULL,
    dedupe_key TEXT NOT NULL,
    seq INTEGER NOT NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL,
    created_at DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (run_id, wait_key, dedupe_key)
);
ALTER TABLE workflow_steps ADD COLUMN IF NOT EXISTS queue TEXT NOT NULL DEFAULT 'default';
CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs (status);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_flow
    ON workflow_runs (workflow_id, flow_key);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_parent
    ON workflow_runs (parent_run_id, parent_ordinal);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_claimable
    ON workflow_steps (status, due_at);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_lease
    ON workflow_steps (status, lease_expires_at);
CREATE INDEX IF NOT EXISTS idx_workflow_inbox_pending
    ON workflow_inbox (run_id, wait_key, status, seq);
"""

_TERMINAL_RUNS: Final = [status.value for status in TERMINAL_RUN_STATUSES]
_TERMINAL_STEPS: Final = [status.value for status in TERMINAL_STEP_STATUSES]
_CLAIMABLE_STEPS: Final = [status.value for status in CLAIMABLE_STEP_STATUSES]

# A slot may be claimed when it is due, or when a wait's deadline has arrived:
# claiming a blocked slot is the timeout branch. A deadline of zero means the
# wait has none, so it is never claimable on the clock alone.
_CLAIMABLE_PREDICATE: Final = (
    "((s.status = ANY(%(claimable)s) AND s.due_at <= %(now)s)"
    " OR (s.status = 'BLOCKED' AND s.due_at > 0 AND s.due_at <= %(now)s))"
)

_FRONTIER_PREDICATE: Final = (
    "s.ordinal = (SELECT MIN(x.ordinal) FROM workflow_steps x"
    " WHERE x.run_id = s.run_id AND NOT (x.status = ANY(%(terminal_steps)s)))"
)

_QUEUE_PREDICATE: Final = "(%(queues)s::text[] IS NULL OR s.queue = ANY(%(queues)s))"

_RUNNABLE_PREDICATE: Final = (
    "NOT (r.status = ANY(%(terminal_runs)s)) AND r.status <> 'NEEDS_ATTENTION'"
    " AND NOT r.cancel_requested"
    " AND (r.deadline IS NULL OR r.deadline > %(now)s)"
)


def _set_search_path(schema: str) -> Composed:
    """Build the statement pointing a connection at a schema.

    Args:
        schema: The schema name.

    Returns:
        The composed statement, with the name quoted as an identifier.
    """
    return SQL("SET search_path TO {}").format(Identifier(schema))


def _json(value: Any) -> Any:
    """Wrap a payload for a JSONB column.

    psycopg has no default adapter for dict or list, so every JSON value has to
    say what it is.

    Args:
        value: The JSON-compatible value, or None.

    Returns:
        The wrapped value, or None.
    """
    return None if value is None else Jsonb(value)


def _run_from_row(row: Mapping[str, Any]) -> RunRecord:
    """Build a run record from a database row.

    Args:
        row: The ``workflow_runs`` row.

    Returns:
        The run record.
    """
    return RunRecord(
        run_id=row["run_id"],
        workflow_id=row["workflow_id"],
        definition_digest=row["definition_digest"],
        status=RunStatus(row["status"]),
        state=row["state"],
        state_version=row["state_version"],
        next_ordinal=row["next_ordinal"],
        result=row["result"],
        error=row["error"],
        flow_key=row["flow_key"],
        parent_run_id=row["parent_run_id"],
        parent_ordinal=row["parent_ordinal"],
        request_key=row["request_key"],
        labels=row["labels"],
        deadline=row["deadline"],
        cancel_requested=row["cancel_requested"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _step_from_row(row: Mapping[str, Any]) -> StepRecord:
    """Build a step record from a database row.

    Args:
        row: The ``workflow_steps`` row.

    Returns:
        The step record.
    """
    return StepRecord(
        run_id=row["run_id"],
        ordinal=row["ordinal"],
        handler_id=row["handler_id"],
        status=StepStatus(row["status"]),
        args=row["args"],
        attempts=row["attempts"],
        recoveries=row["recoveries"],
        due_at=row["due_at"],
        epoch=row["epoch"],
        lease_expires_at=row["lease_expires_at"],
        wait_key=row["wait_key"],
        join_expected=row["join_expected"],
        join_arrived=row["join_arrived"],
        error=row["error"],
        origin=row["origin"],
        queue=row["queue"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PostgresRunStore:
    """Run store backed by PostgreSQL, safe for many concurrent workers."""

    def __init__(
        self,
        conninfo: str,
        *,
        schema: str | None = None,
        min_size: int = 1,
        max_size: int = DEFAULT_POOL_SIZE,
    ):
        """Prepare a store against a Postgres database.

        The connection pool is opened lazily on first use, so constructing a
        store never blocks app import or requires a running event loop.

        Args:
            conninfo: A libpq connection string or URL.
            schema: Postgres schema to own the tables. Defaults to whatever the
                connection's search path resolves to. Naming one keeps a
                deployment's runs in their own namespace inside a shared
                database, which is also how tests isolate from each other. It
                is quoted as an identifier, never interpolated.
            min_size: Connections kept open when idle.
            max_size: Maximum concurrent connections.

        """
        self._conninfo = conninfo
        self._schema = schema
        self._min_size = min_size
        self._max_size = max_size
        self._pool: Any = None
        self._ready = asyncio.Lock()

    async def _open(self) -> Any:
        """Open the pool and create the schema, once.

        Returns:
            The open connection pool.
        """
        if self._pool is not None:
            return self._pool
        async with self._ready:
            if self._pool is not None:
                return self._pool
            schema = self._schema

            async def configure(conn: AsyncConnection) -> None:
                """Point a pooled connection at this store's schema.

                Args:
                    conn: The connection being handed out.
                """
                if schema is not None:
                    await conn.execute(_set_search_path(schema))

            pool = psycopg_pool.AsyncConnectionPool(
                self._conninfo,
                min_size=self._min_size,
                max_size=self._max_size,
                kwargs={
                    "row_factory": dict_row,
                    "autocommit": True,
                    # Naming the schema makes this store's own backends
                    # findable, which is how drop_schema clears its leftovers.
                    "application_name": schema or "reflex_workflow",
                },
                configure=configure,
                open=False,
            )
            await pool.open(wait=True)
            async with pool.connection() as conn:
                if schema is not None:
                    await conn.execute(
                        SQL("CREATE SCHEMA IF NOT EXISTS {}").format(Identifier(schema))
                    )
                    await conn.execute(_set_search_path(schema))
                await conn.execute(_SCHEMA)
            self._pool = pool
            return pool

    @property
    def schema(self) -> str | None:
        """The schema this store's tables live in, if one was named.

        Returns:
            The schema name, or None when the connection's search path decides.
        """
        return self._schema

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    def drop_schema(self) -> None:
        """Delete this store's schema and everything in it.

        Tests use this to reclaim a throwaway namespace. It opens its own
        short-lived connection so it works after the pool's event loop is gone
        -- and because that loop can die mid-transaction, leaving a pooled
        backend idle while still holding locks, it first evicts this store's
        own connections. Otherwise the DROP waits on them forever.

        Raises:
            WorkflowRuntimeError: If the store owns no schema of its own.
        """
        if self._schema is None:
            msg = "drop_schema() needs a store constructed with schema=."
            raise WorkflowRuntimeError(msg)
        with psycopg.connect(self._conninfo, autocommit=True) as conn:
            conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
                " WHERE datname = current_database() AND application_name = %s"
                " AND pid <> pg_backend_pid()",
                (self._schema,),
            )
            conn.execute("SET lock_timeout TO '10s'")
            conn.execute(
                SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(Identifier(self._schema))
            )

    async def _lock_run(self, conn: Connection, run_id: str) -> None:
        """Serialize a run's writers for the rest of the transaction.

        History sequence numbers are per run and allocated as ``MAX + 1``, so
        two transactions appending to the same run must not interleave. Taking
        the run's row first is also the order every other write path uses,
        which is what keeps the store deadlock-free.

        Args:
            conn: The connection inside an open transaction.
            run_id: The run to lock.
        """
        await conn.execute(
            "SELECT 1 FROM workflow_runs WHERE run_id = %s FOR UPDATE", (run_id,)
        )

    async def _append_events(
        self,
        conn: Connection,
        run_id: str,
        events: Iterable[tuple[HistoryEventType, dict[str, Any]]],
        now: float,
    ) -> None:
        """Append history events inside the current transaction.

        Args:
            conn: The connection inside an open transaction.
            run_id: The owning run.
            events: The (type, data) pairs to append.
            now: Current time in epoch seconds.
        """
        rows = list(events)
        if not rows:
            return
        cursor = await conn.execute(
            "SELECT COALESCE(MAX(seq), 0) AS seq FROM workflow_history"
            " WHERE run_id = %s",
            (run_id,),
        )
        row = await cursor.fetchone()
        seq = 0 if row is None else row["seq"]
        for event_type, data in rows:
            seq += 1
            await conn.execute(
                "INSERT INTO workflow_history (run_id, seq, type, at, data)"
                " VALUES (%s, %s, %s, %s, %s)",
                (run_id, seq, event_type.value, now, _json(data)),
            )

    async def _insert_run(self, conn: Connection, run: RunRecord) -> None:
        """Insert a run row inside the current transaction.

        Args:
            conn: The connection inside an open transaction.
            run: The run record.
        """
        await conn.execute(
            "INSERT INTO workflow_runs (run_id, workflow_id, definition_digest,"
            " status, state, state_version, next_ordinal, result, error,"
            " flow_key, parent_run_id, parent_ordinal, request_key, labels,"
            " deadline, cancel_requested, created_at, updated_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,"
            " %s, %s, %s, %s)",
            (
                run.run_id,
                run.workflow_id,
                run.definition_digest,
                run.status.value,
                _json(run.state),
                run.state_version,
                run.next_ordinal,
                _json(run.result),
                _json(run.error),
                run.flow_key,
                run.parent_run_id,
                run.parent_ordinal,
                run.request_key,
                _json(run.labels),
                run.deadline,
                run.cancel_requested,
                run.created_at,
                run.updated_at,
            ),
        )

    async def _insert_step(self, conn: Connection, step: StepRecord) -> None:
        """Insert a step row inside the current transaction.

        Args:
            conn: The connection inside an open transaction.
            step: The step record.
        """
        await conn.execute(
            "INSERT INTO workflow_steps (run_id, ordinal, handler_id, status, args,"
            " attempts, recoveries, due_at, epoch, lease_expires_at, wait_key,"
            " join_expected, join_arrived, error, origin, queue, created_at,"
            " updated_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,"
            " %s, %s, %s)",
            (
                step.run_id,
                step.ordinal,
                step.handler_id,
                step.status.value,
                _json(step.args),
                step.attempts,
                step.recoveries,
                step.due_at,
                step.epoch,
                step.lease_expires_at,
                step.wait_key,
                step.join_expected,
                step.join_arrived,
                _json(step.error),
                step.origin,
                step.queue,
                step.created_at,
                step.updated_at,
            ),
        )

    async def _load_steps(self, conn: Connection, run_id: str) -> list[StepRecord]:
        """Load a run's steps in ordinal order inside the current transaction.

        Args:
            conn: The connection inside an open transaction.
            run_id: The owning run.

        Returns:
            The step records.
        """
        cursor = await conn.execute(
            "SELECT * FROM workflow_steps WHERE run_id = %s ORDER BY ordinal",
            (run_id,),
        )
        return [_step_from_row(row) for row in await cursor.fetchall()]

    async def _frontier(self, conn: Connection, run_id: str) -> StepRecord | None:
        """Load a run's lowest unresolved slot.

        Args:
            conn: The connection inside an open transaction.
            run_id: The owning run.

        Returns:
            The frontier step, or None when every slot is resolved.
        """
        cursor = await conn.execute(
            "SELECT * FROM workflow_steps WHERE run_id = %s"
            " AND NOT (status = ANY(%s)) ORDER BY ordinal LIMIT 1",
            (run_id, _TERMINAL_STEPS),
        )
        row = await cursor.fetchone()
        return None if row is None else _step_from_row(row)

    async def _check_claim(self, conn: Connection, claim: Claim) -> None:
        """Validate that a claim still owns its step and state version.

        Args:
            conn: The connection inside an open transaction.
            claim: The claim to validate.

        Raises:
            StaleClaimError: If the claim was fenced.
        """
        cursor = await conn.execute(
            "SELECT s.status AS step_status, s.epoch AS epoch,"
            " r.state_version AS state_version"
            " FROM workflow_steps s JOIN workflow_runs r ON r.run_id = s.run_id"
            " WHERE s.run_id = %s AND s.ordinal = %s",
            (claim.run.run_id, claim.step.ordinal),
        )
        row = await cursor.fetchone()
        if (
            row is None
            or row["step_status"] != StepStatus.CLAIMED.value
            or row["epoch"] != claim.step.epoch
            or row["state_version"] != claim.run.state_version
        ):
            msg = (
                f"Claim on run {claim.run.run_id} step {claim.step.ordinal} was fenced."
            )
            raise StaleClaimError(msg)

    async def admit(
        self,
        run: RunRecord,
        root_step: StepRecord,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
    ) -> tuple[bool, str]:
        """Atomically admit a run, deduplicating on the request key.

        Args:
            run: The run record to create.
            root_step: The preallocated root mailbox slot.
            events: History events to append on creation.

        Returns:
            Whether the run was created, and the authoritative run id.
        """
        pool = await self._open()
        async with pool.connection() as conn, conn.transaction():
            if run.request_key is not None:
                cursor = await conn.execute(
                    "INSERT INTO workflow_dedupe (workflow_id, request_key, run_id)"
                    " VALUES (%s, %s, %s) ON CONFLICT DO NOTHING RETURNING run_id",
                    (run.workflow_id, run.request_key, run.run_id),
                )
                if await cursor.fetchone() is None:
                    cursor = await conn.execute(
                        "SELECT run_id FROM workflow_dedupe"
                        " WHERE workflow_id = %s AND request_key = %s",
                        (run.workflow_id, run.request_key),
                    )
                    existing = await cursor.fetchone()
                    if existing is not None:
                        return False, existing["run_id"]
            await self._insert_run(conn, run)
            await self._insert_step(conn, root_step)
            await self._append_events(conn, run.run_id, events, run.created_at)
        return True, run.run_id

    async def claim_next(
        self,
        now: float,
        *,
        lease_duration: float = DEFAULT_LEASE_DURATION,
        queues: tuple[str, ...] | None = None,
    ) -> Claim | None:
        """Claim the due frontier step of some runnable run.

        The candidate row is locked with ``SKIP LOCKED``, so concurrent workers
        never contend for the same step and never queue behind each other: a
        worker takes the oldest run whose frontier nobody else is holding.

        Args:
            now: Current time in epoch seconds.
            lease_duration: Seconds of renewal silence tolerated before the
                claim is treated as orphaned.
            queues: Queues this worker serves; None serves every queue.

        Returns:
            A fenced claim, or None when nothing is claimable right now.
        """
        pool = await self._open()
        params = {
            "now": now,
            "terminal_runs": _TERMINAL_RUNS,
            "terminal_steps": _TERMINAL_STEPS,
            "claimable": _CLAIMABLE_STEPS,
            "queues": list(queues) if queues is not None else None,
        }
        async with pool.connection() as conn, conn.transaction():
            cursor = await conn.execute(
                "SELECT s.run_id AS run_id, s.ordinal AS ordinal"
                " FROM workflow_steps s JOIN workflow_runs r ON r.run_id = s.run_id"
                f" WHERE {_RUNNABLE_PREDICATE} AND {_FRONTIER_PREDICATE}"
                f" AND {_CLAIMABLE_PREDICATE} AND {_QUEUE_PREDICATE}"
                " ORDER BY r.created_at, s.run_id"
                " FOR UPDATE OF s SKIP LOCKED LIMIT 1",
                params,
            )
            candidate = await cursor.fetchone()
            if candidate is None:
                return None
            cursor = await conn.execute(
                "UPDATE workflow_steps SET status = %s, epoch = epoch + 1,"
                " lease_expires_at = %s, updated_at = %s"
                " WHERE run_id = %s AND ordinal = %s RETURNING *",
                (
                    StepStatus.CLAIMED.value,
                    now + lease_duration,
                    now,
                    candidate["run_id"],
                    candidate["ordinal"],
                ),
            )
            step_row = await cursor.fetchone()
            cursor = await conn.execute(
                "UPDATE workflow_runs SET status = %s, updated_at = %s"
                " WHERE run_id = %s RETURNING *",
                (RunStatus.RUNNING.value, now, candidate["run_id"]),
            )
            run_row = await cursor.fetchone()
            if step_row is None or run_row is None:
                return None
            return Claim(run=_run_from_row(run_row), step=_step_from_row(step_row))

    async def renew_lease(
        self,
        claim: Claim,
        now: float,
        *,
        lease_duration: float = DEFAULT_LEASE_DURATION,
    ) -> bool:
        """Extend a live claim's lease without transitioning the step.

        Args:
            claim: The claim being renewed.
            now: Current time in epoch seconds.
            lease_duration: Seconds to extend the lease from ``now``.

        Returns:
            True if the claim still owns its step; False if it was fenced.
        """
        pool = await self._open()
        async with pool.connection() as conn, conn.transaction():
            try:
                await self._check_claim(conn, claim)
            except StaleClaimError:
                return False
            await conn.execute(
                "UPDATE workflow_steps SET lease_expires_at = %s"
                " WHERE run_id = %s AND ordinal = %s",
                (now + lease_duration, claim.run.run_id, claim.step.ordinal),
            )
        return True

    async def _arm(self, conn: Connection, step: StepRecord, now: float) -> StepRecord:
        """Resolve a newly armed wait against a buffered delivery.

        Args:
            conn: The connection inside an open transaction.
            step: The slot being inserted.
            now: Current time in epoch seconds.

        Returns:
            The slot, already resolved when a matching delivery was waiting.
        """
        if step.status is not StepStatus.BLOCKED or step.wait_key is None:
            return step
        cursor = await conn.execute(
            "SELECT dedupe_key, payload FROM workflow_inbox"
            " WHERE run_id = %s AND wait_key = %s AND status = 'PENDING'"
            " ORDER BY seq LIMIT 1",
            (step.run_id, step.wait_key),
        )
        row = await cursor.fetchone()
        if row is None:
            return step
        await conn.execute(
            "UPDATE workflow_inbox SET status = 'CONSUMED'"
            " WHERE run_id = %s AND wait_key = %s AND dedupe_key = %s",
            (step.run_id, step.wait_key, row["dedupe_key"]),
        )
        return dataclasses.replace(
            step,
            status=StepStatus.READY,
            due_at=now,
            args={**step.args, "__payload__": row["payload"]},
            updated_at=now,
        )

    async def commit(
        self, claim: Claim, completion: StepCompletion, now: float
    ) -> None:
        """Atomically apply the outcome of a claimed attempt.

        Args:
            claim: The claim being committed.
            completion: The outcome to apply.
            now: Current time in epoch seconds.
        """
        pool = await self._open()
        async with pool.connection() as conn, conn.transaction():
            await self._lock_run(conn, claim.run.run_id)
            await self._check_claim(conn, claim)
            await conn.execute(
                "UPDATE workflow_steps SET status = %s, attempts = attempts + %s,"
                " due_at = %s, lease_expires_at = 0, error = %s, updated_at = %s"
                " WHERE run_id = %s AND ordinal = %s",
                (
                    completion.step_status.value,
                    1 if completion.consume_attempt else 0,
                    completion.due_at if completion.due_at is not None else 0.0,
                    _json(completion.step_error),
                    now,
                    claim.run.run_id,
                    claim.step.ordinal,
                ),
            )
            if completion.tombstones:
                await conn.execute(
                    "UPDATE workflow_steps SET status = %s, updated_at = %s"
                    " WHERE run_id = %s AND ordinal = ANY(%s)"
                    " AND NOT (status = ANY(%s))",
                    (
                        StepStatus.CANCELLED.value,
                        now,
                        claim.run.run_id,
                        list(completion.tombstones),
                        _TERMINAL_STEPS,
                    ),
                )
            for step in completion.new_steps:
                await self._insert_step(conn, await self._arm(conn, step, now))
            for child_run, child_step in completion.children:
                await self._insert_run(conn, child_run)
                await self._insert_step(conn, child_step)
            await conn.execute(
                "UPDATE workflow_runs SET status = %s,"
                " state = CASE WHEN %s THEN %s ELSE state END,"
                " state_version = state_version + %s,"
                " next_ordinal = COALESCE(%s, next_ordinal),"
                " result = COALESCE(%s, result), error = %s, updated_at = %s"
                " WHERE run_id = %s",
                (
                    completion.run_status.value,
                    completion.state is not None,
                    _json(completion.state),
                    1 if completion.state is not None else 0,
                    completion.next_ordinal,
                    _json(completion.result),
                    _json(completion.run_error),
                    now,
                    claim.run.run_id,
                ),
            )
            await self._append_events(conn, claim.run.run_id, completion.events, now)
            if completion.parent_arrival is not None:
                await self._apply_arrival(conn, *completion.parent_arrival, now)

    async def release_claim(
        self,
        claim: Claim,
        *,
        status: StepStatus,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
        now: float,
    ) -> None:
        """Return a claimed step without committing any state.

        Args:
            claim: The claim being released.
            status: The step status to record.
            events: History events to append.
            now: Current time in epoch seconds.
        """
        pool = await self._open()
        async with pool.connection() as conn, conn.transaction():
            await self._lock_run(conn, claim.run.run_id)
            try:
                await self._check_claim(conn, claim)
            except StaleClaimError:
                return
            await conn.execute(
                "UPDATE workflow_steps SET status = %s, lease_expires_at = 0,"
                " updated_at = %s WHERE run_id = %s AND ordinal = %s",
                (status.value, now, claim.run.run_id, claim.step.ordinal),
            )
            await self._append_events(conn, claim.run.run_id, events, now)

    async def append_events(
        self,
        run_id: str,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
        now: float,
    ) -> None:
        """Append evidence events outside a fenced commit.

        Args:
            run_id: The owning run.
            events: The (type, data) pairs to append.
            now: Current time in epoch seconds.
        """
        pool = await self._open()
        async with pool.connection() as conn, conn.transaction():
            await self._lock_run(conn, run_id)
            await self._append_events(conn, run_id, events, now)

    async def _next_inbox_seq(self, conn: Connection, run_id: str) -> int:
        """Allocate the next inbox sequence number for a run.

        Args:
            conn: The connection inside an open transaction.
            run_id: The owning run.

        Returns:
            The next sequence number.
        """
        cursor = await conn.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 AS seq FROM workflow_inbox"
            " WHERE run_id = %s",
            (run_id,),
        )
        row = await cursor.fetchone()
        return 1 if row is None else row["seq"]

    async def deliver(
        self,
        run_id: str,
        wait_key: str,
        dedupe_key: str,
        payload: dict[str, Any],
        now: float,
    ) -> DeliveryDisposition:
        """Deliver a payload to a run, resolving its wait or buffering it.

        Args:
            run_id: The receiving run.
            wait_key: The address the waiting slot declared.
            dedupe_key: Sender-supplied identity, making redelivery a no-op.
            payload: JSON-compatible payload to hand the resuming handler.
            now: Current time in epoch seconds.

        Returns:
            What the store did with the delivery.
        """
        pool = await self._open()
        async with pool.connection() as conn, conn.transaction():
            cursor = await conn.execute(
                "SELECT status FROM workflow_runs WHERE run_id = %s FOR UPDATE",
                (run_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return "unknown_run"
            if row["status"] in _TERMINAL_RUNS:
                return "run_terminal"
            cursor = await conn.execute(
                "SELECT 1 FROM workflow_inbox"
                " WHERE run_id = %s AND wait_key = %s AND dedupe_key = %s",
                (run_id, wait_key, dedupe_key),
            )
            if await cursor.fetchone() is not None:
                return "duplicate"
            frontier = await self._frontier(conn, run_id)
            if (
                frontier is not None
                and frontier.status is StepStatus.BLOCKED
                and 0.0 < frontier.due_at <= now
            ):
                return "expired"
            resolves = (
                frontier is not None
                and frontier.status is StepStatus.BLOCKED
                and frontier.wait_key == wait_key
            )
            await conn.execute(
                "INSERT INTO workflow_inbox (run_id, wait_key, dedupe_key, seq,"
                " payload, status, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    run_id,
                    wait_key,
                    dedupe_key,
                    await self._next_inbox_seq(conn, run_id),
                    _json(payload),
                    "CONSUMED" if resolves else "PENDING",
                    now,
                ),
            )
            if resolves and frontier is not None:
                await conn.execute(
                    "UPDATE workflow_steps SET status = %s, due_at = %s, args = %s,"
                    " updated_at = %s WHERE run_id = %s AND ordinal = %s",
                    (
                        StepStatus.READY.value,
                        now,
                        _json({**frontier.args, "__payload__": payload}),
                        now,
                        run_id,
                        frontier.ordinal,
                    ),
                )
                await self._append_events(
                    conn,
                    run_id,
                    (
                        (
                            HistoryEventType.WAIT_RESOLVED,
                            {"ordinal": frontier.ordinal, "wait_key": wait_key},
                        ),
                    ),
                    now,
                )
            else:
                await self._append_events(
                    conn,
                    run_id,
                    ((HistoryEventType.SIGNAL_BUFFERED, {"wait_key": wait_key}),),
                    now,
                )
        return "resolved" if resolves else "buffered"

    async def admit_children(
        self,
        runs: tuple[tuple[RunRecord, StepRecord], ...],
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
        now: float,
    ) -> None:
        """Create child runs, each with its root slot.

        Args:
            runs: The child run records paired with their root slots.
            events: History events to append to the parent.
            now: Current time in epoch seconds.
        """
        pool = await self._open()
        async with pool.connection() as conn, conn.transaction():
            for run, root_step in runs:
                await self._insert_run(conn, run)
                await self._insert_step(conn, root_step)
            if runs and events:
                parent = runs[0][0].parent_run_id or ""
                await self._lock_run(conn, parent)
                await self._append_events(conn, parent, events, now)

    async def _apply_arrival(
        self,
        conn: Connection,
        run_id: str,
        ordinal: int,
        payload: dict[str, Any],
        dedupe_key: str,
        now: float,
    ) -> str:
        """Count one arrival inside the caller's open transaction.

        Args:
            conn: The connection inside an open transaction.
            run_id: The waiting parent run.
            ordinal: The join slot's ordinal.
            payload: The arriving result.
            dedupe_key: Identity of the arrival.
            now: Current time in epoch seconds.

        Returns:
            What the store did with the arrival.
        """
        wait_key = f"join:{ordinal}"
        cursor = await conn.execute(
            "SELECT status FROM workflow_runs WHERE run_id = %s FOR UPDATE",
            (run_id,),
        )
        run_row = await cursor.fetchone()
        if run_row is None:
            return "unknown_run"
        if run_row["status"] in _TERMINAL_RUNS:
            return "run_terminal"
        cursor = await conn.execute(
            "SELECT 1 FROM workflow_inbox"
            " WHERE run_id = %s AND wait_key = %s AND dedupe_key = %s",
            (run_id, wait_key, dedupe_key),
        )
        if await cursor.fetchone() is not None:
            return "duplicate"
        cursor = await conn.execute(
            "SELECT * FROM workflow_steps WHERE run_id = %s AND ordinal = %s",
            (run_id, ordinal),
        )
        step_row = await cursor.fetchone()
        if step_row is None or step_row["status"] != StepStatus.BLOCKED.value:
            return "run_terminal"
        step = _step_from_row(step_row)
        await conn.execute(
            "INSERT INTO workflow_inbox (run_id, wait_key, dedupe_key, seq,"
            " payload, status, created_at)"
            " VALUES (%s, %s, %s, %s, %s, 'CONSUMED', %s)",
            (
                run_id,
                wait_key,
                dedupe_key,
                await self._next_inbox_seq(conn, run_id),
                _json(payload),
                now,
            ),
        )
        arrived = step.join_arrived + 1
        results = [*step.args.get("__results__", []), payload]
        done = arrived >= step.join_expected
        await conn.execute(
            "UPDATE workflow_steps SET status = %s, join_arrived = %s,"
            " due_at = %s, args = %s, updated_at = %s"
            " WHERE run_id = %s AND ordinal = %s AND join_arrived = %s",
            (
                StepStatus.READY.value if done else StepStatus.BLOCKED.value,
                arrived,
                now if done else step.due_at,
                _json({**step.args, "__results__": results}),
                now,
                run_id,
                ordinal,
                step.join_arrived,
            ),
        )
        await self._append_events(
            conn,
            run_id,
            (
                (
                    HistoryEventType.CHILD_RESOLVED,
                    {"ordinal": ordinal, "arrived": arrived},
                ),
            ),
            now,
        )
        return "resolved" if done else "counted"

    async def record_arrival(
        self,
        run_id: str,
        ordinal: int,
        payload: dict[str, Any],
        dedupe_key: str,
        now: float,
    ) -> DeliveryDisposition:
        """Count one arrival against a join slot.

        Args:
            run_id: The waiting parent run.
            ordinal: The join slot's ordinal.
            payload: The arriving result.
            dedupe_key: Identity of the arrival.
            now: Current time in epoch seconds.

        Returns:
            What the store did with the arrival.
        """
        pool = await self._open()
        wait_key = f"join:{ordinal}"
        async with pool.connection() as conn, conn.transaction():
            cursor = await conn.execute(
                "SELECT status FROM workflow_runs WHERE run_id = %s FOR UPDATE",
                (run_id,),
            )
            run_row = await cursor.fetchone()
            if run_row is None:
                return "unknown_run"
            if run_row["status"] in _TERMINAL_RUNS:
                return "run_terminal"
            cursor = await conn.execute(
                "SELECT 1 FROM workflow_inbox"
                " WHERE run_id = %s AND wait_key = %s AND dedupe_key = %s",
                (run_id, wait_key, dedupe_key),
            )
            if await cursor.fetchone() is not None:
                return "duplicate"
            cursor = await conn.execute(
                "SELECT * FROM workflow_steps WHERE run_id = %s AND ordinal = %s",
                (run_id, ordinal),
            )
            step_row = await cursor.fetchone()
            if step_row is None or step_row["status"] != StepStatus.BLOCKED.value:
                return "run_terminal"
            step = _step_from_row(step_row)
            await conn.execute(
                "INSERT INTO workflow_inbox (run_id, wait_key, dedupe_key, seq,"
                " payload, status, created_at)"
                " VALUES (%s, %s, %s, %s, %s, 'CONSUMED', %s)",
                (
                    run_id,
                    wait_key,
                    dedupe_key,
                    await self._next_inbox_seq(conn, run_id),
                    _json(payload),
                    now,
                ),
            )
            arrived = step.join_arrived + 1
            results = [*step.args.get("__results__", []), payload]
            done = arrived >= step.join_expected
            await conn.execute(
                "UPDATE workflow_steps SET status = %s, join_arrived = %s,"
                " due_at = %s, args = %s, updated_at = %s"
                " WHERE run_id = %s AND ordinal = %s AND join_arrived = %s",
                (
                    StepStatus.READY.value if done else StepStatus.BLOCKED.value,
                    arrived,
                    now if done else step.due_at,
                    _json({**step.args, "__results__": results}),
                    now,
                    run_id,
                    ordinal,
                    step.join_arrived,
                ),
            )
            await self._append_events(
                conn,
                run_id,
                (
                    (
                        HistoryEventType.CHILD_RESOLVED,
                        {"ordinal": ordinal, "arrived": arrived},
                    ),
                ),
                now,
            )
        return "resolved" if done else "counted"

    async def count_active(self, workflow_id: str, flow_key: str) -> int:
        """Count runs of a root still in flight under a flow-control key.

        Args:
            workflow_id: The workflow identity.
            flow_key: The computed grouping key.

        Returns:
            How many runs are active.
        """
        pool = await self._open()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) AS n FROM workflow_runs"
                " WHERE workflow_id = %s AND flow_key = %s"
                " AND NOT (status = ANY(%s))",
                (workflow_id, flow_key, _TERMINAL_RUNS),
            )
            row = await cursor.fetchone()
            return 0 if row is None else row["n"]

    async def first_active(self, workflow_id: str, flow_key: str) -> RunRecord | None:
        """Find the oldest active run under a flow-control key.

        Args:
            workflow_id: The workflow identity.
            flow_key: The computed grouping key.

        Returns:
            The run record, or None when nothing is active.
        """
        pool = await self._open()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM workflow_runs"
                " WHERE workflow_id = %s AND flow_key = %s"
                " AND NOT (status = ANY(%s))"
                " ORDER BY created_at, run_id LIMIT 1",
                (workflow_id, flow_key, _TERMINAL_RUNS),
            )
            row = await cursor.fetchone()
            return None if row is None else _run_from_row(row)

    async def count_started_since(
        self, workflow_id: str, flow_key: str, since: float
    ) -> int:
        """Count runs of a root admitted under a key since a point in time.

        Args:
            workflow_id: The workflow identity.
            flow_key: The computed grouping key.
            since: Exclusive lower bound in epoch seconds.

        Returns:
            How many runs were admitted in the window.
        """
        pool = await self._open()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) AS n FROM workflow_runs"
                " WHERE workflow_id = %s AND flow_key = %s AND created_at > %s",
                (workflow_id, flow_key, since),
            )
            row = await cursor.fetchone()
            return 0 if row is None else row["n"]

    async def nth_recent_start(
        self, workflow_id: str, flow_key: str, n: int
    ) -> float | None:
        """Find the nth most recent scheduled start under a flow key.

        Args:
            workflow_id: The workflow identity.
            flow_key: The computed grouping key.
            n: How far back to look, counting from the most recent as 1.

        Returns:
            The scheduled start, or None when fewer than n runs exist.
        """
        pool = await self._open()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT GREATEST(s.due_at, r.created_at) AS start FROM workflow_runs r"
                " JOIN workflow_steps s ON s.run_id = r.run_id AND s.ordinal = 0"
                " WHERE r.workflow_id = %s AND r.flow_key = %s"
                " ORDER BY start DESC LIMIT 1 OFFSET %s",
                (workflow_id, flow_key, n - 1),
            )
            row = await cursor.fetchone()
            return None if row is None else row["start"]

    async def defer_root(self, run_id: str, due_at: float, now: float) -> bool:
        """Push a not-yet-started run's root slot later, for debouncing.

        Args:
            run_id: The pending run.
            due_at: The new earliest start time.
            now: Current time in epoch seconds.

        Returns:
            True when the root had not started and was deferred.
        """
        pool = await self._open()
        async with pool.connection() as conn, conn.transaction():
            cursor = await conn.execute(
                "UPDATE workflow_steps SET due_at = %s, updated_at = %s"
                " WHERE run_id = %s AND ordinal = 0 AND status = %s",
                (due_at, now, run_id, StepStatus.READY.value),
            )
            return cursor.rowcount > 0

    async def request_cancel(self, run_id: str, now: float) -> bool:
        """Record cancellation intent on a run.

        Args:
            run_id: The run to cancel.
            now: Current time in epoch seconds.

        Returns:
            True if intent was recorded on a nonterminal run.
        """
        pool = await self._open()
        async with pool.connection() as conn, conn.transaction():
            cursor = await conn.execute(
                "UPDATE workflow_runs SET cancel_requested = TRUE, status = %s,"
                " updated_at = %s WHERE run_id = %s AND NOT (status = ANY(%s))",
                (RunStatus.CANCELLING.value, now, run_id, _TERMINAL_RUNS),
            )
            if cursor.rowcount == 0:
                return False
            await self._append_events(
                conn, run_id, ((HistoryEventType.RUN_CANCEL_REQUESTED, {}),), now
            )
        return True

    async def control_pending(self, now: float) -> tuple[RunRecord, ...]:
        """List drained runs awaiting a control transition.

        Args:
            now: Current time in epoch seconds.

        Returns:
            The runs awaiting finalization.
        """
        pool = await self._open()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM workflow_runs r WHERE NOT (r.status = ANY(%s))"
                " AND (r.cancel_requested OR (r.deadline IS NOT NULL"
                " AND r.deadline <= %s))"
                " AND NOT EXISTS (SELECT 1 FROM workflow_steps s"
                " WHERE s.run_id = r.run_id AND s.status = %s)",
                (_TERMINAL_RUNS, now, StepStatus.CLAIMED.value),
            )
            return tuple(_run_from_row(row) for row in await cursor.fetchall())

    async def finalize_run(
        self,
        run_id: str,
        *,
        status: RunStatus,
        error: dict[str, Any] | None,
        event: HistoryEventType,
        now: float,
        result: Any = None,
        parent_arrival: tuple[str, int, dict[str, Any], str] | None = None,
    ) -> bool:
        """Terminate a drained run and tombstone its unresolved slots.

        Args:
            run_id: The run to finalize.
            status: The terminal status to record.
            error: Error payload recorded on the run.
            event: The terminal history event type.
            now: Current time in epoch seconds.
            result: Result to record, for an operator forcing completion.
            parent_arrival: When this run is a child, the arrival to deliver
                to its parent's join, applied in this same transaction.

        Returns:
            True if the run was finalized.
        """
        pool = await self._open()
        async with pool.connection() as conn, conn.transaction():
            cursor = await conn.execute(
                "SELECT status FROM workflow_runs WHERE run_id = %s FOR UPDATE",
                (run_id,),
            )
            row = await cursor.fetchone()
            if row is None or row["status"] in _TERMINAL_RUNS:
                return False
            cursor = await conn.execute(
                "SELECT 1 FROM workflow_steps WHERE run_id = %s AND status = %s",
                (run_id, StepStatus.CLAIMED.value),
            )
            if await cursor.fetchone() is not None:
                return False
            cursor = await conn.execute(
                "SELECT ordinal FROM workflow_steps WHERE run_id = %s"
                " AND NOT (status = ANY(%s)) ORDER BY ordinal",
                (run_id, _TERMINAL_STEPS),
            )
            open_rows = await cursor.fetchall()
            await conn.execute(
                "UPDATE workflow_steps SET status = %s, updated_at = %s"
                " WHERE run_id = %s AND NOT (status = ANY(%s))",
                (StepStatus.CANCELLED.value, now, run_id, _TERMINAL_STEPS),
            )
            await conn.execute(
                "UPDATE workflow_runs SET status = %s, error = %s,"
                " result = COALESCE(%s, result), updated_at = %s"
                " WHERE run_id = %s",
                (status.value, _json(error), _json(result), now, run_id),
            )
            events: list[tuple[HistoryEventType, dict[str, Any]]] = [
                (HistoryEventType.STEP_TOMBSTONED, {"ordinal": open_row["ordinal"]})
                for open_row in open_rows
            ]
            events.append((event, {} if error is None else dict(error)))
            await self._append_events(conn, run_id, events, now)
            if parent_arrival is not None:
                await self._apply_arrival(conn, *parent_arrival, now)
        return True

    async def resume_run(self, run_id: str, now: float) -> bool:
        """Re-open a suspended run so its frontier step runs again.

        Args:
            run_id: The run to resume.
            now: Current time in epoch seconds.

        Returns:
            True if a suspended run was re-opened.
        """
        pool = await self._open()
        async with pool.connection() as conn, conn.transaction():
            cursor = await conn.execute(
                "UPDATE workflow_runs SET status = %s, error = NULL, updated_at = %s"
                " WHERE run_id = %s AND status = %s",
                (RunStatus.PENDING.value, now, run_id, RunStatus.NEEDS_ATTENTION.value),
            )
            if cursor.rowcount == 0:
                return False
            await conn.execute(
                "UPDATE workflow_steps SET status = %s, attempts = 0, due_at = %s,"
                " lease_expires_at = 0, error = NULL, updated_at = %s"
                " WHERE run_id = %s AND status = %s",
                (
                    StepStatus.READY.value,
                    now,
                    now,
                    run_id,
                    StepStatus.NEEDS_ATTENTION.value,
                ),
            )
            await self._append_events(
                conn, run_id, ((HistoryEventType.RUN_RESUMED, {}),), now
            )
        return True

    async def retry_run(self, run_id: str, now: float) -> bool:
        """Re-open a failed run at the step that failed.

        Args:
            run_id: The run to retry.
            now: Current time in epoch seconds.

        Returns:
            True if a failed run was re-opened.
        """
        pool = await self._open()
        async with pool.connection() as conn, conn.transaction():
            await self._lock_run(conn, run_id)
            cursor = await conn.execute(
                "SELECT ordinal FROM workflow_steps WHERE run_id = %s"
                " AND status = ANY(%s) ORDER BY ordinal LIMIT 1",
                (run_id, [StepStatus.FAILED.value, StepStatus.TIMED_OUT.value]),
            )
            row = await cursor.fetchone()
            cursor = await conn.execute(
                "UPDATE workflow_runs SET status = %s, error = NULL, updated_at = %s"
                " WHERE run_id = %s AND status = %s",
                (RunStatus.PENDING.value, now, run_id, RunStatus.FAILED.value),
            )
            if row is None or cursor.rowcount == 0:
                return False
            await conn.execute(
                "UPDATE workflow_steps SET status = %s, attempts = 0, due_at = %s,"
                " lease_expires_at = 0, error = NULL, updated_at = %s"
                " WHERE run_id = %s AND ordinal = %s",
                (StepStatus.READY.value, now, now, run_id, row["ordinal"]),
            )
            await self._append_events(
                conn,
                run_id,
                ((HistoryEventType.RUN_RESUMED, {"origin": "retry"}),),
                now,
            )
        return True

    async def skip_step(self, run_id: str, now: float) -> bool:
        """Give up on a stuck step and let the run carry on past it.

        Args:
            run_id: The run to unstick.
            now: Current time in epoch seconds.

        Returns:
            True if a blocking step was skipped.
        """
        pool = await self._open()
        async with pool.connection() as conn, conn.transaction():
            await self._lock_run(conn, run_id)
            cursor = await conn.execute(
                "SELECT s.ordinal AS ordinal FROM workflow_steps s"
                " JOIN workflow_runs r ON r.run_id = s.run_id"
                " WHERE s.run_id = %s AND s.status = ANY(%s)"
                " AND r.status = ANY(%s) ORDER BY s.ordinal LIMIT 1",
                (
                    run_id,
                    [
                        StepStatus.FAILED.value,
                        StepStatus.TIMED_OUT.value,
                        StepStatus.NEEDS_ATTENTION.value,
                    ],
                    [RunStatus.NEEDS_ATTENTION.value, RunStatus.FAILED.value],
                ),
            )
            row = await cursor.fetchone()
            if row is None:
                return False
            await conn.execute(
                "UPDATE workflow_steps SET status = %s, lease_expires_at = 0,"
                " updated_at = %s WHERE run_id = %s AND ordinal = %s",
                (StepStatus.SKIPPED.value, now, run_id, row["ordinal"]),
            )
            cursor = await conn.execute(
                "SELECT 1 FROM workflow_steps WHERE run_id = %s"
                " AND NOT (status = ANY(%s)) LIMIT 1",
                (run_id, _TERMINAL_STEPS),
            )
            open_left = await cursor.fetchone() is not None
            await conn.execute(
                "UPDATE workflow_runs SET status = %s, error = NULL, updated_at = %s"
                " WHERE run_id = %s",
                (
                    RunStatus.PENDING.value if open_left else RunStatus.COMPLETED.value,
                    now,
                    run_id,
                ),
            )
            events = [(HistoryEventType.STEP_SKIPPED, {"ordinal": row["ordinal"]})]
            if not open_left:
                events.append((HistoryEventType.RUN_COMPLETED, {}))
            await self._append_events(conn, run_id, tuple(events), now)
        return True

    async def recover_orphans(
        self, now: float, max_recoveries: int
    ) -> tuple[int, tuple[str, ...]]:
        """Recover claims whose lease has expired.

        Args:
            now: Current time in epoch seconds.
            max_recoveries: Recovery budget per logical step.

        Returns:
            How many steps were transitioned, and the runs failed outright.
        """
        pool = await self._open()
        exhausted = {"reason": "recovery_budget_exhausted"}
        async with pool.connection() as conn, conn.transaction():
            cursor = await conn.execute(
                "SELECT s.* FROM workflow_steps s"
                " JOIN workflow_runs r ON r.run_id = s.run_id"
                " WHERE s.status = %s AND s.lease_expires_at <= %s"
                " AND NOT (r.status = ANY(%s))"
                " ORDER BY s.run_id FOR UPDATE OF s SKIP LOCKED",
                (StepStatus.CLAIMED.value, now, _TERMINAL_RUNS),
            )
            rows = await cursor.fetchall()
            recovered = 0
            failed: list[str] = []
            for row in rows:
                step = _step_from_row(row)
                recovered += 1
                if step.recoveries + 1 > max_recoveries:
                    await conn.execute(
                        "UPDATE workflow_steps SET status = %s, recoveries = %s,"
                        " lease_expires_at = 0, error = %s, updated_at = %s"
                        " WHERE run_id = %s AND ordinal = %s",
                        (
                            StepStatus.FAILED.value,
                            step.recoveries + 1,
                            _json(exhausted),
                            now,
                            step.run_id,
                            step.ordinal,
                        ),
                    )
                    await conn.execute(
                        "UPDATE workflow_runs SET status = %s, error = %s,"
                        " updated_at = %s WHERE run_id = %s",
                        (
                            RunStatus.FAILED.value,
                            _json(exhausted),
                            now,
                            step.run_id,
                        ),
                    )
                    failed.append(step.run_id)
                    cursor = await conn.execute(
                        "SELECT parent_run_id, parent_ordinal FROM workflow_runs"
                        " WHERE run_id = %s",
                        (step.run_id,),
                    )
                    parent = await cursor.fetchone()
                    if parent is not None and parent["parent_run_id"] is not None:
                        await self._apply_arrival(
                            conn,
                            parent["parent_run_id"],
                            parent["parent_ordinal"],
                            {
                                "run_id": step.run_id,
                                "status": RunStatus.FAILED.value,
                                "result": None,
                                "error": dict(exhausted),
                            },
                            step.run_id,
                            now,
                        )
                    await self._append_events(
                        conn,
                        step.run_id,
                        ((HistoryEventType.RUN_FAILED, dict(exhausted)),),
                        now,
                    )
                else:
                    await conn.execute(
                        "UPDATE workflow_steps SET status = %s, recoveries = %s,"
                        " due_at = %s, lease_expires_at = 0, updated_at = %s"
                        " WHERE run_id = %s AND ordinal = %s",
                        (
                            StepStatus.RECOVERY_WAIT.value,
                            step.recoveries + 1,
                            now,
                            now,
                            step.run_id,
                            step.ordinal,
                        ),
                    )
                    await self._append_events(
                        conn,
                        step.run_id,
                        ((HistoryEventType.STEP_RECOVERED, {"ordinal": step.ordinal}),),
                        now,
                    )
        return recovered, tuple(failed)

    async def list_runs(self, query: RunQuery) -> tuple[RunRecord, ...]:
        """List runs matching a query, newest first.

        Args:
            query: The filters and pagination cursor to apply.

        Returns:
            The matching run records.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if query.workflow_id is not None:
            clauses.append("workflow_id = %s")
            params.append(query.workflow_id)
        if query.statuses:
            clauses.append("status = ANY(%s)")
            params.append([status.value for status in query.statuses])
        if query.created_before is not None:
            clauses.append("(created_at, run_id) < (%s, %s)")
            params.extend(query.created_before)
        if query.labels:
            # Containment matches the whole filter at once, and takes user keys
            # as data rather than splicing them into a path expression.
            clauses.append("labels @> %s")
            params.append(_json(dict(query.labels)))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        pool = await self._open()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                f"SELECT * FROM workflow_runs{where}"
                " ORDER BY created_at DESC, run_id DESC LIMIT %s",
                (*params, query.limit),
            )
            return tuple(_run_from_row(row) for row in await cursor.fetchall())

    async def list_children(
        self, parent_run_id: str, parent_ordinal: int
    ) -> tuple[RunRecord, ...]:
        """List the child runs admitted for one join slot.

        Args:
            parent_run_id: The run that fanned out.
            parent_ordinal: The join slot the children report to.

        Returns:
            The child run records, oldest first.
        """
        pool = await self._open()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM workflow_runs WHERE parent_run_id = %s"
                " AND parent_ordinal = %s ORDER BY created_at, run_id",
                (parent_run_id, parent_ordinal),
            )
            return tuple(_run_from_row(row) for row in await cursor.fetchall())

    async def find_by_request_key(
        self, workflow_id: str, request_key: str
    ) -> str | None:
        """Find the run a request key already admitted, if any.

        Args:
            workflow_id: The workflow identity.
            request_key: The idempotent admission key.

        Returns:
            The existing run id, or None when the key is unused.
        """
        pool = await self._open()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT run_id FROM workflow_dedupe"
                " WHERE workflow_id = %s AND request_key = %s",
                (workflow_id, request_key),
            )
            row = await cursor.fetchone()
            return None if row is None else row["run_id"]

    async def get_run(self, run_id: str) -> RunRecord | None:
        """Load one run record.

        Args:
            run_id: The run identity.

        Returns:
            The record, or None if unknown.
        """
        pool = await self._open()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM workflow_runs WHERE run_id = %s", (run_id,)
            )
            row = await cursor.fetchone()
            return None if row is None else _run_from_row(row)

    async def get_steps(self, run_id: str) -> tuple[StepRecord, ...]:
        """Load a run's mailbox slots in ordinal order.

        Args:
            run_id: The run identity.

        Returns:
            The step records.
        """
        pool = await self._open()
        async with pool.connection() as conn:
            return tuple(await self._load_steps(conn, run_id))

    async def record_substep(
        self, run_id: str, ordinal: int, epoch: int, key: str, payload: Any, now: float
    ) -> bool:
        """Durably record one substep result inside a claimed attempt.

        Args:
            run_id: The owning run.
            ordinal: The mailbox slot being executed.
            epoch: The claim fence of the writing attempt.
            key: The substep's memoization key, unique within the step.
            payload: JSON-compatible result to record.
            now: Current time in epoch seconds.

        Returns:
            True when recorded (or already recorded); False when the writer
            was fenced and must stop.
        """
        pool = await self._open()
        async with pool.connection() as conn, conn.transaction():
            await self._lock_run(conn, run_id)
            cursor = await conn.execute(
                "SELECT status, epoch FROM workflow_steps"
                " WHERE run_id = %s AND ordinal = %s",
                (run_id, ordinal),
            )
            row = await cursor.fetchone()
            if (
                row is None
                or row["status"] != StepStatus.CLAIMED.value
                or row["epoch"] != epoch
            ):
                return False
            cursor = await conn.execute(
                "INSERT INTO workflow_substeps"
                " (run_id, ordinal, key, payload, created_at)"
                " VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (run_id, ordinal, key, _json(payload), now),
            )
            if cursor.rowcount:
                await self._append_events(
                    conn,
                    run_id,
                    (
                        (
                            HistoryEventType.SUBSTEP_RECORDED,
                            {"ordinal": ordinal, "key": key},
                        ),
                    ),
                    now,
                )
        return True

    async def get_substeps(self, run_id: str, ordinal: int) -> dict[str, Any]:
        """Load the recorded substep results of one step.

        Args:
            run_id: The owning run.
            ordinal: The mailbox slot.

        Returns:
            Recorded payloads by key, in recording order.
        """
        pool = await self._open()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT key, payload FROM workflow_substeps"
                " WHERE run_id = %s AND ordinal = %s ORDER BY created_at, key",
                (run_id, ordinal),
            )
            return {row["key"]: row["payload"] for row in await cursor.fetchall()}

    async def get_history(self, run_id: str) -> tuple[HistoryEvent, ...]:
        """Load a run's append-only history in sequence order.

        Args:
            run_id: The run identity.

        Returns:
            The history events.
        """
        pool = await self._open()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM workflow_history WHERE run_id = %s ORDER BY seq",
                (run_id,),
            )
            return tuple(
                HistoryEvent(
                    run_id=row["run_id"],
                    seq=row["seq"],
                    type=HistoryEventType(row["type"]),
                    at=row["at"],
                    data=row["data"],
                )
                for row in await cursor.fetchall()
            )

    async def read_schedule_cursor(self, key: str) -> float | None:
        """Read where a schedule's catch-up last reached.

        Args:
            key: The schedule identity, "{workflow_id}:{handler_id}".

        Returns:
            The last swept time, or None when the schedule is new here.
        """
        pool = await self._open()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT at FROM workflow_schedules WHERE key = %s", (key,)
            )
            row = await cursor.fetchone()
            return None if row is None else row["at"]

    async def write_schedule_cursor(self, key: str, at: float) -> None:
        """Record where a schedule's catch-up has now reached.

        Args:
            key: The schedule identity, "{workflow_id}:{handler_id}".
            at: The time swept up to, in epoch seconds.
        """
        pool = await self._open()
        async with pool.connection() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO workflow_schedules (key, at) VALUES (%s, %s)"
                " ON CONFLICT (key) DO UPDATE SET"
                " at = GREATEST(workflow_schedules.at, EXCLUDED.at)",
                (key, at),
            )

    async def next_due(
        self, now: float, *, queues: tuple[str, ...] | None = None
    ) -> float | None:
        """Earliest future time any runnable run becomes claimable.

        Args:
            now: Current time in epoch seconds.
            queues: Queues this worker serves; None serves every queue.

        Returns:
            The epoch time, or None when no future work is scheduled.
        """
        pool = await self._open()
        params = {
            "now": now,
            "terminal_runs": _TERMINAL_RUNS,
            "terminal_steps": _TERMINAL_STEPS,
            "claimable": _CLAIMABLE_STEPS,
            "queues": list(queues) if queues is not None else None,
        }
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT MIN(s.due_at) AS due FROM workflow_steps s"
                " JOIN workflow_runs r ON r.run_id = s.run_id"
                f" WHERE {_RUNNABLE_PREDICATE} AND {_FRONTIER_PREDICATE}"
                f" AND {_QUEUE_PREDICATE}"
                " AND (s.status = ANY(%(claimable)s)"
                " OR (s.status = 'BLOCKED' AND s.due_at > 0))",
                params,
            )
            row = await cursor.fetchone()
            return None if row is None else row["due"]
