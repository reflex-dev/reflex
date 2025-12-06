"""Base classes for shared / linked states."""

import contextlib
from collections.abc import AsyncIterator

from reflex.event import Event, get_hydrate_event
from reflex.state import BaseState, State, _override_base_method, _substate_key
from reflex.utils.exceptions import ReflexRuntimeError


class SharedStateBaseInternal(State):
    """The private base state for all shared states."""

    # Maps the state full_name to an arbitrary token it is linked to.
    _links: dict[str, str]
    # While _modify_linked_states is active, this holds the original substates for the client's tree.
    _original_substates: dict[str, tuple[BaseState, BaseState | None]]

    @classmethod
    def _init_var_dependency_dicts(cls):
        super()._init_var_dependency_dicts()
        if (
            "_links" in cls.inherited_backend_vars
            or (parent_state_cls := cls.get_parent_state()) is None
        ):
            return
        # Mark the internal state as always dirty so the state manager
        # automatically fetches this state containing the _links.
        parent_state_cls._always_dirty_substates.add(cls.get_name())

    def __getstate__(self):
        """Override redis serialization to remove temporary fields.

        Returns:
            The state dictionary without temporary fields.
        """
        s = super().__getstate__()
        # Don't want to persist the cached substates
        s.pop("_original_substates", None)
        s.pop("_previous_dirty_vars", None)
        return s

    @_override_base_method
    def _clean(self):
        """Override BaseState._clean to track the last set of dirty vars.

        This is necessary for applying dirty vars from one event to other linked states.
        """
        if hasattr(self, "_previous_dirty_vars"):
            self._previous_dirty_vars.clear()
            self._previous_dirty_vars.update(self.dirty_vars)
        super()._clean()

    @_override_base_method
    def _mark_dirty(self):
        """Override BaseState._mark_dirty to avoid marking certain vars as dirty.

        Since these internal fields are not persisted to redis, they shouldn't cause the
        state to be considered dirty either.
        """
        self.dirty_vars.discard("_original_substates")
        self.dirty_vars.discard("_previously_dirty_substates")
        if self.dirty_vars:
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

    async def _link_to(self, token: str):
        """Link this shared state to a token.

        After linking, subsequent access to this shared state will affect the
        linked token's state, and cause changes to be propagated to all other
        clients linked to that token.

        Args:
            token: The token to link to.

        Returns:
            The events to rehydrate the state after linking (these should be returned/yielded).
        """
        # TODO: Change StateManager to accept token + class instead of combining them in a string.
        if "_" in token:
            msg = f"Invalid token {token} for linking state {self.get_full_name()}, cannot use underscore (_) in the token name."
            raise ReflexRuntimeError(msg)
        state_name = self.get_full_name()
        self._links[state_name] = token
        async with self._modify_linked_states() as _:
            linked_state = await self.get_state(type(self))
            linked_state._linked_from.add(self.router.session.client_token)
            linked_state._linked_to = token
            linked_state.dirty_vars.update(self.base_vars)
            linked_state.dirty_vars.update(self.backend_vars)
            linked_state.dirty_vars.update(self.computed_vars)
            linked_state._mark_dirty()
            # Apply the updates into the existing state tree, then rehydrate.
            root_state = self._get_root_state()
            await root_state._get_resolved_delta()
            root_state._clean()
        return self._rehydrate()

    async def _unlink(self):
        """Unlink this shared state from its linked token.

        Returns:
            The events to rehydrate the state after unlinking (these should be returned/yielded
        """
        state_name = self.get_full_name()
        if state_name not in self._links:
            msg = f"State {state_name} is not linked and cannot be unlinked."
            raise ReflexRuntimeError(msg)
        self._links.pop(state_name)
        self._linked_from.discard(self.router.session.client_token)
        # Rehydrate after unlinking to restore original values.
        return self._rehydrate()

    async def _restore_original_substates(self, *_exc_info) -> None:
        """Restore the original substates that were linked."""
        root_state = self._get_root_state()
        for linked_state_name, (
            original_state,
            linked_parent_state,
        ) in self._original_substates.items():
            linked_state_cls = root_state.get_class_substate(linked_state_name)
            linked_state = await root_state.get_state(linked_state_cls)
            if (parent_state := linked_state.parent_state) is not None:
                parent_state.substates[original_state.get_name()] = original_state
                linked_state.parent_state = linked_parent_state
        self._original_substates = {}

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
        from reflex.istate.manager import get_state_manager

        exit_stack = contextlib.AsyncExitStack()
        held_locks: set[str] = set()
        linked_states: list[BaseState] = []
        current_dirty_vars: dict[str, set[str]] = {}
        affected_tokens: set[str] = set()
        # Go through all linked states and patch them in if they are present in the tree
        for linked_state_name, linked_token in self._links.items():
            linked_state_cls = self.get_root_state().get_class_substate(
                linked_state_name
            )
            # TODO: Avoid always fetched linked states, it should be based on
            # whether the state is accessed, however then `get_state` would need
            # to know how to fetch in a linked state.
            original_state = await self.get_state(linked_state_cls)
            if linked_token not in held_locks:
                linked_root_state = await exit_stack.enter_async_context(
                    get_state_manager().modify_state(
                        _substate_key(linked_token, linked_state_cls)
                    )
                )
                held_locks.add(linked_token)
            else:
                linked_root_state = await get_state_manager().get_state(
                    _substate_key(linked_token, linked_state_cls)
                )
            linked_state = await linked_root_state.get_state(linked_state_cls)
            self._original_substates[linked_state_name] = (
                original_state,
                linked_state.parent_state,
            )
            if (parent_state := original_state.parent_state) is not None:
                parent_state.substates[original_state.get_name()] = linked_state
                linked_state.parent_state = parent_state
                linked_states.append(linked_state)
            if (
                previous_dirty_vars
                and (dv := previous_dirty_vars.get(linked_state_name)) is not None
            ):
                linked_state.dirty_vars.update(dv)
                linked_state._mark_dirty()
        # Make sure to restore the non-linked substates after exiting the context.
        if self._original_substates:
            exit_stack.push_async_exit(self._restore_original_substates)
        async with exit_stack:
            yield None
            # Collect dirty vars and other affected clients that need to be updated.
            for linked_state in linked_states:
                if hasattr(linked_state, "_previous_dirty_vars"):
                    current_dirty_vars[linked_state.get_full_name()] = set(
                        linked_state._previous_dirty_vars
                    )
                if linked_state._get_was_touched():
                    affected_tokens.update(
                        token
                        for token in linked_state._linked_from
                        if token != self.router.session.client_token
                    )

        # Only propagate dirty vars when we are not already propagating from another state.
        if previous_dirty_vars is None:
            from reflex.utils.prerequisites import get_app

            app = get_app().app

            for affected_token in affected_tokens:
                # Don't send updates for disconnected clients.
                if (
                    affected_token
                    not in app.event_namespace._token_manager.token_to_socket
                ):
                    continue
                async with app.modify_state(
                    _substate_key(affected_token, type(self)),
                    previous_dirty_vars=current_dirty_vars,
                ):
                    pass


class SharedState(SharedStateBaseInternal, mixin=True):
    """Mixin for defining new shared states."""

    _linked_from: set[str]
    _linked_to: str
    _previous_dirty_vars: set[str]

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Initialize subclass and set up shared state fields.

        Args:
            **kwargs: The kwargs to pass to the init_subclass method.
        """
        kwargs["mixin"] = False
        cls._mixin = False
        super().__init_subclass__(**kwargs)
