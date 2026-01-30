"""Base classes for shared / linked states."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Self, TypeVar

from reflex.constants import ROUTER_DATA
from reflex.event import Event, get_hydrate_event
from reflex.state import BaseState, State, _override_base_method, _substate_key
from reflex.utils import console
from reflex.utils.exceptions import ReflexRuntimeError

UPDATE_OTHER_CLIENT_TASKS: set[asyncio.Task] = set()
LINKED_STATE = TypeVar("LINKED_STATE", bound="SharedStateBaseInternal")


def _log_update_client_errors(task: asyncio.Task):
    """Log errors from updating other clients.

    Args:
        task: The asyncio task to check for errors.
    """
    try:
        task.result()
    except Exception as e:
        console.warn(f"Error updating linked client: {e}")
    finally:
        UPDATE_OTHER_CLIENT_TASKS.discard(task)


def _do_update_other_tokens(
    affected_tokens: set[str],
    previous_dirty_vars: dict[str, set[str]],
    state_type: type[BaseState],
) -> list[asyncio.Task]:
    """Update other clients after a shared state update.

    Submit the updates in separate asyncio tasks to avoid deadlocking.

    Args:
        affected_tokens: The tokens to update.
        previous_dirty_vars: The dirty vars to apply to other clients.
        state_type: The type of the shared state.

    Returns:
        The list of asyncio tasks created to perform the updates.
    """
    from reflex.utils.prerequisites import get_app

    app = get_app().app

    async def _update_client(token: str):
        async with app.modify_state(
            _substate_key(token, state_type),
            previous_dirty_vars=previous_dirty_vars,
        ):
            pass

    tasks = []
    for affected_token in affected_tokens:
        # Don't send updates for disconnected clients.
        if affected_token not in app.event_namespace._token_manager.token_to_socket:
            continue
        # TODO: remove disconnected clients after some time.
        t = asyncio.create_task(_update_client(affected_token))
        UPDATE_OTHER_CLIENT_TASKS.add(t)
        t.add_done_callback(_log_update_client_errors)
        tasks.append(t)
    return tasks


@contextlib.asynccontextmanager
async def _patch_state(
    original_state: BaseState, linked_state: BaseState, full_delta: bool = False
):
    """Patch the linked state into the original state's tree, restoring it afterward.

    Args:
        original_state: The original shared state.
        linked_state: The linked shared state.
        full_delta: If True, mark all Vars in linked_state dirty and resolve
            the delta from the root. This option is used when linking or unlinking
            to ensure that other computed vars in the tree pick up the newly
            linked/unlinked values.
    """
    if (original_parent_state := original_state.parent_state) is None:
        msg = "Cannot patch root state as linked state."
        raise ReflexRuntimeError(msg)

    state_name = original_state.get_name()
    original_parent_state.substates[state_name] = linked_state
    linked_parent_state = linked_state.parent_state
    linked_state.parent_state = original_parent_state
    try:
        if full_delta:
            linked_state.dirty_vars.update(linked_state.base_vars)
            linked_state.dirty_vars.update(linked_state.backend_vars)
            linked_state.dirty_vars.update(linked_state.computed_vars)
            linked_state._mark_dirty()
        # Apply the updates into the existing state tree for rehydrate.
        root_state = original_state._get_root_state()
        root_state.dirty_vars.add("router")
        root_state.dirty_vars.add(ROUTER_DATA)
        root_state._mark_dirty()
        await root_state._get_resolved_delta()
        yield
    finally:
        original_parent_state.substates[state_name] = original_state
        linked_state.parent_state = linked_parent_state


class SharedStateBaseInternal(State):
    """The private base state for all shared states."""

    _exit_stack: contextlib.AsyncExitStack | None = None
    _held_locks: dict[str, dict[type[BaseState], BaseState]] | None = None

    def __getstate__(self):
        """Override redis serialization to remove temporary fields.

        Returns:
            The state dictionary without temporary fields.
        """
        s = super().__getstate__()
        s.pop("_previous_dirty_vars", None)
        s.pop("_exit_stack", None)
        s.pop("_held_locks", None)
        return s

    @_override_base_method
    def _clean(self):
        """Override BaseState._clean to track the last set of dirty vars.

        This is necessary for applying dirty vars from one event to other linked states.
        """
        if (
            previous_dirty_vars := getattr(self, "_previous_dirty_vars", None)
        ) is not None:
            previous_dirty_vars.clear()
            previous_dirty_vars.update(self.dirty_vars)
        super()._clean()

    @_override_base_method
    def _mark_dirty(self):
        """Override BaseState._mark_dirty to avoid marking certain vars as dirty.

        Since these internal fields are not persisted to redis, they shouldn't cause the
        state to be considered dirty either.
        """
        self.dirty_vars.discard("_previous_dirty_vars")
        self.dirty_vars.discard("_exit_stack")
        self.dirty_vars.discard("_held_locks")
        # Only mark dirty if there are still dirty vars, or any substate is dirty
        if self.dirty_vars or any(
            substate.dirty_vars for substate in self.substates.values()
        ):
            super()._mark_dirty()

    def _rehydrate(self):
        """Get the events to rehydrate the state.

        Returns:
            The events to rehydrate the state (these should be returned/yielded).
        """
        return [
            Event(
                token=self.router.session.client_token,
                name=get_hydrate_event(self._get_root_state()),
            ),
            State.set_is_hydrated(True),
        ]

    async def _link_to(self, token: str) -> Self:
        """Link this shared state to a token.

        After linking, subsequent access to this shared state will affect the
        linked token's state, and cause changes to be propagated to all other
        clients linked to that token.

        Args:
            token: The token to link to (Cannot contain underscore characters).

        Returns:
            The newly linked state.

        Raises:
            ReflexRuntimeError: If linking fails or token is invalid.
        """
        if not token:
            msg = "Cannot link shared state to empty token."
            raise ReflexRuntimeError(msg)
        if not isinstance(self, SharedState):
            msg = "Can only link SharedState instances."
            raise RuntimeError(msg)
        if self._linked_to == token:
            return self  # already linked to this token
        if self._linked_to and self._linked_to != token:
            # Disassociate from previous linked token since unlink will not be called.
            self._linked_from.discard(self.router.session.client_token)
        # TODO: Change StateManager to accept token + class instead of combining them in a string.
        if "_" in token:
            msg = f"Invalid token {token} for linking state {self.get_full_name()}, cannot use underscore (_) in the token name."
            raise ReflexRuntimeError(msg)

        # Associate substate with the given link token.
        state_name = self.get_full_name()
        if self._reflex_internal_links is None:
            self._reflex_internal_links = {}
        self._reflex_internal_links[state_name] = token
        return await self._internal_patch_linked_state(token, full_delta=True)

    async def _unlink(self):
        """Unlink this shared state from its linked token.

        Returns:
            The events to rehydrate the state after unlinking (these should be returned/yielded).
        """
        from reflex.istate.manager import get_state_manager

        if not isinstance(self, SharedState):
            msg = "Can only unlink SharedState instances."
            raise ReflexRuntimeError(msg)

        state_name = self.get_full_name()
        if (
            not self._reflex_internal_links
            or state_name not in self._reflex_internal_links
        ):
            msg = f"State {state_name} is not linked and cannot be unlinked."
            raise ReflexRuntimeError(msg)

        # Break the linkage for future events.
        self._reflex_internal_links.pop(state_name)
        self._linked_from.discard(self.router.session.client_token)

        # Patch in the original state, apply updates, then rehydrate.
        private_root_state = await get_state_manager().get_state(
            _substate_key(self.router.session.client_token, type(self))
        )
        private_state = await private_root_state.get_state(type(self))
        async with _patch_state(
            original_state=self,
            linked_state=private_state,
            full_delta=True,
        ):
            return self._rehydrate()

    async def _internal_patch_linked_state(
        self, token: str, full_delta: bool = False
    ) -> Self:
        """Load and replace this state with the linked state for a given token.

        Must be called inside a `_modify_linked_states` context, to ensure locks are
        released after the event is done processing.

        Args:
            token: The token of the linked state.
            full_delta: If True, mark all Vars in linked_state dirty and resolve
                delta to update cached computed vars

        Returns:
            The state that was linked into the tree.
        """
        from reflex.istate.manager import get_state_manager

        if self._exit_stack is None or self._held_locks is None:
            msg = "Cannot link shared state outside of _modify_linked_states context."
            raise ReflexRuntimeError(msg)

        # Get the newly linked state and update pointers/delta for subsequent events.
        if token not in self._held_locks:
            linked_root_state = await self._exit_stack.enter_async_context(
                get_state_manager().modify_state(_substate_key(token, type(self)))
            )
            self._held_locks.setdefault(token, {})
        else:
            linked_root_state = await get_state_manager().get_state(
                _substate_key(token, type(self))
            )
        linked_state = await linked_root_state.get_state(type(self))
        if not isinstance(linked_state, SharedState):
            msg = f"Linked state for token {token} is not a SharedState."
            raise ReflexRuntimeError(msg)
        # Avoid unnecessary dirtiness of shared state when there are no changes.
        if type(self) not in self._held_locks[token]:
            self._held_locks[token][type(self)] = linked_state
        if self.router.session.client_token not in linked_state._linked_from:
            linked_state._linked_from.add(self.router.session.client_token)
        if linked_state._linked_to != token:
            linked_state._linked_to = token
        await self._exit_stack.enter_async_context(
            _patch_state(
                original_state=self,
                linked_state=linked_state,
                full_delta=full_delta,
            )
        )
        return linked_state

    def _held_locks_linked_states(self) -> list["SharedState"]:
        """Get all linked states currently held by this state.

        Returns:
            The list of linked states currently held.
        """
        if self._held_locks is None:
            return []
        return [
            linked_state
            for linked_state_cls_to_instance in self._held_locks.values()
            for linked_state in linked_state_cls_to_instance.values()
            if isinstance(linked_state, SharedState)
        ]

    @contextlib.asynccontextmanager
    async def _modify_linked_states(
        self, previous_dirty_vars: dict[str, set[str]] | None = None
    ) -> AsyncIterator[None]:
        """Take lock, fetch all linked states, and patch them into the current state tree.

        If previous_dirty_vars is NOT provided, then any dirty vars after
        exiting the context will be applied to all other clients linked to this
        state's linked token.

        Args:
            previous_dirty_vars: When apply linked state changes to other
                tokens, provide mapping of state full_name to set of dirty vars.

        Yields:
            None.
        """
        if self._exit_stack is not None:
            msg = "Cannot nest _modify_linked_states contexts."
            raise ReflexRuntimeError(msg)
        if self._reflex_internal_links is None:
            msg = "No linked states to modify."
            raise ReflexRuntimeError(msg)
        self._exit_stack = contextlib.AsyncExitStack()
        self._held_locks = {}
        current_dirty_vars: dict[str, set[str]] = {}
        affected_tokens: set[str] = set()
        try:
            # Go through all linked states and patch them in if they are present in the tree
            for linked_state_name, linked_token in self._reflex_internal_links.items():
                linked_state_cls: type[SharedState] = (
                    self.get_root_state().get_class_substate(  # pyright: ignore[reportAssignmentType]
                        linked_state_name
                    )
                )
                try:
                    original_state = self._get_state_from_cache(linked_state_cls)
                except ValueError:
                    # This state wasn't required for processing the event.
                    continue
                linked_state = await original_state._internal_patch_linked_state(
                    linked_token
                )
                if (
                    previous_dirty_vars
                    and (dv := previous_dirty_vars.get(linked_state_name)) is not None
                ):
                    linked_state.dirty_vars.update(dv)
                    linked_state._mark_dirty()
            async with self._exit_stack:
                yield None
                # Collect dirty vars and other affected clients that need to be updated.
                for linked_state in self._held_locks_linked_states():
                    if linked_state._previous_dirty_vars is not None:
                        current_dirty_vars[linked_state.get_full_name()] = set(
                            linked_state._previous_dirty_vars
                        )
                    if (
                        linked_state._get_was_touched()
                        or linked_state._previous_dirty_vars is not None
                    ):
                        affected_tokens.update(
                            token
                            for token in linked_state._linked_from
                            if token != self.router.session.client_token
                        )
        finally:
            self._exit_stack = None

        # Only propagate dirty vars when we are not already propagating from another state.
        if previous_dirty_vars is None:
            _do_update_other_tokens(
                affected_tokens=affected_tokens,
                previous_dirty_vars=current_dirty_vars,
                state_type=type(self),
            )


class SharedState(SharedStateBaseInternal, mixin=True):
    """Mixin for defining new shared states."""

    _linked_from: set[str] = set()
    _linked_to: str = ""
    _previous_dirty_vars: set[str] = set()

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Initialize subclass and set up shared state fields.

        Args:
            **kwargs: The kwargs to pass to the init_subclass method.
        """
        kwargs["mixin"] = False
        cls._mixin = False
        super().__init_subclass__(**kwargs)
        root_state = cls.get_root_state()
        if root_state.backend_vars["_reflex_internal_links"] is None:
            root_state.backend_vars["_reflex_internal_links"] = {}
        if root_state is State:
            # Always fetch SharedStateBaseInternal to access
            # `_modify_linked_states` without having to use `.get_state()` which
            # pulls in all linked states and substates which may not actually be
            # accessed for this event.
            root_state._always_dirty_substates.add(SharedStateBaseInternal.get_name())
