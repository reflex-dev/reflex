"""Incremental Static Regeneration (ISR) for Reflex.

Serves prerendered HTML from a shared cache with stale-while-revalidate (SWR)
semantics and cross-worker single-flight regeneration, so multiple workers
(e.g. Kubernetes replicas) share one cache and never double-render a page.

Responsibilities split:

* This module owns **caching, coordination, and revalidation** — pure Python,
  no JS runtime.  It works across workers when backed by Redis.
* Producing the HTML is delegated to a pluggable :data:`Renderer` (e.g. a Node
  render tier that runs the react-router server bundle and fetches state from
  the ``/_ssr_data`` endpoint).  ISR itself never renders React.

Cache entries are keyed by ``{build_id}:{path}`` so a new deploy (new build id)
transparently rotates the cache and never serves HTML that references
content-hashed assets from a previous build.  ``path`` is the raw request path,
percent-encoding included, without the query string: each page is rendered and
cached per path, and its ``on_load`` fills in query-dependent content after
hydration.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import hmac
import json
import os
import time
import traceback
import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

import httpx
from reflex_base import constants
from reflex_base.config import Config, get_config
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

from reflex.utils import console, prerequisites

if TYPE_CHECKING:
    from redis.asyncio import Redis


@dataclasses.dataclass(frozen=True)
class RenderResult:
    """The result of rendering a page.

    Attributes:
        html: The rendered HTML document.
        revalidate: Seconds until the entry goes stale (``None`` = use default).
        tags: Revalidation tags for on-demand invalidation of related pages.
    """

    html: str
    revalidate: float | None = None
    tags: tuple[str, ...] = ()


# A Renderer turns a raw request path (percent-encoded, no query string) into a
# RenderResult, or None on failure (ISR then serves stale/fallback rather than
# caching an error).
Renderer = Callable[[str], Awaitable["RenderResult | None"]]


@dataclasses.dataclass(frozen=True)
class CachedPage:
    """A cached rendered page.

    Attributes:
        html: The rendered HTML document, UTF-8 encoded.
        generated_at: Unix timestamp when the page was rendered.
        revalidate: Seconds until the page is considered stale (``<= 0`` never).
        tags: Revalidation tags associated with the page.
    """

    html: bytes
    generated_at: float
    revalidate: float
    tags: tuple[str, ...] = ()

    def is_stale(self, now: float | None = None) -> bool:
        """Whether the page is past its revalidation window.

        Args:
            now: The current time (defaults to ``time.time()``).

        Returns:
            True if the page should be revalidated.
        """
        if self.revalidate <= 0:
            return False
        now = time.time() if now is None else now
        return (now - self.generated_at) >= self.revalidate

    def meta_json(self) -> str:
        """Serialize everything but the HTML, which is stored as is beside it.

        Returns:
            A JSON string.
        """
        return json.dumps({
            "generated_at": self.generated_at,
            "revalidate": self.revalidate,
            "tags": self.tags,
        })

    @classmethod
    def from_stored(cls, html: bytes, meta: str | bytes) -> CachedPage:
        """Rebuild a page from its stored HTML and metadata.

        Args:
            html: The stored HTML document.
            meta: The JSON produced by :meth:`meta_json`.

        Returns:
            The reconstructed page.
        """
        data = json.loads(meta)
        return cls(
            html=html,
            generated_at=data["generated_at"],
            revalidate=data["revalidate"],
            tags=tuple(data["tags"]),
        )


@runtime_checkable
class ISRCache(Protocol):
    """Shared cache + coordination backend for ISR.

    A Redis-backed implementation makes the cache, single-flight lock, and tag
    index shared across all workers; the in-memory implementation is per-process
    (dev/test only).
    """

    async def get(self, key: str) -> CachedPage | None:
        """Get a cached page.

        Args:
            key: The cache key.

        Returns:
            The cached page, or None if absent.
        """
        ...

    async def epoch(self) -> int:
        """Get the invalidation epoch, which every invalidation advances.

        Returns:
            The current epoch.
        """
        ...

    async def set(self, key: str, page: CachedPage, epoch: int) -> bool:
        """Store a page and index its tags, unless an invalidation came after ``epoch``.

        A render that started before an invalidation may hold the content it
        was meant to drop, so its page is not stored.

        Args:
            key: The cache key.
            page: The page to store.
            epoch: The :meth:`epoch` read before the page was rendered.

        Returns:
            Whether the page was stored.
        """
        ...

    async def delete(self, key: str) -> None:
        """Remove a cached page, advancing the invalidation epoch.

        Args:
            key: The cache key.
        """
        ...

    async def acquire_lock(self, key: str, ttl: float) -> str | None:
        """Try to acquire the single-flight render lock for ``key``.

        Args:
            key: The cache key.
            ttl: Lock expiry in seconds.

        Returns:
            An owner token if this caller now holds the lock, else None.
        """
        ...

    async def release_lock(self, key: str, token: str) -> None:
        """Release the single-flight render lock for ``key`` if ``token`` owns it.

        Args:
            key: The cache key.
            token: The owner token returned by :meth:`acquire_lock`.
        """
        ...

    async def invalidate_tag(self, tag: str) -> int:
        """Delete every cached page carrying ``tag``, advancing the invalidation epoch.

        Args:
            tag: The tag to invalidate.

        Returns:
            The number of pages removed.
        """
        ...


class MemoryISRCache:
    """In-process ISR cache (single worker; dev/test only).

    Not shared across workers — use :class:`RedisISRCache` in production.
    """

    def __init__(self) -> None:
        """Initialize empty stores."""
        self._pages: dict[str, CachedPage] = {}
        self._tags: dict[str, set[str]] = {}
        self._locks: dict[str, str] = {}
        self._epoch = 0

    async def get(self, key: str) -> CachedPage | None:
        """Get a cached page.

        Args:
            key: The cache key.

        Returns:
            The cached page, or None.
        """
        return self._pages.get(key)

    async def epoch(self) -> int:
        """Get the invalidation epoch.

        Returns:
            The current epoch.
        """
        return self._epoch

    async def set(self, key: str, page: CachedPage, epoch: int) -> bool:
        """Store a page and index its tags, unless an invalidation came after ``epoch``.

        Args:
            key: The cache key.
            page: The page to store.
            epoch: The epoch read before the page was rendered.

        Returns:
            Whether the page was stored.
        """
        if epoch != self._epoch:
            return False
        self._pages[key] = page
        for tag in page.tags:
            self._tags.setdefault(tag, set()).add(key)
        return True

    async def delete(self, key: str) -> None:
        """Remove a cached page, advancing the invalidation epoch.

        Args:
            key: The cache key.
        """
        self._epoch += 1
        self._pages.pop(key, None)

    async def acquire_lock(self, key: str, ttl: float) -> str | None:
        """Acquire the render lock (no TTL needed in-process).

        Args:
            key: The cache key.
            ttl: Unused for the in-memory backend.

        Returns:
            An owner token if the lock was acquired, else None.
        """
        if key in self._locks:
            return None
        token = self._locks[key] = uuid.uuid4().hex
        return token

    async def release_lock(self, key: str, token: str) -> None:
        """Release the render lock if ``token`` owns it.

        Args:
            key: The cache key.
            token: The owner token returned by :meth:`acquire_lock`.
        """
        if self._locks.get(key) == token:
            del self._locks[key]

    async def invalidate_tag(self, tag: str) -> int:
        """Delete all pages carrying ``tag``.

        Args:
            tag: The tag to invalidate.

        Returns:
            The number of pages removed.
        """
        self._epoch += 1
        keys = self._tags.pop(tag, set())
        for key in keys:
            self._pages.pop(key, None)
        return len(keys)


# Deletes the lock in KEYS[1] only while ARGV[1] still owns it, so a worker
# whose lock expired cannot release the lock another worker acquired since.
_RELEASE_LOCK_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


# Stores a page as a hash of its HTML and metadata JSON unless the invalidation
# epoch in KEYS[1] moved past ARGV[1], and indexes it in each tag's sorted set
# (KEYS[3:]) scored by the page's expiry: expired members are pruned and a set
# expires with its last page.
# ARGV: epoch, HTML, metadata JSON, page TTL in seconds (0 = none), cache key, now.
_SET_PAGE_SCRIPT = """
if (redis.call('GET', KEYS[1]) or '0') ~= ARGV[1] then
    return 0
end
redis.call('DEL', KEYS[2])
redis.call('HSET', KEYS[2], 'html', ARGV[2], 'meta', ARGV[3])
local ttl = tonumber(ARGV[4])
local expires = '+inf'
if ttl > 0 then
    redis.call('EXPIRE', KEYS[2], ttl)
    expires = tostring(tonumber(ARGV[6]) + ttl)
end
for i = 3, #KEYS do
    redis.call('ZADD', KEYS[i], expires, ARGV[5])
    redis.call('ZREMRANGEBYSCORE', KEYS[i], '-inf', '(' .. ARGV[6])
    local last = redis.call('ZRANGE', KEYS[i], -1, -1, 'WITHSCORES')[2]
    if last == 'inf' then
        redis.call('PERSIST', KEYS[i])
    else
        redis.call('EXPIREAT', KEYS[i], math.ceil(tonumber(last)))
    end
end
return 1
"""


# Advances the epoch in KEYS[1] and deletes the tag's sorted set in KEYS[2] with
# every page it holds that has not expired by ARGV[1] (page key prefix ARGV[2]),
# atomically, so no page gets stored and indexed between lookup and deletion.
_INVALIDATE_TAG_SCRIPT = """
redis.call('INCR', KEYS[1])
local members = redis.call('ZRANGEBYSCORE', KEYS[2], ARGV[1], '+inf')
for _, member in ipairs(members) do
    redis.call('DEL', ARGV[2] .. member)
end
redis.call('DEL', KEYS[2])
return #members
"""


class RedisISRCache:
    """Redis-backed ISR cache shared across all workers."""

    _PAGE_PREFIX = "reflex_isr:page:"
    _LOCK_PREFIX = "reflex_isr:lock:"
    _TAG_PREFIX = "reflex_isr:tag:"
    _EPOCH_KEY = "reflex_isr:epoch"

    def __init__(self, redis: Redis) -> None:
        """Store the async Redis client.

        Args:
            redis: An async Redis client.
        """
        self._redis = redis

    async def get(self, key: str) -> CachedPage | None:
        """Get a cached page.

        Args:
            key: The cache key.

        Returns:
            The cached page, or None.
        """
        # A page's fields are stored together, so they are all set or all missing.
        stored = cast(
            "tuple[bytes, bytes] | tuple[None, None]",
            await self._redis.hmget(self._PAGE_PREFIX + key, "html", "meta"),
        )
        return CachedPage.from_stored(*stored) if stored[0] is not None else None

    async def epoch(self) -> int:
        """Get the invalidation epoch.

        Returns:
            The current epoch.
        """
        return int(await self._redis.get(self._EPOCH_KEY) or 0)

    async def set(self, key: str, page: CachedPage, epoch: int) -> bool:
        """Store a page and index its tags, unless an invalidation came after ``epoch``.

        The stored value gets a generous TTL (well past ``revalidate``) so stale
        entries remain available for stale-while-revalidate but do not leak
        forever; each tag index expires with the last page it holds.

        Args:
            key: The cache key.
            page: The page to store.
            epoch: The epoch read before the page was rendered.

        Returns:
            Whether the page was stored.
        """
        # Keep stale entries around for SWR: TTL = revalidate window + 24h grace.
        ttl = int(page.revalidate) + 86400 if page.revalidate > 0 else 0
        stored = await self._redis.eval(  # pyright: ignore[reportGeneralTypeIssues]
            _SET_PAGE_SCRIPT,
            2 + len(page.tags),
            self._EPOCH_KEY,
            self._PAGE_PREFIX + key,
            *(self._TAG_PREFIX + tag for tag in page.tags),
            epoch,
            page.html,
            page.meta_json(),
            ttl,
            key,
            time.time(),
        )
        return bool(stored)

    async def delete(self, key: str) -> None:
        """Remove a cached page, advancing the invalidation epoch.

        Args:
            key: The cache key.
        """
        pipe = self._redis.pipeline()
        pipe.incr(self._EPOCH_KEY)
        pipe.delete(self._PAGE_PREFIX + key)
        await pipe.execute()

    async def acquire_lock(self, key: str, ttl: float) -> str | None:
        """Acquire the single-flight lock via ``SET NX EX``.

        Args:
            key: The cache key.
            ttl: Lock expiry in seconds (guards against a crashed holder).

        Returns:
            An owner token if the lock was acquired, else None.
        """
        token = uuid.uuid4().hex
        acquired = await self._redis.set(
            self._LOCK_PREFIX + key, token, nx=True, ex=max(1, int(ttl))
        )
        return token if acquired else None

    async def release_lock(self, key: str, token: str) -> None:
        """Release the single-flight lock if ``token`` still owns it.

        Args:
            key: The cache key.
            token: The owner token returned by :meth:`acquire_lock`.
        """
        await self._redis.eval(_RELEASE_LOCK_SCRIPT, 1, self._LOCK_PREFIX + key, token)  # pyright: ignore[reportGeneralTypeIssues]

    async def invalidate_tag(self, tag: str) -> int:
        """Delete all pages carrying ``tag``.

        Args:
            tag: The tag to invalidate.

        Returns:
            The number of pages removed.
        """
        return await self._redis.eval(  # pyright: ignore[reportGeneralTypeIssues]
            _INVALIDATE_TAG_SCRIPT,
            2,
            self._EPOCH_KEY,
            self._TAG_PREFIX + tag,
            time.time(),
            self._PAGE_PREFIX,
        )


def cache_key(build_id: str, path: str) -> str:
    """Build the cache key for a page.

    Args:
        build_id: The current build identifier (rotates the cache per deploy).
        path: The request path.

    Returns:
        The cache key.
    """
    return f"{build_id}:{path}"


class ISRManager:
    """Coordinates ISR serving: cache lookup, SWR, and single-flight rendering.

    Args:
        cache: The shared cache/coordination backend.
        renderer: Produces HTML for a path (e.g. calls the Node render tier).
        build_id: Identifier that rotates the cache on each deploy.
        default_revalidate: Default seconds-until-stale when a render does not
            specify its own.
        lock_ttl: Max seconds a single-flight render may hold the lock.
        wait_timeout: Max seconds a request waits for another worker's in-flight
            render on a cache miss before falling back.
    """

    def __init__(
        self,
        cache: ISRCache,
        renderer: Renderer,
        *,
        build_id: str = "dev",
        default_revalidate: float = 60.0,
        lock_ttl: float = 30.0,
        wait_timeout: float = 5.0,
    ) -> None:
        """Store configuration."""
        self.cache = cache
        self.renderer = renderer
        self.build_id = build_id
        self.default_revalidate = default_revalidate
        self.lock_ttl = lock_ttl
        self.wait_timeout = wait_timeout
        self._background: set[asyncio.Task] = set()

    async def get_html(self, path: str) -> bytes | None:
        """Return HTML for ``path`` using ISR semantics.

        * Fresh cache hit -> serve immediately.
        * Stale hit -> serve stale immediately, revalidate in the background
          (single-flight).
        * Miss -> single-flight render; losing waiters briefly poll for the
          winner's result, then fall back to ``None`` (caller serves the shell).

        Args:
            path: The concrete request path.

        Returns:
            The encoded HTML, or None if it could not be produced.
        """
        key = cache_key(self.build_id, path)
        page = await self.cache.get(key)

        if page is not None and not page.is_stale():
            return page.html

        if page is not None:
            # Stale-while-revalidate: serve stale now, refresh in the background.
            self._spawn_revalidate(key, path)
            return page.html

        # Cache miss: block on a single-flight render.
        return await self._render_single_flight(key, path)

    async def _render_single_flight(self, key: str, path: str) -> bytes | None:
        """Render ``path`` once across workers, or wait for the winner.

        Args:
            key: The cache key.
            path: The request path.

        Returns:
            The rendered HTML, or None on failure/timeout.
        """
        if (token := await self.cache.acquire_lock(key, self.lock_ttl)) is not None:
            try:
                return await self._render_and_store(key, path)
            finally:
                await self.cache.release_lock(key, token)

        # Another worker is rendering; poll briefly for its result.
        deadline = time.monotonic() + self.wait_timeout
        while time.monotonic() < deadline:
            await asyncio.sleep(0.05)
            page = await self.cache.get(key)
            if page is not None:
                return page.html
        return None

    async def _render_and_store(self, key: str, path: str) -> bytes | None:
        """Render ``path`` and cache the result.

        Args:
            key: The cache key.
            path: The request path.

        Returns:
            The rendered HTML, or None on failure. A render that an invalidation
            overtakes is returned but not cached.
        """
        epoch = await self.cache.epoch()
        try:
            result = await self.renderer(path)
        except Exception:
            console.warn(f"ISR render failed for {path}: {traceback.format_exc()}")
            return None
        if result is None:
            return None
        revalidate = (
            result.revalidate
            if result.revalidate is not None
            else self.default_revalidate
        )
        html = result.html.encode()
        await self.cache.set(
            key,
            CachedPage(
                html=html,
                generated_at=time.time(),
                revalidate=revalidate,
                tags=result.tags,
            ),
            epoch,
        )
        return html

    def _spawn_revalidate(self, key: str, path: str) -> None:
        """Schedule a background, single-flight revalidation of ``key``.

        Args:
            key: The cache key.
            path: The request path.
        """
        task = asyncio.create_task(self._revalidate(key, path))
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def _revalidate(self, key: str, path: str) -> None:
        """Re-render and refresh a stale entry if no other worker is doing so.

        Args:
            key: The cache key.
            path: The request path.
        """
        if (token := await self.cache.acquire_lock(key, self.lock_ttl)) is None:
            return
        try:
            await self._render_and_store(key, path)
        finally:
            await self.cache.release_lock(key, token)

    async def revalidate_path(self, path: str) -> None:
        """Invalidate the cached page for a specific path.

        Args:
            path: The path to invalidate.
        """
        await self.cache.delete(cache_key(self.build_id, path))

    async def revalidate_tag(self, tag: str) -> int:
        """Invalidate every cached page carrying ``tag``.

        Args:
            tag: The tag to invalidate.

        Returns:
            The number of pages invalidated.
        """
        return await self.cache.invalidate_tag(tag)


class HttpRenderer:
    """Renderer that delegates to a render-tier HTTP service.

    The service receives ``{"path": path}`` and returns
    ``{"html": ..., "revalidate"?: number, "tags"?: string[]}``.  Any error or
    non-200 response yields ``None`` so ISR serves stale/shell instead of
    caching a failure.

    Args:
        render_url: The render-tier endpoint URL.
        timeout: Per-request timeout in seconds.
    """

    def __init__(self, render_url: str, *, timeout: float = 10.0) -> None:
        """Store the render endpoint and timeout."""
        self._url = render_url
        self._timeout = timeout
        # A single pooled client is created lazily on first use (inside the
        # event loop) and reused, so page-server -> render-tier connections stay
        # keep-alive instead of a fresh TCP/TLS handshake per render.
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Return the shared client, creating it on first use.

        Returns:
            The pooled async HTTP client.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def aclose(self) -> None:
        """Close the pooled client (call on page-server shutdown)."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __call__(self, path: str) -> RenderResult | None:
        """Render ``path`` via the render tier.

        Args:
            path: The concrete request path.

        Returns:
            The render result, or None on failure.
        """
        try:
            resp = await self._get_client().post(self._url, json={"path": path})
            if resp.status_code != 200:
                console.warn(f"ISR render tier returned {resp.status_code} for {path}")
                return None
            data = resp.json()
        except Exception as exc:
            console.warn(f"ISR render tier request failed for {path}: {exc}")
            return None

        html = data.get("html")
        if not html:
            return None
        return RenderResult(
            html=html,
            revalidate=data.get("revalidate"),
            tags=tuple(data.get("tags", ())),
        )


def is_enabled(config: Config | None = None) -> bool:
    """Whether ISR is configured (a render tier URL is set).

    Args:
        config: The config to read (defaults to the global config).

    Returns:
        True when ``config.isr_render_url`` is set.
    """
    config = config if config is not None else get_config()
    return config.isr_render_url is not None


def get_build_id(config: Config | None = None) -> str:
    """Resolve the cache-rotating build id.

    Precedence: ``config.isr_build_id`` -> ``REFLEX_BUILD_ID`` env -> ``"dev"``.

    Args:
        config: The config to read (defaults to the global config).

    Returns:
        The build id.
    """
    config = config if config is not None else get_config()
    return config.isr_build_id or os.environ.get("REFLEX_BUILD_ID") or "dev"


def get_cache() -> ISRCache:
    """Build the ISR cache backend: Redis when available, else in-memory.

    Returns:
        A shared Redis-backed cache, or an in-process fallback.
    """
    redis = prerequisites.get_redis()
    if redis is not None:
        return RedisISRCache(redis)
    console.warn(
        "ISR: no redis_url configured; using an in-memory cache that is NOT "
        "shared across workers. Set redis_url for multi-worker deployments."
    )
    return MemoryISRCache()


# The redis client revalidate_path and revalidate_tag share, closed on app shutdown.
_redis: Redis | None = None


def _get_redis() -> Redis | None:
    """Get the long-lived redis client used for on-demand revalidation.

    Returns:
        The asynchronous redis client, or None if redis is not configured.
    """
    global _redis
    if _redis is None:
        _redis = prerequisites.get_redis()
    return _redis


async def close_redis() -> None:
    """Close the cached revalidation redis client, if one was created."""
    global _redis
    if _redis is not None:
        await _redis.aclose(close_connection_pool=True)
        _redis = None


async def revalidate_path(path: str, *, config: Config | None = None) -> None:
    """Invalidate the ISR cache entry for ``path`` from application code.

    Call this from an event handler after content changes so the next request
    re-renders the page.  It operates on the shared Redis cache, so a single
    call propagates to every page-server worker.  No-op when no ``redis_url``
    is configured (nothing is shared to invalidate).

    Args:
        path: The percent-encoded path to invalidate (e.g. ``/blog/hello-world``).
        config: The config to read the build id from (defaults to global).
    """
    redis = _get_redis()
    if redis is not None:
        await RedisISRCache(redis).delete(cache_key(get_build_id(config), path))


async def revalidate_tag(tag: str) -> int:
    """Invalidate every ISR page carrying ``tag`` from application code.

    Propagates to all page-server workers via the shared Redis cache.

    Args:
        tag: The revalidation tag (e.g. ``post-123``).

    Returns:
        The number of pages invalidated (0 when no ``redis_url`` is configured).
    """
    redis = _get_redis()
    if redis is None:
        return 0
    return await RedisISRCache(redis).invalidate_tag(tag)


def create_manager(
    config: Config | None = None,
    *,
    cache: ISRCache | None = None,
    renderer: Renderer | None = None,
) -> ISRManager:
    """Assemble an :class:`ISRManager` from config (and optional overrides).

    Args:
        config: The config to read (defaults to the global config).
        cache: Cache backend override (defaults to :func:`get_cache`).
        renderer: Renderer override (defaults to an :class:`HttpRenderer`).

    Returns:
        A configured ISR manager.

    Raises:
        ValueError: If no renderer is given and ``isr_render_url`` is unset.
    """
    config = config if config is not None else get_config()
    if renderer is None:
        if not config.isr_render_url:
            msg = "ISR requires config.isr_render_url (or an explicit renderer)."
            raise ValueError(msg)
        renderer = HttpRenderer(config.isr_render_url)
    return ISRManager(
        cache if cache is not None else get_cache(),
        renderer,
        build_id=get_build_id(config),
        default_revalidate=float(config.isr_revalidate),
    )


def _load_shell() -> bytes | None:
    """Read the SPA shell HTML from the compiled static build, if present.

    Returns:
        The shell HTML, or None if it cannot be found.
    """
    static_dir = prerequisites.get_web_dir() / constants.Dirs.STATIC
    for name in (constants.ReactRouter.SPA_FALLBACK, "index.html"):
        candidate = static_dir / name
        if candidate.exists():
            return candidate.read_bytes()
    return None


def create_isr_app(
    manager: ISRManager | None = None,
    *,
    shell: str | None = None,
) -> Starlette:
    """Create the dedicated ISR page-server ASGI app.

    Serves documents via ISR (nginx ``proxy_cache`` is expected in front for
    edge caching), falling back to the SPA shell on a miss/render failure, and
    exposes ``POST /_isr/revalidate`` for on-demand invalidation.  Pages are
    rendered and cached per raw request path; the query string is neither
    forwarded nor part of the cache key, so the page's ``on_load`` fills in
    query-dependent content after hydration.  The
    revalidation endpoint exists only when the ``REFLEX_ISR_REVALIDATE_TOKEN``
    env var is set, and requires a matching ``X-Reflex-ISR-Token`` header.

    Run in production as an app factory, e.g.
    ``granian --factory reflex.isr:create_isr_app``.

    Args:
        manager: The ISR manager (defaults to one built from config).
        shell: The SPA shell HTML (defaults to reading the compiled build).

    Returns:
        A Starlette app.
    """
    mgr = manager if manager is not None else create_manager()
    shell_html = shell.encode() if shell is not None else _load_shell()
    revalidate_token = os.environ.get("REFLEX_ISR_REVALIDATE_TOKEN", "").encode()

    async def serve(request: Request) -> Response:
        """Serve a page via ISR, falling back to the SPA shell.

        Args:
            request: The page request.

        Returns:
            The rendered page, the shell, or a 404.
        """
        # The raw path keeps an encoded slash (``/blog/a%2Fb``) in its segment.
        raw_path = request.scope.get("raw_path")
        html = await mgr.get_html(
            raw_path.decode("latin-1") if raw_path is not None else request.url.path
        )
        if html is not None:
            return HTMLResponse(html)
        if shell_html is not None:
            # Miss/failure: serve the SPA shell so the client hydrates.
            return HTMLResponse(shell_html)
        return Response("Not found", status_code=404)

    async def revalidate(request: Request) -> Response:
        """Invalidate the cached pages for the posted path and/or tag.

        Args:
            request: The revalidation request.

        Returns:
            A JSON summary, or 401 when the token does not match.
        """
        if not hmac.compare_digest(
            request.headers.get("x-reflex-isr-token", "").encode(),
            revalidate_token,
        ):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        body = await request.json()
        if path := body.get("path"):
            await mgr.revalidate_path(path)
        count = 0
        if tag := body.get("tag"):
            count = await mgr.revalidate_tag(tag)
        return JSONResponse({"revalidated": True, "tag_pages": count})

    @contextlib.asynccontextmanager
    async def _lifespan(_app: Starlette):
        """Close the renderer's pooled HTTP client on shutdown, if any.

        Args:
            _app: The page-server app.

        Yields:
            Control while the app runs.
        """
        try:
            yield
        finally:
            aclose = getattr(mgr.renderer, "aclose", None)
            if aclose is not None:
                await aclose()

    # Without a token anyone reaching the page server could clear its cache.
    revalidate_routes = (
        [Route("/_isr/revalidate", revalidate, methods=["POST"])]
        if revalidate_token
        else []
    )
    return Starlette(
        routes=[*revalidate_routes, Route("/{path:path}", serve, methods=["GET"])],
        lifespan=_lifespan,
    )
