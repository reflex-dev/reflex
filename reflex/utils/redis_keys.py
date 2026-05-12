"""Helpers for Redis key names."""

from __future__ import annotations

import hashlib


def stable_redis_hash_tag(slot_key: str) -> str:
    """Generate a stable Redis Cluster hash tag for a logical slot key.

    Args:
        slot_key: The logical key that should determine the Redis Cluster slot.

    Returns:
        A stable hash tag safe to place between Redis Cluster hash braces.
    """
    return hashlib.sha256(slot_key.encode()).hexdigest()[:16]


def format_redis_key(logical_key: str, *, cluster: bool, slot_key: str) -> str:
    """Format a Redis key, optionally with a Redis Cluster hash tag.

    Args:
        logical_key: The unmodified logical Redis key.
        cluster: Whether Redis Cluster key tagging is enabled.
        slot_key: The logical key used to choose the Redis Cluster slot.

    Returns:
        The Redis key to send to Redis.
    """
    if not cluster:
        return logical_key
    return f"{{{stable_redis_hash_tag(slot_key)}}}:{logical_key}"


def logical_redis_key(redis_key: str) -> str:
    """Remove a Redis Cluster hash tag from a key if present.

    Args:
        redis_key: The Redis key as sent to or received from Redis.

    Returns:
        The logical key without any Redis Cluster hash tag prefix.
    """
    if redis_key.startswith("{") and "}" in redis_key:
        close = redis_key.index("}")
        if close + 1 < len(redis_key) and redis_key[close + 1] == ":":
            return redis_key[close + 2:]
    return redis_key
