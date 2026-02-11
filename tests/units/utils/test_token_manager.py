"""Unit tests for TokenManager implementations."""

import asyncio
import pickle
import time
from collections.abc import Callable, Generator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest

from reflex import config
from reflex.app import EventNamespace
from reflex.istate.data import RouterData
from reflex.state import StateUpdate
from reflex.utils.token_manager import (
    LocalTokenManager,
    RedisTokenManager,
    SocketRecord,
    TokenManager,
    _TokenNotConnectedError,
    get_token_manager,
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
        mock_redis_client.get_connection_kwargs.return_value = {"db": 0}
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

    async def test_enumerate_tokens(self, manager):
        """Test enumerate_tokens yields all linked tokens.

        Args:
            manager: LocalTokenManager fixture instance.
        """
        tokens_sids = [("token1", "sid1"), ("token2", "sid2"), ("token3", "sid3")]

        for token, sid in tokens_sids:
            await manager.link_token_to_sid(token, sid)

        found_tokens = set()
        async for token in manager.enumerate_tokens():
            found_tokens.add(token)

        expected_tokens = {token for token, _ in tokens_sids}
        assert found_tokens == expected_tokens

        # Disconnect a token and ensure it's removed.
        await manager.disconnect_token("token2", "sid2")
        expected_tokens.remove("token2")

        found_tokens = set()
        async for token in manager.enumerate_tokens():
            found_tokens.add(token)

        assert found_tokens == expected_tokens

        # Disconnect all tokens, none should remain
        await manager.disconnect_all()
        found_tokens = set()
        async for token in manager.enumerate_tokens():
            found_tokens.add(token)
        assert not found_tokens


class TestTokenManagerLifecycle:
    """Tests for TokenManager lifecycle APIs (issue #5669)."""

    @pytest.fixture
    def manager(self):
        """Create a LocalTokenManager instance.

        Returns:
            A LocalTokenManager instance for testing.
        """
        return LocalTokenManager()

    async def test_when_token_disconnects_connected(self, manager):
        """Event not set while connected, set after disconnect.

        Args:
            manager: LocalTokenManager fixture instance.
        """
        await manager.link_token_to_sid("tok1", "sid1")
        evt = manager.when_token_disconnects("tok1")
        assert not evt.is_set()
        manager._notify_disconnect("tok1", "sid1")
        assert evt.is_set()

    async def test_when_token_disconnects_already_disconnected(self, manager):
        """Event set immediately for unknown token.

        Args:
            manager: LocalTokenManager fixture instance.
        """
        evt = manager.when_token_disconnects("nonexistent")
        assert evt.is_set()

    async def test_when_session_disconnects_connected(self, manager):
        """Event not set while connected, set after disconnect.

        Args:
            manager: LocalTokenManager fixture instance.
        """
        await manager.link_token_to_sid("tok2", "sid2")
        evt = manager.when_session_disconnects("sid2")
        assert not evt.is_set()
        manager._notify_disconnect("tok2", "sid2")
        assert evt.is_set()

    async def test_when_session_disconnects_already_disconnected(self, manager):
        """Event set immediately for unknown sid.

        Args:
            manager: LocalTokenManager fixture instance.
        """
        evt = manager.when_session_disconnects("nonexistent")
        assert evt.is_set()

    async def test_when_token_connects_not_yet(self, manager):
        """Event set after connect.

        Args:
            manager: LocalTokenManager fixture instance.
        """
        evt = manager.when_token_connects("future_tok")
        assert not evt.is_set()
        await manager.link_token_to_sid("future_tok", "sid_f")
        manager._notify_connect("future_tok", "sid_f")
        assert evt.is_set()

    async def test_when_token_connects_already_connected(self, manager):
        """Event set immediately for already connected token.

        Args:
            manager: LocalTokenManager fixture instance.
        """
        await manager.link_token_to_sid("tok3", "sid3")
        evt = manager.when_token_connects("tok3")
        assert evt.is_set()

    async def test_session_is_connected_yields_and_stops(self, manager):
        """Yields token, stops on disconnect.

        Args:
            manager: LocalTokenManager fixture instance.
        """
        await manager.link_token_to_sid("tok4", "sid4")
        iterations = 0
        async for token in manager.session_is_connected("sid4"):
            assert token == "tok4"
            iterations += 1
            if iterations >= 3:
                manager._notify_disconnect("tok4", "sid4")
        assert iterations == 3

    async def test_session_is_connected_raises_for_unknown(self, manager):
        """Raises for unknown sid.

        Args:
            manager: LocalTokenManager fixture instance.
        """
        with pytest.raises(_TokenNotConnectedError):
            async for _ in manager.session_is_connected("unknown_sid"):
                pass

    async def test_token_is_connected_yields_and_stops(self, manager):
        """Yields sid, stops on disconnect.

        Args:
            manager: LocalTokenManager fixture instance.
        """
        await manager.link_token_to_sid("tok5", "sid5")
        iterations = 0
        async for sid in manager.token_is_connected("tok5"):
            assert sid == "sid5"
            iterations += 1
            if iterations >= 3:
                manager._notify_disconnect("tok5", "sid5")
        assert iterations == 3

    async def test_token_is_connected_raises_for_unknown(self, manager):
        """Raises for unknown token.

        Args:
            manager: LocalTokenManager fixture instance.
        """
        with pytest.raises(_TokenNotConnectedError):
            async for _ in manager.token_is_connected("unknown_tok"):
                pass

    async def test_multiple_watchers_token_disconnect(self, manager):
        """Multiple watchers on same token all get notified.

        Args:
            manager: LocalTokenManager fixture instance.
        """
        await manager.link_token_to_sid("tok6", "sid6")
        evt1 = manager.when_token_disconnects("tok6")
        evt2 = manager.when_token_disconnects("tok6")
        assert not evt1.is_set() and not evt2.is_set()
        manager._notify_disconnect("tok6", "sid6")
        assert evt1.is_set() and evt2.is_set()

    async def test_multiple_watchers_session_disconnect(self, manager):
        """Multiple session watchers all get notified.

        Args:
            manager: LocalTokenManager fixture instance.
        """
        await manager.link_token_to_sid("tok7", "sid7")
        evt1 = manager.when_session_disconnects("sid7")
        evt2 = manager.when_session_disconnects("sid7")
        manager._notify_disconnect("tok7", "sid7")
        assert evt1.is_set() and evt2.is_set()

    async def test_notify_connect_only_matching(self, manager):
        """_notify_connect only fires for matching token.

        Args:
            manager: LocalTokenManager fixture instance.
        """
        evt_a = manager.when_token_connects("tok_a")
        evt_b = manager.when_token_connects("tok_b")
        await manager.link_token_to_sid("tok_a", "sid_a")
        manager._notify_connect("tok_a", "sid_a")
        assert evt_a.is_set()
        assert not evt_b.is_set()

    async def test_notify_disconnect_only_matching(self, manager):
        """_notify_disconnect only fires for matching token.

        Args:
            manager: LocalTokenManager fixture instance.
        """
        await manager.link_token_to_sid("tok_c", "sid_c")
        await manager.link_token_to_sid("tok_d", "sid_d")
        evt_c = manager.when_token_disconnects("tok_c")
        evt_d = manager.when_token_disconnects("tok_d")
        manager._notify_disconnect("tok_c", "sid_c")
        assert evt_c.is_set()
        assert not evt_d.is_set()

    async def test_cleanup_after_disconnect_notify(self, manager):
        """Events dict cleaned up after notify.

        Args:
            manager: LocalTokenManager fixture instance.
        """
        await manager.link_token_to_sid("tok8", "sid8")
        manager.when_token_disconnects("tok8")
        assert "tok8" in manager._token_disconnect_events
        manager._notify_disconnect("tok8", "sid8")
        assert "tok8" not in manager._token_disconnect_events

    async def test_session_iterator_cleanup_with_aclosing(self, manager):
        """Events list cleaned up when using aclosing.

        Args:
            manager: LocalTokenManager fixture instance.
        """
        import contextlib

        await manager.link_token_to_sid("tok9", "sid9")
        async with contextlib.aclosing(
            manager.session_is_connected("sid9")
        ) as gen:
            async for _token in gen:
                break
        assert len(manager._sid_disconnect_events.get("sid9", [])) == 0

    async def test_token_iterator_cleanup_with_aclosing(self, manager):
        """Events list cleaned up when using aclosing.

        Args:
            manager: LocalTokenManager fixture instance.
        """
        import contextlib

        await manager.link_token_to_sid("tok10", "sid10")
        async with contextlib.aclosing(
            manager.token_is_connected("tok10")
        ) as gen:
            async for _sid in gen:
                break
        assert len(manager._token_disconnect_events.get("tok10", [])) == 0

    def test_get_token_manager_callable(self):
        """get_token_manager is importable and callable."""
        assert callable(get_token_manager)

    def test_rx_mapping_has_get_token_manager(self):
        """rx.__init__ has get_token_manager in its lazy mapping."""
        from reflex import _MAPPING

        assert "get_token_manager" in _MAPPING.get("utils.token_manager", [])


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

        # Non-async call
        redis.get_connection_kwargs = Mock(return_value={"db": 0})

        # Mock out pubsub
        async def listen():
            await asyncio.sleep(1)
            if False:
                yield
            return

        @asynccontextmanager
        async def pubsub():  # noqa: RUF029
            pubsub_mock = AsyncMock()
            pubsub_mock.listen = listen
            yield pubsub_mock

        redis.pubsub = pubsub
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
            pickle.dumps(SocketRecord(instance_id=manager.instance_id, sid=sid)),
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
            pickle.dumps(SocketRecord(instance_id=manager.instance_id, sid=sid)),
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


@pytest.fixture
def redis_url():
    """Returns the Redis URL from the environment."""
    redis_url = config.get_config().redis_url
    if redis_url is None:
        pytest.skip("Redis URL not configured")
    return redis_url


def query_string_for(token: str) -> dict[str, str]:
    """Generate query string for given token.

    Args:
        token: The token to generate query string for.

    Returns:
        The generated query string.
    """
    return {"QUERY_STRING": f"token={token}"}


@pytest.fixture
def event_namespace_factory() -> Generator[Callable[[], EventNamespace], None, None]:
    """Yields the EventNamespace factory function."""
    namespace = config.get_config().get_event_namespace()
    created_objs = []

    def new_event_namespace() -> EventNamespace:
        state = Mock()
        state.router_data = {}

        mock_app = Mock()
        mock_app.state_manager.modify_state = Mock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=state))
        )

        event_namespace = EventNamespace(namespace=namespace, app=mock_app)
        event_namespace.emit = AsyncMock()
        created_objs.append(event_namespace)
        return event_namespace

    yield new_event_namespace

    for obj in created_objs:
        asyncio.run(obj._token_manager.disconnect_all())


@pytest.mark.usefixtures("redis_url")
@pytest.mark.asyncio
async def test_redis_token_manager_enumerate_tokens(
    event_namespace_factory: Callable[[], EventNamespace],
):
    """Integration test for RedisTokenManager enumerate_tokens interface.

    Should support enumerating tokens across separate instances of the
    RedisTokenManager.

    Args:
        event_namespace_factory: Factory fixture for EventNamespace instances.
    """
    event_namespace1 = event_namespace_factory()
    event_namespace2 = event_namespace_factory()

    await event_namespace1.on_connect(sid="sid1", environ=query_string_for("token1"))
    await event_namespace2.on_connect(sid="sid2", environ=query_string_for("token2"))

    found_tokens = set()
    async for token in event_namespace1._token_manager.enumerate_tokens():
        found_tokens.add(token)

    assert "token1" in found_tokens
    assert "token2" in found_tokens
    assert len(found_tokens) == 2

    await event_namespace1._token_manager.disconnect_all()

    found_tokens = set()
    async for token in event_namespace1._token_manager.enumerate_tokens():
        found_tokens.add(token)
    assert "token2" in found_tokens
    assert len(found_tokens) == 1

    await event_namespace2._token_manager.disconnect_all()

    found_tokens = set()
    async for token in event_namespace1._token_manager.enumerate_tokens():
        found_tokens.add(token)
    assert not found_tokens


@pytest.mark.usefixtures("redis_url")
@pytest.mark.asyncio
async def test_redis_token_manager_get_token_owner(
    event_namespace_factory: Callable[[], EventNamespace],
):
    """Integration test for RedisTokenManager get_token_owner interface.

    Should support retrieving the owner of a token across separate instances of the
    RedisTokenManager.

    Args:
        event_namespace_factory: Factory fixture for EventNamespace instances.
    """
    event_namespace1 = event_namespace_factory()
    event_namespace2 = event_namespace_factory()

    await event_namespace1.on_connect(sid="sid1", environ=query_string_for("token1"))
    await event_namespace2.on_connect(sid="sid2", environ=query_string_for("token2"))

    assert isinstance((manager1 := event_namespace1._token_manager), RedisTokenManager)
    assert isinstance((manager2 := event_namespace2._token_manager), RedisTokenManager)

    assert await manager1._get_token_owner("token1") == manager1.instance_id
    assert await manager1._get_token_owner("token2") == manager2.instance_id
    assert await manager2._get_token_owner("token1") == manager1.instance_id
    assert await manager2._get_token_owner("token2") == manager2.instance_id


async def _wait_for_call_count_positive(mock: Mock, timeout: float = 5.0):
    """Wait until the mock's call count is positive.

    Args:
        mock: The mock to wait on.
        timeout: The maximum time to wait in seconds.
    """
    deadline = time.monotonic() + timeout
    while mock.call_count == 0 and time.monotonic() < deadline:  # noqa: ASYNC110
        await asyncio.sleep(0.1)


@pytest.mark.usefixtures("redis_url")
@pytest.mark.asyncio
async def test_redis_token_manager_lost_and_found(
    event_namespace_factory: Callable[[], EventNamespace],
):
    """Updates emitted for lost and found tokens should be routed correctly via redis.

    Args:
        event_namespace_factory: Factory fixture for EventNamespace instances.
    """
    event_namespace1 = event_namespace_factory()
    emit1_mock: Mock = event_namespace1.emit  # pyright: ignore[reportAssignmentType]
    event_namespace2 = event_namespace_factory()
    emit2_mock: Mock = event_namespace2.emit  # pyright: ignore[reportAssignmentType]

    await event_namespace1.on_connect(sid="sid1", environ=query_string_for("token1"))
    await event_namespace2.on_connect(sid="sid2", environ=query_string_for("token2"))

    await event_namespace2.emit_update(StateUpdate(), token="token1")
    await _wait_for_call_count_positive(emit1_mock)
    emit2_mock.assert_not_called()
    emit1_mock.assert_called_once()
    emit1_mock.reset_mock()

    await event_namespace2.emit_update(StateUpdate(), token="token2")
    await _wait_for_call_count_positive(emit2_mock)
    emit1_mock.assert_not_called()
    emit2_mock.assert_called_once()
    emit2_mock.reset_mock()

    if task := event_namespace1.on_disconnect(sid="sid1"):
        await task
    await event_namespace2.emit_update(StateUpdate(), token="token1")
    # Update should be dropped on the floor.
    await asyncio.sleep(2)
    emit1_mock.assert_not_called()
    emit2_mock.assert_not_called()

    await event_namespace2.on_connect(sid="sid1", environ=query_string_for("token1"))
    await event_namespace2.emit_update(StateUpdate(), token="token1")
    await _wait_for_call_count_positive(emit2_mock)
    emit1_mock.assert_not_called()
    emit2_mock.assert_called_once()
    emit2_mock.reset_mock()

    if task := event_namespace2.on_disconnect(sid="sid1"):
        await task
    await event_namespace1.on_connect(sid="sid1", environ=query_string_for("token1"))
    await event_namespace2.emit_update(StateUpdate(), token="token1")
    await _wait_for_call_count_positive(emit1_mock)
    emit2_mock.assert_not_called()
    emit1_mock.assert_called_once()
    emit1_mock.reset_mock()


@pytest.mark.usefixtures("redis_url")
@pytest.mark.asyncio
async def test_redis_token_manager_lost_and_found_router_data(
    event_namespace_factory: Callable[[], EventNamespace],
):
    """Updates emitted for lost and found tokens should serialize properly.

    Args:
        event_namespace_factory: Factory fixture for EventNamespace instances.
    """
    event_namespace1 = event_namespace_factory()
    emit1_mock: Mock = event_namespace1.emit  # pyright: ignore[reportAssignmentType]
    event_namespace2 = event_namespace_factory()
    emit2_mock: Mock = event_namespace2.emit  # pyright: ignore[reportAssignmentType]

    await event_namespace1.on_connect(sid="sid1", environ=query_string_for("token1"))
    await event_namespace2.on_connect(sid="sid2", environ=query_string_for("token2"))

    router = RouterData.from_router_data(
        {"headers": {"x-test": "value"}},
    )

    await event_namespace2.emit_update(
        StateUpdate(delta={"state": {"router": router}}), token="token1"
    )
    await _wait_for_call_count_positive(emit1_mock)
    emit2_mock.assert_not_called()
    emit1_mock.assert_called_once()
    assert isinstance(emit1_mock.call_args[0][1], StateUpdate)
    assert isinstance(emit1_mock.call_args[0][1].delta["state"]["router"], RouterData)
    assert emit1_mock.call_args[0][1].delta["state"]["router"] == router
    emit1_mock.reset_mock()
