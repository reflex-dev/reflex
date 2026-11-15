"""Token manager for handling client token to session ID mappings."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
import pickle
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable, Coroutine
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar, cast

from reflex_base.utils import console

from reflex.istate.manager.redis import enable_keyspace_notifications
from reflex.state import StateUpdate
from reflex.utils import prerequisites
from reflex.utils.tasks import ensure_task

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from redis.asyncio import Redis


def _get_new_token() -> str:
    """Generate a new unique token.

    Returns:
        A new UUID4 token string.
    """
    return str(uuid.uuid4())


@dataclasses.dataclass(frozen=True, kw_only=True)
class SocketRecord:
    """Record for a connected socket client."""

    instance_id: str
    sid: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class LostAndFoundRecord:
    """Record for a StateUpdate for a token with sockets on another instance."""

    token: str
    update: StateUpdate


class TokenManager(ABC):
    """Abstract base class for managing client token to session ID mappings.

    A client token identifies a session, not a socket: any number of sockets
    may be linked to one token (a reconnect whose old socket has not been
    dropped yet, duplicated tabs), on any instance of the app.
    """

    def __init__(self):
        """Initialize the token manager with local dictionaries."""
        # Each process has an instance_id to identify its own sockets.
        self._reset_instance_id()
        # The sockets connected to this instance for each client token, oldest first.
        self.token_to_sids: dict[str, tuple[str, ...]] = {}
        # Keep a mapping between socket ID and client token.
        self.sid_to_token: dict[str, str] = {}

    def _reset_instance_id(self) -> None:
        """Assign a fresh socket-owner identity when a server worker starts."""
        self.instance_id: str = _get_new_token()

    @property
    def token_to_socket(self) -> MappingProxyType[str, SocketRecord]:
        """Deprecated read-only view of the newest local socket of each token.

        Returns:
            The token to socket record mapping.
        """
        console.deprecate(
            feature_name="TokenManager.token_to_socket",
            reason="A client token can have several sockets. Use token_to_sids instead.",
            deprecation_version="0.11.1",
            removal_version="1.0",
        )
        return MappingProxyType({
            token: SocketRecord(instance_id=self.instance_id, sid=sids[-1])
            for token, sids in self.token_to_sids.items()
        })

    @property
    def token_to_sid(self) -> MappingProxyType[str, str]:
        """Deprecated read-only view of the newest local socket ID of each token.

        Returns:
            The token to session ID mapping.
        """
        console.deprecate(
            feature_name="TokenManager.token_to_sid",
            reason="A client token can have several sockets. Use token_to_sids instead.",
            deprecation_version="0.11.1",
            removal_version="1.0",
        )
        return MappingProxyType({
            token: sids[-1] for token, sids in self.token_to_sids.items()
        })

    def _link(self, token: str, sid: str) -> bool:
        """Link a socket of this instance to a token.

        Args:
            token: The client token.
            sid: The Socket.IO session ID.

        Returns:
            False if the socket was already linked to the token.
        """
        if (previous := self.sid_to_token.get(sid)) == token:
            return False
        if previous is not None:
            # One socket serves one token: it moved to another one.
            self._unlink(previous, sid)
        self.token_to_sids[token] = (*self.token_to_sids.get(token, ()), sid)
        self.sid_to_token[sid] = token
        return True

    def _unlink(self, token: str, sid: str) -> bool:
        """Unlink a socket of this instance from a token.

        Only the given socket is dropped: the token stays linked for as long
        as another socket uses it.

        Args:
            token: The client token.
            sid: The Socket.IO session ID.

        Returns:
            False if the socket was not linked to the token.
        """
        if self.sid_to_token.get(sid) != token:
            return False
        del self.sid_to_token[sid]
        if remaining := tuple(
            other for other in self.token_to_sids.get(token, ()) if other != sid
        ):
            self.token_to_sids[token] = remaining
        else:
            self.token_to_sids.pop(token, None)
        return True

    async def enumerate_tokens(self) -> AsyncIterator[str]:
        """Iterate over all tokens in the system.

        Yields:
            All client tokens known to the TokenManager.
        """
        for token in self.token_to_sids:
            yield token

    async def is_token_connected(self, token: str) -> bool:
        """Whether the token has a connected client socket on any instance.

        Args:
            token: The client token.

        Returns:
            True if the token has a connected socket.
        """
        return token in self.token_to_sids

    @abstractmethod
    async def link_token_to_sid(self, token: str, sid: str) -> str | None:
        """Link a token to a session ID.

        Args:
            token: The client token.
            sid: The Socket.IO session ID.

        Returns:
            A replacement token the client must switch to, None to keep its own.
        """

    @abstractmethod
    async def disconnect_token(self, token: str, sid: str) -> None:
        """Clean up token mapping when client disconnects.

        Args:
            token: The client token.
            sid: The Socket.IO session ID.
        """

    @classmethod
    def create(cls) -> TokenManager:
        """Factory method to create appropriate TokenManager implementation.

        Returns:
            RedisTokenManager if Redis is available, LocalTokenManager otherwise.
        """
        if prerequisites.check_redis_used():
            redis_client = prerequisites.get_redis()
            if redis_client is not None:
                return RedisTokenManager(redis_client)

        return LocalTokenManager()

    async def disconnect_all(self):
        """Disconnect all tracked tokens when the server is going down."""
        for sid, token in tuple(self.sid_to_token.items()):
            await self.disconnect_token(token, sid)

    @abstractmethod
    async def close(self) -> None:
        """Release any resources held by the token manager."""


class LocalTokenManager(TokenManager):
    """Token manager using local in-memory dictionaries (single worker)."""

    def __init__(self):
        """Initialize the local token manager."""
        super().__init__()

    async def link_token_to_sid(self, token: str, sid: str) -> str | None:
        """Link a token to a session ID.

        A token that already has a socket keeps it: the new socket joins the
        same session instead of being handed a fresh token.

        Args:
            token: The client token.
            sid: The Socket.IO session ID.

        Returns:
            None: the client always keeps its token.
        """
        self._link(token, sid)
        return None

    async def disconnect_token(self, token: str, sid: str) -> None:
        """Clean up token mapping when client disconnects.

        Args:
            token: The client token.
            sid: The Socket.IO session ID.
        """
        self._unlink(token, sid)

    async def close(self) -> None:
        """Release any resources held by the token manager (no-op)."""


class RedisTokenManager(LocalTokenManager):
    """Token manager using Redis for distributed multi-worker support.

    Inherits local dict logic from LocalTokenManager and adds a Redis set per
    token holding the sockets every instance has linked to it, so an update
    can be relayed to each instance that owns one.
    """

    _token_sockets_prefix: ClassVar[str] = "token_manager_sockets_"

    # Seconds a cached set of other owning instances is trusted without a
    # keyspace notification, which redis does not guarantee to deliver.
    _remote_owners_max_age: ClassVar[float] = 5.0

    def __init__(self, redis: Redis):
        """Initialize the Redis token manager.

        Args:
            redis: The Redis client instance.
        """
        # Initialize parent's local dicts
        super().__init__()

        self.redis = redis

        # Get token expiration from config (default 1 hour)
        from reflex_base.config import get_config

        config = get_config()
        self.token_expiration = config.redis_token_expiration

        # The other instances owning sockets of a token, with the time read.
        self._remote_owners: dict[str, tuple[frozenset[str], float]] = {}
        # Bumped on every invalidation, so a read that raced one is not cached.
        self._remote_owners_generation = 0

        # Pub/sub tasks for handling sockets owned by other instances.
        self._socket_record_task: asyncio.Task | None = None
        self._lost_and_found_task: asyncio.Task | None = None

    def _get_redis_key(self, token: str) -> str:
        """Get Redis key for the set of sockets linked to a token.

        Args:
            token: The client token.

        Returns:
            Redis key following Reflex conventions: token_manager_sockets_{token}
        """
        return f"{self._token_sockets_prefix}{token}"

    def _get_socket_member(self, sid: str) -> str:
        """Get the member of a token's Redis set for a socket of this instance.

        Args:
            sid: The Socket.IO session ID.

        Returns:
            The owning instance ID and the session ID, separated by a colon.
        """
        return f"{self.instance_id}:{sid}"

    async def enumerate_tokens(self) -> AsyncIterator[str]:
        """Iterate over all tokens in the system.

        Yields:
            All client tokens known to the RedisTokenManager.
        """
        cursor = 0
        while scan_result := await self.redis.scan(
            cursor=cursor, match=self._get_redis_key("*")
        ):
            cursor = int(scan_result[0])
            for key in cast("list[bytes]", scan_result[1]):
                yield key.decode().replace(self._token_sockets_prefix, "")
            if not cursor:
                break

    def _invalidate_remote_owners(self, token: str) -> None:
        """Forget which other instances own sockets of a token.

        Args:
            token: The client token.
        """
        self._remote_owners.pop(token, None)
        self._remote_owners_generation += 1

    async def _handle_socket_record_del(self, token: str) -> None:
        """Handle deletion of a token's socket set from Redis.

        The set of a token with sockets on this instance only goes away by
        expiring or being evicted, so those sockets are added back to keep
        them reachable from the other instances. Adding is idempotent and
        each instance only writes its own sockets, so no instance can
        overwrite what another one stored.

        Args:
            token: The client token whose socket set was deleted.
        """
        self._invalidate_remote_owners(token)
        if sids := self.token_to_sids.get(token):
            await self._store_sockets(token, sids)

    async def _subscribe_socket_record_updates(self) -> None:
        """Subscribe to Redis keyspace notifications for socket set updates."""
        await enable_keyspace_notifications(self.redis)
        redis_db = self.redis.get_connection_kwargs().get("db", 0)

        async with self.redis.pubsub() as pubsub:
            await pubsub.psubscribe(
                f"__keyspace@{redis_db}__:{self._get_redis_key('*')}"
            )
            async for message in pubsub.listen():
                if message["type"] == "pmessage":
                    key = message["channel"].split(b":", 1)[1].decode()
                    token = key.replace(self._token_sockets_prefix, "")

                    if (
                        token not in self.token_to_sids
                        and token not in self._remote_owners
                    ):
                        # We don't know about this token, skip
                        continue

                    event = message["data"].decode()
                    if event in ("del", "expired", "evicted"):
                        await self._handle_socket_record_del(token)
                    elif event in ("sadd", "srem"):
                        self._invalidate_remote_owners(token)

    def _ensure_socket_record_task(self) -> None:
        """Ensure the socket record updates subscriber task is running."""
        ensure_task(
            owner=self,
            task_attribute="_socket_record_task",
            coro_function=self._subscribe_socket_record_updates,
            suppress_exceptions=[Exception],
        )

    async def link_token_to_sid(self, token: str, sid: str) -> str | None:
        """Link a token to a session ID and announce the socket in Redis.

        Args:
            token: The client token.
            sid: The Socket.IO session ID.

        Returns:
            None: the client always keeps its token.
        """
        previous = self.sid_to_token.get(sid)
        if not self._link(token, sid):
            return None  # Same token, same SID: already announced.

        # Make sure the update subscriber is running
        self._ensure_socket_record_task()

        if previous is not None:
            await self._remove_socket(previous, sid)
        await self._store_sockets(token, (sid,))
        if self.sid_to_token.get(sid) != token:
            # The socket disconnected while it was being announced, and its
            # removal may have reached redis first.
            await self._remove_socket(token, sid)
        return None

    async def _store_sockets(self, token: str, sids: tuple[str, ...]) -> bool:
        """Add sockets of this instance to a token's Redis set.

        The additions and the expiration are sent as one transaction. Errors
        are logged instead of raised.

        Args:
            token: The client token.
            sids: The Socket.IO session IDs to add.

        Returns:
            True if the sockets were stored, False on error.
        """
        redis_key = self._get_redis_key(token)
        try:
            pipe = self.redis.pipeline(transaction=True)
            for sid in sids:
                pipe.sadd(redis_key, self._get_socket_member(sid))
            pipe.expire(redis_key, self.token_expiration)
            await pipe.execute()
        except Exception as e:
            logger.error(f"Redis error storing token: {e}")
            return False
        return True

    async def _remove_socket(self, token: str, sid: str) -> None:
        """Remove a socket of this instance from a token's Redis set.

        Redis drops the set with its last member. Errors are logged instead
        of raised.

        Args:
            token: The client token.
            sid: The Socket.IO session ID.
        """
        try:
            await self.redis.srem(
                self._get_redis_key(token), self._get_socket_member(sid)
            )
        except Exception as e:
            logger.error(f"Redis error deleting token: {e}")

    async def disconnect_token(self, token: str, sid: str) -> None:
        """Clean up token mapping when client disconnects.

        Args:
            token: The client token.
            sid: The Socket.IO session ID.
        """
        # Drop the local mapping before the redis round-trip so the
        # locally-owned fast paths stop treating the socket as connected
        # while the removal is in flight. Only a socket this instance owns
        # is removed from redis.
        if self._unlink(token, sid):
            await self._remove_socket(token, sid)

    @staticmethod
    def _get_lost_and_found_key(instance_id: str) -> str:
        """Get the Redis key for lost and found deltas for an instance.

        Args:
            instance_id: The instance ID.

        Returns:
            The Redis key for lost and found deltas.
        """
        return f"token_manager_lost_and_found_{instance_id}"

    async def _subscribe_lost_and_found_updates(
        self,
        emit_update: Callable[[StateUpdate, str], Coroutine[None, None, object]],
    ) -> None:
        """Subscribe to Redis channel notifications for lost and found deltas.

        Args:
            emit_update: The function to emit state updates to the sockets of
                this instance. It must not relay them any further: the sender
                publishes to every owning instance itself.
        """
        async with self.redis.pubsub() as pubsub:
            await pubsub.psubscribe(
                f"channel:{self._get_lost_and_found_key(self.instance_id)}"
            )
            async for message in pubsub.listen():
                if message["type"] == "pmessage":
                    record = pickle.loads(message["data"])
                    await emit_update(record.update, record.token)

    def ensure_lost_and_found_task(
        self,
        emit_update: Callable[[StateUpdate, str], Coroutine[None, None, object]],
    ) -> None:
        """Ensure the lost and found subscriber task is running.

        Args:
            emit_update: The function to emit state updates to the sockets of
                this instance.
        """
        ensure_task(
            owner=self,
            task_attribute="_lost_and_found_task",
            coro_function=self._subscribe_lost_and_found_updates,
            suppress_exceptions=[Exception],
            emit_update=emit_update,
        )

    async def _fetch_remote_owners(self, token: str) -> frozenset[str]:
        """Read from redis which other instances own sockets of a token.

        Redis errors propagate to the caller so it can distinguish a lookup
        failure from a token without sockets elsewhere. Members claiming this
        instance are skipped: its own sockets are tracked locally, and one
        without a live local link is a stale leftover of a disconnected
        socket (its removal is still in flight or failed).

        Args:
            token: The client token.

        Returns:
            The IDs of the other instances with a socket linked to the token.
        """
        generation = self._remote_owners_generation
        members = cast(
            "set[bytes]", await self.redis.smembers(self._get_redis_key(token))
        )
        owners = frozenset(
            instance_id
            for member in members
            if (instance_id := member.decode().partition(":")[0]) != self.instance_id
        )
        # Nothing invalidates the entry of a token unknown to this instance.
        if generation == self._remote_owners_generation and (
            owners or token in self.token_to_sids
        ):
            self._remote_owners[token] = (owners, time.monotonic())
        else:
            self._remote_owners.pop(token, None)
        return owners

    async def _get_remote_owners(self, token: str) -> frozenset[str]:
        """Get the other instances owning sockets of a token.

        The cached answer is used while it is fresh. An answer that would
        leave the update without any recipient (no socket here, none cached
        elsewhere) is always read again.

        Args:
            token: The client token.

        Returns:
            The IDs of the other instances with a socket linked to the token.
        """
        cached = self._remote_owners.get(token)
        if (
            cached is not None
            and time.monotonic() - cached[1] < self._remote_owners_max_age
            and (cached[0] or token in self.token_to_sids)
        ):
            return cached[0]
        try:
            return await self._fetch_remote_owners(token)
        except Exception as e:
            logger.error(f"Redis error getting token owners: {e}")
            return cached[0] if cached is not None else frozenset()

    async def is_token_connected(self, token: str) -> bool:
        """Whether the token has a connected client socket on any instance.

        A socket linked to this instance is authoritative. Sockets of other
        instances are looked up in redis; if that fails, the cached answer
        is trusted.

        Args:
            token: The client token.

        Returns:
            True if the token has a connected socket on any instance.
        """
        if token in self.token_to_sids:
            return True
        try:
            return bool(await self._fetch_remote_owners(token))
        except Exception as e:
            logger.warning(f"Redis error checking token connection: {e}")
            return (cached := self._remote_owners.get(token)) is not None and bool(
                cached[0]
            )

    async def emit_lost_and_found(
        self,
        token: str,
        update: StateUpdate,
    ) -> bool:
        """Relay a delta to the other instances owning sockets of a token.

        Each of them emits it to its own sockets only, so every socket of
        the token receives the delta once.

        Args:
            token: The client token.
            update: The state update.

        Returns:
            True if the delta was published to another instance, False otherwise.
        """
        owners = await self._get_remote_owners(token)
        if not owners:
            return False
        record = pickle.dumps(LostAndFoundRecord(token=token, update=update))
        published = False
        for owner_instance_id in owners:
            try:
                await self.redis.publish(
                    f"channel:{self._get_lost_and_found_key(owner_instance_id)}",
                    record,
                )
            except Exception as e:
                logger.error(f"Redis error publishing lost and found delta: {e}")
            else:
                published = True
        return published

    async def close(self) -> None:
        """Cancel background pub/sub tasks and close the Redis client."""
        for task in (self._socket_record_task, self._lost_and_found_task):
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._socket_record_task = None
        self._lost_and_found_task = None
        await self.redis.aclose()
