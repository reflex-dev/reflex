"""Telling other processes that a row is ready, instead of waiting to be asked."""

from __future__ import annotations

import asyncio
import datetime
import logging
from collections.abc import Collection

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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


async def listen_once(runtime: Runtime, tables: frozenset[str]) -> bool:
    """Listen on one connection until it breaks, waking the worker as it goes.

    Args:
        runtime: The running engine, whose wake event this sets.
        tables: The tables to wake for; empty wakes for everything.

    Returns:
        Whether listening is worth trying again.
    """
    try:
        async with runtime.session_factory() as session:
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


async def wake_on_notify(runtime: Runtime, tables: Collection[str]) -> None:
    """Wake this worker whenever another process says one of its tables is ready.

    The worker still polls: this only shortens the wait from the poll interval to
    the round trip. A driver with no way to listen, or a connection that keeps
    breaking, therefore costs latency rather than correctness.

    Args:
        runtime: The running engine, whose wake event this sets.
        tables: The tables this worker runs; notifications about others are
            ignored rather than starting a pass that would find nothing.
    """
    wanted = frozenset(tables)
    # Backing off before reconnecting, rather than waiting on a condition: what
    # this waits for is a database that is not answering.
    while await listen_once(runtime, wanted):  # noqa: ASYNC110
        await asyncio.sleep(RECONNECT.total_seconds())
