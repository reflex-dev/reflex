"""Unit tests for the mock redis client."""

import asyncio

from tests.units.mock_redis import mock_redis


async def test_pubsub_listen_yields_pmessage_for_pattern_without_handler():
    """A pattern subscribed without a handler yields a redis-py shaped pmessage."""
    redis = mock_redis()
    async with redis.pubsub() as pubsub:
        await pubsub.psubscribe("__keyspace@1__:foo*")
        messages = pubsub.listen()
        confirmation = await anext(messages)
        assert confirmation["type"] == "psubscribe"

        await redis.set("foo1", b"bar")
        message = await asyncio.wait_for(anext(messages), timeout=1)

    assert message == {
        "type": "pmessage",
        "pattern": b"__keyspace@1__:foo*",
        "channel": b"__keyspace@1__:foo1",
        "data": b"set",
    }
    # The internal event log keeps its raw entries.
    assert redis._internals["event_log"][-1] == {  # pyright: ignore[reportAttributeAccessIssue]
        "channel": b"__keyspace@1__:foo1",
        "data": b"set",
    }


async def test_publish_reaches_pattern_subscribers():
    """A published message is delivered to a pubsub whose pattern matches the channel."""
    redis = mock_redis()
    async with redis.pubsub() as pubsub:
        await pubsub.psubscribe("channel:foo*")
        messages = pubsub.listen()
        confirmation = await anext(messages)
        assert confirmation["type"] == "psubscribe"

        await redis.publish("channel:bar", b"skipped")
        await redis.publish("channel:foo1", b"payload")
        message = await asyncio.wait_for(anext(messages), timeout=1)

    assert message == {
        "type": "pmessage",
        "pattern": b"channel:foo*",
        "channel": b"channel:foo1",
        "data": b"payload",
    }
