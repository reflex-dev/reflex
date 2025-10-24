"""Unit tests for TokenManager implementations."""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from reflex.utils.token_manager import (
    LocalTokenManager,
    RedisTokenManager,
    SocketRecord,
    TokenManager,
)


class TestTokenManager:
    """Tests for the TokenManager factory."""

    @patch("reflex.utils.token_manager.prerequisites.check_redis_used")
    @patch("reflex.utils.token_manager.prerequisites.get_redis")
    def test_create_local_when_no_redis(self, mock_get_redis, mock_check_redis_used):
        """Test factory creates LocalTokenManager when Redis is not available.

        Args:
            mock_get_redis: Mock for prerequisites.get_redis.
            mock_check_redis_used: Mock for prerequisites.check_redis_used.
        """
        mock_check_redis_used.return_value = False

        manager = TokenManager.create()

        assert isinstance(manager, LocalTokenManager)
        mock_get_redis.assert_not_called()

    @patch("reflex.utils.token_manager.prerequisites.check_redis_used")
    @patch("reflex.utils.token_manager.prerequisites.get_redis")
    def test_create_local_when_redis_client_none(
        self, mock_get_redis, mock_check_redis_used
    ):
        """Test factory creates LocalTokenManager when Redis client is None.

        Args:
            mock_get_redis: Mock for prerequisites.get_redis.
            mock_check_redis_used: Mock for prerequisites.check_redis_used.
        """
        mock_check_redis_used.return_value = True
        mock_get_redis.return_value = None

        manager = TokenManager.create()

        assert isinstance(manager, LocalTokenManager)

    @patch("reflex.utils.token_manager.prerequisites.check_redis_used")
    @patch("reflex.utils.token_manager.prerequisites.get_redis")
    def test_create_redis_when_redis_available(
        self, mock_get_redis, mock_check_redis_used
    ):
        """Test factory creates RedisTokenManager when Redis is available.

        Args:
            mock_get_redis: Mock for prerequisites.get_redis.
            mock_check_redis_used: Mock for prerequisites.check_redis_used.
        """
        mock_check_redis_used.return_value = True
        mock_redis_client = Mock()
        mock_get_redis.return_value = mock_redis_client

        manager = TokenManager.create()

        assert isinstance(manager, RedisTokenManager)
        assert manager.redis is mock_redis_client


class TestLocalTokenManager:
    """Tests for LocalTokenManager."""

    @pytest.fixture
    def manager(self):
        """Create a LocalTokenManager instance.

        Returns:
            A LocalTokenManager instance for testing.
        """
        return LocalTokenManager()

    @pytest.mark.parametrize(
        ("token", "sid"),
        [
            ("token1", "sid1"),
            ("test-token", "test-sid"),
            ("12345", "67890"),
        ],
    )
    async def test_link_token_to_sid_normal_case(self, manager, token, sid):
        """Test normal token linking returns None.

        Args:
            manager: LocalTokenManager fixture instance.
            token: Token string to test.
            sid: Session ID string to test.
        """
        result = await manager.link_token_to_sid(token, sid)

        assert result is None
        assert manager.token_to_sid[token] == sid
        assert manager.sid_to_token[sid] == token

    async def test_link_token_to_sid_same_token_same_sid(self, manager):
        """Test linking same token to same SID (reconnection).

        Args:
            manager: LocalTokenManager fixture instance.
        """
        token, sid = "token1", "sid1"

        await manager.link_token_to_sid(token, sid)
        result = await manager.link_token_to_sid(token, sid)

        assert result is None
        assert manager.token_to_sid[token] == sid
        assert manager.sid_to_token[sid] == token

    async def test_link_token_to_sid_duplicate_token_different_sid(self, manager):
        """Test duplicate token detection generates new token.

        Args:
            manager: LocalTokenManager fixture instance.
        """
        token = "duplicate_token"
        sid1, sid2 = "sid1", "sid2"

        # First connection
        result1 = await manager.link_token_to_sid(token, sid1)
        assert result1 is None

        # Duplicate token with different SID
        result2 = await manager.link_token_to_sid(token, sid2)
        assert result2 is not None
        assert result2 != token

        # Check mappings
        assert manager.token_to_sid[result2] == sid2
        assert manager.sid_to_token[sid2] == result2
        assert manager.token_to_sid[token] == sid1

    @pytest.mark.parametrize(
        ("token", "sid"),
        [
            ("token1", "sid1"),
            ("test-token", "test-sid"),
        ],
    )
    async def test_disconnect_token(self, manager, token, sid):
        """Test token disconnection cleans up mappings.

        Args:
            manager: LocalTokenManager fixture instance.
            token: Token string to test.
            sid: Session ID string to test.
        """
        await manager.link_token_to_sid(token, sid)

        await manager.disconnect_token(token, sid)

        assert token not in manager.token_to_sid
        assert sid not in manager.sid_to_token

    async def test_disconnect_nonexistent_token(self, manager):
        """Test disconnecting nonexistent token doesn't raise error.

        Args:
            manager: LocalTokenManager fixture instance.
        """
        await manager.disconnect_token("nonexistent", "nonexistent")

        assert len(manager.token_to_sid) == 0
        assert len(manager.sid_to_token) == 0


class TestRedisTokenManager:
    """Tests for RedisTokenManager."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client.

        Returns:
            AsyncMock configured as Redis client for testing.
        """
        redis = AsyncMock()
        redis.exists = AsyncMock()
        redis.set = AsyncMock()
        redis.delete = AsyncMock()
        return redis

    @pytest.fixture
    def manager(self, mock_redis):
        """Create a RedisTokenManager instance with mocked config.

        Args:
            mock_redis: Mock Redis client fixture.

        Returns:
            RedisTokenManager instance for testing.
        """
        with patch("reflex.config.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.redis_token_expiration = 3600
            mock_get_config.return_value = mock_config

            return RedisTokenManager(mock_redis)

    def test_get_redis_key(self, manager):
        """Test Redis key generation follows expected pattern.

        Args:
            manager: RedisTokenManager fixture instance.
        """
        token = "test_token_123"
        expected_key = f"token_manager_socket_record_{token}"

        assert manager._get_redis_key(token) == expected_key

    async def test_link_token_to_sid_normal_case(self, manager, mock_redis):
        """Test normal token linking stores in both Redis and local dicts.

        Args:
            manager: RedisTokenManager fixture instance.
            mock_redis: Mock Redis client fixture.
        """
        token, sid = "token1", "sid1"
        mock_redis.exists.return_value = False

        result = await manager.link_token_to_sid(token, sid)

        assert result is None
        mock_redis.exists.assert_called_once_with(
            f"token_manager_socket_record_{token}"
        )
        mock_redis.set.assert_called_once_with(
            f"token_manager_socket_record_{token}",
            json.dumps({"instance_id": manager.instance_id, "sid": sid}),
            ex=3600,
        )
        assert manager.token_to_socket[token].sid == sid
        assert manager.sid_to_token[sid] == token

    async def test_link_token_to_sid_reconnection_skips_redis(
        self, manager, mock_redis
    ):
        """Test reconnection with same token/SID skips Redis check.

        Args:
            manager: RedisTokenManager fixture instance.
            mock_redis: Mock Redis client fixture.
        """
        token, sid = "token1", "sid1"
        manager.token_to_socket[token] = SocketRecord(
            instance_id=manager.instance_id, sid=sid
        )

        result = await manager.link_token_to_sid(token, sid)

        assert result is None
        mock_redis.exists.assert_not_called()
        mock_redis.set.assert_not_called()

    async def test_link_token_to_sid_duplicate_detected(self, manager, mock_redis):
        """Test duplicate token detection generates new token.

        Args:
            manager: RedisTokenManager fixture instance.
            mock_redis: Mock Redis client fixture.
        """
        token, sid = "token1", "sid1"
        mock_redis.exists.return_value = True

        result = await manager.link_token_to_sid(token, sid)

        assert result is not None
        assert result != token
        assert len(result) == 36  # UUID4 length

        mock_redis.exists.assert_called_once_with(
            f"token_manager_socket_record_{token}"
        )
        mock_redis.set.assert_called_once_with(
            f"token_manager_socket_record_{result}",
            json.dumps({"instance_id": manager.instance_id, "sid": sid}),
            ex=3600,
        )
        assert manager.token_to_sid[result] == sid
        assert manager.sid_to_token[sid] == result

    async def test_link_token_to_sid_redis_error_fallback(self, manager, mock_redis):
        """Test Redis error falls back to local manager behavior.

        Args:
            manager: RedisTokenManager fixture instance.
            mock_redis: Mock Redis client fixture.
        """
        token, sid = "token1", "sid1"
        mock_redis.exists.side_effect = Exception("Redis connection error")

        with patch.object(
            LocalTokenManager, "link_token_to_sid", new_callable=AsyncMock
        ) as mock_super:
            mock_super.return_value = None

            result = await manager.link_token_to_sid(token, sid)

            assert result is None
            mock_super.assert_called_once_with(token, sid)

    async def test_link_token_to_sid_redis_set_error_continues(
        self, manager, mock_redis
    ):
        """Test Redis set error doesn't prevent local storage.

        Args:
            manager: RedisTokenManager fixture instance.
            mock_redis: Mock Redis client fixture.
        """
        token, sid = "token1", "sid1"
        mock_redis.exists.return_value = False
        mock_redis.set.side_effect = Exception("Redis set error")

        result = await manager.link_token_to_sid(token, sid)

        assert result is None
        assert manager.token_to_sid[token] == sid
        assert manager.sid_to_token[sid] == token

    async def test_disconnect_token_owned_locally(self, manager, mock_redis):
        """Test disconnect cleans up both Redis and local mappings when owned locally.

        Args:
            manager: RedisTokenManager fixture instance.
            mock_redis: Mock Redis client fixture.
        """
        token, sid = "token1", "sid1"
        manager.token_to_socket[token] = SocketRecord(
            instance_id=manager.instance_id, sid=sid
        )
        manager.sid_to_token[sid] = token

        await manager.disconnect_token(token, sid)

        mock_redis.delete.assert_called_once_with(
            f"token_manager_socket_record_{token}"
        )
        assert token not in manager.token_to_sid
        assert sid not in manager.sid_to_token

    async def test_disconnect_token_not_owned_locally(self, manager, mock_redis):
        """Test disconnect doesn't clean up when not owned locally.

        Args:
            manager: RedisTokenManager fixture instance.
            mock_redis: Mock Redis client fixture.
        """
        token, sid = "token1", "sid1"

        await manager.disconnect_token(token, sid)

        mock_redis.delete.assert_not_called()

    async def test_disconnect_token_redis_error(self, manager, mock_redis):
        """Test disconnect continues with local cleanup even if Redis fails.

        Args:
            manager: RedisTokenManager fixture instance.
            mock_redis: Mock Redis client fixture.
        """
        token, sid = "token1", "sid1"
        manager.token_to_socket[token] = SocketRecord(
            instance_id=manager.instance_id, sid=sid
        )
        manager.sid_to_token[sid] = token
        mock_redis.delete.side_effect = Exception("Redis delete error")

        await manager.disconnect_token(token, sid)

        assert token not in manager.token_to_sid
        assert sid not in manager.sid_to_token

    @pytest.mark.parametrize(
        "redis_error",
        [
            Exception("Connection timeout"),
            Exception("Redis server down"),
            Exception("Network error"),
        ],
    )
    async def test_various_redis_errors_handled_gracefully(
        self, manager, mock_redis, redis_error
    ):
        """Test various Redis errors are handled gracefully.

        Args:
            manager: RedisTokenManager fixture instance.
            mock_redis: Mock Redis client fixture.
            redis_error: Exception to test error handling.
        """
        token, sid = "token1", "sid1"
        mock_redis.exists.side_effect = redis_error

        with patch.object(
            LocalTokenManager, "link_token_to_sid", new_callable=AsyncMock
        ) as mock_super:
            mock_super.return_value = None

            result = await manager.link_token_to_sid(token, sid)

            assert result is None
            mock_super.assert_called_once()

    def test_inheritance_from_local_manager(self, manager):
        """Test RedisTokenManager inherits from LocalTokenManager.

        Args:
            manager: RedisTokenManager fixture instance.
        """
        assert isinstance(manager, LocalTokenManager)
        assert hasattr(manager, "token_to_sid")
        assert hasattr(manager, "sid_to_token")
