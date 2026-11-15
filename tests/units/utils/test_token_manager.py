"""Unit tests for TokenManager implementations."""

import asyncio
import pickle
import time
from collections.abc import AsyncGenerator, Callable
from operator import itemgetter
from typing import Any, cast
from unittest.mock import AsyncMock, Mock, call, patch

import pytest
from redis.asyncio import Redis

from reflex import config
from reflex.app import EventNamespace
from reflex.istate.data import RouterData
from reflex.state import StateUpdate
from reflex.utils import prerequisites
from reflex.utils.token_manager import (
    LocalTokenManager,
    LostAndFoundRecord,
    RedisTokenManager,
    SocketRecord,
    TokenManager,
)
from tests.units.mock_redis import mock_redis


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


@pytest.fixture(params=["local", "redis"])
async def manager(request: pytest.FixtureRequest) -> AsyncGenerator[TokenManager]:
    """A token manager of each kind, the redis one backed by the mock redis.

    Args:
        request: The fixture request carrying the kind of manager.

    Yields:
        The token manager.
    """
    manager = (
        LocalTokenManager()
        if request.param == "local"
        else RedisTokenManager(mock_redis())
    )
    yield manager
    await manager.close()


@pytest.fixture
async def redis_manager() -> AsyncGenerator[RedisTokenManager]:
    """A RedisTokenManager backed by the mock redis.

    Yields:
        The token manager.
    """
    manager = RedisTokenManager(mock_redis())
    yield manager
    await manager.close()


async def _tokens(manager: TokenManager) -> list[str]:
    """Collect the tokens a manager enumerates.

    Args:
        manager: The token manager.

    Returns:
        The enumerated tokens, sorted.
    """
    return sorted([token async for token in manager.enumerate_tokens()])


async def _redis_sockets(manager: TokenManager, token: str) -> set[Any] | None:
    """Read the sockets redis holds for a token.

    Args:
        manager: The token manager.
        token: The client token.

    Returns:
        The members of the token's redis set, or None for a local manager.
    """
    if not isinstance(manager, RedisTokenManager):
        return None
    return await manager.redis.smembers(manager._get_redis_key(token))  # pyright: ignore[reportGeneralTypeIssues]


def _members(manager: TokenManager, *sids: str) -> set[bytes] | None:
    """Build the redis set members expected for sockets of a manager.

    Args:
        manager: The token manager owning the sockets.
        sids: The Socket.IO session IDs.

    Returns:
        The expected members, or None for a local manager.
    """
    if not isinstance(manager, RedisTokenManager):
        return None
    return {f"{manager.instance_id}:{sid}".encode() for sid in sids}


async def test_link_token_to_sid(manager: TokenManager):
    """Linking a token records its socket and hands back no replacement token.

    Args:
        manager: The token manager.
    """
    assert await manager.link_token_to_sid("token1", "sid1") is None
    # Linking the same socket again changes nothing.
    assert await manager.link_token_to_sid("token1", "sid1") is None
    assert await manager.link_token_to_sid("token2", "sid2") is None

    assert manager.sid_to_token == {"sid1": "token1", "sid2": "token2"}
    assert manager.token_to_sids == {"token1": ("sid1",), "token2": ("sid2",)}
    assert await _tokens(manager) == ["token1", "token2"]
    assert await _redis_sockets(manager, "token1") == _members(manager, "sid1")
    assert await _redis_sockets(manager, "token2") == _members(manager, "sid2")


async def test_reconnect_before_old_sid_disconnects_keeps_token(manager: TokenManager):
    """A token linked to a new sid while the old one is still linked is kept.

    The new socket of a reconnect is often linked before the old socket's
    disconnect is processed. That must not hand the client a new token, which
    would drop the session's state.

    Args:
        manager: The token manager.
    """
    assert await manager.link_token_to_sid("token", "old-sid") is None
    assert await manager.link_token_to_sid("token", "new-sid") is None

    assert manager.sid_to_token == {"old-sid": "token", "new-sid": "token"}
    assert manager.token_to_sids == {"token": ("old-sid", "new-sid")}
    assert await _tokens(manager) == ["token"]
    assert await _redis_sockets(manager, "token") == _members(
        manager, "old-sid", "new-sid"
    )


async def test_late_disconnect_of_old_sid_keeps_new_sid_linked(manager: TokenManager):
    """The late disconnect of a replaced socket leaves its replacement linked.

    Args:
        manager: The token manager.
    """
    await manager.link_token_to_sid("token", "old-sid")
    await manager.link_token_to_sid("token", "new-sid")

    await manager.disconnect_token("token", "old-sid")

    assert manager.sid_to_token == {"new-sid": "token"}
    assert manager.token_to_sids == {"token": ("new-sid",)}
    assert await manager.is_token_connected("token")
    assert await _tokens(manager) == ["token"]
    assert await _redis_sockets(manager, "token") == _members(manager, "new-sid")

    # A repeated or unknown disconnect is ignored.
    await manager.disconnect_token("token", "old-sid")
    await manager.disconnect_token("other-token", "new-sid")
    assert manager.sid_to_token == {"new-sid": "token"}
    assert manager.token_to_sids == {"token": ("new-sid",)}
    assert await _redis_sockets(manager, "token") == _members(manager, "new-sid")


async def test_disconnect_of_last_sid_removes_token(manager: TokenManager):
    """A token is dropped once its last socket disconnects.

    Args:
        manager: The token manager.
    """
    await manager.link_token_to_sid("token", "sid1")
    await manager.link_token_to_sid("token", "sid2")
    await manager.link_token_to_sid("other-token", "sid3")

    await manager.disconnect_token("token", "sid2")
    await manager.disconnect_token("token", "sid1")

    assert manager.sid_to_token == {"sid3": "other-token"}
    assert manager.token_to_sids == {"other-token": ("sid3",)}
    assert not await manager.is_token_connected("token")
    assert await _tokens(manager) == ["other-token"]
    assert await _redis_sockets(manager, "token") == _members(manager)

    await manager.disconnect_all()

    assert manager.sid_to_token == {}
    assert manager.token_to_sids == {}
    assert await _tokens(manager) == []
    assert await _redis_sockets(manager, "other-token") == _members(manager)


async def test_link_sid_to_another_token_moves_it(manager: TokenManager):
    """A socket linked to a second token leaves the first one.

    Args:
        manager: The token manager.
    """
    await manager.link_token_to_sid("token1", "sid1")
    await manager.link_token_to_sid("token2", "sid1")

    assert manager.sid_to_token == {"sid1": "token2"}
    assert manager.token_to_sids == {"token2": ("sid1",)}
    assert await _tokens(manager) == ["token2"]
    assert await _redis_sockets(manager, "token1") == _members(manager)
    assert await _redis_sockets(manager, "token2") == _members(manager, "sid1")


@pytest.mark.parametrize(
    ("attribute", "expected"),
    [
        ("token_to_sid", {"token1": "sid2", "token2": "sid3"}),
        (
            "token_to_socket",
            {
                "token1": SocketRecord(instance_id="instance", sid="sid2"),
                "token2": SocketRecord(instance_id="instance", sid="sid3"),
            },
        ),
    ],
)
async def test_deprecated_single_socket_views(attribute: str, expected: dict[str, Any]):
    """The single-socket mappings keep working, reporting each token's newest socket.

    Args:
        attribute: The deprecated attribute.
        expected: The mapping it is expected to hold.
    """
    manager = LocalTokenManager()
    manager.instance_id = "instance"
    await manager.link_token_to_sid("token1", "sid1")
    await manager.link_token_to_sid("token1", "sid2")
    await manager.link_token_to_sid("token2", "sid3")

    with patch("reflex.utils.token_manager.console.deprecate") as deprecate:
        view = getattr(manager, attribute)

    assert dict(view) == expected
    deprecate.assert_called_once_with(
        feature_name=f"TokenManager.{attribute}",
        reason="A client token can have several sockets. Use token_to_sids instead.",
        deprecation_version="0.11.1",
        removal_version="1.0",
    )


def test_get_redis_key(redis_manager: RedisTokenManager):
    """The redis key and member of a socket follow the expected pattern.

    Args:
        redis_manager: The redis token manager.
    """
    assert redis_manager._get_redis_key("token1") == "token_manager_sockets_token1"
    assert (
        redis_manager._get_socket_member("sid1") == f"{redis_manager.instance_id}:sid1"
    )


async def test_link_token_to_sid_sets_expiration(redis_manager: RedisTokenManager):
    """Linking a socket refreshes the expiration of the token's redis set.

    Args:
        redis_manager: The redis token manager.
    """
    await redis_manager.link_token_to_sid("token1", "sid1")

    expire_times = redis_manager.redis._internals["expire_times"]  # pyright: ignore[reportAttributeAccessIssue]
    remaining = expire_times[b"token_manager_sockets_token1"] - time.monotonic()
    assert (
        redis_manager.token_expiration - 5 < remaining <= redis_manager.token_expiration
    )


async def test_link_token_to_sid_already_linked_skips_redis(
    redis_manager: RedisTokenManager,
):
    """Linking a socket that is already linked makes no redis round trip.

    Args:
        redis_manager: The redis token manager.
    """
    await redis_manager.link_token_to_sid("token1", "sid1")
    redis_manager.redis.pipeline = Mock(side_effect=AssertionError("redis used"))

    assert await redis_manager.link_token_to_sid("token1", "sid1") is None


async def test_link_token_to_sid_redis_error_links_locally(
    redis_manager: RedisTokenManager,
):
    """A redis failure while announcing a socket still links it locally.

    Args:
        redis_manager: The redis token manager.
    """
    redis_manager.redis.pipeline = Mock(side_effect=Exception("Redis down"))

    assert await redis_manager.link_token_to_sid("token1", "sid1") is None

    assert redis_manager.sid_to_token == {"sid1": "token1"}
    assert redis_manager.token_to_sids == {"token1": ("sid1",)}
    assert await redis_manager.is_token_connected("token1")


async def test_disconnect_during_link_removes_announced_socket(
    redis_manager: RedisTokenManager,
):
    """A socket that disconnects while it is announced does not stay in redis.

    Args:
        redis_manager: The redis token manager.
    """
    redis = cast("Any", redis_manager.redis)
    pipeline = redis.pipeline

    def disconnecting_pipeline(transaction: bool = True):
        """Disconnect the socket before its announcement is executed.

        Args:
            transaction: Whether the pipeline is a transaction.

        Returns:
            The pipeline.
        """
        pipe = pipeline(transaction=transaction)
        execute = pipe.execute

        async def execute_after_disconnect():
            await redis_manager.disconnect_token("token1", "sid1")
            return await execute()

        pipe.execute = execute_after_disconnect
        return pipe

    redis.pipeline = disconnecting_pipeline

    await redis_manager.link_token_to_sid("token1", "sid1")

    assert redis_manager.sid_to_token == {}
    assert redis_manager.token_to_sids == {}
    assert await redis.smembers("token_manager_sockets_token1") == set()


async def test_disconnect_token_clears_local_before_redis_removal(
    redis_manager: RedisTokenManager,
):
    """Local mappings are dropped before the redis removal round-trip starts.

    Args:
        redis_manager: The redis token manager.
    """
    await redis_manager.link_token_to_sid("token1", "sid1")
    linked_at_removal = {}
    redis = cast("Any", redis_manager.redis)
    srem = redis.srem

    async def recording_srem(key: str, member: str) -> int:
        linked_at_removal["token"] = "token1" in redis_manager.token_to_sids
        linked_at_removal["sid"] = "sid1" in redis_manager.sid_to_token
        return await srem(key, member)

    redis.srem = recording_srem

    await redis_manager.disconnect_token("token1", "sid1")

    assert linked_at_removal == {"token": False, "sid": False}
    assert await redis.smembers("token_manager_sockets_token1") == set()


async def test_disconnect_token_not_owned_locally_skips_redis(
    redis_manager: RedisTokenManager,
):
    """Disconnecting a socket this instance does not own leaves redis alone.

    Args:
        redis_manager: The redis token manager.
    """
    redis_manager.redis.srem = AsyncMock()

    await redis_manager.disconnect_token("token1", "sid1")

    redis_manager.redis.srem.assert_not_called()


async def test_disconnect_token_redis_error(redis_manager: RedisTokenManager):
    """Disconnect cleans up locally even if the redis removal fails.

    Args:
        redis_manager: The redis token manager.
    """
    await redis_manager.link_token_to_sid("token1", "sid1")
    redis_manager.redis.srem = AsyncMock(side_effect=Exception("Redis down"))

    await redis_manager.disconnect_token("token1", "sid1")

    assert redis_manager.sid_to_token == {}
    assert redis_manager.token_to_sids == {}


async def test_is_token_connected_locally_owned_skips_redis(
    redis_manager: RedisTokenManager,
):
    """A socket linked to this instance is authoritative, without a redis lookup.

    Args:
        redis_manager: The redis token manager.
    """
    await redis_manager.link_token_to_sid("token1", "sid1")
    redis_manager.redis.smembers = AsyncMock(side_effect=AssertionError("redis used"))

    assert await redis_manager.is_token_connected("token1")


async def test_is_token_connected_ignores_stale_own_member(
    redis_manager: RedisTokenManager,
):
    """A redis member claiming this instance without a live local link is stale.

    Args:
        redis_manager: The redis token manager.
    """
    await redis_manager.redis.sadd(
        "token_manager_sockets_token1", f"{redis_manager.instance_id}:sid1"
    )

    assert not await redis_manager.is_token_connected("token1")
    assert redis_manager._remote_owners == {}


async def test_is_token_connected_on_another_instance(
    redis_manager: RedisTokenManager,
):
    """A token with a socket on another instance is connected until it leaves.

    Args:
        redis_manager: The redis token manager.
    """
    other = RedisTokenManager(redis_manager.redis)
    await other.link_token_to_sid("token1", "sid1")

    assert await redis_manager.is_token_connected("token1")
    assert redis_manager._remote_owners["token1"][0] == frozenset({other.instance_id})

    await other.disconnect_token("token1", "sid1")

    assert not await redis_manager.is_token_connected("token1")
    assert redis_manager._remote_owners == {}


async def test_is_token_connected_redis_error_trusts_cache(
    redis_manager: RedisTokenManager,
):
    """A redis failure preserves and trusts the cached owners of a token.

    Args:
        redis_manager: The redis token manager.
    """
    cached = (frozenset({"other-instance"}), time.monotonic())
    redis_manager._remote_owners["token1"] = cached
    redis_manager.redis.smembers = AsyncMock(side_effect=Exception("Redis down"))

    assert await redis_manager.is_token_connected("token1")
    assert not await redis_manager.is_token_connected("unknown-token")
    assert redis_manager._remote_owners == {"token1": cached}


async def test_remote_owners_cached_until_invalidated(redis_manager: RedisTokenManager):
    """The other owners of a token are read once, until a notification or age.

    Args:
        redis_manager: The redis token manager.
    """
    other = RedisTokenManager(redis_manager.redis)
    await redis_manager.link_token_to_sid("token1", "sid1")
    await other.link_token_to_sid("token1", "sid2")
    smembers = redis_manager.redis.smembers
    redis_manager.redis.smembers = AsyncMock(side_effect=smembers)
    owners = frozenset({other.instance_id})

    assert await redis_manager._get_remote_owners("token1") == owners
    assert await redis_manager._get_remote_owners("token1") == owners
    assert redis_manager.redis.smembers.await_count == 1

    # A keyspace notification drops the cached answer.
    redis_manager._invalidate_remote_owners("token1")
    assert await redis_manager._get_remote_owners("token1") == owners
    assert redis_manager.redis.smembers.await_count == 2

    # So does its age: a notification may never arrive.
    redis_manager._remote_owners["token1"] = (
        owners,
        time.monotonic() - redis_manager._remote_owners_max_age,
    )
    assert await redis_manager._get_remote_owners("token1") == owners
    assert redis_manager.redis.smembers.await_count == 3

    # A redis failure falls back to the outdated answer.
    redis_manager._remote_owners["token1"] = (owners, 0.0)
    redis_manager.redis.smembers = AsyncMock(side_effect=Exception("Redis down"))
    assert await redis_manager._get_remote_owners("token1") == owners
    assert await redis_manager._get_remote_owners("unknown-token") == frozenset()


async def test_remote_owners_without_any_recipient_are_read_again(
    redis_manager: RedisTokenManager,
):
    """An answer leaving an update without a recipient is never served from cache.

    Args:
        redis_manager: The redis token manager.
    """
    other = RedisTokenManager(redis_manager.redis)

    assert await redis_manager._get_remote_owners("token1") == frozenset()
    # Nothing would invalidate the entry of a token unknown to this instance.
    assert redis_manager._remote_owners == {}

    await other.link_token_to_sid("token1", "sid1")

    assert await redis_manager._get_remote_owners("token1") == frozenset({
        other.instance_id
    })


async def test_remote_owners_read_racing_an_invalidation_is_not_cached(
    redis_manager: RedisTokenManager,
):
    """A read overtaken by a keyspace notification is used but not cached.

    Args:
        redis_manager: The redis token manager.
    """
    await redis_manager.link_token_to_sid("token1", "sid1")
    redis = cast("Any", redis_manager.redis)
    smembers = redis.smembers

    async def smembers_then_notification(key: str) -> set[bytes]:
        members = await smembers(key)
        redis_manager._invalidate_remote_owners("token1")
        return members

    redis.smembers = smembers_then_notification

    assert await redis_manager._get_remote_owners("token1") == frozenset()
    assert redis_manager._remote_owners == {}


async def test_socket_record_del_restores_all_local_sockets(
    redis_manager: RedisTokenManager,
):
    """An expired redis set is restored with every socket this instance owns.

    Args:
        redis_manager: The redis token manager.
    """
    await redis_manager.link_token_to_sid("token1", "sid1")
    await redis_manager.link_token_to_sid("token1", "sid2")
    redis_manager._remote_owners["token1"] = (frozenset({"other"}), time.monotonic())
    await redis_manager.redis.delete("token_manager_sockets_token1")

    await redis_manager._handle_socket_record_del("token1")

    assert await _redis_sockets(redis_manager, "token1") == _members(
        redis_manager, "sid1", "sid2"
    )
    assert redis_manager._remote_owners == {}
    assert redis_manager.token_to_sids == {"token1": ("sid1", "sid2")}


async def test_socket_record_del_without_local_sockets_stores_nothing(
    redis_manager: RedisTokenManager,
):
    """A del notification for a token without local sockets only drops the cache.

    Args:
        redis_manager: The redis token manager.
    """
    redis_manager._remote_owners["token1"] = (frozenset({"other"}), time.monotonic())

    await redis_manager._handle_socket_record_del("token1")

    assert redis_manager._remote_owners == {}
    assert await redis_manager.redis.smembers("token_manager_sockets_token1") == set()


async def _logged(redis: Redis, channel: bytes, data: bytes, start: int = 0):
    """Wait until the mock redis logs an event.

    Args:
        redis: The mock redis client.
        channel: The channel of the event.
        data: The data of the event.
        start: The event log index to search from.
    """
    event_log = redis._internals["event_log"]  # pyright: ignore[reportAttributeAccessIssue]
    on_update = redis._internals["event_log_on_update"]  # pyright: ignore[reportAttributeAccessIssue]
    while {"channel": channel, "data": data} not in event_log[start:]:
        on_update.clear()
        await on_update.wait()


async def test_socket_record_subscriber_restores_deleted_live_sockets(
    redis_manager: RedisTokenManager,
):
    """The keyspace subscriber restores a deleted set of live local sockets.

    Args:
        redis_manager: The redis token manager.
    """
    redis = redis_manager.redis
    key = redis_manager._get_redis_key("token1")
    await redis_manager.link_token_to_sid("token1", "sid1")
    await redis_manager.link_token_to_sid("token1", "sid2")
    await asyncio.wait_for(
        _logged(
            redis,
            b"psubscribe",
            f"__keyspace@1__:{redis_manager._get_redis_key('*')}".encode(),
        ),
        timeout=1,
    )
    start = len(redis._internals["event_log"])  # pyright: ignore[reportAttributeAccessIssue]

    await redis.delete(key)
    # Shorter than the subscriber's retry delay, so a crashed listen fails.
    await asyncio.wait_for(
        _logged(redis, f"__keyspace@1__:{key}".encode(), b"expire", start),
        timeout=0.5,
    )

    assert await _redis_sockets(redis_manager, "token1") == _members(
        redis_manager, "sid1", "sid2"
    )


async def test_socket_record_subscriber_invalidates_remote_owners(
    redis_manager: RedisTokenManager,
):
    """A socket joining or leaving on another instance drops the cached owners.

    Args:
        redis_manager: The redis token manager.
    """
    redis = redis_manager.redis
    other = RedisTokenManager(redis)
    await redis_manager.link_token_to_sid("token1", "sid1")
    await asyncio.wait_for(
        _logged(
            redis,
            b"psubscribe",
            f"__keyspace@1__:{redis_manager._get_redis_key('*')}".encode(),
        ),
        timeout=1,
    )

    async def owners_become(expected: frozenset[str]):
        """Wait until the manager reports the expected owners from its cache.

        Args:
            expected: The expected other owners of the token.
        """
        while await redis_manager._get_remote_owners("token1") != expected:  # noqa: ASYNC110
            await asyncio.sleep(0)

    assert await redis_manager._get_remote_owners("token1") == frozenset()
    # Only a notification can change the answer from here on.
    redis_manager._remote_owners_max_age = float("inf")  # pyright: ignore[reportAttributeAccessIssue]

    await other.link_token_to_sid("token1", "sid2")
    await asyncio.wait_for(owners_become(frozenset({other.instance_id})), timeout=1)

    await other.disconnect_token("token1", "sid2")
    await asyncio.wait_for(owners_become(frozenset()), timeout=1)
    await other.close()


async def test_emit_lost_and_found_publishes_to_every_other_owner(
    redis_manager: RedisTokenManager,
):
    """A delta is published once to each other instance owning a socket.

    Args:
        redis_manager: The redis token manager.
    """
    redis = redis_manager.redis
    others = [RedisTokenManager(redis), RedisTokenManager(redis)]
    await redis_manager.link_token_to_sid("token1", "sid1")
    await others[0].link_token_to_sid("token1", "sid2")
    await others[0].link_token_to_sid("token1", "sid3")
    await others[1].link_token_to_sid("token1", "sid4")
    update = StateUpdate(delta={"state": {"count": 1}})
    start = len(redis._internals["event_log"])  # pyright: ignore[reportAttributeAccessIssue]

    assert await redis_manager.emit_lost_and_found("token1", update)

    record = pickle.dumps(LostAndFoundRecord(token="token1", update=update))
    published = redis._internals["event_log"][start:]  # pyright: ignore[reportAttributeAccessIssue]
    assert sorted(published, key=itemgetter("channel")) == sorted(
        (
            {
                "channel": f"channel:token_manager_lost_and_found_{other.instance_id}".encode(),
                "data": record,
            }
            for other in others
        ),
        key=itemgetter("channel"),
    )


async def test_emit_lost_and_found_without_other_owner(
    redis_manager: RedisTokenManager,
):
    """Nothing is published for a token without a socket on another instance.

    Args:
        redis_manager: The redis token manager.
    """
    await redis_manager.link_token_to_sid("token1", "sid1")
    redis_manager.redis.publish = AsyncMock()

    assert not await redis_manager.emit_lost_and_found("token1", StateUpdate())
    assert not await redis_manager.emit_lost_and_found("unknown", StateUpdate())

    redis_manager.redis.publish.assert_not_called()


async def test_emit_lost_and_found_publish_error(redis_manager: RedisTokenManager):
    """A failed publish is reported as not delivered.

    Args:
        redis_manager: The redis token manager.
    """
    other = RedisTokenManager(redis_manager.redis)
    await other.link_token_to_sid("token1", "sid1")
    redis_manager.redis.publish = AsyncMock(side_effect=Exception("Redis down"))

    assert not await redis_manager.emit_lost_and_found("token1", StateUpdate())


def test_inheritance_from_local_manager(redis_manager: RedisTokenManager):
    """RedisTokenManager inherits from LocalTokenManager.

    Args:
        redis_manager: The redis token manager.
    """
    assert isinstance(redis_manager, LocalTokenManager)


async def test_close_cancels_tasks_and_closes_redis():
    """Close cancels the background pub/sub tasks and closes the Redis client."""
    manager = RedisTokenManager(mock_redis())
    manager._ensure_socket_record_task()
    manager.ensure_lost_and_found_task(AsyncMock())
    tasks = (manager._socket_record_task, manager._lost_and_found_task)
    assert None not in tasks

    await manager.close()

    assert [task.cancelled() for task in tasks if task is not None] == [True, True]
    assert manager._socket_record_task is None
    assert manager._lost_and_found_task is None
    cast("AsyncMock", manager.redis.aclose).assert_awaited_once_with()


async def test_close_without_tasks():
    """Close works when no background tasks were started."""
    manager = RedisTokenManager(mock_redis())

    await manager.close()

    cast("AsyncMock", manager.redis.aclose).assert_awaited_once_with()


def query_string_for(token: str) -> dict[str, str]:
    """Generate query string for given token.

    Args:
        token: The token to generate query string for.

    Returns:
        The generated query string.
    """
    return {"QUERY_STRING": f"token={token}"}


def _new_event_namespace(token_manager: TokenManager) -> EventNamespace:
    """Create an EventNamespace with a mocked app and socket.

    Args:
        token_manager: The token manager the namespace uses.

    Returns:
        The EventNamespace, whose emit is a mock.
    """
    state = Mock()
    state.router_data = {}

    mock_app = Mock()
    mock_app.state_manager.modify_state = Mock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=state))
    )

    event_namespace = EventNamespace(
        namespace=config.get_config().get_event_namespace(), app=mock_app
    )
    event_namespace._token_manager = token_manager
    event_namespace.emit = AsyncMock()
    return event_namespace


@pytest.fixture(params=["mock", "real"])
async def event_namespace_factory(
    request: pytest.FixtureRequest,
) -> AsyncGenerator[Callable[[], EventNamespace]]:
    """A factory of EventNamespaces acting as instances of one app on one redis.

    Args:
        request: The fixture request carrying the kind of redis.

    Yields:
        The EventNamespace factory function.
    """
    if request.param == "mock":
        shared_redis = mock_redis()

        def new_redis() -> Redis:
            return shared_redis

    else:
        if config.get_config().redis_url is None:
            pytest.skip("Redis URL not configured")

        def new_redis() -> Redis:
            redis = prerequisites.get_redis()
            assert redis is not None
            return redis

    created: list[EventNamespace] = []

    def new_event_namespace() -> EventNamespace:
        event_namespace = _new_event_namespace(RedisTokenManager(new_redis()))
        created.append(event_namespace)
        return event_namespace

    yield new_event_namespace

    for event_namespace in created:
        await event_namespace._token_manager.disconnect_all()
        await event_namespace._token_manager.close()


def _emit_mock(event_namespace: EventNamespace) -> AsyncMock:
    """Get the mocked emit of an EventNamespace.

    Args:
        event_namespace: The EventNamespace.

    Returns:
        The mock standing in for its emit.
    """
    return cast("AsyncMock", event_namespace.emit)


async def _wait_for_call_count(mock: Mock, count: int = 1, timeout: float = 5.0):
    """Wait until the mock was called at least a number of times.

    Args:
        mock: The mock to wait on.
        count: The number of calls to wait for.
        timeout: The maximum time to wait in seconds.
    """
    deadline = time.monotonic() + timeout
    while mock.call_count < count and time.monotonic() < deadline:  # noqa: ASYNC110
        await asyncio.sleep(0.01)


async def _settle(delay: float = 0.3):
    """Give updates that must not be delivered the time to show up.

    Args:
        delay: The time to wait in seconds.
    """
    await asyncio.sleep(delay)


async def test_emit_update_reaches_every_local_sid_once():
    """An update for a token is emitted once to each socket linked to it."""
    event_namespace = _new_event_namespace(LocalTokenManager())
    await event_namespace.on_connect(sid="sid1", environ=query_string_for("token1"))
    await event_namespace.on_connect(sid="sid2", environ=query_string_for("token1"))
    await event_namespace.on_connect(sid="sid3", environ=query_string_for("token2"))
    emit = _emit_mock(event_namespace)
    update = StateUpdate(delta={"state": {"count": 1}})

    await event_namespace.emit_update(update, token="token1")

    # No new token was handed out for the second socket of the token.
    assert emit.await_args_list == [
        call("event", update, to="sid1"),
        call("event", update, to="sid2"),
    ]

    # The late disconnect of the first socket leaves the second one receiving.
    emit.reset_mock()
    task = event_namespace.on_disconnect(sid="sid1")
    assert task is not None
    await task
    await event_namespace.emit_update(update, token="token1")

    assert emit.await_args_list == [call("event", update, to="sid2")]


async def test_emit_update_without_sockets_warns(caplog: pytest.LogCaptureFixture):
    """An update for a token without any socket is dropped with a warning.

    Args:
        caplog: The log capture fixture.
    """
    event_namespace = _new_event_namespace(LocalTokenManager())

    with caplog.at_level("WARNING", logger="reflex.app"):
        await event_namespace.emit_update(StateUpdate(), token="token1")

    _emit_mock(event_namespace).assert_not_called()
    assert [record.getMessage() for record in caplog.records] == [
        "Attempting to send delta to disconnected client 'token1'"
    ]


async def test_redis_token_manager_enumerate_tokens(
    event_namespace_factory: Callable[[], EventNamespace],
):
    """Tokens are enumerated across separate instances of the RedisTokenManager.

    Args:
        event_namespace_factory: Factory fixture for EventNamespace instances.
    """
    event_namespace1 = event_namespace_factory()
    event_namespace2 = event_namespace_factory()

    await event_namespace1.on_connect(sid="sid1", environ=query_string_for("token1"))
    await event_namespace2.on_connect(sid="sid2", environ=query_string_for("token2"))
    # A token with sockets on both instances is enumerated once.
    await event_namespace1.on_connect(sid="sid3", environ=query_string_for("token3"))
    await event_namespace2.on_connect(sid="sid4", environ=query_string_for("token3"))

    assert await _tokens(event_namespace1._token_manager) == [
        "token1",
        "token2",
        "token3",
    ]

    await event_namespace1._token_manager.disconnect_all()

    assert await _tokens(event_namespace1._token_manager) == ["token2", "token3"]

    await event_namespace2._token_manager.disconnect_all()

    assert await _tokens(event_namespace1._token_manager) == []


async def test_redis_token_manager_remote_owners(
    event_namespace_factory: Callable[[], EventNamespace],
):
    """Each instance sees which other instances own sockets of a token.

    Args:
        event_namespace_factory: Factory fixture for EventNamespace instances.
    """
    event_namespace1 = event_namespace_factory()
    event_namespace2 = event_namespace_factory()

    await event_namespace1.on_connect(sid="sid1", environ=query_string_for("token1"))
    await event_namespace2.on_connect(sid="sid2", environ=query_string_for("token2"))
    await event_namespace1.on_connect(sid="sid3", environ=query_string_for("token3"))
    await event_namespace2.on_connect(sid="sid4", environ=query_string_for("token3"))

    manager1 = event_namespace1._token_manager
    manager2 = event_namespace2._token_manager
    assert isinstance(manager1, RedisTokenManager)
    assert isinstance(manager2, RedisTokenManager)
    owner1 = frozenset({manager1.instance_id})
    owner2 = frozenset({manager2.instance_id})

    assert await manager1._fetch_remote_owners("token1") == frozenset()
    assert await manager1._fetch_remote_owners("token2") == owner2
    assert await manager1._fetch_remote_owners("token3") == owner2
    assert await manager2._fetch_remote_owners("token1") == owner1
    assert await manager2._fetch_remote_owners("token2") == frozenset()
    assert await manager2._fetch_remote_owners("token3") == owner1


async def test_redis_token_manager_restore_keeps_other_instance_sockets(
    event_namespace_factory: Callable[[], EventNamespace],
):
    """A late keep-alive restore adds to what another instance stored meanwhile.

    Args:
        event_namespace_factory: Factory fixture for EventNamespace instances.
    """
    event_namespace1 = event_namespace_factory()
    event_namespace2 = event_namespace_factory()

    manager1 = event_namespace1._token_manager
    manager2 = event_namespace2._token_manager
    assert isinstance(manager1, RedisTokenManager)
    assert isinstance(manager2, RedisTokenManager)

    await event_namespace1.on_connect(sid="sid1", environ=query_string_for("token1"))
    # Stop the live subscriber so the deletion notification is handled manually.
    assert manager1._socket_record_task is not None
    manager1._socket_record_task.cancel()
    # The set expires and another instance links a socket to the token.
    await manager1.redis.delete(manager1._get_redis_key("token1"))
    await event_namespace2.on_connect(sid="sid2", environ=query_string_for("token1"))
    # The first instance processes the expiration notification late.
    await manager1._handle_socket_record_del("token1")

    assert await _redis_sockets(manager1, "token1") == {
        f"{manager1.instance_id}:sid1".encode(),
        f"{manager2.instance_id}:sid2".encode(),
    }
    assert await manager1._fetch_remote_owners("token1") == frozenset({
        manager2.instance_id
    })
    assert await manager2._fetch_remote_owners("token1") == frozenset({
        manager1.instance_id
    })


async def test_redis_token_manager_update_reaches_every_sid_once(
    event_namespace_factory: Callable[[], EventNamespace],
):
    """An update for a token reaches each of its sockets once, on every instance.

    Args:
        event_namespace_factory: Factory fixture for EventNamespace instances.
    """
    event_namespace1 = event_namespace_factory()
    event_namespace2 = event_namespace_factory()
    event_namespace3 = event_namespace_factory()
    emit1, emit2, emit3 = map(
        _emit_mock, (event_namespace1, event_namespace2, event_namespace3)
    )

    # A reconnect leaves two sockets on the first instance; a second tab with
    # the same token is served by the second instance.
    await event_namespace1.on_connect(sid="sid1", environ=query_string_for("token1"))
    await event_namespace1.on_connect(sid="sid2", environ=query_string_for("token1"))
    await event_namespace2.on_connect(sid="sid3", environ=query_string_for("token1"))
    await event_namespace3.on_connect(sid="sid4", environ=query_string_for("token2"))
    for emit in (emit1, emit2, emit3):
        # Nothing was emitted on connect: no socket was handed a new token.
        emit.assert_not_called()

    # From an instance owning some of the sockets.
    update = StateUpdate(delta={"state": {"count": 1}})
    await event_namespace1.emit_update(update, token="token1")
    await _wait_for_call_count(emit2)
    await _settle()
    assert emit1.await_args_list == [
        call("event", update, to="sid1"),
        call("event", update, to="sid2"),
    ]
    assert emit2.await_args_list == [call("event", update, to="sid3")]
    emit3.assert_not_called()

    # From an instance owning none of them.
    for emit in (emit1, emit2):
        emit.reset_mock()
    update = StateUpdate(delta={"state": {"count": 2}})
    await event_namespace3.emit_update(update, token="token1")
    await _wait_for_call_count(emit1, 2)
    await _wait_for_call_count(emit2)
    await _settle()
    assert emit1.await_args_list == [
        call("event", update, to="sid1"),
        call("event", update, to="sid2"),
    ]
    assert emit2.await_args_list == [call("event", update, to="sid3")]
    emit3.assert_not_called()

    # The late disconnect of the replaced socket only stops its own updates.
    for emit in (emit1, emit2):
        emit.reset_mock()
    task = event_namespace1.on_disconnect(sid="sid1")
    assert task is not None
    await task
    update = StateUpdate(delta={"state": {"count": 3}})
    await event_namespace2.emit_update(update, token="token1")
    await _wait_for_call_count(emit1)
    await _settle()
    assert emit1.await_args_list == [call("event", update, to="sid2")]
    assert emit2.await_args_list == [call("event", update, to="sid3")]
    emit3.assert_not_called()


async def test_redis_token_manager_lost_and_found(
    event_namespace_factory: Callable[[], EventNamespace],
):
    """Updates emitted for lost and found tokens should be routed correctly via redis.

    Args:
        event_namespace_factory: Factory fixture for EventNamespace instances.
    """
    event_namespace1 = event_namespace_factory()
    emit1_mock = _emit_mock(event_namespace1)
    event_namespace2 = event_namespace_factory()
    emit2_mock = _emit_mock(event_namespace2)

    await event_namespace1.on_connect(sid="sid1", environ=query_string_for("token1"))
    await event_namespace2.on_connect(sid="sid2", environ=query_string_for("token2"))

    await event_namespace2.emit_update(StateUpdate(), token="token1")
    await _wait_for_call_count(emit1_mock)
    emit2_mock.assert_not_called()
    emit1_mock.assert_called_once()
    emit1_mock.reset_mock()

    await event_namespace2.emit_update(StateUpdate(), token="token2")
    await _wait_for_call_count(emit2_mock)
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
    await _wait_for_call_count(emit2_mock)
    emit1_mock.assert_not_called()
    emit2_mock.assert_called_once()
    emit2_mock.reset_mock()

    if task := event_namespace2.on_disconnect(sid="sid1"):
        await task
    await event_namespace1.on_connect(sid="sid1", environ=query_string_for("token1"))
    await event_namespace2.emit_update(StateUpdate(), token="token1")
    await _wait_for_call_count(emit1_mock)
    emit2_mock.assert_not_called()
    emit1_mock.assert_called_once()
    emit1_mock.reset_mock()


async def test_redis_token_manager_lost_and_found_router_data(
    event_namespace_factory: Callable[[], EventNamespace],
):
    """Updates emitted for lost and found tokens should serialize properly.

    Args:
        event_namespace_factory: Factory fixture for EventNamespace instances.
    """
    event_namespace1 = event_namespace_factory()
    emit1_mock = _emit_mock(event_namespace1)
    event_namespace2 = event_namespace_factory()
    emit2_mock = _emit_mock(event_namespace2)

    await event_namespace1.on_connect(sid="sid1", environ=query_string_for("token1"))
    await event_namespace2.on_connect(sid="sid2", environ=query_string_for("token2"))

    router = RouterData.from_router_data(
        {"headers": {"x-test": "value"}},
    )

    await event_namespace2.emit_update(
        StateUpdate(delta={"state": {"router": router}}), token="token1"
    )
    await _wait_for_call_count(emit1_mock)
    emit2_mock.assert_not_called()
    emit1_mock.assert_called_once()
    assert isinstance(emit1_mock.call_args[0][1], StateUpdate)
    assert isinstance(emit1_mock.call_args[0][1].delta["state"]["router"], RouterData)
    assert emit1_mock.call_args[0][1].delta["state"]["router"] == router
    emit1_mock.reset_mock()
