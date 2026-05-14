"""Frontend serving: SPA-aware static-files mount and routes manifest."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

from reflex_base import constants
from reflex_base.config import get_config
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

# File extensions that mark a request as a static asset rather than a page
# navigation. Asset misses are left as 404 instead of being routed through the
# SPA fallback machinery.
_ASSET_EXTENSIONS = frozenset({
    "js",
    "mjs",
    "cjs",
    "css",
    "map",
    "json",
    "ico",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "svg",
    "webp",
    "avif",
    "woff",
    "woff2",
    "ttf",
    "otf",
    "eot",
    "mp4",
    "webm",
    "mp3",
    "wav",
    "ogg",
    "wasm",
    "pdf",
    "txt",
    "xml",
})


def _is_html_navigation(path: str) -> bool:
    """Return True if path looks like a page navigation rather than an asset.

    Args:
        path: The request path (without query string).

    Returns:
        True for extension-less paths and `.html` paths; False for typical
        static-asset extensions.
    """
    last = path.replace(os.sep, "/").rsplit("/", 1)[-1]
    if "." not in last:
        return True
    return last.rsplit(".", 1)[-1].lower() not in _ASSET_EXTENSIONS


class ReflexStaticFiles(StaticFiles):
    """StaticFiles that returns the right HTTP status for SPA routes.

    Starlette's StaticFiles with html=True serves 404.html with status 404
    for any path that doesn't exist on disk. That's wrong for valid dynamic
    routes (e.g. /blog/[slug]) where the SPA shell is the intended response.
    This subclass consults a route resolver on a miss: if the path matches a
    defined route, the response status is rewritten to 200 (the body is
    already the SPA shell, since the build step copies __spa-fallback.html /
    index.html to 404.html). Otherwise the 404 is preserved so true misses
    surface as real 404s.
    """

    def __init__(
        self,
        *args: Any,
        route_resolver: Callable[[str], str | None] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the static files handler.

        Args:
            *args: Positional args forwarded to ``StaticFiles``.
            route_resolver: Callable returning the matched route for a
                given path, or None if the path doesn't match any defined
                route.
            **kwargs: Keyword args forwarded to ``StaticFiles``.
        """
        super().__init__(*args, **kwargs)
        self._route_resolver = route_resolver

    async def get_response(self, path: str, scope: Scope) -> Response:
        """Serve a static file or fall back to the SPA shell with the right status.

        Args:
            path: The relative path under the mount.
            scope: The ASGI request scope.

        Returns:
            The static-file response, with the status rewritten to 200 if
            the path matches a defined dynamic route.
        """
        response = await super().get_response(path, scope)
        if (
            response.status_code != 404
            or self._route_resolver is None
            or not _is_html_navigation(path)
        ):
            return response
        normalized = "/" + path.replace(os.sep, "/").lstrip("/")
        if self._route_resolver(normalized) is not None:
            response.status_code = 200
        return response


def _load_routes_manifest() -> Callable[[str], str | None] | None:
    """Build a route resolver from the on-disk routes manifest, if present.

    Returns:
        A resolver callable, or None if the manifest is missing or empty.
    """
    from reflex.route import get_router
    from reflex.utils import prerequisites

    manifest_path = prerequisites.get_web_dir() / constants.Dirs.ROUTES_MANIFEST
    if not manifest_path.exists():
        return None
    try:
        routes = json.loads(manifest_path.read_text())
    except (OSError, ValueError):
        return None
    if not routes:
        return None
    return get_router(list(routes))


def get_frontend_mount(
    route_resolver: Callable[[str], str | None] | None = None,
):
    """Get a Starlette Mount for the compiled frontend static files.

    Args:
        route_resolver: Optional callable that returns the matching route
            for a given path, or None if the path doesn't match any defined
            route. When omitted, falls back to the on-disk routes manifest
            written at compile time. When neither is available, dynamic
            routes that don't have a prerendered file will return 404.

    Returns:
        A Mount serving the compiled frontend static files.
    """
    from starlette.routing import Mount

    from reflex.utils import prerequisites

    config = get_config()
    if route_resolver is None:
        route_resolver = _load_routes_manifest()

    return Mount(
        config.prepend_frontend_path("/"),
        app=ReflexStaticFiles(
            directory=prerequisites.get_web_dir()
            / constants.Dirs.STATIC
            / config.frontend_path.strip("/"),
            html=True,
            route_resolver=route_resolver,
        ),
        name="frontend",
    )


def _frontend_prod_app():
    """Create a Starlette app that serves the compiled frontend static files.

    Returns:
        A Starlette ASGI app serving static files.
    """
    from starlette.applications import Starlette

    return Starlette(routes=[get_frontend_mount()])
