"""Telling other processes that a row is ready, instead of waiting to be asked."""

from __future__ import annotations

import asyncio
import datetime
import logging
from collections.abc import Collection

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import QueuePool

from reflex_workflow.engine.runtime import Runtime

logger = logging.getLogger(__name__)

# The one channel every worker listens on; the payload names the table.
CHANNEL = "reflex_workflow"

# How long to wait before listening again after the connection breaks.
RECONNECT = datetime.timedelta(seconds=1)


async def announce(session: AsyncSession, table: str) -> None:
    """Say that a table has work ready, when this transaction commits.

    Postgres holds the notification until commit and drops it if the transaction
    rolls back, so a run that was never written is never announced.

    Args:
        session: The transaction doing the writing.
        table: The table that now has work.
    """
    await session.execute(select(func.pg_notify(CHANNEL, table)))


async def listen_once(
    runtime: Runtime,
    tables: frozenset[str],
    sessions: async_sessionmaker[AsyncSession],
) -> bool:
    """Listen on one connection until it breaks, waking the worker as it goes.

    Args:
        runtime: The running engine, whose wake event this sets.
        tables: The tables to wake for; empty wakes for everything.
        sessions: Where the listening connection comes from.

    Returns:
        Whether listening is worth trying again.
    """
    try:
        async with sessions() as session:
            connection = await session.connection(
                execution_options={"isolation_level": "AUTOCOMMIT"}
            )
            await connection.exec_driver_sql(f"LISTEN {CHANNEL}")
            raw = await connection.get_raw_connection()
            driver = raw.driver_connection
            notifies = getattr(driver, "notifies", None)
            if notifies is None:
                logger.info(
                    "reflex_workflow cannot listen with %s; workers will poll",
                    type(driver).__name__,
                )
                return False
            async for notice in notifies():
                if not tables or notice.payload in tables:
                    runtime.wake.set()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("reflex_workflow lost its listening connection")
    return True


def can_spare_a_connection(runtime: Runtime) -> bool:
    """Tell whether the pool can hold a connection open to listen on.

    Listening keeps one connection for as long as the worker runs. A pool that
    can only ever hand out one would give it to the listener and leave the claims
    waiting on it forever.

    Args:
        runtime: The running engine.

    Returns:
        Whether the pool has room for the listener and the work beside it.
    """
    bind = runtime.session_factory.kw.get("bind")
    pool = getattr(getattr(bind, "sync_engine", None), "pool", None)
    if not isinstance(pool, QueuePool):
        return True
    overflow = pool._max_overflow
    return overflow < 0 or pool.size() + overflow >= 2


async def wake_on_notify(
    runtime: Runtime,
    tables: Collection[str],
    listen_engine: AsyncEngine | None = None,
) -> None:
    """Wake this worker whenever another process says one of its tables is ready.

    The worker still polls: this only shortens the wait from the poll interval to
    the round trip. A driver with no way to listen, or a connection that keeps
    breaking, therefore costs latency rather than correctness.

    Args:
        runtime: The running engine, whose wake event this sets.
        tables: The tables this worker runs; notifications about others are
            ignored rather than starting a pass that would find nothing.
        listen_engine: Where to listen, when it cannot be where the steps run.
            A pooler in transaction mode -- Neon's pooled endpoint, PgBouncer --
            hands a different connection back with every statement, so it never
            delivers what a ``LISTEN`` on it would have heard; point this at the
            direct endpoint and the steps keep the pool.
    """
    sessions = runtime.session_factory
    if listen_engine is not None:
        sessions = async_sessionmaker(listen_engine, expire_on_commit=False)
    elif not can_spare_a_connection(runtime):
        logger.info(
            "reflex_workflow's connection pool has no room to listen; workers will poll"
        )
        return
    wanted = frozenset(tables)
    # Backing off before reconnecting, rather than waiting on a condition: what
    # this waits for is a database that is not answering.
    while await listen_once(runtime, wanted, sessions):  # noqa: ASYNC110
        await asyncio.sleep(RECONNECT.total_seconds())
