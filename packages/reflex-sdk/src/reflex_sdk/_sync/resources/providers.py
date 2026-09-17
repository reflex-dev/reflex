# Generated from packages/reflex-sdk/src/reflex_sdk/_async/resources/providers.py by packages/reflex-sdk/scripts/unasync.py. Do not edit.
"""The cloud provider endpoints."""

from __future__ import annotations

import builtins
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from reflex_sdk._base import path_segment
from reflex_sdk.types import (
    CloudRunManifest,
    GcpBlockingApp,
    GcpKeyRotation,
    GcpStatus,
    GcpVerification,
    ProviderAccount,
)

if TYPE_CHECKING:
    from reflex_sdk._sync._client import ReflexCloud


@dataclass(frozen=True, slots=True, kw_only=True)
class _GcpSave:
    """The body of saving a Google Cloud connection."""

    skipped_checks: list[str]


def _key_text(service_account_key: str | Mapping[str, Any]) -> str:
    # The API takes the key file's contents as a string.
    return (
        service_account_key
        if isinstance(service_account_key, str)
        else json.dumps(dict(service_account_key))
    )


def _gcp_path(org_id: uuid.UUID | str, suffix: str = "") -> str:
    return f"orgs/{path_segment(org_id)}/provider-accounts/gcp{suffix}"


def _gcp_settings(
    *,
    runtime_service_account: str | None,
    ingress: str | None,
    vpc_connector: str | None,
    vpc_egress: str | None,
) -> dict[str, str | None]:
    return {
        "runtime_service_account": runtime_service_account,
        "ingress": ingress,
        "vpc_connector": vpc_connector,
        "vpc_egress": vpc_egress,
    }


class GcpConnections:
    """Manage the Google Cloud projects an organization deploys apps to.

    Connections verify their service account key's access when they are saved,
    which takes seconds, or minutes when Google is slow. Every method needs
    permission to manage the organization's cloud providers and a token with full
    access; tokens from ``reflex login`` are refused with ``PermissionDeniedError``.
    Adding and changing connections needs the Enterprise plan.
    """

    def __init__(self, client: ReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client

    def create(
        self,
        org_id: uuid.UUID | str,
        name: str,
        *,
        service_account_key: str | Mapping[str, Any],
        project_number: str,
        region: str,
        artifact_repo: str | None = None,
        runtime_service_account: str | None = None,
        ingress: str | None = None,
        vpc_connector: str | None = None,
        vpc_egress: str | None = None,
    ) -> builtins.list[str]:
        """Connect another Google Cloud project, after verifying the key's access.

        It becomes the default if the organization has none. Find its id with
        ``providers.gcp_status``.

        Args:
            org_id: The organization.
            name: The connection name: letters, digits, spaces, dots, dashes and
                underscores, starting with a letter or digit, and not ``"default"``.
            service_account_key: The service account's JSON key, as the key file's
                contents or parsed. The project is the key's.
            project_number: The project's number.
            region: The Cloud Run region, e.g. ``"us-central1"``.
            artifact_repo: The Artifact Registry repository to push images to.
                Defaults to ``"reflex-build-apps"``.
            runtime_service_account: The service account apps run as. Defaults to
                the project's default compute service account.
            ingress: Where apps accept traffic from: ``"all"`` (the default),
                ``"internal"`` or ``"internal-and-cloud-load-balancing"``.
            vpc_connector: The Serverless VPC Access connector apps reach private
                networks through, by name or full path.
            vpc_egress: Which traffic goes through the connector:
                ``"private-ranges-only"`` or ``"all-traffic"``.

        Returns:
            The names of the checks that could not run.
        """
        body: dict[str, Any] = {
            "name": name,
            "service_account_key": _key_text(service_account_key),
            "project_number": project_number,
            "region": region,
            **_gcp_settings(
                runtime_service_account=runtime_service_account,
                ingress=ingress,
                vpc_connector=vpc_connector,
                vpc_egress=vpc_egress,
            ),
        }
        if artifact_repo is not None:
            body["artifact_repo"] = artifact_repo
        saved = self._client._request(
            "POST", _gcp_path(org_id, "/connections"), _GcpSave, json=body
        )
        return saved.skipped_checks

    def update(
        self,
        org_id: uuid.UUID | str,
        connection_id: uuid.UUID | str,
        *,
        expected_project_id: str,
        expected_region: str,
        runtime_service_account: str | None = None,
        ingress: str | None = None,
        vpc_connector: str | None = None,
        vpc_egress: str | None = None,
    ) -> builtins.list[str]:
        """Change a connection's runtime identity and network settings.

        Settings not passed are kept, and ``""`` resets one to its default. Apps
        use the settings from their next deployment. Changing the runtime service
        account verifies the stored key's access again.

        Args:
            org_id: The organization.
            connection_id: The connection.
            expected_project_id: The connection's Google Cloud project id, so an edit
                made against another project is refused if it was reconnected.
            expected_region: The connection's region, likewise.
            runtime_service_account: The service account apps run as.
            ingress: Where apps accept traffic from.
            vpc_connector: The Serverless VPC Access connector; ``""`` also resets
                ``vpc_egress``.
            vpc_egress: Which traffic goes through the connector.

        Returns:
            The names of the checks that could not run.
        """
        settings = _gcp_settings(
            runtime_service_account=runtime_service_account,
            ingress=ingress,
            vpc_connector=vpc_connector,
            vpc_egress=vpc_egress,
        )
        saved = self._client._request(
            "PATCH",
            _gcp_path(org_id, f"/connections/{path_segment(connection_id)}"),
            _GcpSave,
            json={
                "expected_project_id": expected_project_id,
                "expected_region": expected_region,
                **{key: value for key, value in settings.items() if value is not None},
            },
            idempotent=True,
        )
        return saved.skipped_checks

    def rotate_key(
        self,
        org_id: uuid.UUID | str,
        connection_id: uuid.UUID | str,
        service_account_key: str | Mapping[str, Any],
    ) -> GcpKeyRotation:
        """Replace a connection's service account key, after verifying its access.

        The key must be for the connection's project. Delete the old key in Google
        Cloud afterwards: rotating does not revoke it.

        Args:
            org_id: The organization.
            connection_id: The connection.
            service_account_key: The new JSON key, as the key file's contents or
                parsed.

        Returns:
            The new and replaced keys.
        """
        return self._client._request(
            "POST",
            _gcp_path(org_id, f"/connections/{path_segment(connection_id)}/rotate-key"),
            GcpKeyRotation,
            json={"service_account_key": _key_text(service_account_key)},
        )

    def verify(
        self, org_id: uuid.UUID | str, connection_id: uuid.UUID | str
    ) -> GcpVerification:
        """Check that a connection's stored key can still deploy, changing nothing.

        Args:
            org_id: The organization.
            connection_id: The connection.

        Returns:
            Each check's outcome, and what is wrong.
        """
        return self._client._request(
            "POST",
            _gcp_path(org_id, f"/connections/{path_segment(connection_id)}/verify"),
            GcpVerification,
            idempotent=True,
        )

    def set_default(
        self, org_id: uuid.UUID | str, connection_id: uuid.UUID | str
    ) -> None:
        """Make a connection the one new apps deploy to unless told otherwise.

        Existing apps keep deploying where they do.

        Args:
            org_id: The organization.
            connection_id: The connection.
        """
        self._client._request(
            "POST",
            _gcp_path(org_id, f"/connections/{path_segment(connection_id)}/default"),
            None,
            idempotent=True,
        )

    def delete(self, org_id: uuid.UUID | str, connection_id: uuid.UUID | str) -> None:
        """Remove a connection that is not the default and no app uses.

        The key is not revoked in Google Cloud, and nothing deployed there is
        deleted.

        Args:
            org_id: The organization.
            connection_id: The connection.
        """
        self._client._request(
            "DELETE",
            _gcp_path(org_id, f"/connections/{path_segment(connection_id)}"),
            None,
        )


class Providers:
    """Manage the cloud providers an organization deploys apps to."""

    # Manage the Google Cloud projects an organization deploys apps to.
    gcp_connections: GcpConnections

    def __init__(self, client: ReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client
        self.gcp_connections = GcpConnections(client)

    def gcp_status(self, org_id: uuid.UUID | str) -> GcpStatus:
        """Get whether an organization can deploy apps to its own Google Cloud.

        Any member of the organization can read this.

        Args:
            org_id: The organization, e.g. ``auth.me().org_id``.

        Returns:
            Whether Google Cloud deploys are configured and allowed, and the
            connections to deploy to.
        """
        return self._client._request(
            "GET",
            f"orgs/{path_segment(org_id)}/provider-accounts/gcp/status",
            GcpStatus,
        )

    def accounts(self, org_id: uuid.UUID | str) -> list[ProviderAccount]:
        """List the cloud provider accounts connected to an organization.

        Needs permission to manage the organization's cloud providers, and a token
        with full access: restricted tokens, including those from ``reflex login``,
        are refused. ``gcp_status`` lists the connections for any member.

        Args:
            org_id: The organization.

        Returns:
            The accounts.
        """
        return self._client._request(
            "GET",
            f"orgs/{path_segment(org_id)}/provider-accounts",
            list[ProviderAccount],
        )

    def cloud_run_manifest(self) -> CloudRunManifest:
        """Get the Dockerfile and script to deploy an app to Google Cloud Run yourself.

        Needs an organization on the Enterprise plan.

        Returns:
            The Dockerfile and deploy script.
        """
        return self._client._request(
            "GET", "cli/gcp-cloud-run-manifest", CloudRunManifest
        )

    def connect_gcp(
        self,
        org_id: uuid.UUID | str,
        *,
        service_account_key: str | Mapping[str, Any],
        project_number: str,
        region: str,
        artifact_repo: str | None = None,
        runtime_service_account: str | None = None,
        ingress: str | None = None,
        vpc_connector: str | None = None,
        vpc_egress: str | None = None,
        relocate_from: Mapping[str, str] | None = None,
    ) -> builtins.list[str]:
        """Connect an organization's Google Cloud, or reconnect its default connection.

        Verifies the key's access first. Reconnecting replaces the default
        connection's key, repository and runtime service account, keeping network
        settings not passed. To replace only the key, use
        ``gcp_connections.rotate_key``. Needs the Enterprise plan, permission to
        manage the organization's cloud providers, and a token with full access.

        Args:
            org_id: The organization.
            service_account_key: The service account's JSON key, as the key file's
                contents or parsed. The project is the key's.
            project_number: The project's number.
            region: The Cloud Run region, e.g. ``"us-central1"``.
            artifact_repo: The Artifact Registry repository. Defaults to
                ``"reflex-build-apps"``.
            runtime_service_account: The service account apps run as. Defaults to
                the project's default compute service account.
            ingress: Where apps accept traffic from; ``""`` resets it to ``"all"``.
            vpc_connector: The Serverless VPC Access connector; ``""`` removes it.
            vpc_egress: Which traffic goes through the connector.
            relocate_from: Confirms moving the default connection to another
                project, region or repository: the ``relocation["from"]`` of the
                ``ConflictError`` detail that refused the move.

        Returns:
            The names of the checks that could not run.
        """
        body: dict[str, Any] = {
            "service_account_key": _key_text(service_account_key),
            "project_number": project_number,
            "region": region,
            **_gcp_settings(
                runtime_service_account=runtime_service_account,
                ingress=ingress,
                vpc_connector=vpc_connector,
                vpc_egress=vpc_egress,
            ),
        }
        if artifact_repo is not None:
            body["artifact_repo"] = artifact_repo
        if relocate_from is not None:
            body["acknowledge_relocation"] = True
            body["acknowledged_from"] = dict(relocate_from)
        saved = self._client._request("PUT", _gcp_path(org_id), _GcpSave, json=body)
        return saved.skipped_checks

    def disconnect_gcp(self, org_id: uuid.UUID | str) -> None:
        """Remove every Google Cloud connection of an organization.

        Refused while apps still use them; ``gcp_blocking_apps`` lists those. Keys
        are not revoked in Google Cloud, and nothing deployed there is deleted.
        Needs permission to manage the organization's cloud providers and a token
        with full access.

        Args:
            org_id: The organization.
        """
        self._client._request("DELETE", _gcp_path(org_id), None)

    def gcp_blocking_apps(
        self, org_id: uuid.UUID | str
    ) -> builtins.list[GcpBlockingApp]:
        """List the apps that stop an organization's Google Cloud from being removed.

        Other leftovers can still refuse the removal when this list is empty. Needs
        permission to manage the organization's cloud providers and a token with
        full access.

        Args:
            org_id: The organization.

        Returns:
            The apps.
        """
        return self._client._request(
            "GET", _gcp_path(org_id, "/blocking-apps"), builtins.list[GcpBlockingApp]
        )
