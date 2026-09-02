"""Token manager for handling client token to session ID mappings."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
import pickle
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable, Coroutine
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar

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
    """Record for a StateUpdate for a token with its socket on another instance."""

    token: str
    update: StateUpdate


class TokenManager(ABC):
    """Abstract base class for managing client token to session ID mappings."""

    def __init__(self):
        """Initialize the token manager with local dictionaries."""
        # Each process has an instance_id to identify its own sockets.
        self.instance_id: str = _get_new_token()
        # Keep a mapping between client token and socket ID.
        self.token_to_socket: dict[str, SocketRecord] = {}
        # Keep a mapping between socket ID and client token.
        self.sid_to_token: dict[str, str] = {}

    @property
    def token_to_sid(self) -> MappingProxyType[str, str]:
        """Read-only compatibility property for token_to_socket mapping.

        Returns:
            The token to session ID mapping.
        """
        return MappingProxyType({
            token: sr.sid for token, sr in self.token_to_socket.items()
        })

    async def enumerate_tokens(self) -> AsyncIterator[str]:
        """Iterate over all tokens in the system.

        Yields:
            All client tokens known to the TokenManager.
        """
        for token in self.token_to_socket:
            yield token

    async def is_token_connected(self, token: str) -> bool:
        """Whether the token has a connected client socket on any instance.

        Args:
            token: The client token.

        Returns:
            True if the token has a connected socket.
        """
        return token in self.token_to_socket

    @abstractmethod
    async def link_token_to_sid(self, token: str, sid: str) -> str | None:
        """Link a token to a session ID.

        Args:
            token: The client token.
            sid: The Socket.IO session ID.

        Returns:
            New token if duplicate detected and new token generated, None otherwise.
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
        token_sid_pairs: set[tuple[str, str]] = {
            (token, sr.sid) for token, sr in self.token_to_socket.items()
        }
        token_sid_pairs.update(
            ((token, sid) for sid, token in self.sid_to_token.items())
        )
        # Perform the disconnection logic here
        for token, sid in token_sid_pairs:
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

        Args:
            token: The client token.
            sid: The Socket.IO session ID.

        Returns:
            New token if duplicate detected and new token generated, None otherwise.
        """
        # Check if token is already mapped to a different SID (duplicate tab)
        if (
            socket_record := self.token_to_socket.get(token)
        ) is not None and sid != socket_record.sid:
            new_token = _get_new_token()
            self.token_to_socket[new_token] = SocketRecord(
                instance_id=self.instance_id, sid=sid
            )
            self.sid_to_token[sid] = new_token
            return new_token

        # Normal case - link token to SID
        self.token_to_socket[token] = SocketRecord(
            instance_id=self.instance_id, sid=sid
        )
        self.sid_to_token[sid] = token
        return None

    async def disconnect_token(self, token: str, sid: str) -> None:
        """Clean up token mapping when client disconnects.

        Args:
            token: The client token.
            sid: The Socket.IO session ID.
        """
        # Clean up both mappings
        self.token_to_socket.pop(token, None)
        self.sid_to_token.pop(sid, None)

    async def close(self) -> None:
        """Release any resources held by the token manager (no-op)."""


class RedisTokenManager(LocalTokenManager):
    """Token manager using Redis for distributed multi-worker support.

    Inherits local dict logic from LocalTokenManager and adds Redis layer
    for cross-worker duplicate detection.
    """

    _token_socket_record_prefix: ClassVar[str] = "token_manager_socket_record_"

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

        # Pub/sub tasks for handling sockets owned by other instances.
        self._socket_record_task: asyncio.Task | None = None
        self._lost_and_found_task: asyncio.Task | None = None

    def _get_redis_key(self, token: str) -> str:
        """Get Redis key for token mapping.

        Args:
            token: The client token.

        Returns:
            Redis key following Reflex conventions: token_manager_socket_record_{token}
        """
        return f"{self._token_socket_record_prefix}{token}"

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
            for key in scan_result[1]:
                yield key.decode().replace(self._token_socket_record_prefix, "")
            if not cursor:
                break

    async def _handle_socket_record_del(self, token: str) -> None:
        """Handle deletion of a socket record from Redis.

        Disconnects pop the local mapping before touching redis, so a
        self-owned record still present locally was created by a newer link
        and refers to a live socket; the deletion is an expiration or an
        outdated notification, and the record is re-stored to keep it alive.
        A cached foreign record is dropped and refetched on demand.

        Args:
            token: The client token whose record was deleted.
        """
        if (socket_record := self.token_to_socket.get(token)) is None:
            return
        if socket_record.instance_id == self.instance_id:
            # Restore only if the key is still absent: a newer record (a
            # relink here or a claim by another instance) must win.
            if not await self._store_socket_record(token, socket_record, nx=True):
                # Adopt the newer record without waiting for its set
                # notification, which may be lost across pubsub reconnects.
                await self._get_token_owner(token, refresh=True)
        else:
            self.token_to_socket.pop(token, None)

    async def _subscribe_socket_record_updates(self) -> None:
        """Subscribe to Redis keyspace notifications for socket record updates."""
        await enable_keyspace_notifications(self.redis)
        redis_db = self.redis.get_connection_kwargs().get("db", 0)

        async with self.redis.pubsub() as pubsub:
            await pubsub.psubscribe(
                f"__keyspace@{redis_db}__:{self._get_redis_key('*')}"
            )
            async for message in pubsub.listen():
                if message["type"] == "pmessage":
                    key = message["channel"].split(b":", 1)[1].decode()
                    token = key.replace(self._token_socket_record_prefix, "")

                    if token not in self.token_to_socket:
                        # We don't know about this token, skip
                        continue

                    event = message["data"].decode()
                    if event in ("del", "expired", "evicted"):
                        await self._handle_socket_record_del(token)
                    elif event == "set":
                        await self._get_token_owner(token, refresh=True)

    def _ensure_socket_record_task(self) -> None:
        """Ensure the socket record updates subscriber task is running."""
        ensure_task(
            owner=self,
            task_attribute="_socket_record_task",
            coro_function=self._subscribe_socket_record_updates,
            suppress_exceptions=[Exception],
        )

    async def link_token_to_sid(self, token: str, sid: str) -> str | None:
        """Link a token to a session ID with Redis-based duplicate detection.

        Args:
            token: The client token.
            sid: The Socket.IO session ID.

        Returns:
            New token if duplicate detected and new token generated, None otherwise.
        """
        # Fast local check first (handles reconnections)
        if (
            socket_record := self.token_to_socket.get(token)
        ) is not None and sid == socket_record.sid:
            return None  # Same token, same SID = reconnection, no Redis check needed

        # Make sure the update subscriber is running
        self._ensure_socket_record_task()

        # Check Redis for cross-worker duplicates
        redis_key = self._get_redis_key(token)

        try:
            token_exists_in_redis = await self.redis.exists(redis_key)
        except Exception as e:
            logger.error(f"Redis error checking token existence: {e}")
            return await super().link_token_to_sid(token, sid)

        new_token = None
        if token_exists_in_redis:
            # Duplicate exists somewhere - generate new token
            token = new_token = _get_new_token()

        # Store in local dicts
        socket_record = self.token_to_socket[token] = SocketRecord(
            instance_id=self.instance_id, sid=sid
        )
        self.sid_to_token[sid] = token

        await self._store_socket_record(token, socket_record)
        # Return the new token if one was generated
        return new_token

    async def _store_socket_record(
        self, token: str, socket_record: SocketRecord, nx: bool = False
    ) -> bool:
        """Store a socket record in Redis, logging errors instead of raising.

        Args:
            token: The client token.
            socket_record: The record to store.
            nx: Only store the record if the key does not already exist.

        Returns:
            True if the record was stored, False if rejected (nx) or on error.
        """
        try:
            return bool(
                await self.redis.set(
                    self._get_redis_key(token),
                    pickle.dumps(socket_record),
                    ex=self.token_expiration,
                    nx=nx,
                )
            )
        except Exception as e:
            logger.error(f"Redis error storing token: {e}")
            return False

    async def disconnect_token(self, token: str, sid: str) -> None:
        """Clean up token mapping when client disconnects.

        Args:
            token: The client token.
            sid: The Socket.IO session ID.
        """
        # Only clean up if we own it locally (fast ownership check)
        if (
            (socket_record := self.token_to_socket.get(token)) is not None
            and socket_record.sid == sid
            and socket_record.instance_id == self.instance_id
        ):
            # Drop the local mapping before the redis round-trip so the
            # locally-owned fast paths stop treating the token as connected
            # while the delete is in flight.
            await super().disconnect_token(token, sid)

            redis_key = self._get_redis_key(token)
            try:
                await self.redis.delete(redis_key)
            except Exception as e:
                logger.error(f"Redis error deleting token: {e}")

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
        emit_update: Callable[[StateUpdate, str], Coroutine[None, None, None]],
    ) -> None:
        """Subscribe to Redis channel notifications for lost and found deltas.

        Args:
            emit_update: The function to emit state updates.
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
        emit_update: Callable[[StateUpdate, str], Coroutine[None, None, None]],
    ) -> None:
        """Ensure the lost and found subscriber task is running.

        Args:
            emit_update: The function to emit state updates.
        """
        ensure_task(
            owner=self,
            task_attribute="_lost_and_found_task",
            coro_function=self._subscribe_lost_and_found_updates,
            suppress_exceptions=[Exception],
            emit_update=emit_update,
        )

    async def _get_token_owner(self, token: str, refresh: bool = False) -> str | None:
        """Get the instance ID of the owner of a token.

        Args:
            token: The client token.
            refresh: Whether to fetch the latest record from Redis.

        Returns:
            The instance ID of the owner, or None if not found.
        """
        if (
            not refresh
            and (socket_record := self.token_to_socket.get(token)) is not None
        ):
            return socket_record.instance_id

        try:
            socket_record = await self._fetch_socket_record(token)
        except Exception as e:
            logger.error(f"Redis error getting token owner: {e}")
            return None
        return socket_record.instance_id if socket_record is not None else None

    async def _fetch_socket_record(self, token: str) -> SocketRecord | None:
        """Fetch the socket record for a token from redis and cache it.

        Redis errors propagate to the caller so it can distinguish a lookup
        failure from an absent record. This instance is authoritative for its
        own sockets: a record claiming this instance without a live local
        link is a stale leftover of a disconnected socket (its delete is
        still in flight or failed) and is treated as absent.

        Args:
            token: The client token.

        Returns:
            The refreshed socket record, or None if the token has no live socket.
        """
        record_pkl = await self.redis.get(self._get_redis_key(token))
        if not record_pkl:
            return None
        socket_record = pickle.loads(record_pkl)
        # Stale leftover of one of this instance's own disconnected sockets.
        if (
            socket_record.instance_id == self.instance_id
            and self.sid_to_token.get(socket_record.sid) != token
        ):
            return None
        # Drop the reverse mapping of a superseded record (client moved sids).
        if (
            (previous := self.token_to_socket.get(token)) is not None
            and previous.sid != socket_record.sid
            and self.sid_to_token.get(previous.sid) == token
        ):
            self.sid_to_token.pop(previous.sid, None)
        self.token_to_socket[token] = socket_record
        self.sid_to_token[socket_record.sid] = token
        return socket_record

    async def is_token_connected(self, token: str) -> bool:
        """Whether the token has a connected client socket on any instance.

        A record owned by this instance is authoritative. A cached record
        from another instance may be stale, so it is refreshed from redis
        (dropped if the client is gone) and trusted as-is if the refresh fails.

        Args:
            token: The client token.

        Returns:
            True if the token has a connected socket on any instance.
        """
        if (
            socket_record := self.token_to_socket.get(token)
        ) is not None and socket_record.instance_id == self.instance_id:
            return True
        try:
            if await self._fetch_socket_record(token) is not None:
                return True
        except Exception as e:
            logger.warning(f"Redis error checking token connection: {e}")
            return socket_record is not None
        if (
            socket_record is not None
            and self.token_to_socket.get(token) is socket_record
        ):
            self.token_to_socket.pop(token, None)
            self.sid_to_token.pop(socket_record.sid, None)
        return False

    async def emit_lost_and_found(
        self,
        token: str,
        update: StateUpdate,
    ) -> bool:
        """Emit a lost and found delta to Redis.

        Args:
            token: The client token.
            update: The state update.

        Returns:
            True if the delta was published, False otherwise.
        """
        # See where this update belongs
        owner_instance_id = await self._get_token_owner(token)
        if owner_instance_id is None:
            return False
        record = LostAndFoundRecord(token=token, update=update)
        try:
            await self.redis.publish(
                f"channel:{self._get_lost_and_found_key(owner_instance_id)}",
                pickle.dumps(record),
            )
        except Exception as e:
            logger.error(f"Redis error publishing lost and found delta: {e}")
        else:
            return True
        return False

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
