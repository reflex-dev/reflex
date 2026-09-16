# Generated from packages/reflex-sdk/src/reflex_sdk/_async/resources/auth.py by scripts/unasync_reflex_sdk.py. Do not edit.
"""The identity and access token endpoints."""

from __future__ import annotations

import builtins
import dataclasses
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from reflex_sdk.types import AccessScope, Me, Token

if TYPE_CHECKING:
    from reflex_sdk._sync._client import ReflexCloud


class Tokens:
    """Manage the caller's access tokens."""

    def __init__(self, client: ReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client

    def create(
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
        return self._client._request("POST", "user/token", str, json=body)

    def list(self) -> builtins.list[Token]:
        """List the caller's live and expired access tokens, without their values.

        Returns:
            The tokens, live ones first.
        """
        return self._client._request("GET", "user/token", builtins.list[Token])

    def delete(self, name: str) -> None:
        """Revoke one of the caller's live access tokens by name.

        Args:
            name: The name of the token.
        """
        self._client._request("DELETE", f"user/token/{quote(name, safe='')}", None)


class Auth:
    """The identity of the access token, and the access token endpoints."""

    # Manage the caller's access tokens.
    tokens: Tokens

    def __init__(self, client: ReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client
        self.tokens = Tokens(client)

    def me(self) -> Me:
        """Validate the access token and get the identity it authenticates as.

        Returns:
            The user, organization and plan behind the token.
        """
        return self._client._request("POST", "authenticate/me", Me)
