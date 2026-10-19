# Generated from packages/reflex-build-sdk/src/reflex_build_sdk/_async/resources/sign_in.py by packages/reflex-build-sdk/scripts/unasync.py. Do not edit.
"""The endpoints for signing an app's users in."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from reflex_build_sdk._base import path_segment
from reflex_build_sdk.transports import Response
from reflex_build_sdk.types import (
    Audience,
    AudienceChange,
    EndUserBlock,
    EndUserExport,
    EndUserPage,
    InviteRemoval,
    SignInInvite,
    SignInStatus,
)

if TYPE_CHECKING:
    from reflex_build_sdk._sync._client import ReflexBuild

# The file name the user export is served under when it stops at its row limit.
_TRUNCATED_EXPORT = "app-users.partial.csv"


@dataclass(frozen=True, slots=True, kw_only=True)
class _EnabledSignIn:
    """The body of enabling sign-in."""

    issuer: str
    client_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class _SignInDisabled:
    """The body of disabling sign-in."""

    deleted: bool


class SignIn:
    """Sign an app's users in with their Reflex accounts.

    Reflex Build is the OpenID Connect provider: the app uses ``rxe.AuthPlugin``
    from ``reflex-enterprise`` and reads its settings from its secrets. Every method
    but ``get`` and ``get_audience`` needs edit access to the app and a token with
    full access; tokens from ``reflex login`` are refused with ``NotFoundError``.
    """

    def __init__(self, client: ReflexBuild) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client

    def _path(self, app_id: uuid.UUID | str, suffix: str = "") -> str:
        """Build the path of an app's sign-in endpoint.

        Args:
            app_id: The app.
            suffix: The rest of the path, e.g. ``"/users"``.

        Returns:
            The path.
        """
        return f"apps/{path_segment(app_id)}/auth{suffix}"

    def get(self, app_id: uuid.UUID | str) -> SignInStatus:
        """Get whether an app signs its users in.

        Args:
            app_id: The app.

        Returns:
            Whether sign-in is enabled, and its OpenID Connect settings.
        """
        return self._client._request("GET", self._path(app_id), SignInStatus)

    def enable(self, app_id: uuid.UUID | str) -> SignInStatus:
        """Set up sign-in for an app, or repair it.

        Sets the OpenID Connect settings as secrets in every environment of the app,
        where its next deployment picks them up. An app with its own identity
        provider is refused with ``ConflictError``.

        Args:
            app_id: The app.

        Returns:
            The sign-in settings.
        """
        enabled = self._client._request(
            "POST", self._path(app_id), _EnabledSignIn, idempotent=True
        )
        return SignInStatus(
            enabled=True,
            issuer=enabled.issuer,
            client_id=enabled.client_id,
            client_enabled=True,
        )

    def disable(self, app_id: uuid.UUID | str) -> bool:
        """Stop signing an app's users in, ending their sessions.

        Removes the sign-in settings from the app's secrets. The app's users,
        invitations and audience are kept for if it is enabled again.

        Args:
            app_id: The app.

        Returns:
            Whether sign-in was enabled.
        """
        disabled = self._client._request("DELETE", self._path(app_id), _SignInDisabled)
        return disabled.deleted

    def list_users(
        self,
        app_id: uuid.UUID | str,
        *,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> EndUserPage:
        """List a page of the Reflex accounts that have signed in to an app.

        Pages shift as users sign in, so use ``export_users`` to read them all.

        Args:
            app_id: The app.
            search: Only list users whose email address contains this text, ignoring
                case. Users who did not share their address never match.
            limit: How many users to list, from 1 to 200.
            offset: How many users to skip.

        Returns:
            The page of users, and how many match.
        """
        return self._client._request(
            "GET",
            self._path(app_id, "/users"),
            EndUserPage,
            params={"search": search, "limit": limit, "offset": offset},
        )

    def export_users(self, app_id: uuid.UUID | str) -> EndUserExport:
        """Export every user of an app as CSV, oldest first.

        Args:
            app_id: The app.

        Returns:
            The CSV, and whether it stops at its limit of 20,000 users.
        """
        response = self._client._request(
            "GET", self._path(app_id, "/users/export"), Response
        )
        # Truncation is only signalled by the file name.
        disposition = response.headers.get("content-disposition", "")
        return EndUserExport(
            csv=response.text, truncated=_TRUNCATED_EXPORT in disposition
        )

    def block_user(
        self, app_id: uuid.UUID | str, user_id: uuid.UUID | str
    ) -> EndUserBlock:
        """Stop a user from signing in to an app, and end their sessions.

        Args:
            app_id: The app.
            user_id: The user's Reflex account id.

        Returns:
            The user's standing.
        """
        return self._client._request(
            "POST",
            self._path(app_id, f"/users/{path_segment(user_id)}/block"),
            EndUserBlock,
            idempotent=True,
        )

    def unblock_user(
        self, app_id: uuid.UUID | str, user_id: uuid.UUID | str
    ) -> EndUserBlock:
        """Let a blocked user sign in to an app again.

        Args:
            app_id: The app.
            user_id: The user's Reflex account id.

        Returns:
            The user's standing. Check ``blocked``: the user stays blocked if their
            remaining sessions could not be ended first.
        """
        return self._client._request(
            "POST",
            self._path(app_id, f"/users/{path_segment(user_id)}/unblock"),
            EndUserBlock,
            idempotent=True,
        )

    def get_audience(self, app_id: uuid.UUID | str) -> Audience:
        """Get who may sign in to an app.

        Args:
            app_id: The app.

        Returns:
            The audience, with the invited addresses for callers who can edit the app.
        """
        return self._client._request("GET", self._path(app_id, "/audience"), Audience)

    def set_audience(
        self,
        app_id: uuid.UUID | str,
        audience: Literal["public", "members", "invited", "owner_only"],
    ) -> AudienceChange:
        """Choose who may sign in to an app.

        Anything but ``"public"`` needs the Pro or Enterprise plan. Restricting the
        audience ends every session of the app; users who may still sign in are
        signed back in without noticing.

        Args:
            app_id: The app, with sign-in enabled.
            audience: ``"public"``: anyone with a Reflex account; ``"members"``:
                members of the app's project; ``"invited"``: invited addresses and
                the app's editors; ``"owner_only"``: the app's editors.

        Returns:
            The audience, and how many sessions were ended.
        """
        return self._client._request(
            "POST",
            self._path(app_id, "/audience"),
            AudienceChange,
            json={"audience": audience},
            idempotent=True,
        )

    def invite(self, app_id: uuid.UUID | str, email: str) -> SignInInvite:
        """Invite an email address to sign in to an app.

        Invitations only apply while the audience is ``"invited"``, and no email is
        sent: tell the person yourself. Needs the Pro or Enterprise plan; an app
        invites at most 500 addresses.

        Args:
            app_id: The app, with sign-in enabled.
            email: The address.

        Returns:
            The invitation.
        """
        return self._client._request(
            "POST",
            self._path(app_id, "/invites"),
            SignInInvite,
            json={"email": email},
            idempotent=True,
        )

    def uninvite(self, app_id: uuid.UUID | str, email: str) -> InviteRemoval:
        """Withdraw an invitation to sign in to an app.

        Ends the sessions of the account with the address, unless the app still lets
        it sign in.

        Args:
            app_id: The app.
            email: The address.

        Returns:
            The normalized address, and how many sessions were ended.
        """
        return self._client._request(
            "DELETE",
            self._path(app_id, "/invites"),
            InviteRemoval,
            params={"email": email},
            # Withdrawing an address that is not invited succeeds.
            idempotent=True,
        )
