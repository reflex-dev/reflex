"""Unit tests for the ISR (Incremental Static Regeneration) core."""

from __future__ import annotations

import asyncio
import time
import uuid
from types import SimpleNamespace

import pytest

from reflex import isr
from reflex.isr import (
    CachedPage,
    ISRManager,
    MemoryISRCache,
    RedisISRCache,
    RenderResult,
    cache_key,
)
from reflex.utils import prerequisites


class FakeRenderer:
    """A controllable renderer that counts calls and can block on demand."""

    def __init__(
        self,
        html: str = "<html>rendered</html>",
        *,
        revalidate: float | None = None,
        tags: tuple[str, ...] = (),
        gate: asyncio.Event | None = None,
        fail: bool = False,
    ) -> None:
        """Configure the fake renderer."""
        self.html = html
        self.revalidate = revalidate
        self.tags = tags
        self.gate = gate
        self.fail = fail
        self.calls = 0
        self.started = asyncio.Event()

    async def __call__(self, path: str) -> RenderResult | None:
        """Render the path, optionally blocking on the gate or failing.

        Args:
            path: The path being rendered.

        Returns:
            A render result, or None when configured to fail.
        """
        self.calls += 1
        self.started.set()
        if self.gate is not None:
            await self.gate.wait()
        if self.fail:
            return None
        return RenderResult(
            html=f"{self.html}:{path}:{self.calls}",
            revalidate=self.revalidate,
            tags=self.tags,
        )


async def _drain_background(manager: ISRManager) -> None:
    """Wait for any background revalidation tasks to finish.

    Args:
        manager: The manager whose background tasks to await.
    """
    if manager._background:
        await asyncio.gather(*list(manager._background))


def _manager(renderer, **kwargs) -> ISRManager:
    """Build a manager on a fresh in-memory cache.

    Args:
        renderer: The renderer to use.
        **kwargs: Overrides for the manager options.

    Returns:
        The ISR manager.
    """
    kwargs.setdefault("build_id", "b1")
    kwargs.setdefault("default_revalidate", 60.0)
    return ISRManager(MemoryISRCache(), renderer, **kwargs)


def test_cached_page_staleness():
    """A page is stale once past its revalidate window; 0 means never."""
    now = time.time()
    fresh = CachedPage(html="x", generated_at=now, revalidate=60)
    assert not fresh.is_stale(now + 30)
    assert fresh.is_stale(now + 61)
    never = CachedPage(html="x", generated_at=now, revalidate=0)
    assert not never.is_stale(now + 10_000)


def test_cached_page_roundtrip():
    """CachedPage survives JSON serialization."""
    page = CachedPage(html="<p>", generated_at=1.0, revalidate=30, tags=("a", "b"))
    assert CachedPage.from_json(page.to_json()) == page


@pytest.mark.asyncio
async def test_miss_renders_once_and_caches():
    """A cache miss renders and caches; a second request serves from cache."""
    renderer = FakeRenderer()
    mgr = _manager(renderer)

    html1 = await mgr.get_html("/page")
    html2 = await mgr.get_html("/page")

    assert html1 == html2
    assert renderer.calls == 1  # second request hit the cache


@pytest.mark.asyncio
async def test_stale_serves_stale_then_revalidates():
    """A stale entry is served immediately and refreshed in the background."""
    renderer = FakeRenderer()
    mgr = _manager(renderer, default_revalidate=0.05)

    first = await mgr.get_html("/p")
    assert renderer.calls == 1

    # Let it go stale.
    await asyncio.sleep(0.06)

    stale = await mgr.get_html("/p")
    assert stale == first  # served the stale copy immediately (no new render yet)

    await _drain_background(mgr)
    assert renderer.calls == 2  # background revalidation happened exactly once

    # The refreshed value is now cached.
    fresh = await mgr.get_html("/p")
    assert fresh != first
    assert renderer.calls == 2


@pytest.mark.asyncio
async def test_single_flight_on_concurrent_miss():
    """Concurrent misses for one path trigger exactly one render."""
    gate = asyncio.Event()
    renderer = FakeRenderer(gate=gate)
    mgr = _manager(renderer, wait_timeout=5.0)

    tasks = [asyncio.create_task(mgr.get_html("/hot")) for _ in range(10)]
    await asyncio.sleep(0.1)  # let them all reach the lock / poll loop
    gate.set()  # release the single render
    results = await asyncio.gather(*tasks)

    assert renderer.calls == 1  # only one worker rendered
    assert len(set(results)) == 1  # everyone got the same HTML
    assert results[0] is not None


@pytest.mark.asyncio
async def test_revalidate_path_forces_rerender():
    """Invalidating a path drops the cache so the next request re-renders."""
    renderer = FakeRenderer()
    mgr = _manager(renderer)

    await mgr.get_html("/p")
    assert renderer.calls == 1

    await mgr.revalidate_path("/p")
    await mgr.get_html("/p")
    assert renderer.calls == 2


@pytest.mark.asyncio
async def test_revalidate_tag_invalidates_all_matching():
    """Invalidating a tag drops every page carrying it."""
    renderer = FakeRenderer(tags=("blog",))
    mgr = _manager(renderer)

    await mgr.get_html("/blog/a")
    await mgr.get_html("/blog/b")
    assert renderer.calls == 2

    count = await mgr.revalidate_tag("blog")
    assert count == 2

    await mgr.get_html("/blog/a")
    await mgr.get_html("/blog/b")
    assert renderer.calls == 4  # both re-rendered after invalidation


@pytest.mark.asyncio
async def test_build_id_scopes_cache():
    """A different build id yields a different key, forcing a re-render."""
    renderer = FakeRenderer()
    cache = MemoryISRCache()

    mgr_old = ISRManager(cache, renderer, build_id="old")
    mgr_new = ISRManager(cache, renderer, build_id="new")

    await mgr_old.get_html("/p")
    await mgr_new.get_html("/p")

    assert renderer.calls == 2
    assert cache_key("old", "/p") != cache_key("new", "/p")


@pytest.mark.asyncio
async def test_render_failure_is_not_cached():
    """When the renderer returns None, nothing is cached and None is returned."""
    renderer = FakeRenderer(fail=True)
    mgr = _manager(renderer)

    result = await mgr.get_html("/p")
    assert result is None
    # A subsequent request retries (nothing was cached).
    await mgr.get_html("/p")
    assert renderer.calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("invalidate", ["path", "tag"])
async def test_render_overtaken_by_invalidation_is_not_cached(invalidate: str):
    """A render in flight during an invalidation is served but not cached.

    It may hold the content the invalidation was meant to drop.

    Args:
        invalidate: Whether the page is invalidated by path or by tag.
    """
    gate = asyncio.Event()
    renderer = FakeRenderer(tags=("blog",), gate=gate)
    mgr = _manager(renderer)

    render = asyncio.create_task(mgr.get_html("/p"))
    await renderer.started.wait()
    if invalidate == "path":
        await mgr.revalidate_path("/p")
    else:
        await mgr.revalidate_tag("blog")
    gate.set()

    assert await render == "<html>rendered</html>:/p:1"
    assert await mgr.get_html("/p") == "<html>rendered</html>:/p:2"
    assert await mgr.get_html("/p") == "<html>rendered</html>:/p:2"


@pytest.mark.asyncio
async def test_redis_set_rejects_render_overtaken_by_invalidation():
    """A page rendered before an invalidation is not stored, a later one is."""
    redis = prerequisites.get_redis()
    if redis is None:
        pytest.skip("Test requires redis")
    cache = RedisISRCache(redis)
    key = f"test:{uuid.uuid4().hex}"
    page = CachedPage(html="<p>", generated_at=1.0, revalidate=60)
    try:
        before = await cache.epoch()
        await cache.delete(key)
        assert await cache.set(key, page, before) is False
        assert await cache.get(key) is None

        assert await cache.set(key, page, await cache.epoch()) is True
        assert await cache.get(key) == page
    finally:
        await redis.delete(RedisISRCache._PAGE_PREFIX + key)
        await redis.aclose()


@pytest.mark.asyncio
async def test_redis_tag_index_expires_with_its_last_page(
    monkeypatch: pytest.MonkeyPatch,
):
    """A tag's index drops expired pages and expires with the last one it holds."""
    redis = prerequisites.get_redis()
    if redis is None:
        pytest.skip("Test requires redis")
    cache = RedisISRCache(redis)
    tag = f"test-{uuid.uuid4().hex}"
    tag_key = RedisISRCache._TAG_PREFIX + tag
    keys = [f"test:{uuid.uuid4().hex}:{name}" for name in ("a", "b", "c")]
    # Pages keep their stale copy for a day past the revalidate window.
    grace = 86400
    now = float(int(time.time()))

    async def store(key: str, revalidate: float) -> None:
        """Store a page carrying the tag.

        Args:
            key: The cache key.
            revalidate: The page's revalidate window.
        """
        page = CachedPage(
            html=key, generated_at=now, revalidate=revalidate, tags=(tag,)
        )
        assert await cache.set(key, page, await cache.epoch()) is True

    async def members():
        """Read the tag's index.

        Returns:
            The indexed cache keys with their expiry, soonest first.
        """
        return await redis.zrange(tag_key, 0, -1, withscores=True)

    try:
        monkeypatch.setattr(isr, "time", SimpleNamespace(time=lambda: now))
        await store(keys[0], 60)
        assert await members() == [(keys[0].encode(), now + 60 + grace)]
        assert await redis.expiretime(tag_key) == now + 60 + grace

        # A page that never goes stale keeps the index for good.
        await store(keys[1], 0)
        assert await members() == [
            (keys[0].encode(), now + 60 + grace),
            (keys[1].encode(), float("inf")),
        ]
        assert await redis.ttl(tag_key) == -1

        # Once the first page expired, the next write drops it from the index.
        now += 60 + grace + 1
        await store(keys[2], 60)
        assert await members() == [
            (keys[2].encode(), now + 60 + grace),
            (keys[1].encode(), float("inf")),
        ]
        assert await redis.ttl(tag_key) == -1

        assert await cache.invalidate_tag(tag) == 2
        assert not await redis.exists(tag_key)
    finally:
        await redis.delete(tag_key, *(RedisISRCache._PAGE_PREFIX + key for key in keys))
        await redis.aclose()


@pytest.mark.asyncio
async def test_redis_release_lock_keeps_lock_of_next_owner():
    """Releasing an expired lock leaves the lock another worker acquired since."""
    redis = prerequisites.get_redis()
    if redis is None:
        pytest.skip("Test requires redis")
    cache = RedisISRCache(redis)
    key = f"test:{uuid.uuid4().hex}"
    lock_key = RedisISRCache._LOCK_PREFIX + key
    try:
        first = await cache.acquire_lock(key, 30)
        assert first is not None
        await redis.delete(lock_key)  # the first holder's lock expires
        second = await cache.acquire_lock(key, 30)
        assert second is not None

        await cache.release_lock(key, first)
        assert await redis.exists(lock_key)

        await cache.release_lock(key, second)
        assert not await redis.exists(lock_key)
    finally:
        await redis.delete(lock_key)
        await redis.aclose()
