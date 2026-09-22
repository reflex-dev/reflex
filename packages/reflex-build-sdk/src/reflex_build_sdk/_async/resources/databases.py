"""The managed database endpoints."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from reflex_build_sdk._base import path_segment
from reflex_build_sdk.types import ManagedDatabase

if TYPE_CHECKING:
    from reflex_build_sdk._async._client import AsyncReflexBuild


@dataclass(frozen=True, slots=True, kw_only=True)
class _NoDatabase:
    """The body the database route answers with for an app without one."""

    has_database: Literal[False]


@dataclass(frozen=True, slots=True, kw_only=True)
class _DatabaseDeletion:
    """The body of a database deletion."""

    deleted: bool


class AsyncDatabase:
    """Give apps a Postgres database hosted by Reflex Build.

    Every environment of an app uses the same database. Its connection strings are
    set as secrets, ``DATABASE_URL`` among them, and take effect from each
    environment's next deployment.
    """

    def __init__(self, client: AsyncReflexBuild) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client

    async def get(self, app_id: uuid.UUID | str) -> ManagedDatabase | None:
        """Get an app's managed database.

        Args:
            app_id: The app.

        Returns:
            The database, or None if the app has none.
        """
        database = await self._client._request(  # ty:ignore[no-matching-overload]
            "GET",
            f"apps/{path_segment(app_id)}/database",
            ManagedDatabase | _NoDatabase,
        )
        return database if isinstance(database, ManagedDatabase) else None

    async def create(self, app_id: uuid.UUID | str) -> ManagedDatabase:
        """Create an app's managed database, or return the one it has.

        Sets the database's connection strings as secrets in every environment of
        the app. Needs a token with full access: tokens from ``reflex login`` are
        refused with ``NotFoundError``.

        Args:
            app_id: The app. An app with its own ``DATABASE_URL`` secret is refused.

        Returns:
            The database.
        """
        # Creating the database again converges on the existing one.
        return await self._client._request(
            "POST",
            f"apps/{path_segment(app_id)}/database",
            ManagedDatabase,
            idempotent=True,
        )

    async def delete(self, app_id: uuid.UUID | str) -> bool:
        """Permanently delete an app's managed database and all its data.

        Also deletes the database connection secrets, ``DATABASE_URL`` among them,
        from every environment of the app, even if the app had no managed database.
        Running deployments are not restarted and lose their connection. Needs a
        token with full access: tokens from ``reflex login`` are refused with
        ``NotFoundError``.

        Args:
            app_id: The app.

        Returns:
            Whether the app had a managed database.
        """
        deletion = await self._client._request(
            "DELETE", f"apps/{path_segment(app_id)}/database", _DatabaseDeletion
        )
        return deletion.deleted
