"""Benchmarks for pickling and unpickling states."""

import logging
import pickle
import time
import uuid
from typing import Tuple

import pytest
from pytest_benchmark.fixture import BenchmarkFixture
from redis import Redis

from reflex.state import State
from reflex.utils.prerequisites import get_redis_sync

log = logging.getLogger(__name__)


SLOW_REDIS_MAP: dict[bytes, bytes] = {}


class SlowRedis:
    """Simulate a slow Redis client which uses a global dict and sleeps based on size."""

    def __init__(self):
        """Initialize the slow Redis client."""
        pass

    def set(self, key: bytes, value: bytes) -> None:
        """Set a key-value pair in the slow Redis client.

        Args:
            key: The key.
            value: The value.
        """
        SLOW_REDIS_MAP[key] = value
        size = len(value)
        sleep_time = (size / 1e6) + 0.05
        time.sleep(sleep_time)

    def get(self, key: bytes) -> bytes:
        """Get a value from the slow Redis client.

        Args:
            key: The key.

        Returns:
            The value.
        """
        value = SLOW_REDIS_MAP[key]
        size = len(value)
        sleep_time = (size / 1e6) + 0.05
        time.sleep(sleep_time)
        return value


@pytest.mark.parametrize(
    "protocol",
    argvalues=[
        pickle.DEFAULT_PROTOCOL,
        pickle.HIGHEST_PROTOCOL,
    ],
    ids=[
        "pickle_default",
        "pickle_highest",
    ],
)
@pytest.mark.parametrize(
    "redis",
    [
        Redis,
        SlowRedis,
        None,
    ],
    ids=[
        "redis",
        "slow_redis",
        "no_redis",
    ],
)
@pytest.mark.parametrize(
    "should_compress", [True, False], ids=["compress", "no_compress"]
)
@pytest.mark.benchmark(disable_gc=True)
def test_pickle(
    request: pytest.FixtureRequest,
    benchmark: BenchmarkFixture,
    big_state: State,
    big_state_size: Tuple[int, str],
    protocol: int,
    redis: Redis | SlowRedis | None,
    should_compress: bool,
) -> None:
    """Benchmark pickling a big state.

    Args:
        request: The pytest fixture request object.
        benchmark: The benchmark fixture.
        big_state: The big state fixture.
        big_state_size: The big state size fixture.
        protocol: The pickle protocol.
        redis: Whether to use Redis.
        should_compress: Whether to compress the pickled state.
    """
    if should_compress:
        try:
            from blosc2 import compress, decompress
        except ImportError:
            pytest.skip("Blosc is not available.")

        def dump(obj: State) -> bytes:
            return compress(pickle.dumps(obj, protocol=protocol))  # pyright: ignore[reportReturnType]

        def load(data: bytes) -> State:
            return pickle.loads(decompress(data))  # pyright: ignore[reportAny,reportArgumentType]

    else:

        def dump(obj: State) -> bytes:
            return pickle.dumps(obj, protocol=protocol)

        def load(data: bytes) -> State:
            return pickle.loads(data)

    if redis:
        if redis == Redis:
            redis_client = get_redis_sync()
            if redis_client is None:
                pytest.skip("Redis is not available.")
        else:
            redis_client = SlowRedis()

        key = str(uuid.uuid4()).encode()

        def run(obj: State) -> None:
            _ = redis_client.set(key, dump(obj))
            _ = load(redis_client.get(key))  # pyright: ignore[reportArgumentType]

    else:

        def run(obj: State) -> None:
            _ = load(dump(obj))

    # calculate size before benchmark to not affect it
    out = dump(big_state)
    size = len(out)
    log.warning(f"{protocol=}, {redis=}, {should_compress=}, {size=}")

    benchmark.extra_info["size"] = size
    benchmark.extra_info["redis"] = redis
    benchmark.extra_info["pickle_protocol"] = protocol
    redis_group = redis.__name__ if redis else "no_redis"  # pyright: ignore[reportUnknownMemberType,reportAttributeAccessIssue,reportUnknownVariableType]
    benchmark.group = f"{redis_group}_{big_state_size[1]}"

    _ = benchmark(run, big_state)
