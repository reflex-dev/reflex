"""Unit tests for shared state fan-out to other linked clients."""

import asyncio
import pickle
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest
from reflex_base import constants
from reflex_base.constants.state import FIELD_MARKER

import reflex as rx
from reflex.istate.shared import _do_update_other_tokens, _patch_state
from reflex.state import BaseState, State
from reflex.utils.token_manager import (
    LocalTokenManager,
    RedisTokenManager,
    SocketRecord,
)


@pytest.fixture
def mock_redis():
    """Create a mock Redis client.

    Returns:
        The mock Redis client.
    """
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.get_connection_kwargs = Mock(return_value={"db": 0})
    return redis


@pytest.fixture
def redis_manager(mock_redis):
    """Create a RedisTokenManager instance with mocked config.

    Returns:
        The RedisTokenManager instance.
    """
    with patch("reflex_base.config.get_config") as mock_get_config:
        mock_config = Mock()
        mock_config.redis_token_expiration = 3600
        mock_get_config.return_value = mock_config

        return RedisTokenManager(mock_redis)


def _mock_app(token_manager) -> tuple[Mock, list[str]]:
    """Create a mock app recording the tokens passed to modify_state.

    Returns:
        The mock app and the list collecting modified token idents.
    """
    modified_tokens: list[str] = []

    @asynccontextmanager
    async def modify_state(token, previous_dirty_vars=None):
        modified_tokens.append(token.ident)
        yield Mock()

    app = Mock()
    app.modify_state = modify_state
    app.event_namespace = Mock()
    app.event_namespace._token_manager = token_manager
    return app, modified_tokens


async def _run_update_other_tokens(app, affected_tokens: set[str]) -> None:
    """Run _do_update_other_tokens against a mock app and await its tasks."""
    with patch("reflex_base.registry.RegistrationContext.get") as mock_get:
        mock_get.return_value = Mock(app=app)
        tasks = _do_update_other_tokens(
            affected_tokens=affected_tokens,
            previous_dirty_vars={},
            state_type=State,
        )
    await asyncio.gather(*tasks)


async def test_update_other_tokens_local_manager():
    """With a LocalTokenManager, only locally connected tokens are updated."""
    manager = LocalTokenManager()
    manager.token_to_socket["connected"] = SocketRecord(
        instance_id=manager.instance_id, sid="sid1"
    )
    app, modified_tokens = _mock_app(manager)

    await _run_update_other_tokens(app, {"connected", "disconnected"})

    assert modified_tokens == ["connected"]


async def test_update_other_tokens_redis_cross_instance(redis_manager, mock_redis):
    """Tokens connected to another instance are resolved via redis and updated."""
    redis_manager.token_to_socket["local"] = SocketRecord(
        instance_id=redis_manager.instance_id, sid="sid1"
    )
    foreign_record = SocketRecord(instance_id="other-instance", sid="sid2")
    foreign_key = redis_manager._get_redis_key("foreign")
    mock_redis.get.side_effect = lambda key: (
        pickle.dumps(foreign_record) if key == foreign_key else None
    )
    app, modified_tokens = _mock_app(redis_manager)

    await _run_update_other_tokens(app, {"local", "foreign", "disconnected"})

    assert sorted(modified_tokens) == ["foreign", "local"]
    # The foreign socket record is cached locally for later emit_update routing.
    assert redis_manager.token_to_socket["foreign"] == foreign_record
    # Locally owned sockets are authoritative and never require a redis lookup.
    local_key = redis_manager._get_redis_key("local")
    assert local_key not in [call.args[0] for call in mock_redis.get.call_args_list]


class PatchRoot(BaseState):
    """The root of a tree a state is patched into."""


class PatchSource(PatchRoot):
    """A state swapped for another instance while patched."""

    who: str = "private"


class PatchReader(PatchRoot):
    """A state with a computed var reading the patched state."""

    @rx.var
    async def greeting(self) -> str:
        """Read the patched state.

        Returns:
            Its value.
        """
        return (await self.get_state(PatchSource)).who


@pytest.mark.asyncio
async def test_patch_state_recomputes_readers_after_restoring():
    """Computed vars read from a patched state are recomputed once it is swapped back."""
    root = PatchRoot(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    original = root.get_substate([PatchSource.get_name()])
    reader = root.get_substate([PatchReader.get_name()])
    # The state of another client, in a tree of its own.
    linked_root = PatchRoot(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    linked = linked_root.get_substate([PatchSource.get_name()])
    linked.who = "linked"  # pyright: ignore[reportAttributeAccessIssue]

    async with _patch_state(original_state=original, linked_state=linked):
        assert await reader.greeting == "linked"  # pyright: ignore[reportAttributeAccessIssue]
    assert await reader.greeting == "private"  # pyright: ignore[reportAttributeAccessIssue]


_PATCH_TEMPORARY_VAR = "temporary"
_PATCH_INTERVAL_VALUE_VAR = "interval_value"
_PATCH_ROOT_VALUE_VAR = "root_value"
_PATCH_ROUTER_VALUE_VAR = "router_client_token"
_PATCH_EXISTING_SUBSTATE = "existing"


class _LinkedStatePatchRoot(BaseState):
    """Root state for testing linked-state dirty propagation."""

    value: int = 0


class _LinkedStatePatchShared(_LinkedStatePatchRoot):
    """Substate used to exercise _patch_state without full SharedState setup."""

    counter: int = 0

    @rx.var
    def root_value(self) -> int:
        return self.value


class _LinkedStatePatchIntervalRoot(BaseState):
    """Root state for testing interval computed refreshes during patching."""

    value: int = 0


class _LinkedStatePatchIntervalShared(_LinkedStatePatchIntervalRoot):
    """Substate used to exercise interval computed refreshes."""

    counter: int = 0

    @rx.var(interval=60)
    def interval_value(self) -> int:
        return self.value


class _LinkedStatePatchRouterRoot(BaseState):
    """Root state with a computed value derived from the router."""

    @rx.var
    def router_client_token(self) -> str:
        return self.router.session.client_token

    @rx.var
    def unrelated_values(self) -> list[int]:
        return list(range(1000))


class _LinkedStatePatchRouterShared(_LinkedStatePatchRouterRoot):
    """Substate used to exercise root router-dependent computations."""

    counter: int = 0


@pytest.mark.asyncio
async def test_linked_state_event_does_not_dirty_root_state():
    """Linked-state events should not leak temporary router dirtiness."""
    private_tree = _LinkedStatePatchRoot()
    linked_tree = _LinkedStatePatchRoot()

    shared_state_name = _LinkedStatePatchShared.get_name()
    private_state = private_tree.substates[shared_state_name]
    linked_state = linked_tree.substates[shared_state_name]

    assert isinstance(private_state, _LinkedStatePatchShared)
    assert isinstance(linked_state, _LinkedStatePatchShared)

    private_tree._clean()

    async with _patch_state(private_state, linked_state, full_delta=False):
        linked_state.counter = 1

    assert set(constants.ROUTER_VARS).isdisjoint(private_tree.dirty_vars)
    assert constants.ROUTER_DATA not in private_tree.dirty_vars
    assert private_tree.get_full_name() not in private_tree.get_delta()


@pytest.mark.asyncio
async def test_linked_state_patch_does_not_emit_unchanged_router_computed_var():
    """Refreshing a router computed var should not emit it when unchanged."""
    private_tree = _LinkedStatePatchRouterRoot()
    linked_tree = _LinkedStatePatchRouterRoot()

    shared_state_name = _LinkedStatePatchRouterShared.get_name()
    private_state = private_tree.substates[shared_state_name]
    linked_state = linked_tree.substates[shared_state_name]

    original_value = private_tree.router_client_token
    private_tree._clean()

    async with _patch_state(private_state, linked_state, full_delta=False):
        assert private_tree.router_client_token == original_value
        assert _PATCH_ROUTER_VALUE_VAR not in private_tree.dirty_vars
        assert private_tree.get_full_name() not in private_tree.get_delta()


@pytest.mark.asyncio
async def test_linked_state_patch_skips_unrelated_computed_value_keys(
    monkeypatch: pytest.MonkeyPatch,
):
    """Only router-dependent computed values need a cache comparison key."""
    from reflex.istate import shared as shared_module

    private_tree = _LinkedStatePatchRouterRoot()
    linked_tree = _LinkedStatePatchRouterRoot()
    shared_state_name = _LinkedStatePatchRouterShared.get_name()
    private_state = private_tree.substates[shared_state_name]
    linked_state = linked_tree.substates[shared_state_name]

    unrelated_values = private_tree.unrelated_values
    private_tree._clean()
    delta_value_key = shared_module._delta_value_key
    unrelated_key_calls = []

    def track_unrelated_value_key(value):
        if value is unrelated_values:
            unrelated_key_calls.append(value)
        return delta_value_key(value)

    monkeypatch.setattr(shared_module, "_delta_value_key", track_unrelated_value_key)

    async with _patch_state(private_state, linked_state, full_delta=False):
        pass

    assert unrelated_key_calls == []


@pytest.mark.asyncio
async def test_linked_state_patch_restores_root_dirty_state_on_resolve_error():
    """Temporary root dirtiness should be cleaned if delta resolution fails."""
    private_tree = _LinkedStatePatchRoot()
    linked_tree = _LinkedStatePatchRoot()

    shared_state_name = _LinkedStatePatchShared.get_name()
    private_state = private_tree.substates[shared_state_name]
    linked_state = linked_tree.substates[shared_state_name]

    assert isinstance(private_state, _LinkedStatePatchShared)
    assert isinstance(linked_state, _LinkedStatePatchShared)

    private_tree.value = 1
    private_tree.dirty_substates.add(_PATCH_EXISTING_SUBSTATE)
    original_dirty_vars = set(private_tree.dirty_vars)
    original_dirty_substates = set(private_tree.dirty_substates)

    async def raise_resolve_error():
        await asyncio.sleep(0)
        msg = "delta resolution failed"
        raise RuntimeError(msg)

    object.__setattr__(private_tree, "_get_resolved_delta", raise_resolve_error)

    with pytest.raises(RuntimeError, match="delta resolution failed"):
        async with _patch_state(private_state, linked_state, full_delta=False):
            pass

    assert private_tree.dirty_vars == original_dirty_vars
    assert private_tree.dirty_substates == original_dirty_substates
    assert private_tree.substates[shared_state_name] is private_state
    assert linked_state.parent_state is linked_tree


@pytest.mark.asyncio
async def test_linked_state_patch_restores_descendant_dirty_state_on_resolve_error():
    """Temporary descendant dirtiness should be cleaned on resolution failure."""
    private_tree = _LinkedStatePatchRoot()
    linked_tree = _LinkedStatePatchRoot()

    shared_state_name = _LinkedStatePatchShared.get_name()
    private_state = private_tree.substates[shared_state_name]
    linked_state = linked_tree.substates[shared_state_name]

    async def raise_resolve_error():
        await asyncio.sleep(0)
        linked_state.dirty_vars.add(_PATCH_TEMPORARY_VAR)
        linked_state._mark_dirty()
        msg = "descendant delta resolution failed"
        raise RuntimeError(msg)

    object.__setattr__(private_tree, "_get_resolved_delta", raise_resolve_error)

    with pytest.raises(RuntimeError, match="descendant delta resolution failed"):
        async with _patch_state(private_state, linked_state, full_delta=False):
            pass

    assert linked_state.dirty_vars == set()
    assert linked_state.dirty_substates == set()
    assert private_tree.dirty_substates == set()


@pytest.mark.asyncio
async def test_linked_state_patch_restores_descendant_dirty_state_after_resolve():
    """Temporary descendant dirtiness should be cleaned after resolution."""
    private_tree = _LinkedStatePatchRoot()
    linked_tree = _LinkedStatePatchRoot()

    shared_state_name = _LinkedStatePatchShared.get_name()
    private_state = private_tree.substates[shared_state_name]
    linked_state = linked_tree.substates[shared_state_name]

    async def resolve_with_temporary_dirty_state():
        await asyncio.sleep(0)
        linked_state.dirty_vars.add(_PATCH_TEMPORARY_VAR)
        linked_state._mark_dirty()
        return {}

    object.__setattr__(
        private_tree, "_get_resolved_delta", resolve_with_temporary_dirty_state
    )

    async with _patch_state(private_state, linked_state, full_delta=False):
        assert private_tree.substates[shared_state_name] is linked_state

    assert linked_state.dirty_vars == set()
    assert linked_state.dirty_substates == set()
    assert private_tree.dirty_substates == set()


@pytest.mark.asyncio
async def test_linked_state_patch_preserves_interval_computed_refresh():
    """Interval computed vars refreshed during patching must be emitted."""
    private_tree = _LinkedStatePatchIntervalRoot()
    linked_tree = _LinkedStatePatchIntervalRoot()

    shared_state_name = _LinkedStatePatchIntervalShared.get_name()
    private_state = private_tree.substates[shared_state_name]
    linked_state = linked_tree.substates[shared_state_name]

    private_tree._clean()

    resolve_delta = private_tree._get_resolved_delta

    async def resolve_with_dirty_child():
        linked_state._mark_dirty()
        return await resolve_delta()

    object.__setattr__(private_tree, "_get_resolved_delta", resolve_with_dirty_child)

    async with _patch_state(private_state, linked_state, full_delta=False):
        assert private_tree.substates[shared_state_name] is linked_state
        interval_delta = private_tree.get_delta()

    assert _PATCH_INTERVAL_VALUE_VAR in linked_state.dirty_vars
    assert private_tree.dirty_substates == {linked_state.get_name()}
    assert (
        _PATCH_INTERVAL_VALUE_VAR + FIELD_MARKER
        in interval_delta[linked_state.get_full_name()]
    )


@pytest.mark.asyncio
async def test_linked_state_patch_preserves_root_dependent_computed_refresh():
    """Computed vars invalidated through the root must remain in the delta."""
    private_tree = _LinkedStatePatchRoot()
    linked_tree = _LinkedStatePatchRoot()

    shared_state_name = _LinkedStatePatchShared.get_name()
    private_state = private_tree.substates[shared_state_name]
    linked_state = linked_tree.substates[shared_state_name]

    private_tree._clean()

    resolve_delta = private_tree._get_resolved_delta

    async def resolve_with_root_change():
        private_tree.value = 1
        return await resolve_delta()

    object.__setattr__(private_tree, "_get_resolved_delta", resolve_with_root_change)

    async with _patch_state(private_state, linked_state, full_delta=False):
        assert private_tree.substates[shared_state_name] is linked_state
        root_dependent_delta = private_tree.get_delta()

    assert _PATCH_ROOT_VALUE_VAR in linked_state.dirty_vars
    assert private_tree.dirty_substates == {linked_state.get_name()}
    assert (
        _PATCH_ROOT_VALUE_VAR + FIELD_MARKER
        in root_dependent_delta[linked_state.get_full_name()]
    )


@pytest.mark.asyncio
async def test_linked_state_patch_restores_computed_cache_on_resolve_error():
    """Failed resolution should not hide a partially refreshed computed value."""
    private_tree = _LinkedStatePatchIntervalRoot()
    linked_tree = _LinkedStatePatchIntervalRoot()
    shared_state_name = _LinkedStatePatchIntervalShared.get_name()
    private_state = private_tree.substates[shared_state_name]
    linked_state = linked_tree.substates[shared_state_name]
    computed_var = _LinkedStatePatchIntervalShared.computed_vars[
        _PATCH_INTERVAL_VALUE_VAR
    ]
    cache_attr = computed_var._cache_attr
    last_updated_attr = computed_var._last_updated_attr
    cache_before = (
        hasattr(linked_state, cache_attr),
        getattr(linked_state, cache_attr, None),
        hasattr(linked_state, last_updated_attr),
        getattr(linked_state, last_updated_attr, None),
    )
    was_touched_before = linked_state._was_touched

    private_tree._clean()
    resolve_delta = private_tree._get_resolved_delta

    async def resolve_then_fail():
        linked_state._mark_dirty()
        linked_state._was_touched = True
        await resolve_delta()
        msg = "computed refresh failed"
        raise RuntimeError(msg)

    object.__setattr__(private_tree, "_get_resolved_delta", resolve_then_fail)

    with pytest.raises(RuntimeError, match="computed refresh failed"):
        async with _patch_state(private_state, linked_state, full_delta=False):
            assert private_tree.substates[shared_state_name] is linked_state

    assert linked_state.dirty_vars == set()
    assert linked_state._was_touched is was_touched_before
    assert (
        hasattr(linked_state, cache_attr),
        getattr(linked_state, cache_attr, None),
        hasattr(linked_state, last_updated_attr),
        getattr(linked_state, last_updated_attr, None),
    ) == cache_before
