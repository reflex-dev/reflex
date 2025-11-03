"""Mock implementation of redis for unit testing."""

import asyncio
import contextlib
import fnmatch
import time
from collections.abc import AsyncGenerator, Callable
from typing import Any
from unittest.mock import AsyncMock, Mock

from redis.asyncio import Redis
from redis.typing import EncodableT, KeyT

from reflex.utils import prerequisites

WRONGTYPE_MESSAGE = "WRONGTYPE Operation against a key holding the wrong kind of value"


def mock_redis() -> Redis:
    """Mock the redis client with pubsub support.

    Returns:
        The mocked redis client.
    """
    keys: dict[bytes, EncodableT | set[EncodableT]] = {}
    expire_times: dict[bytes, float] = {}
    event_log: list[dict[str, bytes]] = []
    event_log_new_events = asyncio.Event()

    def _key_bytes(key: KeyT) -> bytes:
        if isinstance(key, str):
            return key.encode()
        if isinstance(key, memoryview):
            return key.tobytes()
        return key

    def _keyspace_event(key: KeyT, data: str | bytes):
        if isinstance(key, str):
            key = key.encode()
        if isinstance(data, str):
            data = data.encode()
        event_log.append({"channel": b"__keyspace@1__:" + key, "data": data})
        event_log_new_events.set()

    def _expire_keys():
        to_delete = []
        for key, expire_time in expire_times.items():
            if expire_time <= time.monotonic():
                to_delete.append(key)
        for key in to_delete:
            del keys[key]
            del expire_times[key]
            _keyspace_event(key, "expired")

    async def mock_get(key: KeyT):  # noqa: RUF029
        _expire_keys()
        return keys.get(_key_bytes(key))

    async def mock_set(  # noqa: RUF029
        key: KeyT,
        value: EncodableT,
        ex: int | None = None,
        px: int | None = None,
        nx: bool = False,
    ) -> bool:
        _expire_keys()
        key = _key_bytes(key)
        if nx and key in keys:
            return False
        keys[key] = value
        _keyspace_event(key, "set")
        if ex is not None:
            expire_times[key] = time.monotonic() + ex
            _keyspace_event(key, "expire")
        elif px is not None:
            expire_times[key] = time.monotonic() + (px / 1000)
            _keyspace_event(key, "expire")
        return True

    async def mock_sadd(key: KeyT, value: EncodableT) -> int:  # noqa: RUF029
        _expire_keys()
        key = _key_bytes(key)
        keyset = keys.setdefault(key, set())
        if not isinstance(keyset, set):
            raise TypeError(WRONGTYPE_MESSAGE)
        before = len(keyset)
        keyset.add(value)
        _keyspace_event(key, "sadd")
        return len(keyset) - before

    async def mock_srem(key: KeyT, value: EncodableT) -> int:
        _expire_keys()
        keyset = keys.get(_key_bytes(key))
        if keyset is None:
            return 0
        if not isinstance(keyset, set):
            raise TypeError(WRONGTYPE_MESSAGE)
        if value in keyset:
            keyset.remove(value)
            _keyspace_event(key, "srem")
            if not keyset:
                await redis_mock.delete(key)
            return 1
        return 0

    async def mock_scard(key: KeyT) -> int:  # noqa: RUF029
        _expire_keys()
        keyset = keys.get(_key_bytes(key))
        if keyset is None:
            return 0
        if not isinstance(keyset, set):
            raise TypeError(WRONGTYPE_MESSAGE)
        return len(keyset)

    async def mock_delete(key: KeyT) -> int:  # noqa: RUF029
        _expire_keys()
        key = _key_bytes(key)
        Unset = object()
        expire_times.pop(key, None)
        if keys.pop(key, Unset) is not Unset:
            _keyspace_event(key, "del")
            return 1
        return 0

    async def mock_getdel(key: KeyT) -> Any:
        value = await redis_mock.get(key)
        await redis_mock.delete(key)
        return value

    async def mock_pexpire(key: KeyT, px: int, xx: bool = False) -> bool:  # noqa: RUF029
        _expire_keys()
        key = _key_bytes(key)
        if key in keys:
            if not xx or key in expire_times:
                expire_times[key] = time.monotonic() + (px / 1000)
                _keyspace_event(key, "expire")
            return True
        return False

    def pipeline():
        pipeline_mock = Mock()
        results = []

        def get_pipeline(key: KeyT):
            results.append(redis_mock.get(key=key))

        def set_pipeline(
            key: KeyT,
            value: EncodableT,
            ex: int | None = None,
            px: int | None = None,
            nx: bool = False,
        ):
            results.append(redis_mock.set(key=key, value=value, ex=ex, px=px, nx=nx))

        def sadd_pipeline(key: KeyT, value: EncodableT):
            results.append(redis_mock.sadd(key=key, value=value))

        def pexpire_pipeline(key: KeyT, px: int, xx: bool = False):
            results.append(redis_mock.pexpire(key=key, px=px, xx=xx))

        async def execute():
            _expire_keys()
            return await asyncio.gather(*results)

        pipeline_mock.get = get_pipeline
        pipeline_mock.set = set_pipeline
        pipeline_mock.sadd = sadd_pipeline
        pipeline_mock.pexpire = pexpire_pipeline
        pipeline_mock.execute = execute

        return pipeline_mock

    async def pttl(key: KeyT) -> int:  # noqa: RUF029
        _expire_keys()
        return (
            int(expire_times.get(_key_bytes(key), time.monotonic()) - time.monotonic())
            * 1000
        )

    @contextlib.asynccontextmanager
    async def pubsub():  # noqa: RUF029
        watch_patterns = {}
        event_log_pointer = 0

        async def psubscribe(  # noqa: RUF029
            *patterns: str,
            **handlers: Callable[[dict[str, bytes]], None],
        ):
            nonlocal event_log_pointer, watch_patterns
            event_log_pointer = len(event_log) - 1

            for pattern in patterns:
                watch_patterns[pattern] = None
                event_log.append({"channel": b"psubscribe", "data": pattern.encode()})
                event_log_new_events.set()
            for pattern, handler in handlers.items():
                watch_patterns[pattern] = handler
                event_log.append({"channel": b"psubscribe", "data": pattern.encode()})
                event_log_new_events.set()

        async def listen() -> AsyncGenerator[dict[str, Any] | None, None]:
            nonlocal event_log_pointer
            while True:
                if event_log_pointer >= len(event_log):
                    await event_log_new_events.wait()
                    event_log_new_events.clear()
                    continue
                event = event_log[event_log_pointer]
                channel_str = event["channel"].decode()
                event_log_pointer += 1
                for pattern, handler in watch_patterns.items():
                    if fnmatch.fnmatch(channel_str, pattern):
                        if handler is not None:
                            res = handler(event)
                            if asyncio.iscoroutine(res):
                                res = await res
                            # Yields None to indicate handled
                            yield None
                        else:
                            yield event

        pubsub_mock = AsyncMock()
        pubsub_mock.psubscribe = psubscribe
        pubsub_mock.listen = listen
        yield pubsub_mock

    redis_mock = AsyncMock(spec=Redis)
    redis_mock.get = mock_get
    redis_mock.set = mock_set
    redis_mock.delete = mock_delete
    redis_mock.getdel = mock_getdel
    redis_mock.sadd = mock_sadd
    redis_mock.srem = mock_srem
    redis_mock.scard = mock_scard
    redis_mock.pexpire = mock_pexpire
    redis_mock.pipeline = pipeline
    redis_mock.pttl = pttl
    redis_mock.pubsub = pubsub
    redis_mock.config_set = AsyncMock()
    redis_mock.get_connection_kwargs = Mock(return_value={"db": 1})
    redis_mock._internals = {
        "keys": keys,
        "expire_times": expire_times,
        "event_log": event_log,
    }
    return redis_mock


@contextlib.asynccontextmanager
async def real_redis() -> AsyncGenerator[Redis | None]:
    """Get a real redis client for testing.

    Yields:
        The redis client.
    """
    redis = prerequisites.get_redis()
    if redis is None:
        yield None
        return

    # Create a pubsub to keep the internal event log for assertions.
    event_log = []
    object.__setattr__(
        redis,
        "_internals",
        {
            "event_log": event_log,
        },
    )
    redis_db = redis.get_connection_kwargs().get("db", 0)

    async def log_events():
        async with redis.pubsub() as pubsub:
            await pubsub.psubscribe(f"__keyspace@{redis_db}__:*")
            async for message in pubsub.listen():
                if message is None:
                    continue
                event_log.append(message)

    log_events_task = asyncio.create_task(log_events())
    try:
        yield redis
    finally:
        log_events_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await log_events_task
