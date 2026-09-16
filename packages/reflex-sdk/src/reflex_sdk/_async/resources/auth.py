"""The identity and access token endpoints."""

from __future__ import annotations

import asyncio
import builtins
import dataclasses
import os
import uuid
from time import monotonic
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from reflex_sdk._base import path_segment
from reflex_sdk._errors import (
    LoginDeniedError,
    LoginTimeoutError,
    NotFoundError,
    PermissionDeniedError,
)
from reflex_sdk.types import AccessScope, LoginRequest, Me, Token

if TYPE_CHECKING:
    from reflex_sdk._async._client import AsyncReflexCloud

# How often finish_login() checks whether a login was approved, in seconds.
_LOGIN_POLL_INTERVAL = 1.0


class AsyncTokens:
    """Manage the caller's access tokens."""

    def __init__(self, client: AsyncReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client

    async def create(
        self,
        name: str,
        *,
        expires_in_days: int | None = None,
        access: AccessScope | None = None,
    ) -> str:
        """Create an access token in the organization of the calling token.

        Args:
            name: A name for the token, unique among the caller's live tokens.
            expires_in_days: The token lifetime in days. Defaults to the server default,
                capped by the organization's plan.
            access: Restricts what the token can do. Defaults to full access.

        Returns:
            The new token. It is only returned once, so store it securely.
        """
        body: dict[str, Any] = {"name": name, "expiration": expires_in_days}
        if access is not None:
            body["access"] = dataclasses.asdict(access)
        return await self._client._request("POST", "user/token", str, json=body)

    async def list(self) -> builtins.list[Token]:
        """List the caller's live and expired access tokens, without their values.

        Returns:
            The tokens, live ones first.
        """
        return await self._client._request("GET", "user/token", builtins.list[Token])

    async def delete(self, name: str) -> None:
        """Revoke one of the caller's live access tokens by name.

        Args:
            name: The name of the token.
        """
        await self._client._request("DELETE", f"user/token/{path_segment(name)}", None)


class AsyncAuth:
    """The identity of the access token, and the access token endpoints."""

    # Manage the caller's access tokens.
    tokens: AsyncTokens

    def __init__(self, client: AsyncReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client
        self.tokens = AsyncTokens(client)

    async def me(self, *, source: str | None = None) -> Me:
        """Validate the access token and get the identity it authenticates as.

        Args:
            source: The product the user is logging in through, e.g. ``"reflex"``,
                recorded as a login for product analytics. Defaults to recording
                nothing.

        Returns:
            The user, organization and plan behind the token.
        """
        return await self._client._request(
            "POST", "authenticate/me", Me, params={"source": source}
        )

    def begin_login(self, *, ui_url: str | None = None) -> LoginRequest:
        """Start a browser login, which needs no access token.

        Show or open ``url`` for the user to approve the login, then collect the
        token with ``finish_login``.

        Args:
            ui_url: The Reflex Cloud web app URL. Defaults to the ``REFLEX_CLOUD_URL``
                environment variable, then to the client's ``base_url``.

        Returns:
            The login and the URL to approve it at.
        """
        base = (
            ui_url or os.environ.get("REFLEX_CLOUD_URL") or self._client.base_url
        ).rstrip("/")
        request_id = uuid.uuid4().hex
        return LoginRequest(
            request_id=request_id,
            url=f"{base}/cli/login?{urlencode({'request_id': request_id})}",
        )

    async def finish_login(
        self,
        login: LoginRequest,
        *,
        timeout: float | None = None,
        poll_interval: float = _LOGIN_POLL_INTERVAL,
    ) -> str:
        """Wait for the user to approve a browser login, then collect its token.

        The token can be collected once. Save it with ``credentials.save_token`` for
        clients created later to use.

        Args:
            login: The login from ``begin_login``.
            timeout: How long to wait for approval, in seconds. Defaults to no limit.
            poll_interval: How long to wait between checks, in seconds.

        Returns:
            The access token.

        Raises:
            LoginDeniedError: If the user denied the login.
            LoginTimeoutError: If the login was not approved before ``timeout``.
        """
        deadline = None if timeout is None else monotonic() + timeout
        while True:
            try:
                approval = await self._client._request(
                    "GET",
                    "cli/token",
                    dict[str, str],
                    params={"request_id": login.request_id},
                    authenticated=False,
                )
            except NotFoundError:
                # Not approved yet.
                pass
            except PermissionDeniedError as ex:
                msg = "the login was denied"
                raise LoginDeniedError(msg) from ex
            else:
                return approval["token_id"]
            delay = poll_interval
            if deadline is not None:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    msg = "the login was not approved in time"
                    raise LoginTimeoutError(msg)
                delay = min(delay, remaining)
            await asyncio.sleep(delay)
