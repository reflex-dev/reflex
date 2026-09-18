"""The app, runtime log and secret endpoints."""

from __future__ import annotations

import builtins
import datetime
import uuid
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, NoReturn

from reflex_build_sdk._async.resources.databases import AsyncDatabase
from reflex_build_sdk._async.resources.environments import AsyncEnvironments
from reflex_build_sdk._async.resources.sign_in import AsyncSignIn
from reflex_build_sdk._base import path_segment
from reflex_build_sdk.types import (
    App,
    AppMove,
    AppSummary,
    CustomDomain,
    DeploymentRecord,
    DnsRecord,
    FullDeployChange,
    HostnameReservation,
    InstanceBoundsChange,
    LogRecord,
    ProviderChange,
    RunningDeployment,
    ServiceNameChange,
)

if TYPE_CHECKING:
    from reflex_build_sdk._async._client import AsyncReflexCloud


# The name under which the secrets route reads every secret at once, which a single
# secret can also have.
_ALL_SECRETS = "__all__"


@dataclass(frozen=True, slots=True, kw_only=True)
class _NoRunningDeployment:
    """The body the current deployment route answers with when nothing is running."""

    detail: str


@dataclass(frozen=True, slots=True, kw_only=True)
class _AddedCustomDomain:
    """The body of a newly added custom domain."""

    dns_records: dict[str, DnsRecord]


def _epoch_seconds(dt: datetime.datetime | None) -> int | None:
    """Convert a log window bound to the whole seconds since the Unix epoch the logs endpoint takes.

    Args:
        dt: The bound, timezone-aware, or None for no bound.

    Returns:
        The seconds, or None for no bound.

    Raises:
        ValueError: If ``dt`` is naive.
    """
    if dt is None:
        return None
    # timestamp() reads a naive datetime as local time, which would shift the log
    # window by the machine's UTC offset.
    if dt.utcoffset() is None:
        msg = f"expected a timezone-aware datetime, got naive {dt!r}"
        raise ValueError(msg)
    return int(dt.timestamp())


class AsyncSecrets:
    """Manage the secrets exposed to an app as environment variables.

    Without an ``environment_id``, each method acts on the environment new
    deployments are built for: the first environment of an app that has several.
    """

    def __init__(self, client: AsyncReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client

    async def list(
        self, app_id: uuid.UUID | str, *, environment_id: uuid.UUID | str | None = None
    ) -> builtins.list[str]:
        """List the names of an app's secrets, without their values.

        Args:
            app_id: The app.
            environment_id: The environment whose secrets to list.

        Returns:
            The secret names.
        """
        return await self._client._request(
            "GET",
            f"apps/{path_segment(app_id)}/secrets",
            builtins.list[str],
            params={"environment_id": environment_id},
        )

    async def get(
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
            return (await self.get_all(app_id, environment_id=environment_id))[name]
        return await self._client._request(
            "GET",
            f"apps/{path_segment(app_id)}/secrets/{path_segment(name)}",
            str,
            params={"environment_id": environment_id},
        )

    async def get_all(
        self, app_id: uuid.UUID | str, *, environment_id: uuid.UUID | str | None = None
    ) -> dict[str, str]:
        """Get the names and values of all of an app's secrets.

        Args:
            app_id: The app.
            environment_id: The environment whose secrets to read.

        Returns:
            The secret values by name.
        """
        return await self._client._request(
            "GET",
            f"apps/{path_segment(app_id)}/secrets/{_ALL_SECRETS}",
            dict[str, str],
            params={"environment_id": environment_id},
        )

    async def set(
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
        await self._client._request(
            "POST",
            f"apps/{path_segment(app_id)}/secrets",
            None,
            params={"reboot": reboot, "environment_id": environment_id},
            json={"secrets": dict(secrets)},
        )

    async def delete(
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
        await self._client._request(
            "DELETE",
            f"apps/{path_segment(app_id)}/secrets/{path_segment(name)}",
            None,
            params={"reboot": reboot, "environment_id": environment_id},
        )


class AsyncDomains:
    """Serve apps at custom domains."""

    def __init__(self, client: AsyncReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client

    async def get(self, app_id: uuid.UUID | str) -> CustomDomain | None:
        """Get an app's custom domain and check whether it is ready to serve the app.

        Checking looks the domain up in DNS and at the CDN, and marks the domain
        verified once its ownership is, so poll it no more than every few seconds.
        Only callers who can manage the app's domains get the check; others get
        whether the domain was verified.

        Args:
            app_id: The app.

        Returns:
            The domain, or None if the app has none.
        """
        # An app without a custom domain answers with an empty object, the only
        # value a dict that can hold no values matches.
        domain = await self._client._request(
            "GET",
            f"apps/{path_segment(app_id)}/custom_domain",
            CustomDomain | dict[str, NoReturn],
        )
        return domain if isinstance(domain, CustomDomain) else None

    async def add(self, app_id: uuid.UUID | str, domain: str) -> dict[str, DnsRecord]:
        """Serve an app at a custom domain, once DNS points the domain at it.

        Needs the Pro or Enterprise plan. An app has at most one custom domain, and
        apps serving their frontend from their own container cannot have one. Follow
        the domain's progress with ``get``.

        Args:
            app_id: The app.
            domain: The domain, e.g. ``"app.example.com"``.

        Returns:
            The DNS records to create for the domain, by purpose, e.g.
            ``"DNS_RECORD_CNAME"``.
        """
        added = await self._client._request(
            "POST",
            f"apps/{path_segment(app_id)}/custom_domain",
            _AddedCustomDomain,
            json={"domain": domain},
        )
        return added.dns_records

    async def remove(self, app_id: uuid.UUID | str, domain: str) -> None:
        """Stop serving an app at its custom domain.

        Args:
            app_id: The app.
            domain: The app's custom domain.
        """
        await self._client._request(
            "DELETE",
            f"apps/{path_segment(app_id)}/custom_domain/{path_segment(domain)}",
            None,
        )


class AsyncApps:
    """Manage apps, their lifecycle, deployment history and logs."""

    # Manage the secrets exposed to an app as environment variables.
    secrets: AsyncSecrets
    # Serve apps at custom domains.
    domains: AsyncDomains
    # Deploy apps through a pipeline of environments, such as dev and production.
    environments: AsyncEnvironments
    # Give apps a Postgres database hosted by Reflex Cloud.
    database: AsyncDatabase
    # Sign an app's users in with their Reflex accounts.
    sign_in: AsyncSignIn

    def __init__(self, client: AsyncReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client
        self.secrets = AsyncSecrets(client)
        self.domains = AsyncDomains(client)
        self.environments = AsyncEnvironments(client)
        self.database = AsyncDatabase(client)
        self.sign_in = AsyncSignIn(client)

    async def list(
        self, *, project_id: uuid.UUID | str | None = None
    ) -> builtins.list[AppSummary]:
        """List the apps the caller can access.

        Args:
            project_id: Only list the apps of this project. A project the caller cannot
                access lists no apps.

        Returns:
            The apps.
        """
        return await self._client._request(
            "GET", "apps", builtins.list[AppSummary], params={"project": project_id}
        )

    async def search(
        self, name: str, *, project_id: uuid.UUID | str | None = None
    ) -> builtins.list[AppSummary]:
        """Find the apps with a name, which is unique within a project.

        Args:
            name: The exact app name.
            project_id: Only search this project.

        Returns:
            The matching apps, one per project at most.
        """
        return await self._client._request(
            "GET",
            "apps/search",
            builtins.list[AppSummary],
            params={"app_name": name, "project_id": project_id},
        )

    async def get(self, app_id: uuid.UUID | str) -> App:
        """Get an app and its production deployment.

        Args:
            app_id: The app.

        Returns:
            The app.
        """
        return await self._client._request("GET", f"apps/{path_segment(app_id)}", App)

    async def create(
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
        created = await self._client._request(
            "POST", "apps/", dict[str, Any], json=body
        )
        return await self.get(created["id"])

    async def delete(self, app_id: uuid.UUID | str) -> None:
        """Delete an app and stop its deployments.

        Args:
            app_id: The app.
        """
        await self._client._request(
            "DELETE", f"apps/{path_segment(app_id)}/delete", None
        )

    async def rename(self, app_id: uuid.UUID | str, name: str) -> None:
        """Rename an app. Its URL stays the same.

        Args:
            app_id: The app.
            name: The new name.
        """
        await self._client._request(
            "POST",
            f"apps/{path_segment(app_id)}/update_name",
            None,
            json={"name": name},
        )

    async def set_description(self, app_id: uuid.UUID | str, description: str) -> None:
        """Set an app's description.

        Args:
            app_id: The app.
            description: The description, or ``""`` to clear it.
        """
        await self._client._request(
            "POST",
            f"apps/{path_segment(app_id)}/update_description",
            None,
            json={"description": description},
        )

    async def move(
        self,
        app_id: uuid.UUID | str,
        project_id: uuid.UUID | str,
        *,
        copy_integrations: bool = False,
    ) -> AppMove:
        """Move an app to another project of the same organization.

        The app keeps running, and takes its deployments and this month's usage
        with it.

        Args:
            app_id: The app.
            project_id: The project to move the app to.
            copy_integrations: Whether to copy the source project's integrations the
                app uses into the destination project. Needs admin access to the
                destination project.

        Returns:
            What was copied, and which repository connections need reconnecting.
        """
        return await self._client._request(
            "POST",
            f"apps/{path_segment(app_id)}/move",
            AppMove,
            json={
                "target_project_id": str(project_id),
                "copy_integrations": copy_integrations,
            },
        )

    async def set_persistent(self, app_id: uuid.UUID | str, persistent: bool) -> None:
        """Choose whether an app's machines keep running when idle instead of pausing.

        Keeping them running needs the Pro or Enterprise plan. A running app's
        instances are replaced to apply the change, which ``status`` reports on;
        otherwise it applies from the app's next start or deployment.

        Args:
            app_id: The app, deployed at least once.
            persistent: Whether the machines keep running when idle.
        """
        await self._update_settings(app_id, persist=persistent)

    async def set_rollout_strategy(
        self,
        app_id: uuid.UUID | str,
        strategy: Literal["immediate", "rolling", "bluegreen", "canary"],
    ) -> None:
        """Choose how an app's new deployments replace its running instances.

        Args:
            app_id: The app.
            strategy: ``"immediate"`` replaces every instance at once, ``"rolling"``
                one at a time, ``"bluegreen"`` switches over once a full set of new
                instances is healthy, and ``"canary"`` starts one new instance before
                rolling out the rest. Google Cloud apps support ``"immediate"`` and
                ``"bluegreen"``.
        """
        await self._update_settings(app_id, strategy=strategy)

    async def _update_settings(
        self,
        app_id: uuid.UUID | str,
        *,
        persist: bool | None = None,
        strategy: str | None = None,
    ) -> None:
        """Change an app's settings through the route that takes all of them at once.

        Args:
            app_id: The app.
            persist: Whether the app's machines keep running when idle, or None to
                leave it unchanged.
            strategy: The rollout strategy, or None to leave it unchanged.
        """
        # Every setting must be sent; null leaves one unchanged.
        await self._client._request(
            "POST",
            f"apps/{path_segment(app_id)}/settings",
            None,
            json={
                "name": None,
                "description": None,
                "persist": persist,
                "strategy": strategy,
            },
        )

    async def set_service_name(
        self, app_id: uuid.UUID | str, service_name: str
    ) -> ServiceNameChange:
        """Rename the Cloud Run service of a Google Cloud app.

        Needs the Enterprise plan, and an app that serves its frontend from Google
        Cloud. A running app is stopped and its old service deleted, which can take
        minutes, so use a client with a longer ``timeout``; deploy the app again to
        run it under the new name.

        Args:
            app_id: The app.
            service_name: The service name: lowercase letters, digits and hyphens,
                starting with a letter, at most 49 characters.

        Returns:
            The service name, and whether the app was stopped for it.
        """
        return await self._client._request(
            "POST",
            f"apps/{path_segment(app_id)}/service_name",
            ServiceNameChange,
            json={"service_name": service_name},
        )

    async def set_weekly_report(self, app_id: uuid.UUID | str, enabled: bool) -> None:
        """Choose whether an app is in the weekly traffic report emailed to its editors.

        Args:
            app_id: The app.
            enabled: Whether to include the app.
        """
        await self._client._request(
            "POST",
            f"apps/{path_segment(app_id)}/weekly_report",
            None,
            json={"enabled": enabled},
        )

    async def status(self, app_id: uuid.UUID | str) -> str:
        """Get the progress of the latest start, stop, pause, rollback or scale of an app.

        Args:
            app_id: The app.

        Returns:
            The status message, e.g. ``"Application stopped successfully"``, or one
            starting with ``"App Stop Failed:"``. Every operation writes the same
            message, so it can report a different operation than the one polled for.
        """
        return await self._client._request(
            "GET", f"apps/{path_segment(app_id)}/status", str
        )

    async def current_deployment(
        self,
        app_id: uuid.UUID | str,
        *,
        environment_id: uuid.UUID | str | None = None,
    ) -> RunningDeployment | None:
        """Get the deployment running an app.

        Args:
            app_id: The app.
            environment_id: The environment whose deployment to get. Defaults to
                production.

        Returns:
            The running deployment, or None if the app is not running, e.g. while it
            is stopped, paused or deploying.
        """
        deployment = await self._client._request(
            "GET",
            f"apps/{path_segment(app_id)}/deployment",
            RunningDeployment | _NoRunningDeployment,
            params={"environment_id": environment_id},
        )
        return deployment if isinstance(deployment, RunningDeployment) else None

    async def start(self, app_id: uuid.UUID | str) -> None:
        """Start every stopped or paused environment of an app.

        Args:
            app_id: The app.
        """
        await self._client._request("POST", f"apps/{path_segment(app_id)}/start", None)

    async def stop(self, app_id: uuid.UUID | str) -> None:
        """Stop every environment of an app, releasing its machines.

        Args:
            app_id: The app.
        """
        await self._client._request("POST", f"apps/{path_segment(app_id)}/stop", None)

    async def pause(self, app_id: uuid.UUID | str) -> None:
        """Pause every environment of an app, keeping its machines for a quick start.

        Args:
            app_id: The app. Apps serving their frontend from their own container
                cannot be paused; stop them instead.
        """
        await self._client._request("POST", f"apps/{path_segment(app_id)}/pause", None)

    async def scale(
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
        await self._client._request(
            "POST", f"apps/{path_segment(app_id)}/scale", None, json=body
        )

    async def set_provider(
        self,
        app_id: uuid.UUID | str,
        provider: str,
        *,
        provider_account_id: uuid.UUID | str | None = None,
        service_name: str | None = None,
        full_deploy: bool | None = None,
        expected_project_id: uuid.UUID | str | None = None,
    ) -> ProviderChange:
        """Move an app to another hosting provider.

        Hosting on a connected Google Cloud account needs the Enterprise plan. The
        previous provider's resources are torn down.

        Args:
            app_id: The app.
            provider: ``"fly"`` for Reflex Cloud, or ``"gcp"`` for the organization's
                Google Cloud.
            provider_account_id: The Google Cloud connection to deploy to. Defaults
                to the organization's default connection.
            service_name: The Cloud Run service name, for Google Cloud apps.
            full_deploy: Whether to also serve the frontend from Google Cloud.
            expected_project_id: Refuse the change if the app has moved to another
                project since this id was read.

        Returns:
            The provider the app is now on, and whether the previous one was released.
        """
        body: dict[str, Any] = {"provider": provider}
        if provider_account_id is not None:
            body["provider_account_id"] = str(provider_account_id)
        if service_name is not None:
            body["service_name"] = service_name
        if full_deploy is not None:
            body["full_deploy"] = full_deploy
        return await self._client._request(
            "POST",
            f"apps/{path_segment(app_id)}/provider",
            ProviderChange,
            params={"expected_project_id": expected_project_id},
            json=body,
        )

    async def set_full_deploy(
        self, app_id: uuid.UUID | str, full_deploy: bool
    ) -> FullDeployChange:
        """Choose whether a Google Cloud app serves its frontend from its own container.

        Needs the Enterprise plan. A deployed app is stopped, and serves the new way
        from its next deployment.

        Args:
            app_id: The app.
            full_deploy: Whether to serve the frontend from the app's container
                rather than the CDN.

        Returns:
            The setting, and whether the app was stopped for it.
        """
        return await self._client._request(
            "POST",
            f"apps/{path_segment(app_id)}/full_deploy",
            FullDeployChange,
            json={"full_deploy": full_deploy},
        )

    async def set_instance_bounds(
        self,
        app_id: uuid.UUID | str,
        *,
        min_instances: int | None,
        max_instances: int | None,
    ) -> InstanceBoundsChange:
        """Set how many instances a Google Cloud app scales between.

        Both bounds are replaced, so pass the current value of one to keep it.

        Args:
            app_id: The app.
            min_instances: The fewest instances to run, from 0 to 1000, or None for
                the platform default.
            max_instances: The most instances to run, from 1 to 1000, or None for the
                platform default.

        Returns:
            Whether the bounds changed and were applied to the running app.
        """
        return await self._client._request(
            "POST",
            f"apps/{path_segment(app_id)}/instance_bounds",
            InstanceBoundsChange,
            json={"min_instances": min_instances, "max_instances": max_instances},
        )

    async def reserve_hostname(
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
        return await self._client._request(
            "POST",
            "apps/reserve",
            HostnameReservation,
            json={"app_id": str(app_id), "app_name": app_name, "hostname": hostname},
        )

    async def rollback(
        self, app_id: uuid.UUID | str, deployment_id: uuid.UUID | str
    ) -> None:
        """Redeploy an earlier deployment of an app.

        Args:
            app_id: The app.
            deployment_id: The deployment to roll back to, from ``history``.
        """
        await self._client._request(
            "POST",
            f"apps/{path_segment(app_id)}/deployments/{path_segment(deployment_id)}/rollback",
            None,
        )

    async def history(
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
        return await self._client._request(
            "GET",
            f"apps/{path_segment(app_id)}/history",
            builtins.list[DeploymentRecord],
            params={"environment_id": environment_id},
        )

    async def logs(
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
    ) -> AsyncIterator[LogRecord]:
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
            entries, cursor = await self._client._request(
                "GET", path, tuple[builtins.list[LogRecord], str | None], params=params
            )
            for entry in entries:
                yield entry
            # Depending on the hosting provider, the last page either has no cursor
            # or is followed by an empty page.
            if not entries or cursor is None:
                return
            params["cursor"] = cursor
