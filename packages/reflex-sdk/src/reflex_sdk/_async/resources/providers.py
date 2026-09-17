"""The cloud provider endpoints."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from reflex_sdk._base import path_segment
from reflex_sdk.types import CloudRunManifest, GcpStatus, ProviderAccount

if TYPE_CHECKING:
    from reflex_sdk._async._client import AsyncReflexCloud


class AsyncProviders:
    """Read the cloud providers an organization deploys apps to."""

    def __init__(self, client: AsyncReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client

    async def gcp_status(self, org_id: uuid.UUID | str) -> GcpStatus:
        """Get whether an organization can deploy apps to its own Google Cloud.

        Any member of the organization can read this.

        Args:
            org_id: The organization, e.g. ``auth.me().org_id``.

        Returns:
            Whether Google Cloud deploys are configured and allowed, and the
            connections to deploy to.
        """
        return await self._client._request(
            "GET",
            f"orgs/{path_segment(org_id)}/provider-accounts/gcp/status",
            GcpStatus,
        )

    async def accounts(self, org_id: uuid.UUID | str) -> list[ProviderAccount]:
        """List the cloud provider accounts connected to an organization.

        Needs permission to manage the organization's cloud providers, and a token
        with full access: restricted tokens, including those from ``reflex login``,
        are refused. ``gcp_status`` lists the connections for any member.

        Args:
            org_id: The organization.

        Returns:
            The accounts.
        """
        return await self._client._request(
            "GET",
            f"orgs/{path_segment(org_id)}/provider-accounts",
            list[ProviderAccount],
        )

    async def cloud_run_manifest(self) -> CloudRunManifest:
        """Get the Dockerfile and script to deploy an app to Google Cloud Run yourself.

        Needs an organization on the Enterprise plan.

        Returns:
            The Dockerfile and deploy script.
        """
        return await self._client._request(
            "GET", "cli/gcp-cloud-run-manifest", CloudRunManifest
        )
