"""Token manager for handling client token to session ID mappings."""

from __future__ import annotations

import dataclasses
import json
import uuid
from abc import ABC, abstractmethod
from types import MappingProxyType
from typing import TYPE_CHECKING

from reflex.utils import console, prerequisites

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

    def _get_redis_key(self, token: str) -> str:
        """Get Redis key for token mapping.

        Args:
            token: The client token.

        Returns:
            Redis key following Reflex conventions: token_manager_socket_record_{token}
        """
        return f"token_manager_socket_record_{token}"

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
                json.dumps(dataclasses.asdict(socket_record)),
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
            socket_record := self.token_to_socket.get(token)
        ) is not None and socket_record.sid == sid:
            # Clean up Redis
            redis_key = self._get_redis_key(token)
            try:
                await self.redis.delete(redis_key)
            except Exception as e:
                console.error(f"Redis error deleting token: {e}")

            # Clean up local dicts (always do this)
            await super().disconnect_token(token, sid)
