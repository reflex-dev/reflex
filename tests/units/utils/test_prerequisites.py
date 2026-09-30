"""Tests for reflex.utils.prerequisites."""

import pytest

from reflex.utils import prerequisites


@pytest.mark.parametrize(
    "max_connections", [None, "3"], ids=["default_pool", "capped_pool"]
)
def test_get_redis_pins_driver_version(monkeypatch, max_connections: str | None):
    """Creating a redis connection must not look the library version up.

    redis-py resolves its version through importlib.metadata for every new
    connection unless it is passed in, which scans sys.path on the event loop.
    The blocking pool used when REFLEX_REDIS_MAX_CONNECTIONS is set must pin it
    too.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        max_connections: The REFLEX_REDIS_MAX_CONNECTIONS value, None for no cap.
    """
    redis = pytest.importorskip("redis")
    from redis.asyncio import BlockingConnectionPool

    monkeypatch.setattr(prerequisites, "parse_redis_url", lambda: "redis://localhost")
    monkeypatch.delenv("REFLEX_REDIS_POOL_TIMEOUT", raising=False)
    if max_connections is None:
        monkeypatch.delenv("REFLEX_REDIS_MAX_CONNECTIONS", raising=False)
    else:
        monkeypatch.setenv("REFLEX_REDIS_MAX_CONNECTIONS", max_connections)

    def _lookup():
        pytest.fail("redis-py resolved its version while creating a connection")

    monkeypatch.setattr("redis.utils.get_lib_version", _lookup)

    client = prerequisites.get_redis()
    assert client is not None
    assert isinstance(client.connection_pool, BlockingConnectionPool) == (
        max_connections is not None
    )
    connection = client.connection_pool.make_connection()
    driver_info = getattr(connection, "driver_info", None)
    lib_version = (
        driver_info.lib_version if driver_info is not None else connection.lib_version  # pyright: ignore[reportAttributeAccessIssue]
    )
    assert lib_version == redis.__version__
