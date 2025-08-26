"""Token manager for handling client token to session ID mappings."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
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


class TokenManager(ABC):
    """Abstract base class for managing client token to session ID mappings."""

    def __init__(self):
        """Initialize the token manager with local dictionaries."""
        # Keep a mapping between socket ID and client token.
        self.token_to_sid: dict[str, str] = {}
        # Keep a mapping between client token and socket ID.
        self.sid_to_token: dict[str, str] = {}

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
        if token in self.token_to_sid and sid != self.token_to_sid.get(token):
            new_token = _get_new_token()
            self.token_to_sid[new_token] = sid
            self.sid_to_token[sid] = new_token
            return new_token

        # Normal case - link token to SID
        self.token_to_sid[token] = sid
        self.sid_to_token[sid] = token
        return None

    async def disconnect_token(self, token: str, sid: str) -> None:
        """Clean up token mapping when client disconnects.

        Args:
            token: The client token.
            sid: The Socket.IO session ID.
        """
        # Clean up both mappings
        self.token_to_sid.pop(token, None)
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
            Redis key following Reflex conventions: {token}_sid
        """
        return f"{token}_sid"

    async def link_token_to_sid(self, token: str, sid: str) -> str | None:
        """Link a token to a session ID with Redis-based duplicate detection.

        Args:
            token: The client token.
            sid: The Socket.IO session ID.

        Returns:
            New token if duplicate detected and new token generated, None otherwise.
        """
        # Fast local check first (handles reconnections)
        if token in self.token_to_sid and self.token_to_sid[token] == sid:
            return None  # Same token, same SID = reconnection, no Redis check needed

        # Check Redis for cross-worker duplicates
        redis_key = self._get_redis_key(token)

        try:
            token_exists_in_redis = await self.redis.exists(redis_key)
        except Exception as e:
            console.error(f"Redis error checking token existence: {e}")
            return await super().link_token_to_sid(token, sid)

        if token_exists_in_redis:
            # Duplicate exists somewhere - generate new token
            new_token = _get_new_token()
            new_redis_key = self._get_redis_key(new_token)

            try:
                # Store in Redis
                await self.redis.set(new_redis_key, "1", ex=self.token_expiration)
            except Exception as e:
                console.error(f"Redis error storing new token: {e}")
                # Still update local dicts and continue

            # Store in local dicts (always do this)
            self.token_to_sid[new_token] = sid
            self.sid_to_token[sid] = new_token
            return new_token

        # Normal case - store in both Redis and local dicts
        try:
            await self.redis.set(redis_key, "1", ex=self.token_expiration)
        except Exception as e:
            console.error(f"Redis error storing token: {e}")
            # Continue with local storage

        # Store in local dicts (always do this)
        self.token_to_sid[token] = sid
        self.sid_to_token[sid] = token
        return None

    async def disconnect_token(self, token: str, sid: str) -> None:
        """Clean up token mapping when client disconnects.

        Args:
            token: The client token.
            sid: The Socket.IO session ID.
        """
        # Only clean up if we own it locally (fast ownership check)
        if self.token_to_sid.get(token) == sid:
            # Clean up Redis
            redis_key = self._get_redis_key(token)
            try:
                await self.redis.delete(redis_key)
            except Exception as e:
                console.error(f"Redis error deleting token: {e}")

            # Clean up local dicts (always do this)
            await super().disconnect_token(token, sid)
