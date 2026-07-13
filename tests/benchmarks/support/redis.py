"""Real-Redis helpers for scheduled performance suites."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from redis.asyncio import Redis

from reflex.istate.manager.redis import StateManagerRedis

REDIS_URL_ENV = "REFLEX_PERF_REDIS_URL"


def performance_redis_url() -> str:
    """Return the isolated Redis database used by performance tests.

    Returns:
        Redis connection URL naming an explicit database index.

    Raises:
        ValueError: If the configured URL has no explicit database index, which
            would silently resolve to the shared default database 0.
    """
    url = os.environ.get(REDIS_URL_ENV, "redis://127.0.0.1:6379/15")
    parsed = urlparse(url)
    if not parsed.path.strip("/").isdigit() and "db=" not in parsed.query:
        msg = (
            f"{REDIS_URL_ENV}={url!r} must name an explicit database index "
            "(e.g. redis://host:6379/15); performance tests flush their "
            "database and must never target the shared default database."
        )
        raise ValueError(msg)
    return url


@asynccontextmanager
async def real_redis_state_manager() -> AsyncIterator[StateManagerRedis]:
    """Create an isolated state manager backed by a reachable Redis server.

    The configured database must be empty and dedicated to performance tests;
    it is flushed on exit.

    Yields:
        A state manager whose database is empty at entry and exit.

    Raises:
        ConnectionError: If the configured Redis server is unreachable.
        RuntimeError: If the configured database already contains keys.
    """
    url = performance_redis_url()
    redis = Redis.from_url(url)
    try:
        await redis.ping()  # pyright: ignore [reportGeneralTypeIssues]
        if await redis.dbsize():
            msg = (
                f"Redis database at {url!r} is not empty; performance tests "
                "flush it on exit, so point "
                f"{REDIS_URL_ENV} at an empty, dedicated database."
            )
            raise RuntimeError(msg)
        manager = StateManagerRedis(redis=redis)
        try:
            yield manager
        finally:
            # Close the manager before flushing: with oplock enabled, close()
            # cancels lease-breaker tasks that re-persist cached states, so
            # flushing first would leave those write-backs behind and the next
            # run's empty-database guard would fail. close() also disposes the
            # shared connection pool, so flush through a fresh client.
            try:
                await manager.close()
            finally:
                cleanup = Redis.from_url(url)
                try:
                    await cleanup.flushdb()
                finally:
                    await cleanup.aclose()
    finally:
        await redis.aclose()
