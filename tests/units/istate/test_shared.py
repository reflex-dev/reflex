"""Unit tests for shared state fan-out to other linked clients."""

import asyncio
import pickle
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest

from reflex.istate.shared import (
    DISCONNECT_REAP_TASKS,
    SharedState,
    _do_update_other_tokens,
    _reap_disconnected_client,
    schedule_disconnect_reap,
)
from reflex.state import State
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


def _mock_reap_app(token_manager) -> tuple[Mock, Mock, list[str]]:
    """Create a mock app with one client linked to one shared state.

    Returns:
        The mock app, the mock shared state and the list collecting the
        token idents passed to modify_state.
    """
    modified_tokens: list[str] = []

    shared = Mock(spec=SharedState)
    shared._linked_from = {"gone", "other"}
    shared._on_subscriber_disconnected = AsyncMock()

    @asynccontextmanager
    async def modify_state(token, previous_dirty_vars=None):
        modified_tokens.append(token.ident)
        shared_root = Mock()
        shared_root.get_state = AsyncMock(return_value=shared)
        yield shared_root

    root_state = Mock(spec=State)
    root_state._reflex_internal_links = {"state.shared_sub": "room-token"}

    app = Mock()
    app.modify_state = modify_state
    app.event_namespace = Mock()
    app.event_namespace._token_manager = token_manager
    app.state_manager.get_state = AsyncMock(return_value=root_state)
    app._state = Mock()
    app._state.get_class_substate = Mock(return_value=State)
    return app, shared, modified_tokens


async def test_reap_disconnected_client_unsubscribes():
    """A client that stayed disconnected is removed from its linked states."""
    app, shared, modified_tokens = _mock_reap_app(LocalTokenManager())

    await _reap_disconnected_client(app, "gone", grace=0)

    assert modified_tokens == ["room-token"]
    assert shared._linked_from == {"other"}
    shared._on_subscriber_disconnected.assert_awaited_once_with("gone")


async def test_reap_skips_reconnected_client():
    """A client that reconnected within the grace is left subscribed."""
    manager = LocalTokenManager()
    manager.token_to_socket["gone"] = SocketRecord(
        instance_id=manager.instance_id, sid="sid1"
    )
    app, shared, modified_tokens = _mock_reap_app(manager)

    await _reap_disconnected_client(app, "gone", grace=0)

    assert modified_tokens == []
    assert shared._linked_from == {"gone", "other"}
    shared._on_subscriber_disconnected.assert_not_awaited()


async def test_reap_skips_unsubscribed_client():
    """A token no longer in the subscriber set does not trigger the hook."""
    app, shared, modified_tokens = _mock_reap_app(LocalTokenManager())

    await _reap_disconnected_client(app, "unknown", grace=0)

    assert modified_tokens == ["room-token"]
    assert shared._linked_from == {"gone", "other"}
    shared._on_subscriber_disconnected.assert_not_awaited()


def test_schedule_disconnect_reap_disabled(monkeypatch):
    """Grace 0 disables scheduling entirely."""
    monkeypatch.setenv("REFLEX_SHARED_STATE_DISCONNECT_GRACE", "0")
    app, _, _ = _mock_reap_app(LocalTokenManager())

    assert schedule_disconnect_reap(app, "gone") is None
    assert not DISCONNECT_REAP_TASKS


async def test_schedule_disconnect_reap_restarts_grace(monkeypatch):
    """A new disconnect for the same token cancels the pending reap."""
    monkeypatch.setenv("REFLEX_SHARED_STATE_DISCONNECT_GRACE", "60")
    app, _, modified_tokens = _mock_reap_app(LocalTokenManager())

    first = schedule_disconnect_reap(app, "gone")
    second = schedule_disconnect_reap(app, "gone")
    assert first is not None
    assert second is not None
    with pytest.raises(asyncio.CancelledError):
        await first
    assert {"gone": second} == DISCONNECT_REAP_TASKS

    second.cancel()
    with pytest.raises(asyncio.CancelledError):
        await second
    assert not DISCONNECT_REAP_TASKS
    assert modified_tokens == []
