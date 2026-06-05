"""Tests for Redis key helpers."""

from reflex.utils.redis_keys import format_redis_key, logical_redis_key


def test_format_redis_key_without_cluster():
    """Test Redis keys are unchanged when Redis Cluster support is disabled."""
    assert (
        format_redis_key("token_state", cluster=False, slot_key="token")
        == "token_state"
    )


def test_format_redis_key_with_cluster():
    """Test Redis Cluster keys preserve the logical key after the hash tag."""
    redis_key = format_redis_key("token_state", cluster=True, slot_key="token")

    hash_tag, logical_key = redis_key.split("}:", 1)
    assert hash_tag.startswith("{")
    assert logical_key == "token_state"
    assert logical_redis_key(redis_key) == "token_state"


def test_same_slot_key_uses_same_hash_tag():
    """Test related keys share a Redis Cluster hash tag."""
    first = format_redis_key("token_state", cluster=True, slot_key="token")
    second = format_redis_key("token_lock", cluster=True, slot_key="token")

    assert first.split("}:", 1)[0] == second.split("}:", 1)[0]
