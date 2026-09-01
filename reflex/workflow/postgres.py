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
import uuid
from typing import TYPE_CHECKING, Any, Final

from reflex_base.utils.exceptions import WorkflowRuntimeError
from reflex_base.workflow import DEFAULT_LEASE_DURATION

from reflex.workflow.records import (
    CLAIMABLE_STEP_STATUSES,
    TERMINAL_RUN_STATUSES,
    TERMINAL_STEP_STATUSES,
    AuditEntry,
    HistoryEvent,
    HistoryEventType,
    ParkedDelivery,
    ParkedStatus,
    RunRecord,
    RunStatus,
    StepRecord,
    StepStatus,
    WorkerRecord,
)
from reflex.workflow.store import (
    Claim,
    FlowAdmission,
    FlowGate,
    StaleClaimError,
    _child_admission_events,
    _fence_deadline,
)

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
    parent_close TEXT NOT NULL DEFAULT 'cancel',
    request_key TEXT,
    labels JSONB,
    deadline DOUBLE PRECISION,
    cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
    release_id TEXT,
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
CREATE TABLE IF NOT EXISTS workflow_workers (
    worker_id TEXT PRIMARY KEY,
    release_id TEXT,
    queues JSONB NOT NULL,
    capacity INTEGER NOT NULL,
    started_at DOUBLE PRECISION NOT NULL,
    heartbeat_at DOUBLE PRECISION NOT NULL
);
ALTER TABLE workflow_runs ADD COLUMN IF NOT EXISTS release_id TEXT;
CREATE TABLE IF NOT EXISTS workflow_channel_inbox (
    parked_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    correlation_key TEXT NOT NULL,
    dedupe_key TEXT NOT NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL,
    reason TEXT,
    run_id TEXT,
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    UNIQUE (workflow_id, channel, correlation_key, dedupe_key)
);
CREATE INDEX IF NOT EXISTS idx_workflow_channel_inbox_route
    ON workflow_channel_inbox (workflow_id, correlation_key, status);
CREATE TABLE IF NOT EXISTS workflow_audit (
    audit_id TEXT PRIMARY KEY,
    at DOUBLE PRECISION NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    detail JSONB NOT NULL,
    reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_workflow_audit_at ON workflow_audit (at);
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
ALTER TABLE workflow_runs ADD COLUMN IF NOT EXISTS parent_close TEXT NOT NULL DEFAULT 'cancel';
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
    " AND (r.release_id IS NULL OR %(release)s::text IS NULL"
    " OR r.release_id = %(release)s)"
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


def _audit_from_row(row: Mapping[str, Any]) -> AuditEntry:
    """Build an audit entry from a database row.

    Args:
        row: The ``workflow_audit`` row.

    Returns:
        The entry.
    """
    return AuditEntry(
        audit_id=row["audit_id"],
        at=row["at"],
        actor=row["actor"],
        action=row["action"],
        target=row["target"],
        detail=row["detail"],
        reason=row["reason"],
    )


def _parked_from_row(row: Mapping[str, Any]) -> ParkedDelivery:
    """Build a parked-delivery record from a database row.

    Args:
        row: The ``workflow_channel_inbox`` row.

    Returns:
        The record.
    """
    return ParkedDelivery(
        parked_id=row["parked_id"],
        workflow_id=row["workflow_id"],
        channel=row["channel"],
        correlation_key=row["correlation_key"],
        dedupe_key=row["dedupe_key"],
        payload=row["payload"],
        status=ParkedStatus(row["status"]),
        reason=row["reason"],
        run_id=row["run_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


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
        parent_close=row["parent_close"] or "cancel",
        request_key=row["request_key"],
        labels=row["labels"],
        release_id=row["release_id"],
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


def _run_filters(query: RunQuery) -> tuple[str, tuple[Any, ...]]:
    """Build the WHERE clause a run query means.

    Shared by listing and counting so the two can never disagree about what
    matches.

    Args:
        query: The filters to apply; ``limit`` is not one of them.

    Returns:
        The clause (empty when nothing filters) and its parameters.
    """
    clauses: list[str] = []
    params: list[Any] = []
    if query.workflow_id is not None:
        clauses.append("workflow_id = %s")
        params.append(query.workflow_id)
    if query.definition_digest is not None:
        clauses.append("definition_digest = %s")
        params.append(query.definition_digest)
    if query.release_id is not None:
        clauses.append("release_id = %s")
        params.append(query.release_id)
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
    return where, tuple(params)


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
            try:
                await self._initialize_schema(pool, schema)
            except BaseException:
                # The pool is already open; abandoning it here would leak its
                # connections and every retry would leak another pool's worth.
                await pool.close()
                raise
            self._pool = pool
            return pool

    async def _initialize_schema(self, pool: Any, schema: str | None) -> None:
        """Create this store's schema and tables, safely under concurrency.

        Args:
            pool: The open connection pool.
            schema: The schema to create tables in, or None for the search
                path's default.
        """
        async with pool.connection() as conn, conn.transaction():
            # IF NOT EXISTS does not make concurrent DDL safe: each
            # CREATE TABLE also inserts the table's composite type, and
            # two backends that both saw "not exists" race on pg_type --
            # twelve fresh workers produced one winner and eleven
            # UniqueViolations. The advisory lock serializes the
            # initializers so the losers' IF NOT EXISTS genuinely sees
            # the winner's objects, and running every statement in one
            # transaction means a worker that dies mid-setup leaves
            # nothing half-created behind.
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"reflex-workflow-ddl:{schema or ''}",),
            )
            if schema is not None:
                await conn.execute(
                    SQL("CREATE SCHEMA IF NOT EXISTS {}").format(Identifier(schema))
                )
                await conn.execute(_set_search_path(schema))
            await conn.execute(_SCHEMA)

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
            " flow_key, parent_run_id, parent_ordinal, parent_close,"
            " request_key, labels,"
            " deadline, cancel_requested, release_id, created_at, updated_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,"
            " %s, %s, %s, %s, %s, %s)",
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
                run.parent_close,
                run.request_key,
                _json(run.labels),
                run.deadline,
                run.cancel_requested,
                run.release_id,
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

    async def _check_claim(self, conn: Connection, claim: Claim) -> float | None:
        """Validate that a claim still owns its step and state version.

        Args:
            conn: The connection inside an open transaction.
            claim: The claim to validate.

        Returns:
            The run's deadline, when it has one.

        Raises:
            StaleClaimError: If the claim was fenced.
        """
        cursor = await conn.execute(
            "SELECT s.status AS step_status, s.epoch AS epoch,"
            " r.state_version AS state_version, r.deadline AS deadline"
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
        return row["deadline"]

    async def admit(
        self,
        run: RunRecord,
        root_step: StepRecord,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
    ) -> tuple[bool, str]:
        """Atomically admit a run, deduplicating on the request key.

        Roots with a start policy are admitted through ``admit_flow``, where
        the whole policy decision shares the admitting transaction.

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
                # Channel-inbox rows before the run: ingest locks its row and
                # then the run, so admission takes them in the same order.
                await self._lock_parked_conn(conn, run.workflow_id, run.request_key)
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
            if run.request_key is not None:
                # Deliveries that arrived before this run did, flushed inside
                # the admitting transaction: a crash cannot separate "the run
                # exists" from "its early mail reached it".
                await self._flush_parked_conn(
                    conn,
                    run.workflow_id,
                    run.request_key,
                    run.run_id,
                    run.created_at,
                )
        return True, run.run_id

    async def admit_flow(
        self,
        run: RunRecord,
        root_step: StepRecord,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
        gate: FlowGate,
        now: float,
    ) -> FlowAdmission:
        """Admit a run under a start policy, atomically.

        The transaction opens by taking an advisory lock on the flow key.
        Row locks cannot serialize this decision -- when no run exists yet
        there is no row to lock, and two transactions both count zero and
        both insert -- but an advisory lock exists before any row does, so
        the second admitter waits and then reads what the first committed.

        Args:
            run: The run record to create, carrying the flow key.
            root_step: The preallocated root mailbox slot.
            events: History events to append on creation.
            gate: The policy to enforce.
            now: Current time in epoch seconds.

        Returns:
            What was done, decided inside the transaction.
        """
        pool = await self._open()
        async with pool.connection() as conn, conn.transaction():
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"{run.workflow_id}\x1f{run.flow_key}",),
            )
            if run.request_key is not None:
                # Reserve the key before any policy mutation, exactly as
                # admit() does. Two admissions can share a request key while
                # computing different flow keys -- different advisory locks --
                # and if the reservation came after the singleton-cancel
                # branch, the duplicate would cancel the other flow key's
                # incumbents and then commit those cancellations on its way
                # out as "deduplicated". A duplicate must leave with zero
                # side effects.
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
                        return FlowAdmission("deduplicated", existing["run_id"])
            cursor = await conn.execute(
                "SELECT run_id FROM workflow_runs"
                " WHERE workflow_id = %s AND flow_key = %s"
                " AND NOT (status = ANY(%s))"
                " ORDER BY created_at, run_id",
                (run.workflow_id, run.flow_key, _TERMINAL_RUNS),
            )
            active = await cursor.fetchall()
            if gate.singleton_skip and active:
                return FlowAdmission("skipped", active[0]["run_id"])
            cancelled: list[str] = []
            if gate.singleton_cancel and active:
                ids = [row["run_id"] for row in active]
                # The active SELECT is an unlocked snapshot, and a worker
                # committing one of these runs to a terminal status does not
                # hold the flow lock: under READ COMMITTED this UPDATE would
                # wait out that commit and then flip the finished run back to
                # CANCELLING -- resurrecting a terminal run. The non-terminal
                # guard makes the row-version re-check decide correctly, and
                # RETURNING reports only what was actually cancelled.
                cursor = await conn.execute(
                    "UPDATE workflow_runs SET cancel_requested = TRUE,"
                    " status = %s, updated_at = %s WHERE run_id = ANY(%s)"
                    " AND NOT (status = ANY(%s)) RETURNING run_id",
                    (RunStatus.CANCELLING.value, now, ids, _TERMINAL_RUNS),
                )
                cancelled = [row["run_id"] for row in await cursor.fetchall()]
                for run_id in cancelled:
                    await self._append_events(
                        conn,
                        run_id,
                        ((HistoryEventType.RUN_CANCEL_REQUESTED, {}),),
                        now,
                    )
            due_at = root_step.due_at
            if gate.rate_limit is not None:
                limit, window = gate.rate_limit
                cursor = await conn.execute(
                    "SELECT count(*) AS n FROM workflow_runs"
                    " WHERE workflow_id = %s AND flow_key = %s AND created_at > %s",
                    (run.workflow_id, run.flow_key, now - window),
                )
                row = await cursor.fetchone()
                if row is not None and row["n"] >= limit:
                    return FlowAdmission("rejected", retry_after=window)
            if gate.throttle is not None:
                limit, window = gate.throttle
                cursor = await conn.execute(
                    "SELECT GREATEST(s.due_at, r.created_at) AS start"
                    " FROM workflow_runs r JOIN workflow_steps s"
                    " ON s.run_id = r.run_id AND s.ordinal = 0"
                    " WHERE r.workflow_id = %s AND r.flow_key = %s"
                    " ORDER BY start DESC OFFSET %s LIMIT 1",
                    (run.workflow_id, run.flow_key, limit - 1),
                )
                row = await cursor.fetchone()
                if row is not None and row["start"] + window > now:
                    due_at = row["start"] + window
            if gate.debounce is not None:
                if active:
                    cursor = await conn.execute(
                        "UPDATE workflow_steps SET args = %s, due_at = %s,"
                        " updated_at = %s WHERE run_id = %s AND ordinal = 0"
                        " AND status = %s",
                        (
                            _json(root_step.args),
                            now + gate.debounce,
                            now,
                            active[0]["run_id"],
                            StepStatus.READY.value,
                        ),
                    )
                    if cursor.rowcount:
                        return FlowAdmission("coalesced", active[0]["run_id"])
                due_at = now + gate.debounce
            if run.request_key is not None:
                # Channel-inbox rows before the run row, matching ingest's
                # order.
                await self._lock_parked_conn(conn, run.workflow_id, run.request_key)
            await self._insert_run(conn, run)
            await self._insert_step(conn, dataclasses.replace(root_step, due_at=due_at))
            await self._append_events(conn, run.run_id, events, run.created_at)
            if run.request_key is not None:
                # Policy admission is still admission: early mail flushes on
                # this door exactly as on the plain one.
                await self._flush_parked_conn(
                    conn,
                    run.workflow_id,
                    run.request_key,
                    run.run_id,
                    run.created_at,
                )
        return FlowAdmission("started", run.run_id, cancelled=tuple(cancelled))

    async def purge_runs(
        self,
        before: float,
        *,
        workflow_id: str | None = None,
        attribution: Mapping[str, str] | None = None,
    ) -> int:
        """Delete terminal runs not updated since a cutoff, and all their data.

        Args:
            before: Delete runs whose last update is older than this.
            workflow_id: Restrict to one workflow identity.
            attribution: Who asked and why, recorded in the audit log.

        Returns:
            How many runs were deleted.
        """
        pool = await self._open()
        where = "status = ANY(%s) AND updated_at < %s"
        params: tuple[Any, ...] = (_TERMINAL_RUNS, before)
        if workflow_id is not None:
            where += " AND workflow_id = %s"
            params = (*params, workflow_id)
        async with pool.connection() as conn, conn.transaction():
            cursor = await conn.execute(
                f"SELECT run_id FROM workflow_runs WHERE {where}",
                params,
            )
            doomed = [row["run_id"] for row in await cursor.fetchall()]
            if not doomed:
                return 0
            for table in (
                "workflow_steps",
                "workflow_history",
                "workflow_inbox",
                "workflow_substeps",
            ):
                await conn.execute(
                    SQL("DELETE FROM {} WHERE run_id = ANY(%s)").format(
                        Identifier(table)
                    ),
                    (doomed,),
                )
            await conn.execute(
                "DELETE FROM workflow_dedupe WHERE run_id = ANY(%s)", (doomed,)
            )
            await conn.execute(
                "DELETE FROM workflow_runs WHERE run_id = ANY(%s)", (doomed,)
            )
        await self._audit_conn(
            conn,
            attribution,
            "purge_runs",
            workflow_id or "*",
            {"before": before, "deleted": len(doomed)},
            before,
        )
        return len(doomed)

    async def epoch_time(self) -> float | None:
        """The database clock, the one time source every worker shares.

        Returns:
            Epoch seconds by the database's clock.
        """
        pool = await self._open()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT EXTRACT(EPOCH FROM clock_timestamp())::float8 AS now"
            )
            row = await cursor.fetchone()
            assert row is not None
            return float(row["now"])

    async def claim_next(
        self,
        now: float,
        *,
        lease_duration: float = DEFAULT_LEASE_DURATION,
        queues: tuple[str, ...] | None = None,
        release: str | None = None,
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
            release: The claiming worker's release identity. A run pinned to
                a different release is skipped: it drains on the release that
                admitted it, so one run never mixes two releases' code.

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
            "release": release,
        }
        async with pool.connection() as conn, conn.transaction():
            cursor = await conn.execute(
                "SELECT s.run_id AS run_id, s.ordinal AS ordinal"
                " FROM workflow_steps s JOIN workflow_runs r ON r.run_id = s.run_id"
                f" WHERE {_RUNNABLE_PREDICATE} AND {_FRONTIER_PREDICATE}"
                f" AND {_CLAIMABLE_PREDICATE} AND {_QUEUE_PREDICATE}"
                " ORDER BY r.created_at, s.run_id"
                # OF r, not OF s: every arrival path holds the parent run row
                # and then updates the join step, and a join slot with a
                # lapsed wait deadline is claimable -- locking the step first
                # here was the last remaining inversion of the run-first
                # invariant, and it deadlocked a timeout claim against the
                # child arrival racing it. Holding the run row serializes the
                # step writers just as well, because every one of them takes
                # the run row first. SKIP LOCKED at run granularity also
                # matches the serial mailbox: one claim per run.
                " FOR UPDATE OF r SKIP LOCKED LIMIT 1",
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
            locked_children: list[str] = []
            if completion.run_status in TERMINAL_RUN_STATUSES:
                locked_children = await self._lock_children(conn, claim.run.run_id)
            await self._lock_run(conn, claim.run.run_id)
            deadline = await self._check_claim(conn, claim)
            # Past the deadline the only permitted outcome is TIMED_OUT, and
            # that is the sweep's transition, not this attempt's.
            _fence_deadline(claim.run.run_id, deadline, now)
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
                await self._append_events(
                    conn,
                    child_run.run_id,
                    _child_admission_events(child_run, child_step),
                    now,
                )
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
            if completion.run_status in TERMINAL_RUN_STATUSES:
                await self._close_children(conn, now, locked_children)
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
        payload: Any,
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
            return await self._deliver_with(
                conn, run_id, wait_key, dedupe_key, payload, now
            )

    async def _deliver_with(
        self,
        conn: Any,
        run_id: str,
        wait_key: str,
        dedupe_key: str,
        payload: Any,
        now: float,
    ) -> DeliveryDisposition:
        """Deliver inside the caller's open transaction.

        Takes the run row here, so a caller holding channel-inbox rows keeps
        the canonical channel-before-run lock order. Refusal branches write
        nothing, so the caller's transaction stays committable.

        Args:
            conn: The connection inside an open transaction.
            run_id: The receiving run.
            wait_key: The address the waiting slot declared.
            dedupe_key: Sender-supplied identity, making redelivery a no-op.
            payload: JSON-compatible payload to hand the resuming handler.
            now: Current time in epoch seconds.

        Returns:
            What the store did with the delivery.
        """
        cursor = await conn.execute(
            "SELECT status, deadline FROM workflow_runs WHERE run_id = %s FOR UPDATE",
            (run_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return "unknown_run"
        if row["status"] in _TERMINAL_RUNS:
            return "run_terminal"
        if row["deadline"] is not None and row["deadline"] <= now:
            # Claims exclude past-deadline runs and the sweep is about to
            # finalize this one TIMED_OUT, so "resolved" would tell the
            # sender -- often a person clicking approve -- that their
            # decision landed, moments before it is discarded.
            return "expired"
        cursor = await conn.execute(
            "SELECT 1 FROM workflow_inbox"
            " WHERE run_id = %s AND wait_key = %s AND dedupe_key = %s",
            (run_id, wait_key, dedupe_key),
        )
        if await cursor.fetchone() is not None:
            await self._append_events(
                conn,
                run_id,
                ((HistoryEventType.SIGNAL_DUPLICATE, {"wait_key": wait_key}),),
                now,
            )
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
                Jsonb(payload),
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

    async def _flush_parked_conn(
        self, conn: Any, workflow_id: str, request_key: str, run_id: str, now: float
    ) -> None:
        """Deliver PENDING channel-inbox rows to a freshly admitted run.

        The caller must have locked these rows (``_lock_parked_conn``)
        before creating the run, keeping the canonical channel-before-run
        order.

        Args:
            conn: The connection inside the admitting transaction.
            workflow_id: The workflow identity.
            request_key: The admission key, matched against correlation keys.
            run_id: The run that now exists.
            now: Current time in epoch seconds.
        """
        cursor = await conn.execute(
            "SELECT parked_id, channel, dedupe_key, payload FROM"
            " workflow_channel_inbox WHERE workflow_id = %s AND"
            " correlation_key = %s AND status = %s ORDER BY created_at",
            (workflow_id, request_key, ParkedStatus.PENDING.value),
        )
        for row in await cursor.fetchall():
            disposition = await self._deliver_with(
                conn,
                run_id,
                f"sig:{row['channel']}",
                row["dedupe_key"],
                row["payload"],
                now,
            )
            delivered = disposition in ("resolved", "buffered", "duplicate")
            await conn.execute(
                "UPDATE workflow_channel_inbox SET status = %s, reason = %s,"
                " run_id = %s, updated_at = %s WHERE parked_id = %s",
                (
                    ParkedStatus.DELIVERED.value
                    if delivered
                    else ParkedStatus.DEAD.value,
                    None if delivered else disposition,
                    run_id if delivered else None,
                    now,
                    row["parked_id"],
                ),
            )

    async def _lock_parked_conn(
        self, conn: Any, workflow_id: str, request_key: str
    ) -> None:
        """Take the PENDING channel-inbox rows an admission will flush.

        Before the run row exists: ingest locks its channel row and then the
        run, so admission must also take channel rows first or the two paths
        meet on the same rows in opposite orders.

        Args:
            conn: The connection inside the admitting transaction.
            workflow_id: The workflow identity.
            request_key: The admission key.
        """
        await conn.execute(
            "SELECT parked_id FROM workflow_channel_inbox WHERE workflow_id = %s"
            " AND correlation_key = %s AND status = %s ORDER BY parked_id"
            " FOR UPDATE",
            (workflow_id, request_key, ParkedStatus.PENDING.value),
        )

    async def _route_parked_conn(
        self, conn: Any, parked_id: str, now: float
    ) -> DeliveryDisposition:
        """Route one PENDING channel-inbox row inside an open transaction.

        Args:
            conn: The connection, already holding the row.
            parked_id: The row to route.
            now: Current time in epoch seconds.

        Returns:
            The routing outcome.
        """
        cursor = await conn.execute(
            "SELECT workflow_id, channel, correlation_key, dedupe_key, payload"
            " FROM workflow_channel_inbox WHERE parked_id = %s",
            (parked_id,),
        )
        row = await cursor.fetchone()
        cursor = await conn.execute(
            "SELECT run_id FROM workflow_dedupe WHERE workflow_id = %s"
            " AND request_key = %s",
            (row["workflow_id"], row["correlation_key"]),
        )
        target = await cursor.fetchone()
        if target is None:
            return "parked"
        disposition = await self._deliver_with(
            conn,
            target["run_id"],
            f"sig:{row['channel']}",
            row["dedupe_key"],
            row["payload"],
            now,
        )
        delivered = disposition in ("resolved", "buffered", "duplicate")
        await conn.execute(
            "UPDATE workflow_channel_inbox SET status = %s, reason = %s,"
            " run_id = %s, updated_at = %s WHERE parked_id = %s",
            (
                ParkedStatus.DELIVERED.value if delivered else ParkedStatus.DEAD.value,
                None if delivered else disposition,
                target["run_id"] if delivered else None,
                now,
                parked_id,
            ),
        )
        return disposition if delivered else "dead_letter"

    async def register_worker(self, worker: WorkerRecord) -> None:
        """Record (or refresh) a worker's registration.

        Args:
            worker: The worker's identity, release, queues, and capacity.
        """
        pool = await self._open()
        async with pool.connection() as conn:
            await conn.execute(
                "INSERT INTO workflow_workers (worker_id, release_id, queues,"
                " capacity, started_at, heartbeat_at)"
                " VALUES (%s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (worker_id) DO UPDATE SET release_id ="
                " excluded.release_id, queues = excluded.queues,"
                " capacity = excluded.capacity,"
                " heartbeat_at = excluded.heartbeat_at",
                (
                    worker.worker_id,
                    worker.release_id,
                    Jsonb(list(worker.queues)),
                    worker.capacity,
                    worker.started_at,
                    worker.heartbeat_at,
                ),
            )

    async def heartbeat_worker(self, worker_id: str, now: float) -> None:
        """Refresh a worker's sign of life.

        Args:
            worker_id: The worker.
            now: Current time in epoch seconds.
        """
        pool = await self._open()
        async with pool.connection() as conn:
            await conn.execute(
                "UPDATE workflow_workers SET heartbeat_at = %s WHERE worker_id = %s",
                (now, worker_id),
            )

    async def deregister_worker(self, worker_id: str) -> None:
        """Remove a worker that shut down cleanly.

        Args:
            worker_id: The worker.
        """
        pool = await self._open()
        async with pool.connection() as conn:
            await conn.execute(
                "DELETE FROM workflow_workers WHERE worker_id = %s",
                (worker_id,),
            )

    async def list_workers(self) -> tuple[WorkerRecord, ...]:
        """List registered workers, most recently started first.

        Returns:
            The registrations.
        """
        pool = await self._open()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM workflow_workers ORDER BY started_at DESC"
            )
            return tuple(
                WorkerRecord(
                    worker_id=row["worker_id"],
                    release_id=row["release_id"],
                    queues=tuple(row["queues"]),
                    capacity=row["capacity"],
                    started_at=row["started_at"],
                    heartbeat_at=row["heartbeat_at"],
                )
                for row in await cursor.fetchall()
            )

    async def ingest_channel_delivery(
        self,
        workflow_id: str,
        channel: str,
        correlation_key: str,
        dedupe_key: str,
        payload: Any,
        now: float,
    ) -> DeliveryDisposition:
        """Durably accept a correlated provider event, exactly once.

        Args:
            workflow_id: The workflow whose channel the event addresses.
            channel: The channel name.
            correlation_key: The business key naming the target run.
            dedupe_key: The provider's event identity.
            payload: The canonical event payload.
            now: Current time in epoch seconds.

        Returns:
            The routing outcome.
        """
        pool = await self._open()
        parked_id = uuid.uuid4().hex
        async with pool.connection() as conn, conn.transaction():
            cursor = await conn.execute(
                "INSERT INTO workflow_channel_inbox (parked_id, workflow_id,"
                " channel, correlation_key, dedupe_key, payload, status,"
                " created_at, updated_at)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
                " ON CONFLICT DO NOTHING RETURNING parked_id",
                (
                    parked_id,
                    workflow_id,
                    channel,
                    correlation_key,
                    dedupe_key,
                    Jsonb(payload),
                    ParkedStatus.PENDING.value,
                    now,
                    now,
                ),
            )
            if await cursor.fetchone() is None:
                # The event id is the identity: a provider redelivery and a
                # crash-after-ack replay both land here.
                return "duplicate"
            return await self._route_parked_conn(conn, parked_id, now)

    async def list_parked(
        self,
        *,
        workflow_id: str | None = None,
        status: ParkedStatus | None = None,
        limit: int = 100,
    ) -> tuple[ParkedDelivery, ...]:
        """List channel-inbox deliveries, newest first.

        Args:
            workflow_id: Restrict to one workflow.
            status: Restrict to one lifecycle state.
            limit: Maximum rows.

        Returns:
            The matching deliveries.
        """
        clauses, params = [], []
        if workflow_id is not None:
            clauses.append("workflow_id = %s")
            params.append(workflow_id)
        if status is not None:
            clauses.append("status = %s")
            params.append(status.value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        pool = await self._open()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                f"SELECT * FROM workflow_channel_inbox{where}"
                " ORDER BY created_at DESC LIMIT %s",
                (*params, limit),
            )
            return tuple(_parked_from_row(row) for row in await cursor.fetchall())

    async def replay_parked(
        self,
        parked_id: str,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> DeliveryDisposition:
        """Re-attempt routing of a parked or dead delivery.

        Args:
            parked_id: The delivery to replay.
            now: Current time in epoch seconds.
            attribution: Who asked and why, recorded in the audit log.

        Returns:
            The routing outcome, or ``unknown_key`` if no such delivery.
        """
        pool = await self._open()
        async with pool.connection() as conn, conn.transaction():
            cursor = await conn.execute(
                "SELECT status FROM workflow_channel_inbox WHERE parked_id = %s"
                " FOR UPDATE",
                (parked_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                disposition: DeliveryDisposition = "unknown_key"
            elif row["status"] == ParkedStatus.DELIVERED.value:
                # Replaying what already reached its run must never signal
                # twice.
                disposition = "duplicate"
            else:
                await conn.execute(
                    "UPDATE workflow_channel_inbox SET status = %s, reason = NULL,"
                    " updated_at = %s WHERE parked_id = %s",
                    (ParkedStatus.PENDING.value, now, parked_id),
                )
                disposition = await self._route_parked_conn(conn, parked_id, now)
            await self._audit_conn(
                conn,
                attribution,
                "replay_parked",
                parked_id,
                {"disposition": disposition},
                now,
            )
            return disposition

    async def sweep_parked(self, now: float, ttl: float) -> int:
        """Turn PENDING deliveries older than a ttl into DEAD letters.

        Args:
            now: Current time in epoch seconds.
            ttl: Age in seconds beyond which PENDING is unclaimed.

        Returns:
            How many deliveries became dead letters.
        """
        pool = await self._open()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "UPDATE workflow_channel_inbox SET status = %s,"
                " reason = 'unclaimed', updated_at = %s"
                " WHERE status = %s AND created_at < %s",
                (
                    ParkedStatus.DEAD.value,
                    now,
                    ParkedStatus.PENDING.value,
                    now - ttl,
                ),
            )
            return cursor.rowcount

    async def _audit_conn(
        self,
        conn: Any,
        attribution: Mapping[str, str] | None,
        action: str,
        target: str,
        detail: dict[str, Any],
        now: float,
    ) -> None:
        """Insert one audit entry inside the caller's transaction, if attributed.

        Args:
            conn: The connection inside an open transaction.
            attribution: Who asked and why; nothing is written without it.
            action: What was done.
            target: What it was done to.
            detail: Outcome and parameters.
            now: Current time in epoch seconds.
        """
        if not attribution:
            return
        await conn.execute(
            "INSERT INTO workflow_audit (audit_id, at, actor, action, target,"
            " detail, reason) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                uuid.uuid4().hex,
                now,
                attribution.get("actor", "unknown"),
                action,
                target,
                Jsonb(detail),
                attribution.get("reason"),
            ),
        )

    async def list_audit(
        self, *, action: str | None = None, limit: int = 100
    ) -> tuple[AuditEntry, ...]:
        """List audited operator actions, newest first.

        Args:
            action: Restrict to one action name.
            limit: Maximum entries.

        Returns:
            The matching entries.
        """
        where = " WHERE action = %s" if action is not None else ""
        params: tuple = (action, limit) if action is not None else (limit,)
        pool = await self._open()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                f"SELECT * FROM workflow_audit{where} ORDER BY at DESC LIMIT %s",
                params,
            )
            return tuple(_audit_from_row(row) for row in await cursor.fetchall())

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

    async def _lock_children(self, conn: Any, run_id: str) -> list[str]:
        """Take the branch rows this transaction will close, before its own.

        Closing a parent locks the parent and then its children; a child
        reporting home locks itself and then its parent. Those are the same
        two rows in opposite orders, which is an ABBA deadlock -- Postgres
        detects it and aborts one side, and under a fan-out being cancelled
        that happened constantly.

        Taking the branches first makes every transaction acquire in one
        order: children, then self, then parent. Deeper rows are always taken
        before shallower ones, so no cycle can form. The ORDER BY matters for
        the same reason within one level.

        Children already told to cancel are excluded: the flag is durable
        and monotonic, so there is nothing left to write on them -- and
        skipping them keeps a second close from appending a duplicate
        cancel-requested event to their history.

        Args:
            conn: The connection inside an open transaction.
            run_id: The run whose branches may be closed.

        Returns:
            The child run ids this transaction holds, for _close_children --
            which must write exactly this set, because a child revived
            between the lock and the write would otherwise be written
            parent-before-child, the inversion this ordering exists to
            prevent.
        """
        cursor = await conn.execute(
            "SELECT run_id FROM workflow_runs WHERE parent_run_id = %s"
            " AND parent_close <> 'abandon' AND NOT cancel_requested"
            " AND NOT (status = ANY(%s))"
            " ORDER BY run_id FOR UPDATE",
            (run_id, [s.value for s in TERMINAL_RUN_STATUSES]),
        )
        return [row["run_id"] for row in await cursor.fetchall()]

    async def _close_children(self, conn: Any, now: float, children: list[str]) -> None:
        """Request cancellation of branches the closing run fanned out to.

        Called inside the transaction that takes a run terminal, so an
        operator cancelling a rollout durably stops the regional deploys it
        started -- not best-effort follow-up that dies with the worker.
        Grandchildren are not walked here: a marked child is control-pending
        the moment it drains (a run blocked on its own join holds no claim),
        so it finalizes and closes its own branches in turn.

        Args:
            conn: The connection inside an open transaction.
            now: Current time in epoch seconds.
            children: The child run ids _lock_children pinned earlier in this
                transaction.
        """
        if not children:
            return
        closing = await (
            await conn.execute(
                # Exactly the set _lock_children pinned, never re-derived: a
                # child revived between the lock and this write would match a
                # fresh predicate without ever having been locked, and this
                # transaction would then take its row while holding the
                # parent -- the shallower-before-deeper inversion the lock
                # ordering exists to prevent. The revived child is the
                # operator's decision and keeps running; it was terminal when
                # this close began.
                "UPDATE workflow_runs SET cancel_requested = TRUE, status = %s,"
                " updated_at = %s WHERE run_id = ANY(%s)"
                " AND NOT (status = ANY(%s))"
                " RETURNING run_id",
                (
                    RunStatus.CANCELLING.value,
                    now,
                    children,
                    [s.value for s in TERMINAL_RUN_STATUSES],
                ),
            )
        ).fetchall()
        for row in closing:
            await self._append_events(
                conn,
                row["run_id"],
                ((HistoryEventType.RUN_CANCEL_REQUESTED, {"cause": "parent_close"}),),
                now,
            )

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
            "SELECT status, deadline FROM workflow_runs WHERE run_id = %s FOR UPDATE",
            (run_id,),
        )
        run_row = await cursor.fetchone()
        if run_row is None:
            return "unknown_run"
        if run_row["status"] in _TERMINAL_RUNS:
            return "run_terminal"
        if run_row["deadline"] is not None and run_row["deadline"] <= now:
            # A past-deadline run can never execute the continuation;
            # saying "resolved" would be a lie the sweep then discards.
            return "expired"
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
                Jsonb(payload),
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
                "SELECT status, deadline FROM workflow_runs WHERE run_id = %s"
                " FOR UPDATE",
                (run_id,),
            )
            run_row = await cursor.fetchone()
            if run_row is None:
                return "unknown_run"
            if run_row["status"] in _TERMINAL_RUNS:
                return "run_terminal"
            if run_row["deadline"] is not None and run_row["deadline"] <= now:
                # The join can never run its continuation: the sweep is about
                # to finalize this parent TIMED_OUT and tombstone the slot.
                return "expired"
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
                    Jsonb(payload),
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

    async def request_cancel(
        self,
        run_id: str,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> bool:
        """Record cancellation intent on a run.

        Args:
            run_id: The run to cancel.
            now: Current time in epoch seconds.
            attribution: Who asked and why, e.g. ``{"actor": ..., "reason":
                ...}``, merged into the operator-facing history event so the
                run's own story answers "who did this".

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
                conn,
                run_id,
                ((HistoryEventType.RUN_CANCEL_REQUESTED, dict(attribution or {})),),
                now,
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
        attribution: Mapping[str, str] | None = None,
    ) -> bool:
        """Terminate a drained run and tombstone its unresolved slots.

        Args:
            run_id: The run to finalize.
            status: The terminal status to record.
            error: Error payload recorded on the run.
            event: The terminal history event type.
            now: Current time in epoch seconds.
            attribution: Who asked and why, e.g. ``{"actor": ..., "reason":
                ...}``, merged into the operator-facing history event so the
                run's own story answers "who did this".
            result: Result to record, for an operator forcing completion.
            parent_arrival: When this run is a child, the arrival to deliver
                to its parent's join, applied in this same transaction.

        Returns:
            True if the run was finalized.
        """
        pool = await self._open()
        async with pool.connection() as conn, conn.transaction():
            locked_children = await self._lock_children(conn, run_id)
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
            events.append((
                event,
                {**({} if error is None else dict(error)), **(attribution or {})},
            ))
            await self._append_events(conn, run_id, events, now)
            await self._close_children(conn, now, locked_children)
            if parent_arrival is not None:
                await self._apply_arrival(conn, *parent_arrival, now)
        return True

    async def resume_run(
        self,
        run_id: str,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> bool:
        """Re-open a suspended run so its frontier step runs again.

        Args:
            run_id: The run to resume.
            now: Current time in epoch seconds.
            attribution: Who asked and why, e.g. ``{"actor": ..., "reason":
                ...}``, merged into the operator-facing history event so the
                run's own story answers "who did this".

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
                conn,
                run_id,
                ((HistoryEventType.RUN_RESUMED, dict(attribution or {})),),
                now,
            )
        return True

    @staticmethod
    async def _restore_tombstoned(conn: Any, run_id: str, now: float) -> list[int]:
        """Re-open the slots the run's stopping failure tombstoned.

        Within a run an operator can retry or skip, a CANCELLED slot can only
        be that failure's casualty: run-level cancellation ends in a
        CANCELLED run these actions refuse, and force-finalization leaves no
        failed or suspended step for them to target.

        Args:
            conn: The open transaction's connection.
            run_id: The run being re-opened.
            now: Current time in epoch seconds.

        Returns:
            The restored ordinals, in order.
        """
        cursor = await conn.execute(
            # Waits and joins come back BLOCKED with their arrival counts and
            # deadlines intact, never READY -- restored-as-READY they would
            # run immediately with a missing or partial payload. Plain slots
            # keep their own due_at, so a restored delay still waits out its
            # delay instead of firing the moment an operator retries.
            "UPDATE workflow_steps SET status = CASE WHEN wait_key IS NULL"
            " THEN %s ELSE %s END, attempts = 0,"
            " lease_expires_at = 0, error = NULL, updated_at = %s"
            " WHERE run_id = %s AND status = %s RETURNING ordinal",
            (
                StepStatus.READY.value,
                StepStatus.BLOCKED.value,
                now,
                run_id,
                StepStatus.CANCELLED.value,
            ),
        )
        return sorted(row["ordinal"] for row in await cursor.fetchall())

    async def retry_run(
        self,
        run_id: str,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> bool:
        """Re-open a failed run at the step that failed.

        Args:
            run_id: The run to retry.
            now: Current time in epoch seconds.
            attribution: Who asked and why, e.g. ``{"actor": ..., "reason":
                ...}``, merged into the operator-facing history event so the
                run's own story answers "who did this".

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
            restored = await self._restore_tombstoned(conn, run_id, now)
            await self._append_events(
                conn,
                run_id,
                (
                    (
                        HistoryEventType.RUN_RESUMED,
                        {"origin": "retry", **(attribution or {})},
                    ),
                    *(
                        (HistoryEventType.STEP_RESTORED, {"ordinal": ordinal})
                        for ordinal in restored
                    ),
                ),
                now,
            )
        return True

    async def skip_step(
        self,
        run_id: str,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> bool:
        """Give up on a stuck step and let the run carry on past it.

        Args:
            run_id: The run to unstick.
            now: Current time in epoch seconds.
            attribution: Who asked and why, e.g. ``{"actor": ..., "reason":
                ...}``, merged into the operator-facing history event so the
                run's own story answers "who did this".

        Returns:
            True if a blocking step was skipped.
        """
        pool = await self._open()
        async with pool.connection() as conn, conn.transaction():
            # A skip that removes the last open slot completes the run, and
            # terminal transitions take child locks before their own row.
            # Whether this skip completes is not known until the slot count
            # below, so the branches are taken unconditionally -- the order
            # is what matters, not the need.
            locked_children = await self._lock_children(conn, run_id)
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
            restored = await self._restore_tombstoned(conn, run_id, now)
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
            events = [
                (
                    HistoryEventType.STEP_SKIPPED,
                    {"ordinal": row["ordinal"], **(attribution or {})},
                ),
                *(
                    (HistoryEventType.STEP_RESTORED, {"ordinal": ordinal})
                    for ordinal in restored
                ),
            ]
            if not open_left:
                events.append((HistoryEventType.RUN_COMPLETED, {}))
            await self._append_events(conn, run_id, tuple(events), now)
            if not open_left:
                # Completed by an operator's decision is still completed:
                # branches are told to stop, and a parent joined on this run
                # hears it finished instead of waiting forever.
                await self._close_children(conn, now, locked_children)
                cursor = await conn.execute(
                    "SELECT parent_run_id, parent_ordinal FROM workflow_runs"
                    " WHERE run_id = %s",
                    (run_id,),
                )
                parent = await cursor.fetchone()
                if parent is not None and parent["parent_run_id"] is not None:
                    await self._apply_arrival(
                        conn,
                        parent["parent_run_id"],
                        parent["parent_ordinal"],
                        {
                            "run_id": run_id,
                            "status": RunStatus.COMPLETED.value,
                            "result": None,
                            "error": None,
                        },
                        run_id,
                        now,
                    )
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
        recovered = 0
        failed: list[str] = []
        overdrawn: list[StepRecord] = []
        async with pool.connection() as conn, conn.transaction():
            cursor = await conn.execute(
                # Lock the run rows, not the step rows. Every other write
                # path takes the run first and the step second -- commit()
                # does, through _lock_run -- so locking steps here inverted
                # the order and deadlocked against any attempt committing
                # late. Holding the run serializes its writers just as well,
                # because that is the invariant those writers already obey.
                "SELECT s.* FROM workflow_steps s"
                " JOIN workflow_runs r ON r.run_id = s.run_id"
                " WHERE s.status = %s AND s.lease_expires_at <= %s"
                " AND NOT (r.status = ANY(%s))"
                " ORDER BY s.run_id FOR UPDATE OF r SKIP LOCKED",
                (StepStatus.CLAIMED.value, now, _TERMINAL_RUNS),
            )
            rows = await cursor.fetchall()
            for row in rows:
                step = _step_from_row(row)
                if step.recoveries + 1 > max_recoveries:
                    # Exhaustion is a terminal transition, and terminal
                    # transitions take child locks before their own row. This
                    # transaction already holds a batch of run rows, so
                    # taking children now would acquire shallower before
                    # deeper -- the inversion both deadlock fixes removed.
                    # The step stays CLAIMED with its lapsed lease (nothing
                    # can claim it) and fails in its own transaction below,
                    # in the canonical order.
                    overdrawn.append(step)
                    continue
                cursor = await conn.execute(
                    # Guarded like the exhaustion write below: a renewal can
                    # land between the batch SELECT and this UPDATE because
                    # renew_lease takes no run-row lock.
                    "UPDATE workflow_steps SET status = %s, recoveries = %s,"
                    " due_at = %s, lease_expires_at = 0, updated_at = %s"
                    " WHERE run_id = %s AND ordinal = %s AND status = %s"
                    " AND lease_expires_at <= %s",
                    (
                        StepStatus.RECOVERY_WAIT.value,
                        step.recoveries + 1,
                        now,
                        now,
                        step.run_id,
                        step.ordinal,
                        StepStatus.CLAIMED.value,
                        now,
                    ),
                )
                if cursor.rowcount == 0:
                    continue
                recovered += 1
                await self._append_events(
                    conn,
                    step.run_id,
                    ((HistoryEventType.STEP_RECOVERED, {"ordinal": step.ordinal}),),
                    now,
                )
        for step in overdrawn:
            if await self._fail_exhausted(step, now):
                recovered += 1
                failed.append(step.run_id)
        return recovered, tuple(failed)

    async def _fail_exhausted(self, step: StepRecord, now: float) -> bool:
        """Fail a run whose step outlived its recovery budget, completely.

        The budget path used to mark the one step and the run FAILED and stop
        there: preallocated slots stayed open on a dead run, and child runs
        kept working for a parent that no longer existed. This is the same
        terminal transition failure takes everywhere else -- open slots
        tombstoned, branches closed, the parent told -- in the same lock
        order: children, then self, then parent.

        Args:
            step: The exhausted step, as phase one saw it.
            now: Current time in epoch seconds.

        Returns:
            True if this call performed the transition.
        """
        exhausted = {"reason": "recovery_budget_exhausted"}
        pool = await self._open()
        async with pool.connection() as conn, conn.transaction():
            locked_children = await self._lock_children(conn, step.run_id)
            cursor = await conn.execute(
                "SELECT status, parent_run_id, parent_ordinal FROM workflow_runs"
                " WHERE run_id = %s FOR UPDATE",
                (step.run_id,),
            )
            run_row = await cursor.fetchone()
            if run_row is None or run_row["status"] in _TERMINAL_RUNS:
                return False
            cursor = await conn.execute(
                "SELECT status, lease_expires_at, recoveries FROM workflow_steps"
                " WHERE run_id = %s AND ordinal = %s",
                (step.run_id, step.ordinal),
            )
            step_row = await cursor.fetchone()
            if (
                step_row is None
                or step_row["status"] != StepStatus.CLAIMED.value
                or step_row["lease_expires_at"] > now
            ):
                # Renewed, recovered, or failed by a peer between phases; the
                # attempt is someone else's to account for.
                return False
            cursor = await conn.execute(
                # The guard repeats the re-check inside the write itself:
                # renew_lease is the one writer that takes no run-row lock,
                # so a renewal can land in the round trip between the SELECT
                # above and this UPDATE -- and an unguarded write would
                # acknowledge the worker's lease and fail its run in the
                # same instant, discarding in-flight work the store just
                # promised another lease_duration to.
                "UPDATE workflow_steps SET status = %s, recoveries = %s,"
                " lease_expires_at = 0, error = %s, updated_at = %s"
                " WHERE run_id = %s AND ordinal = %s AND status = %s"
                " AND lease_expires_at <= %s",
                (
                    StepStatus.FAILED.value,
                    step_row["recoveries"] + 1,
                    _json(exhausted),
                    now,
                    step.run_id,
                    step.ordinal,
                    StepStatus.CLAIMED.value,
                    now,
                ),
            )
            if cursor.rowcount == 0:
                # Renewed in the window; the attempt is someone else's to
                # account for after all.
                return False
            cursor = await conn.execute(
                "SELECT ordinal FROM workflow_steps WHERE run_id = %s"
                " AND ordinal != %s AND NOT (status = ANY(%s)) ORDER BY ordinal",
                (step.run_id, step.ordinal, _TERMINAL_STEPS),
            )
            tombstoned = [row["ordinal"] for row in await cursor.fetchall()]
            if tombstoned:
                await conn.execute(
                    "UPDATE workflow_steps SET status = %s, updated_at = %s"
                    " WHERE run_id = %s AND ordinal = ANY(%s)",
                    (StepStatus.CANCELLED.value, now, step.run_id, tombstoned),
                )
            await conn.execute(
                "UPDATE workflow_runs SET status = %s, error = %s, updated_at = %s"
                " WHERE run_id = %s",
                (RunStatus.FAILED.value, _json(exhausted), now, step.run_id),
            )
            await self._append_events(
                conn,
                step.run_id,
                (
                    *(
                        (HistoryEventType.STEP_TOMBSTONED, {"ordinal": ordinal})
                        for ordinal in tombstoned
                    ),
                    (HistoryEventType.RUN_FAILED, dict(exhausted)),
                ),
                now,
            )
            await self._close_children(conn, now, locked_children)
            if run_row["parent_run_id"] is not None:
                await self._apply_arrival(
                    conn,
                    run_row["parent_run_id"],
                    run_row["parent_ordinal"],
                    {
                        "run_id": step.run_id,
                        "status": RunStatus.FAILED.value,
                        "result": None,
                        "error": dict(exhausted),
                    },
                    step.run_id,
                    now,
                )
            return True

    async def list_runs(self, query: RunQuery) -> tuple[RunRecord, ...]:
        """List runs matching a query, newest first.

        Args:
            query: The filters and pagination cursor to apply.

        Returns:
            The matching run records.
        """
        where, params = _run_filters(query)
        pool = await self._open()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                f"SELECT * FROM workflow_runs{where}"
                " ORDER BY created_at DESC, run_id DESC LIMIT %s",
                (*params, query.limit),
            )
            return tuple(_run_from_row(row) for row in await cursor.fetchall())

    async def count_runs(self, query: RunQuery) -> int:
        """Count runs matching a query.

        The count ignores ``limit`` and ``created_before``: those page a
        listing, and an aggregate is not a page. Everything else filters as
        it does for ``list_runs``, so a count and a listing always describe
        the same set.

        Args:
            query: The filters to apply.

        Returns:
            How many runs match.
        """
        where, params = _run_filters(dataclasses.replace(query, created_before=None))
        pool = await self._open()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                f"SELECT count(*) AS n FROM workflow_runs{where}", tuple(params)
            )
            row = await cursor.fetchone()
            return 0 if row is None else int(row["n"])

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
                # Jsonb, not _json: a substep that recorded None recorded
                # the JSON value null, and the column is NOT NULL because
                # every journal entry has a payload.
                (run_id, ordinal, key, Jsonb(payload), now),
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
            # next_due bounds the sleep for every runnable run; release
            # pinning shapes who claims, not when the fleet wakes.
            "release": None,
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
