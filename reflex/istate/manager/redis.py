"""A state manager that stores states in redis."""

import asyncio
import contextlib
import dataclasses
import inspect
import os
import sys
import time
import uuid
from collections.abc import AsyncIterator
from typing import TypedDict

from redis import ResponseError
from redis.asyncio import Redis
from typing_extensions import Unpack, override

from reflex.config import get_config
from reflex.environment import environment
from reflex.istate.manager import (
    StateManager,
    StateModificationContext,
    _default_token_expiration,
)
from reflex.state import BaseState, _split_substate_key, _substate_key
from reflex.utils import console
from reflex.utils.exceptions import (
    InvalidLockWarningThresholdError,
    LockExpiredError,
    StateSchemaMismatchError,
)
from reflex.utils.tasks import ensure_task


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
    """
    return environment.REFLEX_OPLOCK_HOLD_TIME_MS.get() or (
        _default_lock_expiration() // 2
    )


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
        default="K"  # Enable keyspace notifications (target a particular key)
        "$"  # For String commands (like setting keys)
        "s"  # For Set commands (SADD, SREM, etc)
        "g"  # For generic commands (DEL, EXPIRE, etc)
        "x"  # For expired events
        "e"  # For evicted events (i.e. maxmemory exceeded)
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
        default=asyncio.Lock(), init=False
    )

    # Whether to opportunistically hold locks for fast in-memory access.
    _oplock_enabled: bool = dataclasses.field(
        default_factory=environment.REFLEX_OPLOCK_ENABLED.get, init=False
    )

    # Cached states
    _cached_states: dict[str, BaseState] = dataclasses.field(
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

    def _get_required_state_classes(
        self,
        target_state_cls: type[BaseState],
        subclasses: bool = False,
        required_state_classes: set[type[BaseState]] | None = None,
    ) -> set[type[BaseState]]:
        """Recursively determine which states are required to fetch the target state.

        This will always include potentially dirty substates that depend on vars
        in the target_state_cls.

        Args:
            target_state_cls: The target state class being fetched.
            subclasses: Whether to include subclasses of the target state.
            required_state_classes: Recursive argument tracking state classes that have already been seen.

        Returns:
            The set of state classes required to fetch the target state.
        """
        if required_state_classes is None:
            required_state_classes = set()
        # Get the substates if requested.
        if subclasses:
            for substate in target_state_cls.get_substates():
                self._get_required_state_classes(
                    substate,
                    subclasses=True,
                    required_state_classes=required_state_classes,
                )
        if target_state_cls in required_state_classes:
            return required_state_classes
        required_state_classes.add(target_state_cls)

        # Get dependent substates.
        for pd_substates in target_state_cls._get_potentially_dirty_states():
            self._get_required_state_classes(
                pd_substates,
                subclasses=False,
                required_state_classes=required_state_classes,
            )

        # Get the parent state if it exists.
        if parent_state := target_state_cls.get_parent_state():
            self._get_required_state_classes(
                parent_state,
                subclasses=False,
                required_state_classes=required_state_classes,
            )
        return required_state_classes

    def _get_populated_states(
        self,
        target_state: BaseState,
        populated_states: dict[str, BaseState] | None = None,
    ) -> dict[str, BaseState]:
        """Recursively determine which states from target_state are already fetched.

        Args:
            target_state: The state to check for populated states.
            populated_states: Recursive argument tracking states seen in previous calls.

        Returns:
            A dictionary of state full name to state instance.
        """
        if populated_states is None:
            populated_states = {}
        if target_state.get_full_name() in populated_states:
            return populated_states
        populated_states[target_state.get_full_name()] = target_state
        for substate in target_state.substates.values():
            self._get_populated_states(substate, populated_states=populated_states)
        if target_state.parent_state is not None:
            self._get_populated_states(
                target_state.parent_state, populated_states=populated_states
            )
        return populated_states

    @override
    async def get_state(
        self,
        token: str,
        top_level: bool = True,
        for_state_instance: BaseState | None = None,
    ) -> BaseState:
        """Get the state for a token.

        Args:
            token: The token to get the state for.
            top_level: If true, return an instance of the top-level state (self.state).
            for_state_instance: If provided, attach the requested states to this existing state tree.

        Returns:
            The state for the token.

        Raises:
            RuntimeError: when the state_cls is not specified in the token, or when the parent state for a
                requested state was not fetched.
        """
        # Split the actual token from the fully qualified substate name.
        token, state_path = _split_substate_key(token)
        if state_path:
            # Get the State class associated with the given path.
            state_cls = self.state.get_class_substate(state_path)
        else:
            msg = f"StateManagerRedis requires token to be specified in the form of {{token}}_{{state_full_name}}, but got {token}"
            raise RuntimeError(msg)

        # Determine which states we already have.
        flat_state_tree: dict[str, BaseState] = (
            self._get_populated_states(for_state_instance) if for_state_instance else {}
        )

        # Determine which states from the tree need to be fetched.
        required_state_classes = sorted(
            self._get_required_state_classes(state_cls, subclasses=True)
            - {type(s) for s in flat_state_tree.values()},
            key=lambda x: x.get_full_name(),
        )

        redis_pipeline = self.redis.pipeline()
        for state_cls in required_state_classes:
            redis_pipeline.get(_substate_key(token, state_cls))

        for state_cls, redis_state in zip(
            required_state_classes,
            await redis_pipeline.execute(),
            strict=False,
        ):
            state = None

            if redis_state is not None:
                # Deserialize the substate.
                with contextlib.suppress(StateSchemaMismatchError):
                    state = BaseState._deserialize(data=redis_state)
            if state is None:
                # Key didn't exist or schema mismatch so create a new instance for this token.
                state = state_cls(
                    init_substates=False,
                    _reflex_internal_init=True,
                )
            flat_state_tree[state.get_full_name()] = state
            if state.get_parent_state() is not None:
                parent_state_name, _dot, state_name = state.get_full_name().rpartition(
                    "."
                )
                parent_state = flat_state_tree.get(parent_state_name)
                if parent_state is None:
                    msg = (
                        f"Parent state for {state.get_full_name()} was not found "
                        "in the state tree, but should have already been fetched. "
                        "This is a bug"
                    )
                    raise RuntimeError(msg)
                parent_state.substates[state_name] = state
                state.parent_state = parent_state

        # To retain compatibility with previous implementation, by default, we return
        # the top-level state which should always be fetched or already cached.
        if top_level:
            return flat_state_tree[self.state.get_full_name()]
        return flat_state_tree[state_cls.get_full_name()]

    @override
    async def set_state(
        self,
        token: str,
        state: BaseState,
        *,
        lock_id: bytes | None = None,
        **context: Unpack[StateModificationContext],
    ):
        """Set the state for a token.

        Args:
            token: The token to set the state for.
            state: The state to set.
            lock_id: If provided, the lock_key must be set to this value to set the state.
            context: The event context.

        Raises:
            LockExpiredError: If lock_id is provided and the lock for the token is not held by that ID.
            RuntimeError: If the state instance doesn't match the state name in the token.
        """
        # Check that we're holding the lock.
        if (
            lock_id is not None
            and await self.redis.get(self._lock_key(token)) != lock_id
        ):
            msg = (
                f"Lock expired for token {token} while processing. Consider increasing "
                f"`app.state_manager.lock_expiration` (currently {self.lock_expiration}) "
                "or use `@rx.event(background=True)` decorator for long-running tasks."
                + (
                    f" Happened in event: {event.name}"
                    if (event := context.get("event")) is not None
                    else ""
                )
            )
            raise LockExpiredError(msg)

        client_token, substate_name = _split_substate_key(token)

        if lock_id is not None and client_token not in self._local_leases:
            time_taken = (
                self.lock_expiration - (await self.redis.pttl(self._lock_key(token)))
            ) / 1000
            if time_taken > self.lock_warning_threshold / 1000:
                console.warn(
                    f"Lock for token {token} was held too long {time_taken=}s, "
                    f"use `@rx.event(background=True)` decorator for long-running tasks."
                    + (
                        f" Happened in event: {event.name}"
                        if (event := context.get("event")) is not None
                        else ""
                    ),
                    dedupe=True,
                )

        # If the substate name on the token doesn't match the instance name, it cannot have a parent.
        if state.parent_state is not None and state.get_full_name() != substate_name:
            msg = f"Cannot `set_state` with mismatching token {token} and substate {state.get_full_name()}."
            raise RuntimeError(msg)

        # Recursively set_state on all known substates.
        tasks = [
            asyncio.create_task(
                self.set_state(
                    _substate_key(client_token, substate),
                    substate,
                    lock_id=lock_id,
                    **context,
                ),
                name=f"reflex_set_state|{client_token}|{substate.get_full_name()}",
            )
            for substate in state.substates.values()
        ]
        # Persist only the given state (parents or substates are excluded by BaseState.__getstate__).
        if state._get_was_touched():
            pickle_state = state._serialize()
            if pickle_state:
                await self.redis.set(
                    _substate_key(client_token, state),
                    pickle_state,
                    ex=self.token_expiration,
                )

        # Wait for substates to be persisted.
        for t in tasks:
            await t

    @contextlib.asynccontextmanager
    async def _try_modify_state(
        self, token: str, **context: Unpack[StateModificationContext]
    ) -> AsyncIterator[BaseState | None]:
        """Modify the state for a token while holding exclusive lock.

        Args:
            token: The token to modify the state for.
            context: The state modification context.

        Yields:
            The state for the token or None if we couldn't get the lock.
        """
        if not self._oplock_enabled:
            # OpLock is disabled, get a fresh lock, write, and release.
            async with self._lock(token) as lock_id:
                state = await self.get_state(token)
                yield state
                await self.set_state(token, state, lock_id=lock_id, **context)
            return

        # Opportunistically reuse existing lock.
        async with self._get_state_cached(token) as cached_state:
            if cached_state is not None:
                yield cached_state
                self._notify_next_waiter(self._lock_key(token))
                return

        # Opportunistic locking is enabled, so try to hold the lock across multiple calls.
        client_token, _ = _split_substate_key(token)
        lock_held_ctx = contextlib.AsyncExitStack()
        try:
            lock_id = await lock_held_ctx.enter_async_context(self._lock(token))
        except OplockFound:
            # While waiting for the lock, another process has acquired it, but we can piggy back.
            pass
        else:
            # Do not create a lease break task when multiple instances are waiting.
            if (
                not await self._get_local_lease(client_token)
                and await self._n_lock_contenders(self._lock_key(token)) > 0
            ):
                if self._debug_enabled:
                    console.debug(
                        f"{SMR} [{time.monotonic() - start:.3f}] {client_token} has contention, not leasing"
                    )
                async with lock_held_ctx:
                    state = await self.get_state(token)
                    yield state
                    await self.set_state(token, state, lock_id=lock_id, **context)
                return

            # Create the lease break task since we got the lock.
            if (
                new_lease_task := await self._create_lease_break_task(
                    token, lock_id, cleanup_ctx=lock_held_ctx, **context
                )
            ) is (
                current_lease_task := await self._get_local_lease(client_token)
            ) and new_lease_task is not None:
                if self._debug_enabled:
                    console.debug(
                        f"{SMR} [{time.monotonic() - start:.3f}] {client_token} obtained lock {lock_id.decode()}."
                    )
            elif current_lease_task is None:
                # Check if we still have the redis lock, then just try to send this one update and release it.
                await self._try_extend_lock(self._lock_key(token))
                if await self.redis.get(self._lock_key(token)) == lock_id:
                    if self._debug_enabled:
                        console.debug(
                            f"{SMR} [{time.monotonic() - start:.3f}] {client_token} holding lock {lock_id.decode()}, {new_lease_task=} already exited, doing single update..."
                        )
                    async with lock_held_ctx:
                        state = await self.get_state(token)
                        yield state
                        await self.set_state(token, state, lock_id=lock_id, **context)
                    return
                elif self._debug_enabled:
                    console.debug(
                        f"{SMR} [{time.monotonic() - start:.3f}] {client_token} lock {lock_id.decode()} expired while waiting for lease task to exit..."
                    )
        # Have to retry getting the state, but now it's probably cached.
        yield None

    @override
    @contextlib.asynccontextmanager
    async def modify_state(
        self, token: str, **context: Unpack[StateModificationContext]
    ) -> AsyncIterator[BaseState]:
        """Modify the state for a token while holding exclusive lock.

        Args:
            token: The token to modify the state for.
            context: The state modification context.

        Yields:
            The state for the token.
        """
        while True:
            async with self._try_modify_state(token, **context) as state_instance:
                if state_instance is not None:
                    yield state_instance
                    return

    @contextlib.asynccontextmanager
    async def _get_state_cached(self, token: str) -> AsyncIterator[BaseState | None]:
        """Get the cached state for a token, while holding the local lease lock.

        Args:
            token: The token to get the cached state for.

        Yields:
            The cached state for the token, or None if not cached/uncachable.

        Raises:
            RuntimeError: when the state_cls is not specified in the token.
        """
        client_token, state_path = _split_substate_key(token)
        # Opportunistically reuse existing lock.
        if (
            client_token in self._local_leases
            and (state_lock := self._cached_states_locks.get(client_token)) is not None
        ):
            async with state_lock:
                if await self._get_local_lease(client_token) is not None:
                    if (
                        cached_state := self._cached_states.get(client_token)
                    ) is not None:
                        # Make sure we have the substate cached (or fetch it from redis).
                        try:
                            substate = cached_state.get_substate(state_path.split("."))
                            if len(substate.substates) != len(
                                type(substate).get_substates()
                            ):
                                # If the substate is missing substates, we need to refetch it.
                                raise ValueError  # noqa: TRY301
                        except ValueError:
                            await self.get_state(token, for_state_instance=cached_state)
                        yield cached_state
                        return
                    elif self._debug_enabled:
                        console.debug(
                            f"{SMR} [{time.monotonic() - start:.3f}] {client_token} lease task found, lock held, but no cached state"
                        )
                elif self._debug_enabled:
                    console.debug(
                        f"{SMR} [{time.monotonic() - start:.3f}] {client_token} no active lease task found"
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
                    console.debug(
                        f"{SMR} [{time.monotonic() - start:.3f}] {key.decode()} NOTIFY 1 / {len(self._lock_waiters[key])} waiters {event=}"
                    )
                break

    async def _create_lease_break_task(
        self,
        token: str,
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

        client_token, _ = _split_substate_key(token)

        async def do_flush() -> None:
            if (state_lock := self._cached_states_locks.get(client_token)) is None:
                # If we lost the lock, we can't write the state, something went wrong.
                console.warn(
                    f"State lock for {client_token} missing while finalizing lease."
                )
                return
            async with state_lock:
                # Write the state to redis while no one else can modify the cached copy.
                state = self._cached_states.pop(client_token, None)
                try:
                    if state:
                        if self._debug_enabled:
                            console.debug(
                                f"{SMR} [{time.monotonic() - start:.3f}] {client_token} lease breaker {lock_id.decode()} flushing state"
                            )
                        await self.set_state(token, state, lock_id=lock_id, **context)
                finally:
                    if (current_lease := self._local_leases.get(client_token)) is task:
                        self._local_leases.pop(client_token, None)
                        # TODO: clean up the cached states locks periodically
                    elif self._debug_enabled:
                        console.debug(
                            f"{SMR} [{time.monotonic() - start:.3f}] {client_token} lease breaker {lock_id.decode()} cleanup of {task=} found different task in _local_leases {current_lease=}."
                        )

        async def lease_breaker():
            cancelled_error: asyncio.CancelledError | None = None
            async with cleanup_ctx:
                lease_break_time = self.oplock_hold_time_ms / 1000
                if self._debug_enabled:
                    console.debug(
                        f"{SMR} [{time.monotonic() - start:.3f}] {client_token} lease breaker {lock_id.decode()} started, sleeping for {lease_break_time}s"
                    )
                try:
                    await asyncio.sleep(lease_break_time)
                except asyncio.CancelledError as err:
                    cancelled_error = err
                    # We got cancelled so if someone is holding the lock,
                    # extend the timeout so they get the full time to complete.
                    if (
                        state_lock := self._cached_states_locks[client_token]
                    ) is not None and state_lock.locked():
                        await self._try_extend_lock(self._lock_key(token))
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

        if (state_lock := self._cached_states_locks.get(client_token)) is not None:
            # We have an existing lock, so lets see if we have an existing lease to cancel.
            async with state_lock:
                if (existing_task := self._local_leases.get(client_token)) is not None:
                    # There's already a lease break task, so cancel it to clear it out.
                    existing_task.cancel()
            if existing_task is not None:
                with contextlib.suppress(asyncio.CancelledError):
                    await existing_task

        # Now we might need to create a new lock.
        if (state_lock := self._cached_states_locks.get(client_token)) is None:
            async with self._state_manager_lock:
                if (state_lock := self._cached_states_locks.get(client_token)) is None:
                    state_lock = self._cached_states_locks[client_token] = (
                        asyncio.Lock()
                    )

        async with state_lock:
            # Create the task now if one didn't sneak past us.
            if (
                client_token not in self._local_leases
                and await self._n_lock_contenders(self._lock_key(token)) == 0
            ):
                self._local_leases[client_token] = task = asyncio.create_task(
                    lease_breaker(),
                    name=f"reflex_lease_breaker|{client_token}|{lock_id.decode()}",
                )
                # Fetch the requested state into the cache.
                self._cached_states[client_token] = await self.get_state(token)
                return task
        return None

    @staticmethod
    def _lock_key(token: str) -> bytes:
        """Get the redis key for a token's lock.

        Args:
            token: The token to get the lock key for.

        Returns:
            The redis lock key for the token.
        """
        # All substates share the same lock domain, so ignore any substate path suffix.
        client_token = _split_substate_key(token)[0]
        return f"{client_token}_lock".encode()

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
        return await self.redis.set(
            lock_key,
            lock_id,
            px=self.lock_expiration,
            nx=True,  # only set if it doesn't exist
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
                        console.debug(
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
            async for _ in pubsub.listen():
                pass

    def _ensure_lock_task(self) -> None:
        """Ensure the lock updates subscriber task is running."""
        ensure_task(
            owner=self,
            task_attribute="_lock_task",
            coro_function=self._subscribe_lock_updates,
            suppress_exceptions=[Exception],
        )

    async def _enable_keyspace_notifications(self):
        """Enable keyspace notifications for the redis server.

        Raises:
            ResponseError: when the keyspace config cannot be set.
        """
        if self._redis_notify_keyspace_events_enabled:
            return

        try:
            await self.redis.config_set(
                "notify-keyspace-events",
                self._redis_notify_keyspace_events,
            )
        except ResponseError:
            # Some redis servers only allow out-of-band configuration, so ignore errors here.
            if not environment.REFLEX_IGNORE_REDIS_CONFIG_ERROR.get():
                raise
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
                console.debug(
                    f"{SMR} [{time.monotonic() - start:.3f}] {lock_key.decode()} instaque by {lock_id.decode()}"
                )
            return
        # Make sure lock waiter task is running.
        self._ensure_lock_task()
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
                    console.debug(
                        f"{SMR} [{time.monotonic() - start:.3f}] {lock_key.decode()} waiting for {lock_id.decode()}"
                    )
                try:
                    await asyncio.wait_for(
                        lock_released_event.wait(),
                        timeout=max(self.lock_expiration / 1000, 0),
                    )
                except (TimeoutError, asyncio.TimeoutError):
                    if self._debug_enabled:
                        console.debug(
                            f"{SMR} [{time.monotonic() - start:.3f}] {lock_key.decode()} wait timeout for {lock_id.decode()}"
                        )
                    lock_released_event.set()  # to re-check the lock
            if self._debug_enabled:
                console.debug(
                    f"{SMR} [{time.monotonic() - start:.3f}] {lock_key.decode()} acquired by {lock_id.decode()} event={lock_released_event}"
                )

    @contextlib.asynccontextmanager
    async def _lock(self, token: str):
        """Obtain a redis lock for a token.

        Args:
            token: The token to obtain a lock for.

        Yields:
            The ID of the lock (to be passed to set_state).

        Raises:
            LockExpiredError: If the lock has expired while processing the event.
        """
        lock_key = self._lock_key(token)
        lock_id = uuid.uuid4().hex.encode()

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
                deleted_lock_id = await self.redis.getdel(lock_key)
                if deleted_lock_id == lock_id:
                    if self._debug_enabled:
                        console.debug(
                            f"{SMR} [{time.monotonic() - start:.3f}] {lock_key.decode()} released by {lock_id.decode()}"
                        )
                elif deleted_lock_id is not None:
                    # This can happen if the caller never tried to `set_state` before the lock expired and is a pretty bad bug.
                    console.warn(
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
