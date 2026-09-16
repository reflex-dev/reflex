"""A transport built on aiohttp."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from reflex_sdk.transports._base import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_TIMEOUT,
    Request,
    Response,
    TransportError,
)

if TYPE_CHECKING:
    import aiohttp


class AiohttpTransport:
    """Sends the asynchronous client's requests with an ``aiohttp.ClientSession``.

    aiohttp is imported when the transport first sends a request rather than with
    the SDK: importing it costs more than the rest of the SDK together, and
    synchronous callers never use it.
    """

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Create the transport.

        Args:
            session: The session to send requests with, e.g. to configure proxies.
                The caller keeps ownership of it: closing the transport leaves it open.
                Defaults to a session the transport creates on first use and closes.
        """
        self._owns_session = session is None
        self._session = session

    def _get_session(self) -> aiohttp.ClientSession:
        # Created on first use because a session binds to the running event loop.
        if self._session is None:
            import aiohttp

            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(
                    total=None,
                    sock_connect=DEFAULT_CONNECT_TIMEOUT,
                    sock_read=DEFAULT_TIMEOUT,
                )
            )
        return self._session

    async def send(self, request: Request) -> Response:
        """Send a request and read the whole response.

        Args:
            request: The request.

        Returns:
            The response, whatever its status code.

        Raises:
            TransportError: If the request failed without getting a response.
        """
        import aiohttp

        session = self._get_session()
        options: dict[str, Any] = {}
        if request.timeout is not None:
            # Per operation, like httpx: a total would cut off long uploads.
            options["timeout"] = aiohttp.ClientTimeout(
                total=None, sock_connect=request.timeout, sock_read=request.timeout
            )
        if not any(name.lower() == "content-type" for name in request.headers):
            # aiohttp labels any body application/octet-stream; httpx sends none,
            # and a presigned upload may be signed without one.
            options["skip_auto_headers"] = ("Content-Type",)
        try:
            async with session.request(
                request.method,
                request.url,
                headers=request.headers,
                data=request.content,
                # Redirects and error statuses are returned for the client to
                # handle, like the httpx transport does, even from a session
                # configured to follow or raise on them.
                allow_redirects=False,
                raise_for_status=False,
                **options,
            ) as response:
                content = await response.read()
        except aiohttp.ConnectionTimeoutError as ex:
            msg = str(ex) or "connection timed out"
            raise TransportError(
                msg, request=request, sent=False, timed_out=True
            ) from ex
        except aiohttp.ClientConnectorError as ex:
            raise TransportError(str(ex), request=request, sent=False) from ex
        except (aiohttp.ServerTimeoutError, asyncio.TimeoutError) as ex:
            msg = str(ex) or "timed out"
            raise TransportError(
                msg, request=request, sent=True, timed_out=True
            ) from ex
        except aiohttp.ClientError as ex:
            msg = str(ex) or type(ex).__name__
            raise TransportError(msg, request=request, sent=True) from ex
        return Response(
            request=request,
            status_code=response.status,
            reason_phrase=response.reason or "",
            headers={name.lower(): value for name, value in response.headers.items()},
            content=content,
        )

    async def aclose(self) -> None:
        """Close the session, unless it was passed in."""
        if self._owns_session and self._session is not None:
            await self._session.close()
