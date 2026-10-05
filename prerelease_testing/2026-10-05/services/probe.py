"""Exercise duration configuration and bounded pools against real local Redis."""

import argparse
import asyncio
import importlib.metadata
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import reflex
from redis.exceptions import ConnectionError as RedisConnectionError
from reflex.utils.prerequisites import get_redis
from reflex_base import environment as env_module


@contextmanager
def settings(values: dict[str, str]):
    """Temporarily set framework configuration values.

    Args:
        values: Environment values for one scenario.

    Yields:
        The configured scenario.
    """
    previous = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def durations() -> list[dict]:
    """Read new duration settings and their legacy compatibility path.

    Returns:
        Parsed values and assertions.
    """
    results = []
    for name, value, expected in (
        ("SQLALCHEMY_POOL_TIMEOUT", "2m", 120),
        ("REFLEX_SOCKET_INTERVAL", "250ms", 0.25),
        ("REFLEX_SOCKET_TIMEOUT", "3", 3),
        ("REFLEX_BACKEND_COLD_START_TIMEOUT", "1.5m", 90),
    ):
        with settings({name: value}):
            actual = getattr(env_module.environment, name).get().total_seconds()
            assert actual == expected, (name, actual)
            results.append({"name": name, "input": value, "seconds": actual})
    for function, legacy, value, expected in (
        (
            env_module.auto_reload_cooldown,
            "REFLEX_AUTO_RELOAD_COOLDOWN_TIME_MS",
            "350",
            0.35,
        ),
        (env_module.oplock_hold_time, "REFLEX_OPLOCK_HOLD_TIME_MS", "550", 0.55),
        (
            env_module.state_manager_disk_debounce,
            "REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS",
            "2.5",
            2.5,
        ),
    ):
        with settings({legacy: value}):
            actual = function().total_seconds()
            assert actual == expected, (legacy, actual)
            results.append({"name": legacy, "input": value, "seconds": actual})
    with settings(
        {
            "REFLEX_AUTO_RELOAD_COOLDOWN_TIME_MS": "350",
            "REFLEX_AUTO_RELOAD_COOLDOWN": "750ms",
        }
    ):
        assert env_module.auto_reload_cooldown().total_seconds() == 0.75
        results.append({"legacy_and_new": True, "seconds": 0.75})
    return results


async def redis_pool() -> dict:
    """Check bounded concurrency, waiting, timeout and configuration validation.

    Returns:
        Pool behavior evidence.
    """
    with settings(
        {"REFLEX_REDIS_MAX_CONNECTIONS": "3", "REFLEX_REDIS_POOL_TIMEOUT": "200ms"}
    ):
        client = get_redis()
        assert client is not None
        pool = client.connection_pool
        assert pool.max_connections == 3 and pool.timeout == 0.2
        assert all(await asyncio.gather(*(client.ping() for _ in range(100))))
        connections = [await pool.get_connection() for _ in range(3)]
        try:
            pending = asyncio.create_task(client.ping())
            await asyncio.sleep(0.05)
            assert not pending.done(), "Saturated pool should wait"
            await pool.release(connections.pop())
            assert await pending
            connections.append(await pool.get_connection())
            started = time.monotonic()
            try:
                await client.ping()
                raise AssertionError("Full pool must time out")
            except RedisConnectionError as error:
                timeout_error = str(error)
            waited = time.monotonic() - started
            assert 0.15 <= waited < 1, waited
        finally:
            for connection in connections:
                await pool.release(connection)
            await client.aclose()
    errors = []
    for values in (
        {"REFLEX_REDIS_MAX_CONNECTIONS": "2"},
        {"REFLEX_REDIS_MAX_CONNECTIONS": "3", "REFLEX_REDIS_POOL_TIMEOUT": "0"},
        {"REFLEX_REDIS_MAX_CONNECTIONS": "3", "REFLEX_REDIS_POOL_TIMEOUT": "10s"},
    ):
        with settings(values):
            try:
                get_redis()
            except env_module.EnvironmentVarValueError as error:
                errors.append({"settings": values, "error": str(error)})
            else:
                raise AssertionError(values)
    return {
        "ping_operations": 100,
        "max_connections": 3,
        "waiter_recovered": True,
        "timeout_seconds": waited,
        "timeout_error": timeout_error,
        "invalid_configuration": errors,
    }


def main() -> None:
    """Run infrastructure probes from a neutral app directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert Path(reflex.__file__).is_relative_to(Path(sys.prefix)), reflex.__file__
    result = {
        "python": sys.executable,
        "reflex": reflex.__file__,
        "version": importlib.metadata.version("reflex"),
        "durations": durations(),
        "redis": asyncio.run(redis_pool()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
