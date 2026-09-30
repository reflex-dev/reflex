"""A state manager that stores states in redis."""

import asyncio
import contextlib
import dataclasses
import inspect
import logging
import os
import sys
import time
import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import timedelta
from typing import Any, TypedDict, cast

from redis import ResponseError
from redis.asyncio import Redis
from reflex_base.config import get_config
from reflex_base.environment import environment, oplock_hold_time
from reflex_base.utils.exceptions import (
    EnvironmentVarValueError,
    InvalidLockWarningThresholdError,
    LockExpiredError,
    StateSchemaMismatchError,
)
from typing_extensions import Unpack, override

from reflex.istate.manager import (
    StateLease,
    StateManager,
    StateModificationContext,
    _default_token_expiration,
)
from reflex.istate.manager.token import StateToken
from reflex.utils.tasks import ensure_task

logger = logging.getLogger(__name__)

NOTIFY_KEYSPACE_EVENTS = (
    "K"  # Enable keyspace notifications (target a particular key)
    "$"  # For String commands (like setting keys)
    "s"  # For Set commands (SADD, SREM, etc)
    "g"  # For generic commands (DEL, EXPIRE, etc)
    "x"  # For expired events
    "e"  # For evicted events (i.e. maxmemory exceeded)
)


async def enable_keyspace_notifications(
    redis: Redis, events: str = NOTIFY_KEYSPACE_EVENTS
) -> None:
    """Enable keyspace notifications for the redis server.

    Args:
        redis: The redis client to configure.
        events: The keyspace notification flags to set.

    Raises:
        ResponseError: when the keyspace config cannot be set.
    """
    try:
        await redis.config_set("notify-keyspace-events", events)
    except ResponseError:
        # Some redis servers only allow out-of-band configuration, so ignore errors here.
        if not environment.REFLEX_IGNORE_REDIS_CONFIG_ERROR.get():
            raise


def _default_lock_expiration() -> int:
    """Get the default lock expiration time.

    Returns:
        The default lock expiration time.
    """
    return get_config().redis_lock_expiration


def _default_lock_warning_threshold() -> int:
    """Get the default lock warning threshold.

    Returns:
        The default lock warning threshold.
    """
    return get_config().redis_lock_warning_threshold


def _default_oplock_hold_time_ms() -> int:
    """Get the default opportunistic lock hold time.

    Returns:
        The default opportunistic lock hold time.

    Raises:
        EnvironmentVarValueError: If the configured hold time is negative.
    """
    hold_time = oplock_hold_time()
    if hold_time < timedelta(0):
        msg = (
            "The opportunistic lock hold time must not be negative, got "
            f"{hold_time.total_seconds()} seconds."
        )
        raise EnvironmentVarValueError(msg)
    if not hold_time:
        return _default_lock_expiration() // 2
    # A configured hold time is worth at least one millisecond, so that a
    # sub-millisecond duration is not mistaken for the unset default above.
    return max(hold_time // timedelta(milliseconds=1), 1)


# The lock waiter task should subscribe to lock channel updates within this period.
LOCK_SUBSCRIBE_TASK_TIMEOUT = 2  # seconds


SMR = f"[SMR:{os.getpid()}]"
start = time.monotonic()


class RedisPubSubMessage(TypedDict):
    """A Redis Pub/Sub message."""

    type: str
    pattern: bytes | None
    channel: bytes
    data: bytes | int


class OplockFound(Exception):  # noqa: N818
    """Indicates that an opportunistic lock was found."""


@dataclasses.dataclass(slots=True)
class _LeasedStates:
    """The states cached under this process' lease on an ident."""

    # The tokens and states, by the str of their token.
    states: dict[str, tuple[StateToken, Any]] = dataclasses.field(default_factory=dict)
    # The str of the tokens of the states touched since they were written.
    touched: set[str] = dataclasses.field(default_factory=set)


@dataclasses.dataclass(frozen=True, slots=True)
class RedisStateLease(StateLease):
    """A lease on a redis lock, possibly held locally under this process' lease."""

    # The states cached under this process' lease, when holding it.
    leased: _LeasedStates | None = None


@dataclasses.dataclass
class StateManagerRedis(StateManager):
    """A state manager that stores states in redis."""

    # The redis client to use.
    redis: Redis

    # The token expiration time (s).
    token_expiration: int = dataclasses.field(default_factory=_default_token_expiration)

    # The maximum time to hold a lock (ms).
    lock_expiration: int = dataclasses.field(default_factory=_default_lock_expiration)

    # The maximum time to hold a lock (ms) before warning.
    lock_warning_threshold: int = dataclasses.field(
        default_factory=_default_lock_warning_threshold
    )

    # How long to opportunistically hold the redis lock in milliseconds (must be less than the token expiration).
    oplock_hold_time_ms: int = dataclasses.field(
        default_factory=_default_oplock_hold_time_ms
    )

    # The keyspace subscription string when redis is waiting for lock to be released.
    _redis_notify_keyspace_events: str = dataclasses.field(
        default=NOTIFY_KEYSPACE_EVENTS
    )

    # These events indicate that a lock is no longer held.
    _redis_keyspace_lock_release_events: set[bytes] = dataclasses.field(
        default_factory=lambda: {
            b"del",
            b"expired",
            b"evicted",
        }
    )

    # Whether keyspace notifications have been enabled.
    _redis_notify_keyspace_events_enabled: bool = dataclasses.field(default=False)

    # The mutex ensures the dict of mutexes is updated exclusively
    _state_manager_lock: asyncio.Lock = dataclasses.field(
        default_factory=asyncio.Lock, init=False
    )

    # Whether to opportunistically hold locks for fast in-memory access.
    _oplock_enabled: bool = dataclasses.field(
        default_factory=environment.REFLEX_OPLOCK_ENABLED.get, init=False
    )

    # The states cached under this process' lease on an ident, by ident.
    _cached_states: dict[str, _LeasedStates] = dataclasses.field(
        default_factory=dict, init=False
    )
    _cached_states_locks: dict[str, asyncio.Lock] = dataclasses.field(
        default_factory=dict, init=False
    )

    # Local Leases (token -> flush task)
    _local_leases: dict[str, asyncio.Task] = dataclasses.field(
        default_factory=dict, init=False
    )
    # The unique ID for this state manager, the domain for _local_leases.
    _instance_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))

    # Lock waiters for redis per-token lock.
    _lock_waiters: dict[bytes, list[asyncio.Event]] = dataclasses.field(
        default_factory=dict,
        init=False,
    )
    _lock_updates_subscribed: asyncio.Event = dataclasses.field(
        default_factory=asyncio.Event,
        init=False,
    )
    _lock_task: asyncio.Task | None = dataclasses.field(default=None, init=False)

    # Whether debug prints are enabled.
    _debug_enabled: bool = dataclasses.field(
        default=environment.REFLEX_STATE_MANAGER_REDIS_DEBUG.get(),
        init=False,
    )

    def __post_init__(self):
        """Validate the lock warning threshold.

        Raises:
            InvalidLockWarningThresholdError: If the lock warning threshold is invalid.
        """
        if self.lock_warning_threshold >= (lock_expiration := self.lock_expiration):
            msg = f"The lock warning threshold({self.lock_warning_threshold}) must be less than the lock expiration time({lock_expiration})."
            raise InvalidLockWarningThresholdError(msg)
        if self._oplock_enabled and self.oplock_hold_time_ms >= lock_expiration:
            msg = f"The opportunistic lock hold time({self.oplock_hold_time_ms}) must be less than the lock expiration time({lock_expiration})."
            raise InvalidLockWarningThresholdError(msg)
        with contextlib.suppress(RuntimeError):
            asyncio.get_running_loop()  # Check if we're in an event loop.
            self._ensure_lock_task()

    def _leased_states(self, ident: str) -> _LeasedStates | None:
        """Get the states cached under this process' lease on an ident.

        Args:
            ident: The ident.

        Returns:
            The leased states, or None when there is no lease.
        """
        if not self._oplock_enabled:
            return None
        return self._cached_states.get(ident)

    @override
    async def load_states(
        self, tokens: Sequence[StateToken], *, create: bool = True
    ) -> list[Any]:
        """Load the states for some tokens, from the lease cache or else from redis.

        Args:
            tokens: The tokens of the states to load.
            create: Whether to create the states that are not stored.

        Returns:
            The state for each token, in order.
        """
        states: list[Any] = [None] * len(tokens)
        to_fetch = []
        for index, token in enumerate(tokens):
            if (leased := self._leased_states(token.ident)) is not None and (
                entry := leased.states.get(str(token))
            ) is not None:
                states[index] = entry[1]
            else:
                to_fetch.append(index)
        if not to_fetch:
            return states

        redis_pipeline = self.redis.pipeline()
        for index in to_fetch:
            redis_pipeline.get(str(tokens[index]))
        for index, redis_state in zip(
            to_fetch, await redis_pipeline.execute(), strict=True
        ):
            token = tokens[index]
            state = None
            if redis_state is not None:
                # A schema mismatch is treated like a missing state.
                with contextlib.suppress(StateSchemaMismatchError):
                    state = token.deserialize(data=redis_state)
            if state is None and create:
                state = token.new_instance()
            if state is not None and (leased := self._leased_states(token.ident)):
                # Keep what was stored under the lease while fetching.
                state = leased.states.setdefault(str(token), (token, state))[1]
            states[index] = state
        return states

    async def _write_states(
        self,
        states: Sequence[tuple[StateToken, Any]],
        lease: StateLease | None,
        warn_held_too_long: bool = True,
        **context: Unpack[StateModificationContext],
    ) -> None:
        """Write states to redis, checking that the lock is still held.

        Args:
            states: The tokens and states to write.
            lease: The lease of the lock held on the states' ident, if any.
            warn_held_too_long: Whether to warn if the lock was held too long.
            context: The state modification context.

        Raises:
            LockExpiredError: If the lock of the lease is no longer held.
        """
        if lease is not None and (lock_id := lease.lock_id) is not None:
            lock_key = self._lock_key(lease.ident)
            # Check that we're holding the lock.
            if (existing_lock_id := await self.redis.get(lock_key)) != lock_id:
                msg = (
                    f"Lock expired for token {lease.ident} while processing. Consider increasing "
                    f"`app.state_manager.lock_expiration` (currently {self.lock_expiration}) "
                    "or use `@rx.event(background=True)` decorator for long-running tasks. "
                    f"Current lock id: {existing_lock_id!r}, expected lock id: {lock_id!r}."
                    + (
                        f" Happened in event: {event.name}"
                        if (event := context.get("event")) is not None
                        else ""
                    )
                )
                raise LockExpiredError(msg)
            if warn_held_too_long:
                time_taken = (
                    self.lock_expiration - (await self.redis.pttl(lock_key))
                ) / 1000
                if time_taken > self.lock_warning_threshold / 1000:
                    event_suffix = (
                        f" Happened in event: {event.name}"
                        if (event := context.get("event")) is not None
                        else ""
                    )
                    logger.warning(
                        f"Lock for token {lease.ident} was held too long {time_taken=}s, "
                        "use `@rx.event(background=True)` decorator for long-running "
                        f"tasks.{event_suffix}",
                        extra={"dedupe": True},
                    )
        pickled_states = [
            (str(token), pickle_state)
            for token, state in states
            if (pickle_state := token.serialize(state))
        ]
        if not pickled_states:
            return
        redis_pipeline = self.redis.pipeline()
        for key, pickle_state in pickled_states:
            redis_pipeline.set(key, pickle_state, ex=self.token_expiration)
        await redis_pipeline.execute()

    @override
    async def store_states(
        self,
        states: Sequence[tuple[StateToken, Any]],
        lease: StateLease | None,
        **context: Unpack[StateModificationContext],
    ) -> None:
        """Store the touched states, in the lease cache or else in redis.

        Args:
            states: The tokens and states to store.
            lease: The lease of the lock held on the states' ident, if any.
            context: The state modification context.
        """
        if isinstance(lease, RedisStateLease) and (leased := lease.leased) is not None:
            # Written to redis when the lease breaks.
            for token, state in states:
                key = str(token)
                leased.states[key] = (token, state)
                if token.get_and_reset_touched_state(state):
                    leased.touched.add(key)
            return
        await self._write_states(
            [
                (token, state)
                for token, state in states
                if token.get_and_reset_touched_state(state)
            ],
            lease,
            **context,
        )

    @override
    @contextlib.asynccontextmanager
    async def lock(
        self, token: StateToken, **context: Unpack[StateModificationContext]
    ) -> AsyncIterator[StateLease]:
        """Hold the exclusive lock on a token's ident.

        Args:
            token: The token to lock.
            context: The state modification context.

        Yields:
            The lease of the lock.
        """
        event_name = event.name if (event := context.get("event")) is not None else None
        if not self._oplock_enabled:
            async with self._lock(token, event_name=event_name) as lock_id:
                yield RedisStateLease(ident=token.ident, lock_id=lock_id)
            return
        while True:
            async with self._try_lock(token, event_name, **context) as lease:
                if lease is not None:
                    yield lease
                    return

    @contextlib.asynccontextmanager
    async def _try_lock(
        self,
        token: StateToken,
        event_name: str | None,
        **context: Unpack[StateModificationContext],
    ) -> AsyncIterator[RedisStateLease | None]:
        """Try to hold the lock on a token's ident, opportunistically keeping it leased.

        Args:
            token: The token to lock.
            event_name: The name of the event the lock is for.
            context: The state modification context.

        Yields:
            The lease of the lock, or None if it has to be tried again.
        """
        # Opportunistically reuse existing lock.
        async with self._lease_lock(token.ident) as lease:
            if lease is not None:
                yield lease
                self._notify_next_waiter(self._lock_key(token.ident))
                return

        # Opportunistic locking is enabled, so try to hold the lock across multiple calls.
        ident = token.ident
        lock_key = self._lock_key(ident)
        lock_held_ctx = contextlib.AsyncExitStack()
        try:
            lock_id = await lock_held_ctx.enter_async_context(
                self._lock(token, event_name=event_name)
            )
        except OplockFound:
            # While waiting for the lock, another process has acquired it, but we can piggy back.
            pass
        else:
            # Do not create a lease break task when multiple instances are waiting.
            if (
                not await self._get_local_lease(ident)
                and await self._n_lock_contenders(lock_key) > 0
            ):
                if self._debug_enabled:
                    logger.debug(
                        f"{SMR} [{time.monotonic() - start:.3f}] {ident} has contention, not leasing"
                    )
                async with lock_held_ctx:
                    yield RedisStateLease(ident=ident, lock_id=lock_id)
                return

            # Create the lease break task since we got the lock.
            if (
                new_lease_task := await self._create_lease_break_task(
                    token, lock_id, cleanup_ctx=lock_held_ctx, **context
                )
            ) is (
                current_lease_task := await self._get_local_lease(ident)
            ) and new_lease_task is not None:
                if self._debug_enabled:
                    logger.debug(
                        f"{SMR} [{time.monotonic() - start:.3f}] {ident} obtained lock {lock_id.decode()}."
                    )
            elif current_lease_task is None:
                # Check if we still have the redis lock, then just try to send this one update and release it.
                await self._try_extend_lock(lock_key)
                if await self.redis.get(lock_key) == lock_id:
                    if self._debug_enabled:
                        logger.debug(
                            f"{SMR} [{time.monotonic() - start:.3f}] {ident} holding lock {lock_id.decode()}, {new_lease_task=} already exited, doing single update..."
                        )
                    async with lock_held_ctx:
                        yield RedisStateLease(ident=ident, lock_id=lock_id)
                    return
                if self._debug_enabled:
                    logger.debug(
                        f"{SMR} [{time.monotonic() - start:.3f}] {ident} lock {lock_id.decode()} expired while waiting for lease task to exit..."
                    )
        # Have to retry, but now the lock is probably leased.
        yield None

    @contextlib.asynccontextmanager
    async def _lease_lock(self, ident: str) -> AsyncIterator[RedisStateLease | None]:
        """Hold the local lock on an ident leased by this process.

        Args:
            ident: The ident to lock.

        Yields:
            The lease of the lock, or None if the ident is not leased.
        """
        if (
            ident in self._local_leases
            and (state_lock := self._cached_states_locks.get(ident)) is not None
        ):
            async with state_lock:
                if await self._get_local_lease(ident) is not None:
                    if (leased := self._cached_states.get(ident)) is not None:
                        yield RedisStateLease(ident=ident, leased=leased)
                        return
                    if self._debug_enabled:
                        logger.debug(
                            f"{SMR} [{time.monotonic() - start:.3f}] {ident} lease task found, lock held, but no cached states"
                        )
                elif self._debug_enabled:
                    logger.debug(
                        f"{SMR} [{time.monotonic() - start:.3f}] {ident} no active lease task found"
                    )
        yield None

    def _notify_next_waiter(self, key: bytes):
        """Notify the next waiter for a given lock key.

        Args:
            key: The redis lock key.
        """
        # Notify the next un-notified waiter, if any.
        for event in self._lock_waiters.get(key, ()):
            if not event.is_set():
                event.set()
                if self._debug_enabled:
                    logger.debug(
                        f"{SMR} [{time.monotonic() - start:.3f}] {key.decode()} NOTIFY 1 / {len(self._lock_waiters[key])} waiters {event=}"
                    )
                break

    async def _create_lease_break_task(
        self,
        token: StateToken,
        lock_id: bytes,
        cleanup_ctx: contextlib.AsyncExitStack,
        **context: Unpack[StateModificationContext],
    ) -> asyncio.Task | None:
        """Create a background task to break the local lease after lock expiration.

        Args:
            token: The token to create the lease break task for.
            lock_id: The ID of the lock.
            cleanup_ctx: Enter this context while running the lease break task.
            context: The state modification context.

        Returns:
            The lease break task, or None when there is contention.
        """
        self._ensure_lock_task()

        lock_key = token.lock_key

        async def do_flush() -> None:
            if (state_lock := self._cached_states_locks.get(lock_key)) is None:
                # If we lost the lock, we can't write the state, something went wrong.
                logger.warning(
                    f"State lock for {lock_key} missing while finalizing lease."
                )
                return
            async with state_lock:
                # Write the states to redis while no one else can modify them.
                leased = self._cached_states.pop(lock_key, None)
                try:
                    if leased is not None:
                        if self._debug_enabled:
                            logger.debug(
                                f"{SMR} [{time.monotonic() - start:.3f}] {lock_key} lease breaker {lock_id.decode()} flushing state"
                            )
                        await self._write_states(
                            [leased.states[key] for key in leased.touched],
                            StateLease(ident=lock_key, lock_id=lock_id),
                            warn_held_too_long=False,
                            **context,
                        )
                finally:
                    if (current_lease := self._local_leases.get(lock_key)) is task:
                        self._local_leases.pop(lock_key, None)
                        # TODO: clean up the cached states locks periodically
                    elif self._debug_enabled:
                        logger.debug(
                            f"{SMR} [{time.monotonic() - start:.3f}] {lock_key} lease breaker {lock_id.decode()} cleanup of {task=} found different task in _local_leases {current_lease=}."
                        )

        async def lease_breaker():
            cancelled_error: asyncio.CancelledError | None = None
            async with cleanup_ctx:
                lease_break_time = self.oplock_hold_time_ms / 1000
                if self._debug_enabled:
                    logger.debug(
                        f"{SMR} [{time.monotonic() - start:.3f}] {lock_key} lease breaker {lock_id.decode()} started, sleeping for {lease_break_time}s"
                    )
                try:
                    await asyncio.sleep(lease_break_time)
                except asyncio.CancelledError as err:
                    cancelled_error = err
                    # We got cancelled so if someone is holding the lock,
                    # extend the timeout so they get the full time to complete.
                    if (
                        state_lock := self._cached_states_locks[lock_key]
                    ) is not None and state_lock.locked():
                        await self._try_extend_lock(self._lock_key(token.ident))
                try:
                    # Shield the flush from cancellation to ensure it always runs to completion.
                    await asyncio.shield(do_flush())
                except Exception as e:
                    # Propagate exception to the main loop, since we have nowhere to catch it.
                    if not isinstance(e, asyncio.CancelledError):
                        asyncio.get_running_loop().call_exception_handler({
                            "message": "Exception in Redis State Manager lease breaker",
                            "exception": e,
                        })
                    raise
                finally:
                    # Re-raise any cancellation error after cleaning up.
                    if cancelled_error is not None:
                        raise cancelled_error

        if (state_lock := self._cached_states_locks.get(lock_key)) is not None:
            # We have an existing lock, so lets see if we have an existing lease to cancel.
            async with state_lock:
                if (existing_task := self._local_leases.get(lock_key)) is not None:
                    # There's already a lease break task, so cancel it to clear it out.
                    existing_task.cancel()
            if existing_task is not None:
                with contextlib.suppress(asyncio.CancelledError):
                    await existing_task

        # Now we might need to create a new lock.
        if (state_lock := self._cached_states_locks.get(lock_key)) is None:
            async with self._state_manager_lock:
                if (state_lock := self._cached_states_locks.get(lock_key)) is None:
                    state_lock = self._cached_states_locks[lock_key] = asyncio.Lock()

        async with state_lock:
            # Create the task now if one didn't sneak past us.
            if (
                lock_key not in self._local_leases
                and await self._n_lock_contenders(self._lock_key(token.ident)) == 0
            ):
                self._local_leases[lock_key] = task = asyncio.create_task(
                    lease_breaker(),
                    name=f"reflex_lease_breaker|{lock_key}|{lock_id.decode()}",
                )
                self._cached_states[lock_key] = _LeasedStates()
                return task
        return None

    @staticmethod
    def _lock_key(ident: str) -> bytes:
        """Get the redis key for an ident's lock.

        Args:
            ident: The ident to get the lock key for.

        Returns:
            The redis lock key for the ident.
        """
        return f"{ident}_lock".encode()

    async def _try_extend_lock(self, lock_key: bytes) -> bool | None:
        """Extends the current lock for another lock_expiration period.

        Does not change ownership of the lock!

        Args:
            lock_key: The redis key for the lock.

        Returns:
            True if the lock was extended.
        """
        return await self.redis.pexpire(lock_key, self.lock_expiration, xx=True)

    async def _try_get_lock(self, lock_key: bytes, lock_id: bytes) -> bool | None:
        """Try to get a redis lock for a token.

        Args:
            lock_key: The redis key for the lock.
            lock_id: The ID of the lock.

        Returns:
            True if the lock was obtained.
        """
        # With `nx=True` and no `get=True`, SET replies with True or None.
        return cast(
            "bool | None",
            await self.redis.set(
                lock_key,
                lock_id,
                px=self.lock_expiration,
                nx=True,  # only set if it doesn't exist
            ),
        )

    async def _handle_lock_release(self, message: RedisPubSubMessage) -> None:
        """Handle a lock release message from redis.

        Args:
            message: The redis message.
        """
        if message["data"] in self._redis_keyspace_lock_release_events:
            key = message["channel"].split(b":", 1)[1]
            if key in self._lock_waiters:
                self._notify_next_waiter(key)

    async def _handle_lock_contention(self, message: RedisPubSubMessage) -> None:
        """Handle a lock contention message from redis.

        Args:
            message: The redis message.
        """
        # Opportunistic lock contention notification.
        token = message["channel"].rsplit(b":", 1)[1][: -len(b"_lock_waiters")].decode()
        if (
            message["data"] == b"sadd"
            and (state_lock := self._cached_states_locks.get(token)) is not None
        ):
            # Cancel the lease break task to force a lock reacquisition.
            async with state_lock:
                if (lease_task := await self._get_local_lease(token)) is not None:
                    lease_task.cancel()
                    if self._debug_enabled:
                        logger.debug(
                            f"{SMR} [{time.monotonic() - start:.3f}] {token} OPLOCK CONTEND - lease break task cancelled {lease_task=}"
                        )

    async def _subscribe_lock_updates(self):
        """Subscribe to redis keyspace notifications for lock updates."""
        await self._enable_keyspace_notifications()
        redis_db = self.redis.get_connection_kwargs().get("db", 0)

        lock_key_pattern = f"__keyspace@{redis_db}__:*_lock"
        lock_waiter_key_pattern = f"__keyspace@{redis_db}__:*_lock_waiters"
        handlers = {
            lock_key_pattern: self._handle_lock_release,
            lock_waiter_key_pattern: self._handle_lock_contention,
        }
        async with self.redis.pubsub() as pubsub:
            await pubsub.psubscribe(**handlers)  # pyright: ignore[reportArgumentType]
            self._lock_updates_subscribed.set()
            try:
                async for _ in pubsub.listen():
                    pass
            finally:
                self._lock_updates_subscribed.clear()

    def _ensure_lock_task(self) -> None:
        """Ensure the lock updates subscriber task is running."""
        ensure_task(
            owner=self,
            task_attribute="_lock_task",
            coro_function=self._subscribe_lock_updates,
            suppress_exceptions=[Exception],
        )

    async def _ensure_lock_task_subscribed(self, timeout: float | None = None) -> None:
        """Ensure the lock updates subscriber task is running and subscribed to avoid missing notifications.

        Args:
            timeout: How long to wait for the subscriber to be subscribed before
                raising an error. If None, defaults to
                min(LOCK_SUBSCRIBE_TASK_TIMEOUT, lock_expiration).

        Raises:
            TimeoutError: If the lock updates subscriber task fails to subscribe in time.
        """
        if timeout is None:
            timeout = min(
                LOCK_SUBSCRIBE_TASK_TIMEOUT,
                max(self.lock_expiration / 1000, 0),
            )
        # Make sure lock waiter task is running.
        self._ensure_lock_task()
        # Make sure the lock waiter is subscribed to avoid missing notifications.
        await asyncio.wait_for(
            self._lock_updates_subscribed.wait(),
            timeout=timeout,
        )

    async def _enable_keyspace_notifications(self):
        """Enable keyspace notifications for the redis server.

        Raises:
            ResponseError: when the keyspace config cannot be set.
        """
        if self._redis_notify_keyspace_events_enabled:
            return

        await enable_keyspace_notifications(
            self.redis, self._redis_notify_keyspace_events
        )
        self._redis_notify_keyspace_events_enabled = True

    @contextlib.asynccontextmanager
    async def _lock_waiter(self, lock_key: bytes) -> AsyncIterator[asyncio.Event]:
        """Create a lock waiter for a given lock key.

        Args:
            lock_key: The redis key for the lock.

        Yields:
            The event that will be set when the lock is released.
        """
        lock_released_events = self._lock_waiters.get(lock_key)
        if lock_released_events is None:
            # Create a new or get existing set of waiters in manager lock.
            async with self._state_manager_lock:
                lock_released_events = self._lock_waiters.setdefault(lock_key, [])
        lock_released_event = asyncio.Event()
        lock_released_events.append(lock_released_event)
        try:
            yield lock_released_event
        finally:
            # Set before removing to signal that we don't care about it anymore.
            lock_released_event.set()
            # Clean up the waiter
            lock_released_events.remove(lock_released_event)
            if not lock_released_events:
                # Try to clean up the whole set if empty.
                async with self._state_manager_lock:
                    if not lock_released_events:
                        self._lock_waiters.pop(lock_key, None)

    def _n_lock_waiters(self, lock_key: bytes) -> int:
        """Get the number of local waiters for a given lock key.

        Args:
            lock_key: The redis key for the lock.

        Returns:
            The number of waiters for the lock key on this instance.
        """
        lock_released_events = self._lock_waiters.get(lock_key)
        if lock_released_events is None:
            return 0
        return len(lock_released_events)

    async def _n_lock_contenders(self, lock_key: bytes) -> int:
        """Get the number of contenders for a given lock key.

        Args:
            lock_key: The redis key for the lock.

        Returns:
            The number of contenders for the lock key across all instances.
        """
        res = self.redis.scard(lock_key + b"_waiters")
        if inspect.isawaitable(res):
            res = await res
        return res

    @contextlib.asynccontextmanager
    async def _request_lock_release(
        self, lock_key: bytes, lock_id: bytes
    ) -> AsyncIterator[None]:
        """Request the release of a redis lock.

        Args:
            lock_key: The redis key for the lock.
            lock_id: The ID of the lock.
        """
        if not self._oplock_enabled:
            yield
            return

        lock_waiter_key = lock_key + b"_waiters"
        pipeline = self.redis.pipeline()
        # Signal intention to request oplock for this process.
        pipeline.sadd(lock_waiter_key, self._instance_id)
        pipeline.pexpire(lock_waiter_key, self.lock_expiration)
        await pipeline.execute()
        try:
            yield  # Waiting for redis/oplock to be acquired.
        finally:
            res = self.redis.srem(lock_waiter_key, self._instance_id)
            if inspect.isawaitable(res):
                await res

    async def _get_local_lease(
        self, token: str, raise_when_found: bool = False
    ) -> asyncio.Task | None:
        """Check if there is a local lease for a token.

        Args:
            token: The token to check for a local lease.
            raise_when_found: If true, raise OplockFound when a local lease is found.

        Returns:
            The local lease task if found, None otherwise.

        Raises:
            OplockFound: If there is a local lease for the token and raise_when_found is True.
        """
        if (
            self._oplock_enabled
            and (lease_task := self._local_leases.get(token)) is not None
            and not lease_task.done()
            and not lease_task.cancelled()
            and (sys.version_info < (3, 11) or not lease_task.cancelling())
        ):
            if raise_when_found:
                raise OplockFound
            return lease_task
        return None

    async def _wait_lock(self, lock_key: bytes, lock_id: bytes) -> None:
        """Wait for a redis lock to be released via pubsub.

        Coroutine will not return until the lock is obtained.

        It _might_ raise OplockFound if another coroutine in this process did
        get the lock and Oplock is enabled.

        Args:
            lock_key: The redis key for the lock.
            lock_id: The ID of the lock.
        """
        token = lock_key.decode().rsplit("_lock", 1)[0]
        if (
            # If there's not a line, try to get the lock immediately.
            not self._n_lock_waiters(lock_key)
            and await self._try_get_lock(lock_key, lock_id)
        ):
            if self._debug_enabled:
                logger.debug(
                    f"{SMR} [{time.monotonic() - start:.3f}] {lock_key.decode()} instaque by {lock_id.decode()}"
                )
            return
        # Make sure lock waiter task is running.
        with contextlib.suppress(TimeoutError, asyncio.TimeoutError):
            await self._ensure_lock_task_subscribed()
        async with (
            self._lock_waiter(lock_key) as lock_released_event,
            self._request_lock_release(lock_key, lock_id),
        ):
            while (
                self._n_lock_waiters(lock_key) > 1 and not lock_released_event.is_set()
            ) or (
                # We didn't get the lock so wait for the next release event.
                lock_released_event.clear() is None
                and not await self._try_get_lock(lock_key, lock_id)
            ):
                # Check if this process got a lease, then we can abandon waiting on the redis lock.
                await self._get_local_lease(token, raise_when_found=True)
                if self._debug_enabled:
                    logger.debug(
                        f"{SMR} [{time.monotonic() - start:.3f}] {lock_key.decode()} waiting for {lock_id.decode()}"
                    )
                try:
                    await asyncio.wait_for(
                        lock_released_event.wait(),
                        timeout=max(self.lock_expiration / 1000, 0),
                    )
                except (TimeoutError, asyncio.TimeoutError):
                    if self._debug_enabled:
                        logger.debug(
                            f"{SMR} [{time.monotonic() - start:.3f}] {lock_key.decode()} wait timeout for {lock_id.decode()}"
                        )
                    lock_released_event.set()  # to re-check the lock
            if self._debug_enabled:
                logger.debug(
                    f"{SMR} [{time.monotonic() - start:.3f}] {lock_key.decode()} acquired by {lock_id.decode()} event={lock_released_event}"
                )

    @contextlib.asynccontextmanager
    async def _lock(
        self, token: StateToken[Any], event_name: str | None = None
    ) -> AsyncIterator[bytes]:
        """Obtain a redis lock for a token.

        Args:
            token: The token to obtain a lock for.
            event_name: The name of the event associated with the lock.

        Yields:
            The ID of the lock (to be passed to set_state).

        Raises:
            LockExpiredError: If the lock has expired while processing the event.
        """
        lock_key = self._lock_key(token.ident)
        lock_id = (
            f"{event_name}:{uuid.uuid4().hex}" if event_name else uuid.uuid4().hex
        ).encode()

        await self._wait_lock(lock_key, lock_id)
        state_is_locked = True

        try:
            yield lock_id
        except LockExpiredError:
            state_is_locked = False
            raise
        finally:
            if state_is_locked:
                # only delete our lock
                deleted_lock_id = cast(
                    "bytes | None", await self.redis.getdel(lock_key)
                )
                if deleted_lock_id == lock_id:
                    if self._debug_enabled:
                        logger.debug(
                            f"{SMR} [{time.monotonic() - start:.3f}] {lock_key.decode()} released by {lock_id.decode()}"
                        )
                elif deleted_lock_id is not None:
                    # This can happen if the caller never tried to `set_state` before the lock expired and is a pretty bad bug.
                    logger.warning(
                        f"{lock_key.decode()} was released by {lock_id.decode()}, but it belonged to {deleted_lock_id.decode()}. This is a bug."
                    )
                # To avoid race when a waiter is registered after the del message is processed.
                self._notify_next_waiter(lock_key)

    async def close(self):
        """Explicitly close the redis connection and connection_pool.

        It is necessary in testing scenarios to close between asyncio test cases
        to avoid having lingering redis connections associated with event loops
        that will be closed (each test case uses its own event loop).

        Note: Connections will be automatically reopened when needed.
        """
        try:
            # Kill the lock task first so waiters don't get lock notifications.
            if self._lock_task is not None:
                self._lock_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._lock_task
                self._lock_task = None
            # Then cancel all outstanding leases and write the cached states to redis.
            for lease_task in self._local_leases.values():
                lease_task.cancel()
            await asyncio.gather(*self._local_leases.values(), return_exceptions=True)
        finally:
            await self.redis.aclose(close_connection_pool=True)
