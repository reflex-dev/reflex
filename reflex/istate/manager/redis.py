"""A state manager that stores states in redis."""

import asyncio
import contextlib
import dataclasses
import uuid
from collections.abc import AsyncIterator

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

    # The keyspace subscription string when redis is waiting for lock to be released.
    _redis_notify_keyspace_events: str = dataclasses.field(
        default="K"  # Enable keyspace notifications (target a particular key)
        "$"  # For String commands (like setting keys)
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

    # Lock waiters
    _lock_waiters: dict[bytes, list[asyncio.Event]] = dataclasses.field(
        default_factory=dict,
        init=False,
    )
    _lock_task: asyncio.Task | None = dataclasses.field(default=None, init=False)

    # Whether debug prints are enabled.
    _debug_enabled: bool = dataclasses.field(
        default=environment.REFLEX_REDIS_STATE_MANAGER_DEBUG.get(),
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
        if lock_id is not None:
            time_taken = self.lock_expiration / 1000 - (
                await self.redis.ttl(self._lock_key(token))
            )
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

        client_token, substate_name = _split_substate_key(token)
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
        if token in self._local_leases:
            yield self._cached_states[token]
            return
        async with self._lock(token) as lock_id:
            state = await self.get_state(token)
            yield state
            await self.set_state(token, state, lock_id=lock_id, **context)

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

    async def _subscribe_lock_updates(self, redis_db: int = 0):
        """Subscribe to redis keyspace notifications for lock updates.

        Args:
            redis_db: The logical database number to subscribe to.
        """
        lock_key_pattern = f"__keyspace@{redis_db}__:*_lock"
        async with self.redis.pubsub() as pubsub:
            await pubsub.psubscribe(lock_key_pattern)
            async for message in pubsub.listen():
                if (
                    message is not None
                    and message["data"] in self._redis_keyspace_lock_release_events
                ):
                    key = message["channel"].split(b":", 1)[1]
                    if key in self._lock_waiters:
                        for event in self._lock_waiters[key]:
                            if not event.is_set():
                                event.set()
                                if self._debug_enabled:
                                    console.debug(
                                        f"[SMR] {key.decode()} NOTIFY 1 / {len(self._lock_waiters[key])} waiters {event=}"
                                    )
                                break

    async def _lock_updates_forever(self) -> None:
        """Background task to monitor Redis keyspace notifications for lock updates."""
        await self._enable_keyspace_notifications()
        redis_db = self.redis.get_connection_kwargs().get("db", 0)
        while True:
            try:
                await self._subscribe_lock_updates(redis_db)
            except asyncio.CancelledError:  # noqa: PERF203
                break
            except Exception as e:
                console.error(f"StateManagerRedis lock update task error: {e}")

    async def _ensure_lock_task(self) -> None:
        """Ensure the lock updates subscriber task is running."""
        if self._lock_task is None or self._lock_task.done():
            async with self._state_manager_lock:
                if self._lock_task is None or self._lock_task.done():
                    self._lock_task = asyncio.create_task(self._lock_updates_forever())

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
                        if self._debug_enabled:
                            console.debug(
                                f"[SMR] {lock_key.decode()} all waiters cleaned up"
                            )

    def _n_lock_waiters(self, lock_key: bytes) -> int:
        """Get the number of waiters for a given lock key.

        Args:
            lock_key: The redis key for the lock.

        Returns:
            The number of waiters for the lock key on this instance.
        """
        lock_released_events = self._lock_waiters.get(lock_key)
        if lock_released_events is None:
            return 0
        return len(lock_released_events)

    async def _wait_lock(self, lock_key: bytes, lock_id: bytes) -> None:
        """Wait for a redis lock to be released via pubsub.

        Coroutine will not return until the lock is obtained.

        Args:
            lock_key: The redis key for the lock.
            lock_id: The ID of the lock.
        """
        if (
            # If there's not a line, try to get the lock immediately.
            not self._n_lock_waiters(lock_key)
            and await self._try_get_lock(lock_key, lock_id)
        ):
            if self._debug_enabled:
                console.debug(
                    f"[SMR] {lock_key.decode()} instaque by {lock_id.decode()}"
                )
            return
        # Make sure lock waiter task is running.
        await self._ensure_lock_task()
        async with self._lock_waiter(lock_key) as lock_released_event:
            while (
                self._n_lock_waiters(lock_key) > 1 and not lock_released_event.is_set()
            ) or (
                # We didn't get the lock so wait for the next release event.
                lock_released_event.clear() is None
                and not await self._try_get_lock(lock_key, lock_id)
            ):
                if self._debug_enabled:
                    console.debug(
                        f"[SMR] {lock_key.decode()} waiting for {lock_id.decode()}"
                    )
                try:
                    await asyncio.wait_for(
                        lock_released_event.wait(), timeout=self.lock_expiration / 1000
                    )
                    if self._debug_enabled:
                        console.debug(
                            f"[SMR] {lock_key.decode()} notified {lock_id.decode()} event={lock_released_event}"
                        )
                except TimeoutError:
                    if self._debug_enabled:
                        console.debug(
                            f"[SMR] {lock_key.decode()} wait timeout for {lock_id.decode()}"
                        )
                    lock_released_event.set()  # to re-check the lock
            if self._debug_enabled:
                console.debug(
                    f"[SMR] {lock_key.decode()} acquired by {lock_id.decode()} event={lock_released_event}"
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
                            f"[SMR] {lock_key.decode()} released by {lock_id.decode()}"
                        )
                else:
                    # This can happen if the caller never tried to `set_state` before the lock expired and is a pretty bad bug.
                    console.warn(
                        f"{lock_key.decode()} was released by {lock_id.decode()}, but it belonged to {deleted_lock_id.decode()}. This is a bug."
                    )

    async def close(self):
        """Explicitly close the redis connection and connection_pool.

        It is necessary in testing scenarios to close between asyncio test cases
        to avoid having lingering redis connections associated with event loops
        that will be closed (each test case uses its own event loop).

        Note: Connections will be automatically reopened when needed.
        """
        await self.redis.aclose(close_connection_pool=True)
        if self._lock_task is not None:
            self._lock_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._lock_task
            self._lock_task = None
