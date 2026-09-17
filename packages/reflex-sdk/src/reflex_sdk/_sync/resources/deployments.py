# Generated from packages/reflex-sdk/src/reflex_sdk/_async/resources/deployments.py by packages/reflex-sdk/scripts/unasync.py. Do not edit.
"""The deployment endpoints."""

from __future__ import annotations

import json
import os
import platform
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Literal

from reflex_sdk._base import path_segment, sdk_version
from reflex_sdk._deploy import (
    DEPLOY_PROTOCOL_VERSION,
    UPLOAD_ATTEMPTS,
    ArchiveUploader,
    ProgressCallback,
    UploadReservation,
    UploadTarget,
    report_outcome,
    status_message_outcome,
)
from reflex_sdk._errors import (
    DeploymentFailedError,
    DeploymentTimeoutError,
    PermissionDeniedError,
)
from reflex_sdk.types import DeploymentReport, MachineSize, Region

if TYPE_CHECKING:
    from reflex_sdk._sync._client import ReflexCloud

# How often wait() polls a deployment's status, in seconds.
_POLL_INTERVAL = 2.0
# The status message can go stale when the service caching it is unavailable, so
# wait() also reads the deployment's recorded state every 15 polls (about 30
# seconds at the default interval).
_REPORT_EVERY_POLLS = 15


def _upload_targets(
    archives: tuple[Path, Path],
    sizes: tuple[int, int],
    reservation: UploadReservation,
) -> list[tuple[Path, int, UploadTarget]]:
    return [
        (archives[0], sizes[0], reservation.backend),
        (archives[1], sizes[1], reservation.frontend),
    ]


def _installed_reflex_version() -> str | None:
    try:
        return version("reflex")
    except PackageNotFoundError:
        return None


class Deployments:
    """Deploy apps and follow their deployments."""

    def __init__(self, client: ReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client

    def create(
        self,
        app_id: uuid.UUID | str,
        *,
        backend: str | os.PathLike[str],
        frontend: str | os.PathLike[str],
        regions: Mapping[str, int] | None = None,
        vm_type: str | None = None,
        cpu: float | None = None,
        ram_mb: int | None = None,
        hostname: str | None = None,
        secrets: Mapping[str, str] | None = None,
        packages: Sequence[str] | None = None,
        strategy: Literal["immediate", "rolling", "bluegreen", "canary"] | None = None,
        description: str | None = None,
        reflex_version: str | None = None,
        python_version: str | None = None,
        on_upload_progress: ProgressCallback | None = None,
    ) -> uuid.UUID:
        """Upload a build of an app and deploy it.

        The build is the pair of archives ``reflex export`` produces. They are
        uploaded straight to storage, then the deployment is submitted. Follow it
        with ``wait``. Settings left unset keep the app's previous deployment's
        values, or the platform defaults for a first deployment.

        Args:
            app_id: The app to deploy.
            backend: The path of the backend archive, ``backend.zip``.
            frontend: The path of the frontend archive, ``frontend.zip``.
            regions: The number of machines to run in each region, by region code.
            vm_type: The machine size to run, from ``vm_types``.
            cpu: The number of CPUs of a custom machine size, with ``ram_mb``.
            ram_mb: The memory of a custom machine size, in MB, with ``cpu``.
            hostname: The hostname to serve the app at, e.g. ``"my-app.reflex.run"``.
            secrets: Secrets to set for the deployment, by name.
            packages: System packages to install, by Debian package name.
            strategy: How to replace the running deployment.
            description: A note recorded with the deployment, shown in its history.
            reflex_version: The Reflex version the build was exported with. Defaults
                to the installed version of ``reflex``, when there is one.
            python_version: The Python version to run the backend with. Defaults to
                the version running this client.
            on_upload_progress: Called with the bytes uploaded so far and the total.
                If the upload URLs expire mid-upload, the archives are uploaded again
                and the count restarts.

        Returns:
            The id of the new deployment.

        Raises:
            ValueError: If ``cpu`` and ``ram_mb`` are not passed together, or are
                passed with ``vm_type``.
        """
        # Checked before uploading, which can take minutes for a large build.
        if (cpu is None) != (ram_mb is None) or (
            vm_type is not None and cpu is not None
        ):
            msg = "pass either vm_type, or both cpu and ram_mb, or neither"
            raise ValueError(msg)
        archives = (Path(backend), Path(frontend))
        sizes = (archives[0].stat().st_size, archives[1].stat().st_size)
        reservation = self._upload(app_id, archives, sizes, on_upload_progress)
        form = {
            "reflex_hosting_cli_version": DEPLOY_PROTOCOL_VERSION,
            "reflex_sdk_version": sdk_version(),
            "stored_build_id": str(reservation.deployment_id),
            "app_id": str(app_id),
            "regions": None if regions is None else json.dumps(dict(regions)),
            "vm_type": vm_type,
            "cpu": None if cpu is None else str(cpu),
            "ram_mb": None if ram_mb is None else str(ram_mb),
            "hostname": hostname,
            "secrets": None if secrets is None else json.dumps(dict(secrets)),
            "packages": None if packages is None else json.dumps(list(packages)),
            "deployment_strategy": strategy,
            "description": description,
            "reflex_version": reflex_version or _installed_reflex_version(),
            "python_version": python_version or platform.python_version(),
        }
        return self._client._request(
            "POST",
            "deployments",
            uuid.UUID,
            form={name: value for name, value in form.items() if value is not None},
        )

    def _upload(
        self,
        app_id: uuid.UUID | str,
        archives: tuple[Path, Path],
        sizes: tuple[int, int],
        on_progress: ProgressCallback | None,
    ) -> UploadReservation:
        """Reserve upload URLs for a build and upload its archives to them.

        Args:
            app_id: The app the build belongs to.
            archives: The backend and frontend archives.
            sizes: The size of each archive, in bytes.
            on_progress: Called with the bytes uploaded so far and the total.

        Returns:
            The reservation the archives were uploaded under.
        """
        uploader = ArchiveUploader(
            self._client._transport, on_progress, self._client._timeout
        )
        for _ in range(UPLOAD_ATTEMPTS - 1):
            reservation = self._reserve(app_id, sizes)
            try:
                uploader.upload(_upload_targets(archives, sizes, reservation))
            except PermissionDeniedError:
                # Storage refuses URLs whose signature expired. A new reservation
                # signs new ones, under a new deployment id, so both archives go up
                # again.
                continue
            return reservation
        reservation = self._reserve(app_id, sizes)
        uploader.upload(_upload_targets(archives, sizes, reservation))
        return reservation

    def _reserve(
        self, app_id: uuid.UUID | str, sizes: tuple[int, int]
    ) -> UploadReservation:
        """Reserve a deployment id and signed upload URLs for a build.

        Args:
            app_id: The app the build belongs to.
            sizes: The size of the backend and frontend archives, in bytes.

        Returns:
            The reservation.
        """
        return self._client._request(
            "POST",
            "deployments/reserve",
            UploadReservation,
            json={
                "app_id": str(app_id),
                "backend_size": sizes[0],
                "frontend_size": sizes[1],
            },
        )

    def check(
        self,
        app_id: uuid.UUID | str,
        *,
        app_name: str,
        project_id: uuid.UUID | str,
        regions: Mapping[str, int] | None = None,
        vm_type: str | None = None,
        cpu: float | None = None,
        ram_mb: int | None = None,
        hostname: str | None = None,
    ) -> None:
        """Check that a deployment with these settings would be accepted.

        Checks the settings, plan limits and hostname before the build is exported
        and uploaded; ``create`` checks them again.

        Args:
            app_id: The app.
            app_name: The app's name.
            project_id: The app's project.
            regions: The number of machines to run in each region, by region code.
            vm_type: The machine size to run.
            cpu: The number of CPUs of a custom machine size, with ``ram_mb``.
            ram_mb: The memory of a custom machine size, in MB, with ``cpu``.
            hostname: The hostname to serve the app at.
        """
        self._client._request(
            "GET",
            "deployments/validate_cli",
            None,
            params={
                "app_id": str(app_id),
                "app_name": app_name,
                "project_id": str(project_id),
                # The route requires these; an empty value means unset.
                "regions": "" if regions is None else json.dumps(dict(regions)),
                "vmtype": vm_type or "",
                "hostname": hostname or "",
                "cpu": cpu,
                "ram_mb": ram_mb,
            },
        )

    def status(self, deployment_id: uuid.UUID | str) -> str:
        """Get the latest status message of a deployment.

        Args:
            deployment_id: The deployment.

        Returns:
            A human-readable description of the deployment's progress.
        """
        return self._client._request(
            "GET", f"deployments/{path_segment(deployment_id)}/status", str
        )

    def report(self, deployment_id: uuid.UUID | str) -> DeploymentReport:
        """Get the recorded state of a deployment and, if it failed, why.

        Args:
            deployment_id: The deployment.

        Returns:
            The deployment's report.
        """
        return self._client._request(
            "GET",
            f"deployments/{path_segment(deployment_id)}/failure",
            DeploymentReport,
        )

    def build_logs(self, deployment_id: uuid.UUID | str) -> str:
        """Get the whole build log of a deployment.

        Args:
            deployment_id: The deployment.

        Returns:
            The build log, empty if the deployment has none.
        """
        return self._client._request(
            "GET", f"deployments/{path_segment(deployment_id)}/build/logs", str
        )

    def wait(
        self,
        deployment_id: uuid.UUID | str,
        *,
        timeout: float | None = None,
        poll_interval: float = _POLL_INTERVAL,
        on_status: Callable[[str], None] | None = None,
    ) -> DeploymentReport:
        """Wait until a deployment goes live, fails, or waits for approval.

        Args:
            deployment_id: The deployment.
            timeout: How long to wait, in seconds. Defaults to no limit.
            poll_interval: How long to wait between status checks, in seconds.
            on_status: Called with each new status message.

        Returns:
            The report of a deployment that is running, or awaiting approval when
            ``report.status`` is ``"AwaitingApproval"``.

        Raises:
            DeploymentFailedError: If the deployment failed, or was rejected,
                cancelled or replaced before going live.
            DeploymentTimeoutError: If the deployment was still in progress when
                ``timeout`` passed.
        """
        deployment_uuid = uuid.UUID(str(deployment_id))
        deadline = None if timeout is None else monotonic() + timeout
        last_message = None
        polls = 0
        while True:
            message = self.status(deployment_uuid)
            if message != last_message:
                last_message = message
                if on_status is not None:
                    on_status(message)
            outcome = status_message_outcome(message)
            polls += 1
            stale = "bad response" in message
            if outcome is not None or stale or polls % _REPORT_EVERY_POLLS == 0:
                report = self.report(deployment_uuid)
                if outcome is None:
                    recorded = report_outcome(report.status)
                    # A running deployment is only live once its message says so,
                    # unless the message is stale and cannot.
                    if recorded != "succeeded" or stale:
                        outcome = recorded
                if outcome == "failed":
                    raise DeploymentFailedError(deployment_uuid, report)
                if outcome is not None:
                    return report
            delay = poll_interval
            if deadline is not None:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    msg = (
                        f"deployment {deployment_uuid} was still in progress: {message}"
                    )
                    raise DeploymentTimeoutError(msg)
                # The last wait ends at the deadline rather than a whole interval on.
                delay = min(delay, remaining)
            time.sleep(delay)

    def set_description(
        self,
        app_id: uuid.UUID | str,
        deployment_id: uuid.UUID | str,
        description: str,
    ) -> None:
        """Set the note recorded with a deployment, shown in the app's history.

        Args:
            app_id: The app.
            deployment_id: The deployment.
            description: The note, cut to 500 characters. An empty note clears it.
        """
        self._client._request(
            "POST",
            f"apps/{path_segment(app_id)}/deployments/{path_segment(deployment_id)}/description",
            None,
            json={"description": description},
        )

    def regions(self) -> list[Region]:
        """List the regions apps can be deployed to.

        Returns:
            The regions.
        """
        return self._client._request(
            "GET", "deployments/regions", list[Region], authenticated=False
        )

    def vm_types(self) -> list[MachineSize]:
        """List the machine sizes apps can be deployed with.

        Returns:
            The machine sizes, smallest first.
        """
        return self._client._request(
            "GET",
            "deployments/vm_types",
            list[MachineSize],
            authenticated=False,
        )
