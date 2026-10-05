"""Exercise subscription readiness and contention using real Redis database 5."""

import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

from redis.asyncio import Redis
from redis.asyncio.client import PubSub
from redis_probe.redis_probe import RedisState
from reflex.istate.manager.redis import StateManagerRedis
from reflex.istate.manager.token import BaseStateToken

OUT = Path(sys.argv[1])
RESULTS = {"database": 5, "scenarios": []}


class GatedPubSub(PubSub):
    """Delay delivery of Redis's real subscription acknowledgement."""

    async def listen(self):
        """Gate only the first acknowledgement after actual network receipt.

        Yields:
            The real Redis subscription and keyspace messages.
        """
        async for message in super().listen():
            if message["type"] == "psubscribe" and not self.seen.is_set():
                self.seen.set()
                await self.allow.wait()
            yield message


class GatedRedis(Redis):
    """Return a real network PubSub whose confirmation delivery can be delayed."""

    def pubsub(self, **kwargs) -> PubSub:
        """Attach the delivery gate to the real connection pool's PubSub.

        Args:
            **kwargs: Redis PubSub constructor options.

        Returns:
            The gated network subscriber.
        """
        subscriber = GatedPubSub(self.connection_pool, **kwargs)
        subscriber.seen = self.seen
        subscriber.allow = self.allow
        return subscriber


async def increment(manager: StateManagerRedis, token: BaseStateToken) -> int:
    """Increment the published app state under its real distributed lock.

    Args:
        manager: The participating process's state manager.
        token: The unique targeted state session.

    Returns:
        The resulting counter.
    """
    async with manager.modify_state(token) as root:
        state = root.get_substate(RedisState.get_full_name().split("."))
        state.count += 1
        state._audit.append(state.count)
        return state.count


async def main() -> None:
    """Assert readiness fallback and low-latency contention without stubs."""
    client = GatedRedis(host="localhost", port=9141, db=5)
    client.seen = asyncio.Event()
    client.allow = asyncio.Event()
    other_client = Redis(host="localhost", port=9141, db=5)
    manager = StateManagerRedis(
        redis=client,
        lock_expiration=10000,
        lock_warning_threshold=1000,
        oplock_hold_time_ms=5000,
    )
    other = StateManagerRedis(
        redis=other_client,
        lock_expiration=10000,
        lock_warning_threshold=1000,
        oplock_hold_time_ms=5000,
    )
    token = BaseStateToken(ident="alpha-oplock-" + str(uuid.uuid4()), cls=RedisState)
    RESULTS["token"] = token.ident
    try:
        assert manager._oplock_enabled
        await asyncio.wait_for(client.seen.wait(), timeout=3)
        assert not manager._lock_updates_subscribed.is_set()
        start = time.monotonic()
        count = await asyncio.wait_for(increment(manager, token), timeout=1)
        elapsed = time.monotonic() - start
        assert count == 1
        assert elapsed < 0.5, elapsed
        assert not manager._lock_updates_subscribed.is_set()
        assert token.lock_key not in manager._local_leases
        assert await client.get(manager._lock_key(token)) is None
        assert await client.exists(str(token)) == 1
        RESULTS["scenarios"].append({
            "name": "Real subscription confirmation withheld: single update immediately persists and releases",
            "count": count,
            "elapsed_seconds": round(elapsed, 4),
            "subscriber_ready": False,
            "leases": 0,
            "redis_lock_remaining": False,
        })
        client.allow.set()
        await asyncio.wait_for(manager._lock_updates_subscribed.wait(), timeout=2)
        await asyncio.wait_for(other._lock_updates_subscribed.wait(), timeout=2)
        count = await increment(manager, token)
        assert count == 2
        assert token.lock_key in manager._local_leases
        assert await client.get(manager._lock_key(token)) is not None
        RESULTS["scenarios"].append({
            "name": "Actual acknowledgement permits opportunistic lease",
            "count": count,
            "subscriber_ready": True,
            "leases": 1,
        })
        start = time.monotonic()
        count = await asyncio.wait_for(increment(other, token), timeout=1)
        elapsed = time.monotonic() - start
        assert count == 3
        assert elapsed < 0.5, elapsed
        RESULTS["scenarios"].append({
            "name": "Second manager's real keyspace contention cancels first manager's 5-second lease",
            "count": count,
            "elapsed_seconds": round(elapsed, 4),
        })
        start = time.monotonic()
        counts = await asyncio.wait_for(
            asyncio.gather(
                *(
                    increment(manager if index % 2 else other, token)
                    for index in range(30)
                )
            ),
            timeout=3,
        )
        elapsed = time.monotonic() - start
        assert sorted(counts) == list(range(4, 34)), counts
        await manager.close()
        await other.close()
        inspector = Redis(host="localhost", port=9141, db=5)
        try:
            persisted = await inspector.get(str(token))
            restored = BaseStateToken.deserialize(persisted)
            assert restored.count == 33
            assert restored._audit == list(range(1, 34))
            assert await inspector.get(manager._lock_key(token)) is None
            keys = [key async for key in inspector.scan_iter(match=token.ident + "*")]
            RESULTS["scenarios"].append({
                "name": "30 contending operations preserve every increment and backend mutation",
                "returned_counts": sorted(counts),
                "persisted_count": restored.count,
                "persisted_audit": restored._audit,
                "elapsed_seconds": round(elapsed, 4),
                "remaining_lock": False,
                "cleaned_keys": [key.decode() for key in keys],
            })
            if keys:
                await inspector.delete(*keys)
        finally:
            await inspector.aclose()
        RESULTS["status"] = "passed"
    finally:
        client.allow.set()
        await manager.close()
        await other.close()
        await asyncio.to_thread(OUT.write_text, json.dumps(RESULTS, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
