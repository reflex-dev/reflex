"""The running engine's shared state."""

from __future__ import annotations

import asyncio
import dataclasses
import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclasses.dataclass(frozen=True, slots=True)
class Runtime:
    """What a worker needs to run steps.

    Attributes:
        session_factory: Session factory for the database with the workflow tables.
        wake: Set to make the worker look for due rows now.
        lease: How long a claim lasts without renewal.
    """

    session_factory: async_sessionmaker[AsyncSession]
    wake: asyncio.Event
    lease: datetime.timedelta


_current: Runtime | None = None


def current() -> Runtime:
    """Return the engine running in this process.

    Returns:
        The runtime set by ``run_workflows``.

    Raises:
        RuntimeError: If no engine is running.
    """
    if _current is None:
        msg = (
            "reflex_workflow is not set up in this process; enter "
            "run_workflows(...) to run steps here, or connect_workflows(...) to "
            "start and advance runs that other processes run."
        )
        raise RuntimeError(msg)
    return _current


def set_current(runtime: Runtime | None) -> None:
    """Set or clear the engine running in this process.

    Args:
        runtime: The runtime, or None when the engine stops.
    """
    global _current
    _current = runtime


def replace_current(runtime: Runtime | None) -> Runtime | None:
    """Set the engine for this process, returning what it replaced.

    Nesting is what makes this useful: a process that connects inside a block
    where it is already running puts the runner's own runtime back on the way out.

    Args:
        runtime: The runtime to set, or None to clear it.

    Returns:
        The runtime that was in place.
    """
    global _current
    previous, _current = _current, runtime
    return previous
