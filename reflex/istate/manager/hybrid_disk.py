import asyncio
import contextlib
import dataclasses
import enum
from hashlib import md5
from pathlib import Path
import time
import uuid
from typing import TypedDict, override

import aiosqlite

from reflex.environment import environment
from reflex.istate.manager.disk import StateManagerDisk
from reflex.state import BaseState, _split_substate_key
from reflex.utils.exceptions import ReflexError


class LeaseLostBeforeWriteError(ReflexError):
    """Error raised when a lease is lost before writing."""


@dataclasses.dataclass(frozen=True)
class QueueItem:
    token: str
    state: BaseState
    timestamp: float


class AcquireLeaseOutcome(enum.Enum):
    ACQUIRED = enum.auto()
    ALREADY_OWNED = enum.auto()
    FAILED = enum.auto()


@dataclasses.dataclass
class LeaseData:
    instance_id: str
    contend: bool


@dataclasses.dataclass
class StateManagerHybridDisk(StateManagerDisk):
    """Caching state manager that implements token leasing.

    Token leasing avoids writing to disk for every state change,
    and allows dynamic reloading of state from disk.

    Safe for multi process use!
    """

    _db: aiosqlite.Connection | None = None
    _instance_id: uuid.UUID = dataclasses.field(default_factory=uuid.uuid4, init=False)
    _leased_tokens: dict[str, LeaseData] = dataclasses.field(default_factory=dict, init=False)

    _write_debounce_seconds: float = 1.0
    _write_queue: dict[str, QueueItem] = dataclasses.field(
        default_factory=dict, init=False
    )
    _write_queue_task: asyncio.Task | None = dataclasses.field(
        default=None, init=False
    )

    _instance_heartbeat_seconds: float = 2.0
    _heartbeat_task: asyncio.Task | None = dataclasses.field(default=None, init=False)
    _should_stop: bool = dataclasses.field(default=False, init=False)

    async def db(self) -> aiosqlite.Connection:
        if self._db is None:
            self._db = await aiosqlite.connect(self.states_directory / "leases.db")
            await self._init_db(self._db)
        return self._db

    async def _init_db(self, db: aiosqlite.Connection):
        await db.execute("PRAGMA journal_mode=WAL") # Enable Write-Ahead Logging for better concurrency
        await db.execute(f"PRAGMA busy_timeout = {int(self._instance_heartbeat_seconds * 1000)}") # Set timeout to 2 seconds
        await db.execute("""
            CREATE TABLE IF NOT EXISTS instance (
                id TEXT PRIMARY KEY,
                heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lease (
                token TEXT PRIMARY KEY,
                instance_id TEXT NOT NULL REFERENCES instance(id) ON DELETE CASCADE,
                lock_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                contend BOOLEAN DEFAULT 0
            );""")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_lease_instance ON lease(instance_id);")
        await db.commit()

    async def _kill_stale_instances(self):
        """Remove leases held by instances that have not heartbeated recently."""
        db = await self.db()
        async with db.cursor() as cursor:
            await cursor.execute(
                "DELETE FROM instance WHERE "
                "strftime('%s','now') - strftime('%s', heartbeat) > ?"
                "RETURNING id",
                (self._instance_heartbeat_seconds * 2,),
            )
            print("Cleaned up stale instances:", [row[0] async for row in cursor])
        await db.execute(
            "DELETE FROM lease WHERE instance_id NOT IN (SELECT id FROM instance)"
        )
        await db.commit()

    async def _heartbeat(self):
        """Update the heartbeat for this instance."""
        if self._should_stop:
            return
        db = await self.db()
        await db.execute(
            "INSERT OR REPLACE INTO instance (id) VALUES (?)",
            (str(self._instance_id),)
        )
        await db.commit()
        await self._kill_stale_instances()
        # Schedule the next heartbeat.
        asyncio.get_event_loop().call_later(
            self._instance_heartbeat_seconds,
            self._schedule_heartbeat,
        )

    def _schedule_heartbeat(self) -> asyncio.Task:
        """Schedule the heartbeat task."""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat())
        return self._heartbeat_task

    async def _process_write_queue(self):
        """coroutine that checks for states to write to disk."""
        leased_tokens = await self._refresh_lease_data()
        contended_leases = {
            token for token, lease_data in leased_tokens.items() if lease_data.contend
        }
        # sort the _write_queue by oldest timestamp and exclude items younger than debounce time
        now = time.time()
        items_to_write = sorted(
            (
                item
                for item in self._write_queue.values()
                if item.token in contended_leases or now - item.timestamp >= self._write_debounce_seconds
            ),
            key=lambda item: (item.token not in contended_leases, item.timestamp),
        )
        failed_writes = []
        if items_to_write:
            print("WQ:", [item.token for item in items_to_write])
        for item in items_to_write:
            token = item.token
            client_token, _ = _split_substate_key(token)
            if client_token not in leased_tokens:
                # We lost the lease in the database, cannot safely write :(
                failed_writes.append(self._write_queue.pop(token))
                continue
            await self.set_state_for_substate(
                client_token,
                self._write_queue.pop(token).state
            )
            if leased_tokens[client_token].contend:
                # Another instance wants the lease, release it immediately.
                await self._release_lease(client_token)
        if self._write_queue:
            # There are still items in the queue, schedule another run.
            now = time.time()
            next_write_in = min(
                self._write_debounce_seconds - (now - item.timestamp)
                for item in self._write_queue.values()
            )
            await asyncio.sleep(next_write_in)
            self._schedule_write_queue()
        if failed_writes and not self._should_stop:
            msg = f"Lost lease before writing for tokens: {[item.token for item in failed_writes]}"
            raise LeaseLostBeforeWriteError(msg)

    def _schedule_write_queue(self) -> asyncio.Task:
        """Initialize the write queue processing task."""
        if self._should_stop:
            print("Waring: Scheduling _process_write_queue after close()")
        if self._write_queue_task is None or self._write_queue_task.done():
            self._write_queue_task = asyncio.create_task(self._process_write_queue())
        return self._write_queue_task

    async def _maybe_acquire_lease(self, client_token: str) -> AcquireLeaseOutcome:
        """Maybe acquire a lease for a token.

        Args:
            client_token: The token to acquire the lease for.

        Returns:
            True if the lease was acquired, False otherwise.
        """
        if self._should_stop:
            # Do NOT acquire leases after stopping.
            return AcquireLeaseOutcome.FAILED
        self._schedule_heartbeat()
        try:
            db = await self.db()
            await db.execute(
                "INSERT INTO lease (token, instance_id) VALUES (?, ?)",
                (client_token, str(self._instance_id)),
            )
            await db.commit()
            self._leased_tokens[client_token] = LeaseData(
                instance_id=str(self._instance_id),
                contend=False,
            )
        except aiosqlite.IntegrityError:
            pass
        else:
            return AcquireLeaseOutcome.ACQUIRED
        return AcquireLeaseOutcome.FAILED

    async def _release_lease(self, client_token: str):
        """Release a lease for a token.

        Args:
            client_token: The token to release the lease for.
        """
        db = await self.db()
        await db.execute(
            "DELETE FROM lease WHERE token = ? AND instance_id = ?",
            (client_token, str(self._instance_id)),
        )
        await db.commit()
        self._leased_tokens.pop(client_token, None)

    async def _contend_lease(self, client_token: str):
        """Mark a lease as contended.

        Args:
            client_token: The token to mark as contended.
        """
        db = await self.db()
        await db.execute(
            "UPDATE lease SET contend = 1 WHERE token = ?",
            (client_token,),
        )
        await db.commit()

    async def _lease(self, token: str) -> AcquireLeaseOutcome:
        """Attempt to lease a token.

        Args:
            token: The token to lease.

        Returns:
            True if the lease was acquired, False otherwise.
        """
        client_token, _ = _split_substate_key(token)
        # FAST PATH: Check if our instance already should have the lease
        if client_token in self._leased_tokens:
            # We already should have the lease, no one could have taken it from us
            return AcquireLeaseOutcome.ALREADY_OWNED
        # SLOW PATH: Wait for the lease to be free and try to acquire it
        deadline = time.time() + environment.REFLEX_STATE_LEASE_ACQUIRE_TIMEOUT.get()
        while (lease_acquired := await self._maybe_acquire_lease(client_token)) == AcquireLeaseOutcome.FAILED:
            # Someone else has the lease, mark as contended and wait.
            await self._contend_lease(client_token)
            if time.time() > deadline:
                break
            await asyncio.sleep(0.2)
        return lease_acquired

    async def _refresh_lease_data(self) -> dict[str, LeaseData]:
        """Get the set of leases owned by this instance.

        This will occur before any writing to ensure we still own the leases.

        Returns:
            The updated _leased_tokens mapping.
        """
        db = await self.db()
        async with db.cursor() as cursor:
            try:
                await cursor.execute(
                    "SELECT token, contend FROM lease WHERE instance_id = ?",
                    (str(self._instance_id),)
                )
            except aiosqlite.OperationalError:
                if "database is locked" in str(e):
                    # The database is locked, likely due to another process writing.
                    # We will just keep our existing lease data and try again later.
                    return self._leased_tokens
            rows = await cursor.fetchall()
            self._leased_tokens = {
                row[0]: LeaseData(
                    instance_id=str(self._instance_id),
                    contend=self._should_stop or bool(row[1])
                )
                for row in rows
            }
        return self._leased_tokens

    @override
    async def get_state(
        self,
        token: str,
    ) -> BaseState:
        """Get the state for a token.

        Args:
            token: The token to get the state for.

        Returns:
            The state for the token.
        """
        client_token = _split_substate_key(token)[0]
        lease_outcome = await self._lease(client_token)

        if lease_outcome == AcquireLeaseOutcome.FAILED:
            msg = f"Failed to acquire lease for token {token}."
            raise RuntimeError(msg)

        if lease_outcome == AcquireLeaseOutcome.ALREADY_OWNED:
            # We already have the lease, so we can just return the in-memory state if it exists.
            root_state = self.states.get(client_token)
            if root_state is not None:
                return root_state

        # We just got the lease or the memory state was not found.
        return await self._load_root_state(token)

    @override
    async def set_state(self, token: str, state: BaseState):
        """Set the state for a token.

        Args:
            token: The token to set the state for.
            state: The state to set.
        """
        # The state had direct memory access to munge the state, so we just queue it for writing now.
        self._write_queue[token] = QueueItem(
            token=token, state=state, timestamp=time.time()
        )
        self._schedule_write_queue()

    async def close(self):
        """Close the state manager, ensuring all states are written to disk."""
        self._should_stop = True
        while self._write_queue:
            await self._schedule_write_queue()
        db = await self.db()
        await db.execute(
            "DELETE FROM instance WHERE id = ?",
            (str(self._instance_id),)
        )
        await db.commit()
        await db.close()
        self._db = None
