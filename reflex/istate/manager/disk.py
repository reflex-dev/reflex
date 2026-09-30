"""A state manager that stores states on disk."""

import asyncio
import contextlib
import dataclasses
import functools
import logging
import time
from collections.abc import AsyncIterator, Iterable, Sequence
from hashlib import md5
from pathlib import Path
from typing import Any, Generic

from reflex_base.environment import state_manager_disk_debounce
from typing_extensions import Unpack, override

from reflex.istate.manager import (
    StateLease,
    StateManager,
    StateModificationContext,
    _default_token_expiration,
)
from reflex.istate.manager.token import TOKEN_TYPE, StateToken
from reflex.utils import path_ops, prerequisites
from reflex.utils.misc import run_in_thread

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class QueueItem(Generic[TOKEN_TYPE]):
    """An item in the write queue."""

    token: StateToken[TOKEN_TYPE]
    state: TOKEN_TYPE
    timestamp: float


@dataclasses.dataclass
class StateManagerDisk(StateManager):
    """A state manager that stores states on disk."""

    # The states loaded in memory, by the str of their token.
    states: dict[str, Any] = dataclasses.field(default_factory=dict)

    # The keys of the states of each ident loaded in memory.
    _ident_keys: dict[str, set[str]] = dataclasses.field(
        default_factory=dict, init=False
    )

    # The mutex ensures the dict of mutexes is updated exclusively
    _state_manager_lock: asyncio.Lock = dataclasses.field(default_factory=asyncio.Lock)

    # The dict of mutexes for each ident
    _states_locks: dict[str, asyncio.Lock] = dataclasses.field(
        default_factory=dict,
        init=False,
    )

    # The token expiration time (s).
    token_expiration: int = dataclasses.field(default_factory=_default_token_expiration)

    # Last time the states of an ident were used.
    _token_last_touched: dict[str, float] = dataclasses.field(
        default_factory=dict,
        init=False,
    )

    # Pending writes, by the str of their token.
    _write_queue: dict[str, QueueItem] = dataclasses.field(
        default_factory=dict,
        init=False,
    )
    _write_queue_task: asyncio.Task | None = None
    _write_debounce_seconds: float = dataclasses.field(
        default_factory=lambda: state_manager_disk_debounce().total_seconds()
    )

    def __post_init__(self):
        """Create a new state manager."""
        path_ops.mkdir(self.states_directory)

        self._purge_expired_states()

    @functools.cached_property
    def states_directory(self) -> Path:
        """The states directory.

        Resolved once so later cwd changes do not move where states are
        written or purged.

        Returns:
            The absolute states directory.
        """
        return prerequisites.get_states_dir().absolute()

    def _purge_expired_states(self):
        """Purge expired states from the disk."""
        for path in path_ops.ls(self.states_directory):
            # check path is a pickle file
            if path.suffix != ".pkl":
                continue

            # load last edited field from file
            last_edited = path.stat().st_mtime

            # check if the file is older than the token expiration time
            if time.time() - last_edited > self.token_expiration:
                # remove the file
                path.unlink()

    def token_path(self, token: StateToken) -> Path:
        """Get the path for a token.

        Args:
            token: The token to get the path for.

        Returns:
            The path for the token.
        """
        return (
            self.states_directory / f"{md5(str(token).encode()).hexdigest()}.pkl"
        ).absolute()

    def _load_state(self, token: StateToken[TOKEN_TYPE]) -> TOKEN_TYPE | None:
        """Load a state from disk.

        Args:
            token: The token of the state.

        Returns:
            The loaded state, or None if it is not stored or cannot be loaded.
        """
        token_path = self.token_path(token)

        if token_path.exists():
            try:
                with token_path.open(mode="rb") as file:
                    return token.deserialize(fp=file)
            except Exception:
                pass
        return None

    def _put(self, token: StateToken, state: Any) -> None:
        """Keep a state in memory.

        Args:
            token: The token of the state.
            state: The state.
        """
        key = str(token)
        self.states[key] = state
        self._ident_keys.setdefault(token.ident, set()).add(key)

    def _track_idents(self, tokens: Iterable[StateToken]) -> None:
        """Record that the states of the idents of some tokens are in use.

        Args:
            tokens: The tokens in use.
        """
        now = time.time()
        for token in tokens:
            self._token_last_touched[token.ident] = now

    @override
    async def load_states(
        self, tokens: Sequence[StateToken], *, create: bool = True
    ) -> list[Any]:
        """Load the states for some tokens, from memory or else from disk.

        Args:
            tokens: The tokens of the states to load.
            create: Whether to create the states that are not stored.

        Returns:
            The state for each token, in order.
        """
        states = []
        for token in tokens:
            if (state := self.states.get(str(token))) is None:
                if (state := self._load_state(token)) is None and create:
                    state = token.new_instance()
                if state is not None:
                    self._put(token, state)
            states.append(state)
        self._track_idents(tokens)
        return states

    async def _write_state(self, token: StateToken, state: Any) -> None:
        """Write a state to disk.

        Args:
            token: The token of the state.
            state: The state to write.
        """
        if pickle_state := token.serialize(state):
            if not self.states_directory.exists():
                self.states_directory.mkdir(parents=True, exist_ok=True)
            await run_in_thread(
                lambda: self.token_path(token).write_bytes(pickle_state),
            )

    async def _process_write_queue_delay(self):
        """Wait for the debounce period before processing the write queue again."""
        now = time.time()
        if self._write_queue:
            # There are still items in the queue, schedule another run.
            next_write_in = max(
                0,
                min(
                    self._write_debounce_seconds - (now - item.timestamp)
                    for item in self._write_queue.values()
                ),
            )
            await asyncio.sleep(next_write_in)
        elif self._write_debounce_seconds > 0:
            # No items left, wait a bit before checking again.
            await asyncio.sleep(self._write_debounce_seconds)
        else:
            # Debounce is disabled, so sleep until the next token expiration.
            oldest_token_last_touch = min(
                self._token_last_touched.values(), default=now
            )
            next_expiration_in = self.token_expiration - (now - oldest_token_last_touch)
            await asyncio.sleep(next_expiration_in)

    async def _process_write_queue(self):
        """Long running task that checks for states to write to disk.

        Raises:
            asyncio.CancelledError: When the task is cancelled.
        """
        while True:
            try:
                now = time.time()
                # sort the _write_queue by oldest timestamp and exclude items younger than debounce time
                items_to_write = sorted(
                    (
                        item
                        for item in self._write_queue.values()
                        if now - item.timestamp >= self._write_debounce_seconds
                    ),
                    key=lambda item: item.timestamp,
                )
                for item in items_to_write:
                    self._write_queue.pop(str(item.token))
                    if item.token.get_and_reset_touched_state(item.state):
                        await self._write_state(item.token, item.state)
                # Check for expired states to purge.
                for ident, last_touched in list(self._token_last_touched.items()):
                    if now - last_touched > self.token_expiration and not (
                        (state_lock := self._states_locks.get(ident)) is not None
                        and state_lock.locked()
                    ):
                        self._token_last_touched.pop(ident)
                        for key in self._ident_keys.pop(ident, ()):
                            self.states.pop(key, None)
                await run_in_thread(self._purge_expired_states)
                await self._process_write_queue_delay()
            except asyncio.CancelledError:  # noqa: PERF203
                await self._flush_write_queue()
                raise
            except Exception as e:
                logger.error(f"Error processing write queue: {e!r}")
                if e.args == ("cannot schedule new futures after shutdown",):
                    # Event loop is shutdown, nothing else we can really do...
                    return
                await self._process_write_queue_delay()

    async def _flush_write_queue(self):
        """Flush any remaining items in the write queue to disk."""
        outstanding_items = list(self._write_queue.values())
        n_outstanding_items = len(outstanding_items)
        self._write_queue.clear()
        # When the task is cancelled, write all remaining items to disk.
        logger.debug(
            f"StateManagerDisk._flush_write_queue: writing {n_outstanding_items} remaining items to disk"
        )
        for item in outstanding_items:
            if item.token.get_and_reset_touched_state(item.state):
                await self._write_state(item.token, item.state)
        logger.debug(
            f"StateManagerDisk._flush_write_queue: Finished writing {n_outstanding_items} items"
        )

    async def _schedule_process_write_queue(self):
        """Schedule the write queue processing task if not already running."""
        if self._write_queue_task is None or self._write_queue_task.done():
            async with self._state_manager_lock:
                if self._write_queue_task is None or self._write_queue_task.done():
                    self._write_queue_task = asyncio.create_task(
                        self._process_write_queue(),
                        name="StateManagerDisk|WriteQueueProcessor",
                    )
                    await asyncio.sleep(0)  # Yield to allow the task to start.

    @override
    async def store_states(
        self,
        states: Sequence[tuple[StateToken, Any]],
        lease: StateLease | None,
        **context: Unpack[StateModificationContext],
    ) -> None:
        """Keep states in memory, and write the touched ones to disk.

        Args:
            states: The tokens and states to store.
            lease: The lease of the lock held on the states' ident, if any.
            context: The state modification context.
        """
        now = time.time()
        for token, state in states:
            self._put(token, state)
            if self._write_debounce_seconds > 0:
                # Deferred write to reduce disk IO overhead, if touched by then.
                key = str(token)
                if (queued_item := self._write_queue.get(key)) is None:
                    self._write_queue[key] = QueueItem(
                        token=token, state=state, timestamp=now
                    )
                else:
                    queued_item.state = state
            elif token.get_and_reset_touched_state(state):
                await self._write_state(token, state)
        self._track_idents(token for token, _ in states)
        # Ensure the processing task is scheduled to handle expirations and any deferred writes.
        await self._schedule_process_write_queue()

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
        ident = token.ident
        if ident not in self._states_locks:
            async with self._state_manager_lock:
                if ident not in self._states_locks:
                    self._states_locks[ident] = asyncio.Lock()

        async with self._states_locks[ident]:
            yield StateLease(ident=ident)

    async def close(self):
        """Close the state manager, flushing any pending writes to disk."""
        async with self._state_manager_lock:
            if self._write_queue_task:
                self._write_queue_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._write_queue_task
                self._write_queue_task = None
            # Dump unlocked locks.
            for token, lock in tuple(self._states_locks.items()):
                if not lock.locked():
                    self._states_locks.pop(token)
