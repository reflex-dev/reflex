"""The running engine's shared state."""

from __future__ import annotations

import asyncio
import dataclasses
import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class Settled:
    """Counts the passes a worker made without claiming anything.

    A pass that claims nothing is the worker saying there is nothing it can
    take: either nothing is due, or what is due is held back by a limit. Both
    are answers, so both end a wait for the worker to catch up.
    """

    def __init__(self) -> None:
        """Start with no passes counted and nobody waiting."""
        self.passes = 0
        self.changed = asyncio.Condition()

    async def record(self) -> None:
        """Count a pass that claimed nothing, and tell whoever is waiting."""
        async with self.changed:
            self.passes += 1
            self.changed.notify_all()

    async def after(self, seen: int, timeout: datetime.timedelta) -> bool:
        """Wait for a pass that claimed nothing, later than the one given.

        Args:
            seen: The count read before the worker was told to look.
            timeout: How long to wait for it.

        Returns:
            Whether such a pass happened in time.
        """
        try:
            async with self.changed:
                await asyncio.wait_for(
                    self.changed.wait_for(lambda: self.passes > seen),
                    timeout.total_seconds(),
                )
        except (TimeoutError, asyncio.TimeoutError):
            return False
        return True


@dataclasses.dataclass(frozen=True, slots=True)
class Runtime:
    """What a worker needs to run steps.

    Attributes:
        session_factory: Session factory for the database with the workflow tables.
        wake: Set to make the worker look for due rows now.
        lease: How long a claim lasts without renewal.
        listening: Set while this worker is hearing what other processes write.
            Only then can it afford to sleep past its poll interval: with
            nothing listening, polling is the only way work written elsewhere
            is ever noticed.
        settled: Counts the passes that found nothing to claim, so a caller can
            wait for the worker to have caught up rather than guess at it.
    """

    session_factory: async_sessionmaker[AsyncSession]
    wake: asyncio.Event
    lease: datetime.timedelta
    listening: asyncio.Event = dataclasses.field(default_factory=asyncio.Event)
    settled: Settled = dataclasses.field(default_factory=Settled)


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
