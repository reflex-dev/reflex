"""A state manager that stores states on disk."""

import asyncio
import contextlib
import dataclasses
import functools
import time
from collections.abc import AsyncIterator
from hashlib import md5
from pathlib import Path

from typing_extensions import Unpack, override

from reflex.environment import environment
from reflex.istate.manager import (
    StateManager,
    StateModificationContext,
    _default_token_expiration,
)
from reflex.state import BaseState, _split_substate_key, _substate_key
from reflex.utils import console, path_ops, prerequisites
from reflex.utils.misc import run_in_thread


@dataclasses.dataclass(frozen=True)
class QueueItem:
    """An item in the write queue."""

    token: str
    state: BaseState
    timestamp: float


@dataclasses.dataclass
class StateManagerDisk(StateManager):
    """A state manager that stores states on disk."""

    # The mapping of client ids to states.
    states: dict[str, BaseState] = dataclasses.field(default_factory=dict)

    # The mutex ensures the dict of mutexes is updated exclusively
    _state_manager_lock: asyncio.Lock = dataclasses.field(default=asyncio.Lock())

    # The dict of mutexes for each client
    _states_locks: dict[str, asyncio.Lock] = dataclasses.field(
        default_factory=dict,
        init=False,
    )

    # The token expiration time (s).
    token_expiration: int = dataclasses.field(default_factory=_default_token_expiration)

    # Last time a token was touched.
    _token_last_touched: dict[str, float] = dataclasses.field(
        default_factory=dict,
        init=False,
    )

    # Pending writes
    _write_queue: dict[str, QueueItem] = dataclasses.field(
        default_factory=dict,
        init=False,
    )
    _write_queue_task: asyncio.Task | None = None
    _write_debounce_seconds: float = dataclasses.field(
        default=environment.REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS.get()
    )

    def __post_init__(self):
        """Create a new state manager."""
        path_ops.mkdir(self.states_directory)

        self._purge_expired_states()

    @functools.cached_property
    def states_directory(self) -> Path:
        """Get the states directory.

        Returns:
            The states directory.
        """
        return prerequisites.get_states_dir()

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

    def token_path(self, token: str) -> Path:
        """Get the path for a token.

        Args:
            token: The token to get the path for.

        Returns:
            The path for the token.
        """
        return (
            self.states_directory / f"{md5(token.encode()).hexdigest()}.pkl"
        ).absolute()

    async def load_state(self, token: str) -> BaseState | None:
        """Load a state object based on the provided token.

        Args:
            token: The token used to identify the state object.

        Returns:
            The loaded state object or None.
        """
        token_path = self.token_path(token)

        if token_path.exists():
            try:
                with token_path.open(mode="rb") as file:
                    return BaseState._deserialize(fp=file)
            except Exception:
                pass
        return None

    async def populate_substates(
        self, client_token: str, state: BaseState, root_state: BaseState
    ):
        """Populate the substates of a state object.

        Args:
            client_token: The client token.
            state: The state object to populate.
            root_state: The root state object.
        """
        for substate in state.get_substates():
            substate_token = _substate_key(client_token, substate)

            fresh_instance = await root_state.get_state(substate)
            instance = await self.load_state(substate_token)
            if instance is not None:
                # Ensure all substates exist, even if they weren't serialized previously.
                instance.substates = fresh_instance.substates
            else:
                instance = fresh_instance
            state.substates[substate.get_name()] = instance
            instance.parent_state = state

            await self.populate_substates(client_token, instance, root_state)

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
        self._token_last_touched[client_token] = time.time()
        root_state = self.states.get(client_token)
        if root_state is not None:
            # Retrieved state from memory.
            return root_state

        # Deserialize root state from disk.
        root_state = await self.load_state(_substate_key(client_token, self.state))
        # Create a new root state tree with all substates instantiated.
        fresh_root_state = self.state(_reflex_internal_init=True)
        if root_state is None:
            root_state = fresh_root_state
        else:
            # Ensure all substates exist, even if they were not serialized previously.
            root_state.substates = fresh_root_state.substates
        self.states[client_token] = root_state
        await self.populate_substates(client_token, root_state, root_state)
        return root_state

    async def set_state_for_substate(self, client_token: str, substate: BaseState):
        """Set the state for a substate.

        Args:
            client_token: The client token.
            substate: The substate to set.
        """
        substate_token = _substate_key(client_token, substate)

        if substate._get_was_touched():
            substate._was_touched = False  # Reset the touched flag after serializing.
            pickle_state = substate._serialize()
            if pickle_state:
                if not self.states_directory.exists():
                    self.states_directory.mkdir(parents=True, exist_ok=True)
                await run_in_thread(
                    lambda: self.token_path(substate_token).write_bytes(pickle_state),
                )

        for substate_substate in substate.substates.values():
            await self.set_state_for_substate(client_token, substate_substate)

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
                    token = item.token
                    client_token, _ = _split_substate_key(token)
                    await self.set_state_for_substate(
                        client_token, self._write_queue.pop(token).state
                    )
                # Check for expired states to purge.
                for token, last_touched in list(self._token_last_touched.items()):
                    if now - last_touched > self.token_expiration:
                        self._token_last_touched.pop(token)
                        self.states.pop(token, None)
                await run_in_thread(self._purge_expired_states)
                await self._process_write_queue_delay()
            except asyncio.CancelledError:  # noqa: PERF203
                await self._flush_write_queue()
                raise
            except Exception as e:
                console.error(f"Error processing write queue: {e!r}")
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
        console.debug(
            f"StateManagerDisk._flush_write_queue: writing {n_outstanding_items} remaining items to disk"
        )
        for item in outstanding_items:
            token = item.token
            client_token, _ = _split_substate_key(token)
            await self.set_state_for_substate(
                client_token,
                item.state,
            )
        console.debug(
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
    async def set_state(
        self, token: str, state: BaseState, **context: Unpack[StateModificationContext]
    ):
        """Set the state for a token.

        Args:
            token: The token to set the state for.
            state: The state to set.
            context: The state modification context.
        """
        client_token, _ = _split_substate_key(token)
        if self._write_debounce_seconds > 0:
            # Deferred write to reduce disk IO overhead.
            if client_token not in self._write_queue:
                self._write_queue[client_token] = QueueItem(
                    token=client_token,
                    state=state,
                    timestamp=time.time(),
                )
        else:
            # Immediate write to disk.
            await self.set_state_for_substate(client_token, state)
        # Ensure the processing task is scheduled to handle expirations and any deferred writes.
        await self._schedule_process_write_queue()

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
        # Disk state manager ignores the substate suffix and always returns the top-level state.
        client_token, _ = _split_substate_key(token)
        if client_token not in self._states_locks:
            async with self._state_manager_lock:
                if client_token not in self._states_locks:
                    self._states_locks[client_token] = asyncio.Lock()

        async with self._states_locks[client_token]:
            state = await self.get_state(token)
            yield state
            await self.set_state(token, state, **context)

    async def close(self):
        """Close the state manager, flushing any pending writes to disk."""
        async with self._state_manager_lock:
            if self._write_queue_task:
                self._write_queue_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._write_queue_task
                    self._write_queue_task = None
