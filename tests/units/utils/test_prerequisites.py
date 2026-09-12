"""Tests for reflex.utils.prerequisites."""

import pytest

from reflex.utils import prerequisites


def test_get_redis_pins_driver_version(monkeypatch):
    """Creating a redis connection must not look the library version up.

    redis-py resolves its version through importlib.metadata for every new
    connection unless it is passed in, which scans sys.path on the event loop.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    redis = pytest.importorskip("redis")
    monkeypatch.setattr(prerequisites, "parse_redis_url", lambda: "redis://localhost")

    def _lookup():
        pytest.fail("redis-py resolved its version while creating a connection")

    monkeypatch.setattr("redis.utils.get_lib_version", _lookup)

    client = prerequisites.get_redis()
    assert client is not None
    connection = client.connection_pool.make_connection()
    driver_info = getattr(connection, "driver_info", None)
    lib_version = (
        driver_info.lib_version if driver_info is not None else connection.lib_version  # pyright: ignore[reportAttributeAccessIssue]
    )
    assert lib_version == redis.__version__
