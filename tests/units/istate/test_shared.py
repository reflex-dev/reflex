"""Unit tests for shared state fan-out to other linked clients."""

import asyncio
import pickle
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest

from reflex.istate.shared import _do_update_other_tokens
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
