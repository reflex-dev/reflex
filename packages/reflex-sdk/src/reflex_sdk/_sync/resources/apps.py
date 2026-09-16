# Generated from packages/reflex-sdk/src/reflex_sdk/_async/resources/apps.py by packages/reflex-sdk/scripts/unasync.py. Do not edit.
"""The app, runtime log and secret endpoints."""

from __future__ import annotations

import builtins
import datetime
import uuid
from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Any, Literal

from reflex_sdk._base import path_segment
from reflex_sdk.types import (
    App,
    AppSummary,
    DeploymentRecord,
    HostnameReservation,
    LogRecord,
)

if TYPE_CHECKING:
    from reflex_sdk._sync._client import ReflexCloud


# The name under which the secrets route reads every secret at once, which a single
# secret can also have.
_ALL_SECRETS = "__all__"


def _epoch_seconds(dt: datetime.datetime | None) -> int | None:
    # The logs endpoint takes whole seconds since the Unix epoch.
    if dt is None:
        return None
    # timestamp() reads a naive datetime as local time, which would shift the log
    # window by the machine's UTC offset.
    if dt.utcoffset() is None:
        msg = f"expected a timezone-aware datetime, got naive {dt!r}"
        raise ValueError(msg)
    return int(dt.timestamp())


class Secrets:
    """Manage the secrets exposed to an app as environment variables.

    Without an ``environment_id``, each method acts on the environment new
    deployments are built for: the first environment of an app that has several.
    """

    def __init__(self, client: ReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client

    def list(
        self, app_id: uuid.UUID | str, *, environment_id: uuid.UUID | str | None = None
    ) -> builtins.list[str]:
        """List the names of an app's secrets, without their values.

        Args:
            app_id: The app.
            environment_id: The environment whose secrets to list.

        Returns:
            The secret names.
        """
        return self._client._request(
            "GET",
            f"apps/{path_segment(app_id)}/secrets",
            builtins.list[str],
            params={"environment_id": environment_id},
        )

    def get(
        self,
        app_id: uuid.UUID | str,
        name: str,
        *,
        environment_id: uuid.UUID | str | None = None,
    ) -> str:
        """Get the value of one of an app's secrets.

        Args:
            app_id: The app.
            name: The name of the secret.
            environment_id: The environment whose secret to read.

        Returns:
            The secret's value.

        Raises:
            KeyError: If a secret named ``__all__`` does not exist.
        """
        if name == _ALL_SECRETS:
            # That path reads every secret, so this one secret is picked out of them.
            return (self.get_all(app_id, environment_id=environment_id))[name]
        return self._client._request(
            "GET",
            f"apps/{path_segment(app_id)}/secrets/{path_segment(name)}",
            str,
            params={"environment_id": environment_id},
        )

    def get_all(
        self, app_id: uuid.UUID | str, *, environment_id: uuid.UUID | str | None = None
    ) -> dict[str, str]:
        """Get the names and values of all of an app's secrets.

        Args:
            app_id: The app.
            environment_id: The environment whose secrets to read.

        Returns:
            The secret values by name.
        """
        return self._client._request(
            "GET",
            f"apps/{path_segment(app_id)}/secrets/{_ALL_SECRETS}",
            dict[str, str],
            params={"environment_id": environment_id},
        )

    def set(
        self,
        app_id: uuid.UUID | str,
        secrets: Mapping[str, str],
        *,
        reboot: bool = False,
        environment_id: uuid.UUID | str | None = None,
    ) -> None:
        """Add or update secrets, leaving the app's other secrets as they are.

        Args:
            app_id: The app.
            secrets: The secret values by name.
            reboot: Whether to restart the running app so it picks up the change.
                Otherwise the next deployment does.
            environment_id: The environment whose secrets to update.
        """
        self._client._request(
            "POST",
            f"apps/{path_segment(app_id)}/secrets",
            None,
            params={"reboot": reboot, "environment_id": environment_id},
            json={"secrets": dict(secrets)},
        )

    def delete(
        self,
        app_id: uuid.UUID | str,
        name: str,
        *,
        reboot: bool = False,
        environment_id: uuid.UUID | str | None = None,
    ) -> None:
        """Delete one of an app's secrets.

        Args:
            app_id: The app.
            name: The name of the secret.
            reboot: Whether to restart the running app so it picks up the change.
                Otherwise the next deployment does.
            environment_id: The environment whose secret to delete.
        """
        self._client._request(
            "DELETE",
            f"apps/{path_segment(app_id)}/secrets/{path_segment(name)}",
            None,
            params={"reboot": reboot, "environment_id": environment_id},
        )


class Apps:
    """Manage apps, their lifecycle, deployment history and logs."""

    # Manage the secrets exposed to an app as environment variables.
    secrets: Secrets

    def __init__(self, client: ReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client
        self.secrets = Secrets(client)

    def list(
        self, *, project_id: uuid.UUID | str | None = None
    ) -> builtins.list[AppSummary]:
        """List the apps the caller can access.

        Args:
            project_id: Only list the apps of this project. A project the caller cannot
                access lists no apps.

        Returns:
            The apps.
        """
        return self._client._request(
            "GET", "apps", builtins.list[AppSummary], params={"project": project_id}
        )

    def search(
        self, name: str, *, project_id: uuid.UUID | str | None = None
    ) -> builtins.list[AppSummary]:
        """Find the apps with a name, which is unique within a project.

        Args:
            name: The exact app name.
            project_id: Only search this project.

        Returns:
            The matching apps, one per project at most.
        """
        return self._client._request(
            "GET",
            "apps/search",
            builtins.list[AppSummary],
            params={"app_name": name, "project_id": project_id},
        )

    def get(self, app_id: uuid.UUID | str) -> App:
        """Get an app and its production deployment.

        Args:
            app_id: The app.

        Returns:
            The app.
        """
        return self._client._request("GET", f"apps/{path_segment(app_id)}", App)

    def create(
        self,
        name: str,
        *,
        project_id: uuid.UUID | str | None = None,
        description: str | None = None,
    ) -> App:
        """Create an app, ready for its first deployment.

        Args:
            name: The app name, unique within the project.
            project_id: The project to create the app in. Defaults to the caller's
                default project.
            description: A description of the app.

        Returns:
            The new app.
        """
        body: dict[str, Any] = {"name": name}
        if project_id is not None:
            body["project"] = str(project_id)
        if description is not None:
            body["description"] = description
        # The trailing slash is part of the route: without it the request reaches
        # the list route and is rejected. The response only identifies the app, so
        # the app is read back in full.
        created = self._client._request("POST", "apps/", dict[str, Any], json=body)
        return self.get(created["id"])

    def delete(self, app_id: uuid.UUID | str) -> None:
        """Delete an app and stop its deployments.

        Args:
            app_id: The app.
        """
        self._client._request("DELETE", f"apps/{path_segment(app_id)}/delete", None)

    def start(self, app_id: uuid.UUID | str) -> None:
        """Start every stopped or paused environment of an app.

        Args:
            app_id: The app.
        """
        self._client._request("POST", f"apps/{path_segment(app_id)}/start", None)

    def stop(self, app_id: uuid.UUID | str) -> None:
        """Stop every environment of an app, releasing its machines.

        Args:
            app_id: The app.
        """
        self._client._request("POST", f"apps/{path_segment(app_id)}/stop", None)

    def pause(self, app_id: uuid.UUID | str) -> None:
        """Pause every environment of an app, keeping its machines for a quick start.

        Args:
            app_id: The app. Apps serving their frontend from their own container
                cannot be paused; stop them instead.
        """
        self._client._request("POST", f"apps/{path_segment(app_id)}/pause", None)

    def scale(
        self,
        app_id: uuid.UUID | str,
        *,
        vm_type: str | None = None,
        cpu: float | None = None,
        ram_mb: int | None = None,
        regions: Mapping[str, int] | None = None,
    ) -> None:
        """Resize an app's machines or change how many run in each region.

        Pass either ``vm_type``, both ``cpu`` and ``ram_mb``, or ``regions``.

        Args:
            app_id: The app.
            vm_type: The machine size to run, e.g. ``"c1m1"``.
            cpu: The number of CPUs of a custom machine size.
            ram_mb: The memory of a custom machine size, in MB.
            regions: The number of machines to run in each region, by region code.

        Raises:
            ValueError: If the arguments are not exactly one of those forms.
        """
        custom_size = cpu is not None or ram_mb is not None
        forms = (vm_type is not None) + custom_size + (regions is not None)
        if forms != 1 or (custom_size and (cpu is None or ram_mb is None)):
            msg = "pass exactly one of vm_type, both cpu and ram_mb, or regions"
            raise ValueError(msg)
        body: dict[str, Any] = (
            {"type": "region", "regions": dict(regions)}
            if regions is not None
            else {"type": "size", "size": vm_type}
            if vm_type is not None
            else {"type": "size", "cpu": cpu, "ram_mb": ram_mb}
        )
        self._client._request(
            "POST", f"apps/{path_segment(app_id)}/scale", None, json=body
        )

    def reserve_hostname(
        self,
        app_id: uuid.UUID | str,
        app_name: str,
        *,
        hostname: str | None = None,
    ) -> HostnameReservation:
        """Reserve the URLs an app's next deployment is served at, for 10 minutes.

        The frontend is exported against these URLs, so reserve them before building
        the archives for ``deployments.create``.

        Args:
            app_id: The app.
            app_name: The app's name.
            hostname: The subdomain to serve the app at, as a single label such as
                ``"my-app"``, not a full hostname. Defaults to the app's current or
                generated hostname.

        Returns:
            The frontend and backend URLs.
        """
        return self._client._request(
            "POST",
            "apps/reserve",
            HostnameReservation,
            json={"app_id": str(app_id), "app_name": app_name, "hostname": hostname},
        )

    def rollback(self, app_id: uuid.UUID | str, deployment_id: uuid.UUID | str) -> None:
        """Redeploy an earlier deployment of an app.

        Args:
            app_id: The app.
            deployment_id: The deployment to roll back to, from ``history``.
        """
        self._client._request(
            "POST",
            f"apps/{path_segment(app_id)}/deployments/{path_segment(deployment_id)}/rollback",
            None,
        )

    def history(
        self,
        app_id: uuid.UUID | str,
        *,
        environment_id: uuid.UUID | str | None = None,
    ) -> builtins.list[DeploymentRecord]:
        """List an app's deployments.

        Args:
            app_id: The app.
            environment_id: Only list the deployments of this environment. Defaults to
                every environment.

        Returns:
            The deployments, newest first.
        """
        return self._client._request(
            "GET",
            f"apps/{path_segment(app_id)}/history",
            builtins.list[DeploymentRecord],
            params={"environment_id": environment_id},
        )

    def logs(
        self,
        app_id: uuid.UUID | str,
        *,
        start: datetime.datetime | None = None,
        end: datetime.datetime | None = None,
        search: str | None = None,
        region: str | None = None,
        order: Literal["oldest_first", "newest_first"] = "oldest_first",
        page_size: int | None = None,
        environment_id: uuid.UUID | str | None = None,
    ) -> Iterator[LogRecord]:
        """Iterate over an app's runtime logs, fetching further pages as needed.

        Args:
            app_id: The app.
            start: The earliest time to read logs from, timezone-aware, with second
                precision. Defaults to 30 days ago.
            end: The latest time to read logs until, timezone-aware. Defaults to now.
            search: Only return lines containing this text, ignoring case.
            region: Only return lines logged in this region.
            order: Whether to iterate from the oldest line or the newest.
            page_size: How many lines to fetch per request, between 50 and 1000.
                Defaults to 100.
            environment_id: The environment whose logs to read. Defaults to production.

        Yields:
            The log lines.

        Raises:
            ValueError: If ``start`` or ``end`` is a naive datetime, when iteration starts.
        """
        params: dict[str, Any] = {
            "start": _epoch_seconds(start),
            "end": _epoch_seconds(end),
            "search": search,
            "region": region,
            "order": order,
            "limit": page_size,
            "environment_id": environment_id,
        }
        path = f"apps/{path_segment(app_id)}/logsv2"
        while True:
            entries, cursor = self._client._request(
                "GET", path, tuple[builtins.list[LogRecord], str | None], params=params
            )
            for entry in entries:
                yield entry
            # Depending on the hosting provider, the last page either has no cursor
            # or is followed by an empty page.
            if not entries or cursor is None:
                return
            params["cursor"] = cursor
