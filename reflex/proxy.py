"""Handle proxying frontend requests from the backend server."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from urllib.parse import urlparse

from fastapi import FastAPI
from starlette.types import ASGIApp

from .config import get_config
from .utils import console

try:
    from asgiproxy.config import BaseURLProxyConfigMixin, ProxyConfig
    from asgiproxy.context import ProxyContext
    from asgiproxy.simple_proxy import make_simple_proxy_app
except ImportError:

    @asynccontextmanager
    async def proxy_middleware(*args, **kwargs) -> AsyncGenerator[None, None]:
        """A no-op proxy middleware for when asgiproxy is not installed.

        Args:
            *args: The positional arguments.
            **kwargs: The keyword arguments.

        Yields:
            None
        """
        yield
else:

    def _get_proxy_app_with_context(frontend_host: str) -> tuple[ProxyContext, ASGIApp]:
        """Get the proxy app with the given frontend host.

        Args:
            frontend_host: The frontend host to proxy requests to.

        Returns:
            The proxy context and app.
        """

        class LocalProxyConfig(BaseURLProxyConfigMixin, ProxyConfig):
            upstream_base_url = frontend_host
            rewrite_host_header = urlparse(upstream_base_url).netloc

        proxy_context = ProxyContext(LocalProxyConfig())
        proxy_app = make_simple_proxy_app(proxy_context)
        return proxy_context, proxy_app

    @asynccontextmanager
    async def proxy_middleware(  # pyright: ignore[reportGeneralTypeIssues]
        api: FastAPI,
    ) -> AsyncGenerator[None, None]:
        """A middleware to proxy requests to the separate frontend server.

        The proxy is installed on the / endpoint of the FastAPI instance.

        Args:
            api: The FastAPI instance.

        Yields:
            None
        """
        config = get_config()
        backend_port = config.backend_port
        frontend_host = f"http://localhost:{config.frontend_port}"
        proxy_context, proxy_app = _get_proxy_app_with_context(frontend_host)
        api.mount("/", proxy_app)
        console.debug(
            f"Proxying '/' requests on port {backend_port} to {frontend_host}"
        )
        async with proxy_context:
            yield
