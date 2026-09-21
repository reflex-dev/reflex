"""Permanent redirects for renamed documentation pages."""

from collections.abc import Sequence

from starlette.responses import RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class DocsRedirectMiddleware:
    """Resolve legacy documentation URLs before rendering the frontend."""

    def __init__(
        self,
        app: ASGIApp,
        redirects: Sequence[tuple[str, str]],
        frontend_path: str,
    ) -> None:
        """Build a lookup of public legacy URLs and their canonical destinations.

        Args:
            app: The wrapped application.
            redirects: App-relative source and destination routes.
            frontend_path: The public mount prefix.
        """
        self.app = app
        prefix = frontend_path.rstrip("/")
        self.redirects = {
            prefix + source.rstrip("/"): prefix + target for source, target in redirects
        }

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Redirect known GET/HEAD routes and pass other requests through.

        Args:
            scope: The ASGI connection scope.
            receive: The ASGI receive callable.
            send: The ASGI send callable.
        """
        if scope["type"] == "http" and scope["method"] in {"GET", "HEAD"}:
            target = self.redirects.get(scope["path"].rstrip("/"))
            if target is not None:
                if query := scope.get("query_string", b""):
                    target += "?" + query.decode("latin-1")
                await RedirectResponse(target, status_code=301)(scope, receive, send)
                return
        await self.app(scope, receive, send)
