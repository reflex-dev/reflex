"""The endpoints for an app's connections to third-party services."""

from __future__ import annotations

import builtins
import uuid
from typing import TYPE_CHECKING, Any

from reflex_build_sdk._base import path_segment
from reflex_build_sdk.types import (
    ConnectionProvider,
    ConnectionStatus,
    ConnectLink,
    Credential,
)

if TYPE_CHECKING:
    from reflex_build_sdk._async._client import AsyncReflexCloud

# Names whose connection a request acts on: absent, a route acts on the app's own.
_END_USER_HEADER = "X-End-User"


def _end_user_headers(end_user: str | None) -> dict[str, str] | None:
    """Build the headers naming whose connection to act on.

    Args:
        end_user: The user, or None for the app's own connection.

    Returns:
        The headers, or None to send none: the header must be absent rather than
        empty, since the API reads an absent one as the app's own connection.
    """
    return None if end_user is None else {_END_USER_HEADER: end_user}


class AsyncConnections:
    """Call third-party services an app is connected to, without holding their keys.

    Reflex Cloud keeps the credentials and hands out a live one per call, so an app
    stores none. A connection belongs either to the app itself or to one of its
    users, named by ``end_user``.

    Every method needs the app's own access token, which a deployed app is started
    with, so a client built with no arguments inside a running app is already the
    right one. A personal token is refused with ``PermissionDeniedError``. While
    connections are switched off for a deployment, every method raises
    ``NotFoundError``.

    Refusals name their condition in ``APIStatusError.code``, e.g.
    ``"not_connected"``, ``"connection_gone"`` for a connection the provider no
    longer honours, or ``"unsupported_credential"``.
    """

    def __init__(self, client: AsyncReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client

    def _path(self, app_id: uuid.UUID | str, provider: str, suffix: str = "") -> str:
        """Build the path of one provider's connection endpoint.

        Args:
            app_id: The app.
            provider: The provider.
            suffix: The rest of the path, e.g. ``"/credential"``.

        Returns:
            The path.
        """
        return (
            f"apps/{path_segment(app_id)}/connections/{path_segment(provider)}{suffix}"
        )

    async def providers(self) -> builtins.list[ConnectionProvider]:
        """List the third-party services apps can connect to.

        Returns:
            The providers.
        """
        return await self._client._request(
            "GET", "connections/providers", builtins.list[ConnectionProvider]
        )

    async def list(self, app_id: uuid.UUID | str) -> builtins.list[ConnectionStatus]:
        """List the providers an app itself is connected to.

        Args:
            app_id: The app.

        Returns:
            One status per provider the app has ever connected.
        """
        return await self._client._request(
            "GET",
            f"apps/{path_segment(app_id)}/connections",
            builtins.list[ConnectionStatus],
        )

    async def status(
        self,
        app_id: uuid.UUID | str,
        provider: str,
        *,
        end_user: str | None = None,
    ) -> ConnectionStatus:
        """Get whether an app, or one of its users, is connected to a provider.

        Args:
            app_id: The app.
            provider: The provider, from ``providers``.
            end_user: The user whose connection to read. Defaults to the app's own.

        Returns:
            The status.
        """
        return await self._client._request(
            "GET",
            self._path(app_id, provider, "/status"),
            ConnectionStatus,
            extra_headers=_end_user_headers(end_user),
        )

    async def credential(
        self,
        app_id: uuid.UUID | str,
        provider: str,
        *,
        end_user: str | None = None,
    ) -> Credential:
        """Get a live credential to call a provider with.

        Read it for each call rather than storing it: it is refreshed as it is
        handed out, so a stored copy outlives what the provider accepts.

        Args:
            app_id: The app.
            provider: The provider.
            end_user: The user whose connection to use. Defaults to the app's own.

        Returns:
            The credential.
        """
        return await self._client._request(
            "GET",
            self._path(app_id, provider, "/credential"),
            Credential,
            extra_headers=_end_user_headers(end_user),
        )

    async def connect_link(
        self,
        app_id: uuid.UUID | str,
        provider: str,
        *,
        end_user: str | None = None,
        return_to: str | None = None,
    ) -> ConnectLink:
        """Start connecting a provider, and get the page to send someone to.

        Args:
            app_id: The app.
            provider: The provider.
            end_user: The user connecting their own account. Defaults to connecting
                the app's own.
            return_to: Where to send the browser once the provider is connected.

        Returns:
            The link, which expires.
        """
        body: dict[str, Any] = {"return_to": return_to}
        # Two routes, one for the app's own connection and one for a user's.
        suffix = "/authorize" if end_user is None else "/session"
        return await self._client._request(
            "POST",
            self._path(app_id, provider, suffix),
            ConnectLink,
            json=body,
            extra_headers=_end_user_headers(end_user),
        )

    async def disconnect(
        self,
        app_id: uuid.UUID | str,
        provider: str,
        *,
        end_user: str | None = None,
    ) -> None:
        """Forget a connection, and end it at the provider.

        Args:
            app_id: The app.
            provider: The provider.
            end_user: The user whose connection to end. Defaults to the app's own.
        """
        if end_user is None:
            await self._client._request("DELETE", self._path(app_id, provider), None)
            return
        await self._client._request(
            "POST",
            self._path(app_id, provider, "/disconnect"),
            None,
            extra_headers=_end_user_headers(end_user),
        )
