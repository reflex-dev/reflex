"""Token manager for handling client token to session ID mappings."""

from __future__ import annotations

import asyncio
import dataclasses
import pickle
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable, Coroutine
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar

from reflex.istate.manager.redis import StateManagerRedis
from reflex.state import BaseState, StateUpdate
from reflex.utils import console, prerequisites
from reflex.utils.tasks import ensure_task

if TYPE_CHECKING:
    from redis.asyncio import Redis


class _TokenNotConnectedError(Exception):
    """Raised when a token is not connected."""


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
        # Lifecycle events for connect/disconnect notifications.
        self._token_disconnect_events: dict[str, list[asyncio.Event]] = {}
        self._sid_disconnect_events: dict[str, list[asyncio.Event]] = {}
        self._token_connect_events: dict[str, list[asyncio.Event]] = {}

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

    def _notify_connect(self, token: str, sid: str) -> None:
        """Notify lifecycle watchers that a token/sid has connected.

        Args:
            token: The client token.
            sid: The Socket.IO session ID.
        """
        for event in self._token_connect_events.pop(token, []):
            event.set()

    def _notify_disconnect(self, token: str, sid: str) -> None:
        """Notify lifecycle watchers that a token/sid has disconnected.

        Args:
            token: The client token.
            sid: The Socket.IO session ID.
        """
        for event in self._token_disconnect_events.pop(token, []):
            event.set()
        for event in self._sid_disconnect_events.pop(sid, []):
            event.set()

    async def session_is_connected(self, sid: str) -> AsyncIterator[str]:
        """Yield the client token, then block until the session disconnects.

        Yields the client token once, then suspends until the session
        disconnects. Use with ``async for`` or ``contextlib.aclosing``.

        Args:
            sid: The Socket.IO session ID.

        Yields:
            The client token associated with the session.

        Raises:
            _TokenNotConnectedError: If the session is not currently connected.
        """
        token = self.sid_to_token.get(sid)
        if token is None:
            raise _TokenNotConnectedError(
                f"Session {sid!r} is not currently connected."
            )
        disconnect_event = asyncio.Event()
        self._sid_disconnect_events.setdefault(sid, []).append(disconnect_event)
        try:
            yield token
            await disconnect_event.wait()
        finally:
            events = self._sid_disconnect_events.get(sid, [])
            if disconnect_event in events:
                events.remove(disconnect_event)

    async def token_is_connected(self, client_token: str) -> AsyncIterator[str]:
        """Yield the session ID, then block until the token disconnects.

        Yields the session ID once, then suspends until the token
        disconnects. Use with ``async for`` or ``contextlib.aclosing``.

        Args:
            client_token: The client token.

        Yields:
            The session ID associated with the token.

        Raises:
            _TokenNotConnectedError: If the token is not currently connected.
        """
        socket_record = self.token_to_socket.get(client_token)
        if socket_record is None:
            raise _TokenNotConnectedError(
                f"Token {client_token!r} is not currently connected."
            )
        disconnect_event = asyncio.Event()
        self._token_disconnect_events.setdefault(client_token, []).append(
            disconnect_event
        )
        try:
            yield socket_record.sid
            await disconnect_event.wait()
        finally:
            events = self._token_disconnect_events.get(client_token, [])
            if disconnect_event in events:
                events.remove(disconnect_event)

    def when_session_disconnects(self, sid: str) -> asyncio.Event:
        """Return an asyncio.Event that is set when the session disconnects.

        Args:
            sid: The Socket.IO session ID.

        Returns:
            An asyncio.Event that will be set on disconnect.
        """
        event = asyncio.Event()
        if sid not in self.sid_to_token:
            # Already disconnected, set immediately.
            event.set()
        else:
            self._sid_disconnect_events.setdefault(sid, []).append(event)
        return event

    def when_token_disconnects(self, client_token: str) -> asyncio.Event:
        """Return an asyncio.Event that is set when the token disconnects.

        Args:
            client_token: The client token.

        Returns:
            An asyncio.Event that will be set on disconnect.
        """
        event = asyncio.Event()
        if client_token not in self.token_to_socket:
            # Already disconnected, set immediately.
            event.set()
        else:
            self._token_disconnect_events.setdefault(client_token, []).append(
                event
            )
        return event

    def when_token_connects(self, client_token: str) -> asyncio.Event:
        """Return an asyncio.Event that is set when the token connects.

        Args:
            client_token: The client token.

        Returns:
            An asyncio.Event that will be set on connect.
        """
        event = asyncio.Event()
        if client_token in self.token_to_socket:
            # Already connected, set immediately.
            event.set()
        else:
            self._token_connect_events.setdefault(client_token, []).append(
                event
            )
        return event


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
        from reflex.config import get_config

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

    async def _handle_socket_record_del(
        self, token: str, expired: bool = False
    ) -> None:
        """Handle deletion of a socket record from Redis.

        Args:
            token: The client token whose record was deleted.
            expired: Whether the deletion was due to expiration.
        """
        if (
            socket_record := self.token_to_socket.pop(token, None)
        ) is not None and socket_record.instance_id == self.instance_id:
            self.sid_to_token.pop(socket_record.sid, None)
            if expired:
                # Keep the record alive as long as this process is alive and not deleted.
                await self.link_token_to_sid(token, socket_record.sid)

    async def _subscribe_socket_record_updates(self) -> None:
        """Subscribe to Redis keyspace notifications for socket record updates."""
        await StateManagerRedis(
            state=BaseState, redis=self.redis
        )._enable_keyspace_notifications()
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
                        await self._handle_socket_record_del(
                            token,
                            expired=(event == "expired"),
                        )
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
            console.error(f"Redis error checking token existence: {e}")
            return await super().link_token_to_sid(token, sid)

        new_token = None
        if token_exists_in_redis:
            # Duplicate exists somewhere - generate new token
            token = new_token = _get_new_token()
            redis_key = self._get_redis_key(new_token)

        # Store in local dicts
        socket_record = self.token_to_socket[token] = SocketRecord(
            instance_id=self.instance_id, sid=sid
        )
        self.sid_to_token[sid] = token

        # Store in Redis if possible
        try:
            await self.redis.set(
                redis_key,
                pickle.dumps(socket_record),
                ex=self.token_expiration,
            )
        except Exception as e:
            console.error(f"Redis error storing token: {e}")
        # Return the new token if one was generated
        return new_token

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
            # Clean up Redis
            redis_key = self._get_redis_key(token)
            try:
                await self.redis.delete(redis_key)
            except Exception as e:
                console.error(f"Redis error deleting token: {e}")

            # Clean up local dicts (always do this)
            await super().disconnect_token(token, sid)

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

        redis_key = self._get_redis_key(token)
        try:
            record_pkl = await self.redis.get(redis_key)
            if record_pkl:
                socket_record = pickle.loads(record_pkl)
                self.token_to_socket[token] = socket_record
                self.sid_to_token[socket_record.sid] = token
                return socket_record.instance_id
            console.warn(f"Redis token owner not found for token {token}")
        except Exception as e:
            console.error(f"Redis error getting token owner: {e}")
        return None

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
            console.error(f"Redis error publishing lost and found delta: {e}")
        else:
            return True
        return False


def get_token_manager() -> TokenManager:
    """Get the token manager for the currently running app.

    Returns:
        The active TokenManager instance.

    Raises:
        RuntimeError: If the app or event namespace is not initialized.
    """
    app_mod = prerequisites.get_and_validate_app()
    app = app_mod.app
    event_namespace = app.event_namespace
    if event_namespace is None:
        msg = "Event namespace is not initialized. Is the app running?"
        raise RuntimeError(msg)
    return event_namespace._token_manager
