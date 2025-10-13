import asyncio
from collections.abc import AsyncIterator, Iterator
import contextlib
import dataclasses
import enum
from hashlib import md5
import logging
from pathlib import Path
import random
import sqlite3
import threading
import time
import uuid
from typing import TypedDict, override

import aiosqlite

from reflex.environment import environment
from reflex.istate.manager.disk import StateManagerDisk
from reflex.state import BaseState, _split_substate_key
from reflex.utils.exceptions import ReflexError


logger = logging.getLogger(__name__)
logging.basicConfig(format="[%(asctime)s] %(name)s.%(levelname)s %(message)s", level=logging.DEBUG)


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


@dataclasses.dataclass(frozen=True)
class HeartbeatThread:
    _db_file: Path
    _instance_id: uuid.UUID
    _heartbeat_seconds: float
    _stop_event: threading.Event = dataclasses.field(default_factory=threading.Event)
    _db: sqlite3.Connection | None = dataclasses.field(default=None, init=False)
    _exceptions: list[BaseException] = dataclasses.field(default_factory=list, init=False)

    # The actual underlying thread (for joining, etc).
    thread: threading.Thread = dataclasses.field(init=False)

    # The main state manager can respond to this event to query and release leases without pending writes.
    lease_contention_event: asyncio.Event = dataclasses.field(
        default_factory=asyncio.Event, init=False
    )

    @classmethod
    def launch(cls, db_file: Path, instance_id: uuid.UUID, heartbeat_seconds: float) -> "HeartbeatThread":
        """Launch the heartbeat thread."""
        heartbeat = cls(
            _db_file=db_file,
            _instance_id=instance_id,
            _heartbeat_seconds=heartbeat_seconds,
        )
        thread = threading.Thread(
            target=heartbeat.run,
            name=f"HeartbeatThread-{instance_id}",
            daemon=True,
        )
        object.__setattr__(heartbeat, "thread", thread)
        thread.start()
        return heartbeat

    def db(self) -> sqlite3.Connection:
        if self._db is None:
            db = sqlite3.connect(self._db_file)
            db.execute("PRAGMA journal_mode=WAL") # Enable Write-Ahead Logging for better concurrency
            db.execute(f"PRAGMA busy_timeout = {int(self._heartbeat_seconds * 1000)}") # Set timeout to 2 seconds
            object.__setattr__(self, "_db", db)
            return db
        return self._db

    @contextlib.contextmanager
    def _db_query_with_retry(self, query, params=(), retries=5, delay=0.1) -> Iterator[sqlite3.Cursor]:
        db = self.db()
        for attempt in range(retries):
            try:
                cursor = db.cursor()
                try:
                    cursor.execute(query, params)
                    yield cursor
                finally:
                    cursor.close()
                db.commit()
            except sqlite3.Error as e:  # noqa: PERF203
                db.rollback()
                if "database is locked" in str(e):
                    time.sleep(delay * attempt)
                else:
                    raise
            else:
                return
        msg = f"Failed to execute query after {retries} retries: {query} {params}"
        raise ReflexError(msg)

    def _db_execute_with_retry(self, query, params=(), retries=5, delay=0.1):
        with self._db_query_with_retry(query, params, retries, delay):
            pass

    def run(self):
        try:
            while not self._stop_event.is_set():
                try:
                    self._heartbeat()
                except BaseException as e:
                    self._exceptions.append(e)
                    logger.exception(f"Heartbeat thread {self._instance_id} exiting due to exception:")
                    return
                time.sleep(self._heartbeat_seconds)
        finally:
            if self._db is not None:
                self._db.close()

    def _kill_stale_instances(self):
        """Remove leases held by instances that have not heartbeated recently."""
        if not self.lease_contention_event.is_set():
            with self._db_query_with_retry(
                "SELECT COUNT(token) FROM lease WHERE instance_id = ? AND contend = 1",
                (str(self._instance_id),),
            ) as cursor:
                result = cursor.fetchone()
                if result is not None and result[0] > 0:
                    logger.info(f"{self._instance_id=} Detected lease contention, setting event")
                    self.lease_contention_event.set()
        with self._db_query_with_retry(
            "SELECT count(id) FROM instance WHERE "
            "strftime('%s','now') - strftime('%s', heartbeat) > ?",
            (self._heartbeat_seconds * 2,),
        ) as cursor:
            result = cursor.fetchone()

        if result is not None and result[0] > 0:
            with self._db_query_with_retry(
                "DELETE FROM instance WHERE "
                "strftime('%s','now') - strftime('%s', heartbeat) > ? "
                "RETURNING id",
                (self._heartbeat_seconds * 2,),
            ) as cursor:
                logger.info(f"{self._instance_id=} Cleaned up stale instances: {[row[0] for row in cursor]}")
            self._db_execute_with_retry(
                "DELETE FROM lease WHERE instance_id NOT IN (SELECT id FROM instance)"
            )

    def _heartbeat(self):
        """Update the heartbeat for this instance."""
        self._db_execute_with_retry(
            "INSERT OR REPLACE INTO instance (id) VALUES (?)",
            (str(self._instance_id),)
        )
        logger.debug(f"Heartbeat from instance {self._instance_id}")
        self._kill_stale_instances()


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
    _heartbeat_thread: HeartbeatThread | None = dataclasses.field(default=None, init=False)
    _lease_contention_task: asyncio.Task | None = dataclasses.field(default=None, init=False)
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
        self._heartbeat_thread = HeartbeatThread.launch(
            db_file=self.states_directory / "leases.db",
            instance_id=self._instance_id,
            heartbeat_seconds=self._instance_heartbeat_seconds,
        )
        self._lease_contention_task = asyncio.create_task(self._handle_lease_contention())
        logger.info(f"Started {self._heartbeat_thread=} {self._lease_contention_task=}")

    @contextlib.asynccontextmanager
    async def _db_query_with_retry(self, query, params=(), retries=5, delay=0.1) -> AsyncIterator[aiosqlite.Cursor]:
        db = await self.db()
        for attempt in range(retries):
            try:
                async with db.cursor() as cursor:
                    await cursor.execute(query, params)
                    yield cursor
                    await db.commit()
            except aiosqlite.Error as e:  # noqa: PERF203
                await db.rollback()
                if "database is locked" in str(e):
                    await asyncio.sleep(delay * attempt)
                else:
                    raise
            else:
                return
        msg = f"Failed to execute query after {retries} retries"
        raise ReflexError(msg)

    async def _db_execute_with_retry(self, query, params=(), retries=5, delay=0.1):
        async with self._db_query_with_retry(query, params, retries, delay):
            pass

    async def _handle_lease_contention(self):
        """Remove leases held by this instances that are in contention."""
        if self._heartbeat_thread is None:
            return
        # Clear any contended leases we hold that do not have pending writes.
        while not self._should_stop:
            logger.debug(f"{self._instance_id=} Waiting for lease contention event")
            await self._heartbeat_thread.lease_contention_event.wait()
            logger.debug(f"{self._instance_id=} Detected lease contention event, releasing leases with no pending writes")
            async with self._db_query_with_retry(
                "SELECT token FROM lease WHERE instance_id = ? AND contend = 1",
                (str(self._instance_id),),
            ) as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    token = row[0]
                    if token not in self._write_queue:
                        logger.debug(f"{self._instance_id=} releasing contended lease on {token} with no pending writes")
                        await self._release_lease(token)
            self._heartbeat_thread.lease_contention_event.clear()

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
            logger.debug(f"WQ {self._instance_id=}: {[(item.token, now - item.timestamp) for item in items_to_write]}")
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
                logger.debug(f"{self._instance_id=} releasing contended lease on {token} after writes")
                await self._release_lease(client_token)
        if self._write_queue:
            # There are still items in the queue, schedule another run.
            now = time.time()
            next_write_in = min(
                self._write_debounce_seconds - (now - item.timestamp)
                for item in self._write_queue.values()
            )
            await asyncio.sleep(next_write_in)
            self._write_queue_task = None
            asyncio.get_event_loop().call_soon(self._schedule_write_queue)
        if failed_writes and not self._should_stop:
            msg = f"Lost lease before writing for tokens: {[(item.token, now - item.timestamp) for item in failed_writes]}"
            raise LeaseLostBeforeWriteError(msg)

    def _schedule_write_queue(self) -> asyncio.Task:
        """Initialize the write queue processing task."""
        if self._should_stop:
            logger.warning("Waring: Scheduling _process_write_queue after close()")
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
        with contextlib.suppress(Exception):
            await self._db_execute_with_retry(
                "INSERT INTO lease (token, instance_id) VALUES (?, ?)",
                (client_token, str(self._instance_id)),
            )
            self._leased_tokens[client_token] = LeaseData(
                instance_id=str(self._instance_id),
                contend=False,
            )
            return AcquireLeaseOutcome.ACQUIRED
        return AcquireLeaseOutcome.FAILED

    async def _release_lease(self, client_token: str):
        """Release a lease for a token.

        Args:
            client_token: The token to release the lease for.
        """
        await self._db_execute_with_retry(
            "DELETE FROM lease WHERE token = ? AND instance_id = ?",
            (client_token, str(self._instance_id)),
        )
        self._leased_tokens.pop(client_token, None)

    async def _contend_lease(self, client_token: str) -> bool:
        """Mark a lease as contended.

        Args:
            client_token: The token to mark as contended.
        """
        async with self._db_query_with_retry(
            "UPDATE lease SET contend = 1 WHERE token = ? RETURNING instance_id",
            (client_token,),
        ) as cursor:
            row = await cursor.fetchone()
            if row is not None:
                logger.info(f"{self._instance_id=} Contending for lease on {client_token} held by {row[0]}")
        return True

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
        is_contended = False
        sleep_time = 0.2
        while (lease_acquired := await self._maybe_acquire_lease(client_token)) == AcquireLeaseOutcome.FAILED:
            if time.time() > deadline:
                break
            if not is_contended:
                # Someone else has the lease, mark as contended and wait.
                is_contended = await self._contend_lease(client_token)
            await asyncio.sleep(sleep_time)
            sleep_time = min(sleep_time * 2, 2.0)  # Exponential backoff up to 2 seconds
        return lease_acquired

    async def _refresh_lease_data(self) -> dict[str, LeaseData]:
        """Get the set of leases owned by this instance.

        This will occur before any writing to ensure we still own the leases.

        Returns:
            The updated _leased_tokens mapping.
        """
        async with self._db_query_with_retry(
            "SELECT token, contend FROM lease WHERE instance_id = ?",
            (str(self._instance_id),)
        ) as cursor:
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
        lease_outcome = await asyncio.create_task(self._lease(client_token))

        if lease_outcome == AcquireLeaseOutcome.FAILED:
            msg = f"Failed to acquire lease for {token=} {self._instance_id=}."
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
        if self._heartbeat_thread is not None:
            self._heartbeat_thread._stop_event.set()
        self._should_stop = True
        while self._write_queue:
            await self._schedule_write_queue()
        if self._db is not None:
            await self._db_execute_with_retry(
                "DELETE FROM instance WHERE id = ?",
                (str(self._instance_id),)
            )
            await self._db.close()
            self._db = None
        if self._lease_contention_task is not None:
            self._lease_contention_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._lease_contention_task
        if self._heartbeat_thread is not None:
            logger.debug("Stopping heartbeat thread")
            self._heartbeat_thread.thread.join(timeout=5)