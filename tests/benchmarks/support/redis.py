"""Real-Redis helpers for scheduled performance suites."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from redis.asyncio import Redis

from reflex.istate.manager.redis import StateManagerRedis

REDIS_URL_ENV = "REFLEX_PERF_REDIS_URL"


def performance_redis_url() -> str:
    """Return the isolated Redis database used by performance tests.

    Returns:
        Redis connection URL.
    """
    return os.environ.get(REDIS_URL_ENV, "redis://127.0.0.1:6379/15")


@asynccontextmanager
async def real_redis_state_manager() -> AsyncIterator[StateManagerRedis]:
    """Create an isolated state manager backed by a reachable Redis server.

    Yields:
        A state manager whose database is empty at entry and exit.

    Raises:
        ConnectionError: If the configured Redis server is unreachable.
    """
    redis = Redis.from_url(performance_redis_url())
    await redis.ping()  # pyright: ignore [reportGeneralTypeIssues]
    await redis.flushdb()
    manager = StateManagerRedis(redis=redis)
    try:
        yield manager
    finally:
        await manager.close()
        await redis.flushdb()
        await redis.aclose()
