"""Unit tests for the ISR (Incremental Static Regeneration) core."""

from __future__ import annotations

import asyncio
import time

import pytest

from reflex.isr import CachedPage, ISRManager, MemoryISRCache, RenderResult, cache_key


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

    async def __call__(self, path: str) -> RenderResult | None:
        """Render the path, optionally blocking on the gate or failing.

        Args:
            path: The path being rendered.

        Returns:
            A render result, or None when configured to fail.
        """
        self.calls += 1
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
    """Wait for any background revalidation tasks to finish."""
    if manager._background:
        await asyncio.gather(*list(manager._background))


def _manager(renderer, **kwargs) -> ISRManager:
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
