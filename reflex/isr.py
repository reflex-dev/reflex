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
content-hashed assets from a previous build.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import json
import os
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from reflex.utils import console

if TYPE_CHECKING:
    import httpx
    from redis.asyncio import Redis
    from starlette.applications import Starlette

    from reflex.config import Config


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


# A Renderer turns a concrete request path into a RenderResult, or None on
# failure (in which case ISR serves stale/fallback rather than caching an error).
Renderer = Callable[[str], Awaitable["RenderResult | None"]]


@dataclasses.dataclass(frozen=True)
class CachedPage:
    """A cached rendered page.

    Attributes:
        html: The rendered HTML document.
        generated_at: Unix timestamp when the page was rendered.
        revalidate: Seconds until the page is considered stale (``<= 0`` never).
        tags: Revalidation tags associated with the page.
    """

    html: str
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

    def to_json(self) -> str:
        """Serialize the page for storage.

        Returns:
            A JSON string.
        """
        return json.dumps(dataclasses.asdict(self))

    @classmethod
    def from_json(cls, raw: str | bytes) -> CachedPage:
        """Deserialize a page from storage.

        Args:
            raw: The JSON string/bytes produced by :meth:`to_json`.

        Returns:
            The reconstructed page.
        """
        data = json.loads(raw)
        return cls(
            html=data["html"],
            generated_at=data["generated_at"],
            revalidate=data["revalidate"],
            tags=tuple(data.get("tags", ())),
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

    async def set(self, key: str, page: CachedPage) -> None:
        """Store a page and index its tags.

        Args:
            key: The cache key.
            page: The page to store.
        """
        ...

    async def delete(self, key: str) -> None:
        """Remove a cached page.

        Args:
            key: The cache key.
        """
        ...

    async def acquire_lock(self, key: str, ttl: float) -> bool:
        """Try to acquire the single-flight render lock for ``key``.

        Args:
            key: The cache key.
            ttl: Lock expiry in seconds.

        Returns:
            True if this caller now holds the lock.
        """
        ...

    async def release_lock(self, key: str) -> None:
        """Release the single-flight render lock for ``key``.

        Args:
            key: The cache key.
        """
        ...

    async def invalidate_tag(self, tag: str) -> int:
        """Delete every cached page carrying ``tag``.

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
        self._locks: set[str] = set()

    async def get(self, key: str) -> CachedPage | None:
        """Get a cached page.

        Args:
            key: The cache key.

        Returns:
            The cached page, or None.
        """
        return self._pages.get(key)

    async def set(self, key: str, page: CachedPage) -> None:
        """Store a page and index its tags.

        Args:
            key: The cache key.
            page: The page to store.
        """
        self._pages[key] = page
        for tag in page.tags:
            self._tags.setdefault(tag, set()).add(key)

    async def delete(self, key: str) -> None:
        """Remove a cached page.

        Args:
            key: The cache key.
        """
        self._pages.pop(key, None)

    async def acquire_lock(self, key: str, ttl: float) -> bool:
        """Acquire the render lock (no TTL needed in-process).

        Args:
            key: The cache key.
            ttl: Unused for the in-memory backend.

        Returns:
            True if the lock was acquired.
        """
        if key in self._locks:
            return False
        self._locks.add(key)
        return True

    async def release_lock(self, key: str) -> None:
        """Release the render lock.

        Args:
            key: The cache key.
        """
        self._locks.discard(key)

    async def invalidate_tag(self, tag: str) -> int:
        """Delete all pages carrying ``tag``.

        Args:
            tag: The tag to invalidate.

        Returns:
            The number of pages removed.
        """
        keys = self._tags.pop(tag, set())
        for key in keys:
            self._pages.pop(key, None)
        return len(keys)


class RedisISRCache:
    """Redis-backed ISR cache shared across all workers."""

    _PAGE_PREFIX = "reflex_isr:page:"
    _LOCK_PREFIX = "reflex_isr:lock:"
    _TAG_PREFIX = "reflex_isr:tag:"

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
        raw = await self._redis.get(self._PAGE_PREFIX + key)
        return CachedPage.from_json(raw) if raw is not None else None

    async def set(self, key: str, page: CachedPage) -> None:
        """Store a page and index its tags.

        The stored value gets a generous TTL (well past ``revalidate``) so stale
        entries remain available for stale-while-revalidate but do not leak
        forever.

        Args:
            key: The cache key.
            page: The page to store.
        """
        # Keep stale entries around for SWR: TTL = revalidate window + 24h grace.
        ttl = int(page.revalidate) + 86400 if page.revalidate > 0 else None
        pipe = self._redis.pipeline()
        pipe.set(self._PAGE_PREFIX + key, page.to_json(), ex=ttl)
        for tag in page.tags:
            pipe.sadd(self._TAG_PREFIX + tag, key)
        await pipe.execute()

    async def delete(self, key: str) -> None:
        """Remove a cached page.

        Args:
            key: The cache key.
        """
        await self._redis.delete(self._PAGE_PREFIX + key)

    async def acquire_lock(self, key: str, ttl: float) -> bool:
        """Acquire the single-flight lock via ``SET NX EX``.

        Args:
            key: The cache key.
            ttl: Lock expiry in seconds (guards against a crashed holder).

        Returns:
            True if the lock was acquired.
        """
        acquired = await self._redis.set(
            self._LOCK_PREFIX + key, b"1", nx=True, ex=max(1, int(ttl))
        )
        return bool(acquired)

    async def release_lock(self, key: str) -> None:
        """Release the single-flight lock.

        Args:
            key: The cache key.
        """
        await self._redis.delete(self._LOCK_PREFIX + key)

    async def invalidate_tag(self, tag: str) -> int:
        """Delete all pages carrying ``tag``.

        Args:
            tag: The tag to invalidate.

        Returns:
            The number of pages removed.
        """
        tag_key = self._TAG_PREFIX + tag
        # redis.asyncio stubs type set-commands with their sync (non-awaitable)
        # return type; smembers is awaitable at runtime.
        keys = await self._redis.smembers(tag_key)  # pyright: ignore[reportGeneralTypeIssues]
        if not keys:
            return 0
        page_keys = [
            self._PAGE_PREFIX + (k.decode() if isinstance(k, bytes) else k)
            for k in keys
        ]
        await self._redis.delete(*page_keys, tag_key)
        return len(page_keys)


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

    async def get_html(self, path: str) -> str | None:
        """Return HTML for ``path`` using ISR semantics.

        * Fresh cache hit -> serve immediately.
        * Stale hit -> serve stale immediately, revalidate in the background
          (single-flight).
        * Miss -> single-flight render; losing waiters briefly poll for the
          winner's result, then fall back to ``None`` (caller serves the shell).

        Args:
            path: The concrete request path.

        Returns:
            The HTML string, or None if it could not be produced.
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

    async def _render_single_flight(self, key: str, path: str) -> str | None:
        """Render ``path`` once across workers, or wait for the winner.

        Args:
            key: The cache key.
            path: The request path.

        Returns:
            The rendered HTML, or None on failure/timeout.
        """
        if await self.cache.acquire_lock(key, self.lock_ttl):
            try:
                return await self._render_and_store(key, path)
            finally:
                await self.cache.release_lock(key)

        # Another worker is rendering; poll briefly for its result.
        deadline = time.monotonic() + self.wait_timeout
        while time.monotonic() < deadline:
            await asyncio.sleep(0.05)
            page = await self.cache.get(key)
            if page is not None:
                return page.html
        return None

    async def _render_and_store(self, key: str, path: str) -> str | None:
        """Render ``path`` and cache the result.

        Args:
            key: The cache key.
            path: The request path.

        Returns:
            The rendered HTML, or None on failure.
        """
        try:
            result = await self.renderer(path)
        except Exception:
            import traceback

            console.warn(f"ISR render failed for {path}: {traceback.format_exc()}")
            return None
        if result is None:
            return None
        revalidate = (
            result.revalidate
            if result.revalidate is not None
            else self.default_revalidate
        )
        await self.cache.set(
            key,
            CachedPage(
                html=result.html,
                generated_at=time.time(),
                revalidate=revalidate,
                tags=result.tags,
            ),
        )
        return result.html

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
        if not await self.cache.acquire_lock(key, self.lock_ttl):
            return
        try:
            await self._render_and_store(key, path)
        finally:
            await self.cache.release_lock(key)

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


# ---------------------------------------------------------------------------
# HTTP render tier: the concrete Renderer that calls a separate render service.
# ---------------------------------------------------------------------------


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
        import httpx

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


# ---------------------------------------------------------------------------
# Factories + the dedicated ISR page-server (sits behind nginx proxy_cache).
# ---------------------------------------------------------------------------


def is_enabled(config: Config | None = None) -> bool:
    """Whether ISR is configured (a render tier URL is set).

    Args:
        config: The config to read (defaults to the global config).

    Returns:
        True when ``config.isr_render_url`` is set.
    """
    from reflex.config import get_config

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
    from reflex.config import get_config

    config = config if config is not None else get_config()
    return config.isr_build_id or os.environ.get("REFLEX_BUILD_ID") or "dev"


def get_cache() -> ISRCache:
    """Build the ISR cache backend: Redis when available, else in-memory.

    Returns:
        A shared Redis-backed cache, or an in-process fallback.
    """
    from reflex.utils import prerequisites

    redis = prerequisites.get_redis()
    if redis is not None:
        return RedisISRCache(redis)
    console.warn(
        "ISR: no redis_url configured; using an in-memory cache that is NOT "
        "shared across workers. Set redis_url for multi-worker deployments."
    )
    return MemoryISRCache()


async def revalidate_path(path: str, *, config: Config | None = None) -> None:
    """Invalidate the ISR cache entry for ``path`` from application code.

    Call this from an event handler after content changes so the next request
    re-renders the page.  It operates on the shared Redis cache, so a single
    call propagates to every page-server worker.  No-op when no ``redis_url``
    is configured (nothing is shared to invalidate).

    Args:
        path: The path to invalidate (e.g. ``/blog/hello-world``).
        config: The config to read the build id from (defaults to global).
    """
    from reflex.utils import prerequisites

    redis = prerequisites.get_redis()
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
    from reflex.utils import prerequisites

    redis = prerequisites.get_redis()
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
    from reflex.config import get_config

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


def _load_shell() -> str | None:
    """Read the SPA shell HTML from the compiled static build, if present.

    Returns:
        The shell HTML, or None if it cannot be found.
    """
    from reflex import constants
    from reflex.utils import prerequisites

    static_dir = prerequisites.get_web_dir() / constants.Dirs.STATIC
    for name in (constants.ReactRouter.SPA_FALLBACK, "index.html"):
        candidate = static_dir / name
        if candidate.exists():
            return candidate.read_text()
    return None


def create_isr_app(
    manager: ISRManager | None = None,
    *,
    shell: str | None = None,
) -> Starlette:
    """Create the dedicated ISR page-server ASGI app.

    Serves documents via ISR (nginx ``proxy_cache`` is expected in front for
    edge caching), falling back to the SPA shell on a miss/render failure, and
    exposes ``POST /_isr/revalidate`` for on-demand invalidation.  The
    revalidation endpoint requires a matching ``X-Reflex-ISR-Token`` header when
    the ``REFLEX_ISR_REVALIDATE_TOKEN`` env var is set.

    Run in production as an app factory, e.g.
    ``granian --factory reflex.isr:create_isr_app``.

    Args:
        manager: The ISR manager (defaults to one built from config).
        shell: The SPA shell HTML (defaults to reading the compiled build).

    Returns:
        A Starlette app.
    """
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import HTMLResponse, JSONResponse, Response
    from starlette.routing import Route

    mgr = manager if manager is not None else create_manager()
    shell_html = shell if shell is not None else _load_shell()
    revalidate_token = os.environ.get("REFLEX_ISR_REVALIDATE_TOKEN")

    async def serve(request: Request) -> Response:
        html = await mgr.get_html(request.url.path)
        if html is not None:
            return HTMLResponse(html)
        if shell_html is not None:
            # Miss/failure: serve the SPA shell so the client hydrates.
            return HTMLResponse(shell_html)
        return Response("Not found", status_code=404)

    async def revalidate(request: Request) -> Response:
        if revalidate_token and (
            request.headers.get("x-reflex-isr-token") != revalidate_token
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
        """Close the renderer's pooled HTTP client on shutdown, if any."""
        try:
            yield
        finally:
            aclose = getattr(mgr.renderer, "aclose", None)
            if aclose is not None:
                await aclose()

    return Starlette(
        routes=[
            Route("/_isr/revalidate", revalidate, methods=["POST"]),
            Route("/{path:path}", serve, methods=["GET"]),
        ],
        lifespan=_lifespan,
    )
