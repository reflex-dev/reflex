# Generated from packages/reflex-build-sdk/src/reflex_build_sdk/_async/resources/environments.py by packages/reflex-build-sdk/scripts/unasync.py. Do not edit.
"""The app environment endpoints."""

from __future__ import annotations

import builtins
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from reflex_build_sdk._base import path_segment
from reflex_build_sdk.types import (
    CopiedSecrets,
    Environment,
    EnvironmentsEnabled,
    NewEnvironment,
    Promotion,
)

if TYPE_CHECKING:
    from reflex_build_sdk._sync._client import ReflexBuild


@dataclass(frozen=True, slots=True, kw_only=True)
class _EnvironmentList:
    """The body of an app's environment list."""

    environments: list[Environment]


@dataclass(frozen=True, slots=True, kw_only=True)
class _NamedCopiedSecrets:
    """The body of a secret copy, for callers who can see secret names."""

    source: str
    copied: list[str]


@dataclass(frozen=True, slots=True, kw_only=True)
class _CountedCopiedSecrets:
    """The body of a secret copy, for callers who cannot see secret names."""

    source: str
    copied_count: int


class Environments:
    """Deploy apps through a pipeline of environments, such as dev and production.

    New deployments go to an app's first environment, and each later environment
    runs a version promoted from the one before it, with its own secrets and URL.
    Creating and promoting environments needs the Enterprise plan.
    """

    def __init__(self, client: ReflexBuild) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client

    def list(self, app_id: uuid.UUID | str) -> builtins.list[Environment]:
        """List an app's environments in pipeline order.

        Args:
            app_id: The app.

        Returns:
            The environments, or an empty list for an app without them.
        """
        body = self._client._request(
            "GET", f"apps/{path_segment(app_id)}/environments", _EnvironmentList
        )
        return body.environments

    def enable(self, app_id: uuid.UUID | str) -> EnvironmentsEnabled:
        """Give an app a pipeline of a dev and a production environment.

        Production keeps serving the app, with its URL, deployment history and
        secrets. Dev becomes the first environment, so the app's next deployment
        goes there. Production's secrets are copied to dev if the caller can edit
        secrets. There is no way back to a single environment other than deleting
        every environment but production.

        Args:
            app_id: The app, without a deployment in progress.

        Returns:
            The two environments.
        """
        return self._client._request(
            "POST",
            f"apps/{path_segment(app_id)}/environments/enable",
            EnvironmentsEnabled,
        )

    def create(
        self,
        app_id: uuid.UUID | str,
        name: str,
        *,
        position: int,
        copy_secrets_from: uuid.UUID | str | None = None,
    ) -> NewEnvironment:
        """Add an environment to an app's pipeline.

        Args:
            app_id: The app, with environments enabled.
            name: The name, unique within the app: 1 to 20 lowercase letters, digits
                and dashes, starting and ending with a letter or digit.
            position: Where in the pipeline to insert the environment; the
                environments from this position on move one place later. ``0`` makes
                it the environment new deployments go to.
            copy_secrets_from: An environment whose secrets to copy into the new one.

        Returns:
            The new environment's id, and whether the secrets were copied.
        """
        return self._client._request(
            "POST",
            f"apps/{path_segment(app_id)}/environments",
            NewEnvironment,
            json={
                "name": name,
                "position": position,
                "copy_secrets_from": None
                if copy_secrets_from is None
                else str(copy_secrets_from),
            },
        )

    def update(
        self,
        app_id: uuid.UUID | str,
        environment_id: uuid.UUID | str,
        *,
        name: str | None = None,
        requires_approval: bool | None = None,
        default_hostname: str | None = None,
    ) -> None:
        """Change an environment's settings, leaving those not passed unchanged.

        Settings cannot be cleared.

        Args:
            app_id: The app.
            environment_id: The environment.
            name: The new name, with the same rules as ``create``.
            requires_approval: Whether promoting to the environment needs approval.
                Changing it needs permission to manage the project's approvals.
            default_hostname: The subdomain to serve the environment at when it has
                no URL yet, as a single label such as ``"my-app-staging"``. Set it to
                promote to an environment that has never been served.
        """
        body = {
            "name": name,
            "requires_approval": requires_approval,
            "default_hostname": default_hostname,
        }
        self._client._request(
            "PATCH",
            f"apps/{path_segment(app_id)}/environments/{path_segment(environment_id)}",
            None,
            json={key: value for key, value in body.items() if value is not None},
            idempotent=True,
        )

    def reorder(
        self, app_id: uuid.UUID | str, environment_ids: Sequence[uuid.UUID | str]
    ) -> None:
        """Change the order of an app's pipeline.

        Moving production first makes new deployments go straight to production.

        Args:
            app_id: The app.
            environment_ids: Every environment of the app, in the new order.
        """
        self._client._request(
            "POST",
            f"apps/{path_segment(app_id)}/environments/reorder",
            None,
            json={"ordered_environment_ids": [str(id_) for id_ in environment_ids]},
            idempotent=True,
        )

    def promote(
        self,
        app_id: uuid.UUID | str,
        environment_id: uuid.UUID | str,
        *,
        source_deployment_id: uuid.UUID | str | None = None,
        description: str | None = None,
    ) -> Promotion:
        """Deploy the version running in the previous environment to this one.

        The version's build is reused, run with this environment's secrets, URL and
        machine sizes. Follow the deployment with ``deployments.wait``. A promotion
        that needs approval waits for it in the dashboard.

        Args:
            app_id: The app.
            environment_id: The environment to promote to; not the first one.
            source_deployment_id: The previous environment's deployment to promote,
                one that has run there. Defaults to the one running now.
            description: A note recorded with the deployment, at most 500 characters.
                Defaults to naming the environment it was promoted from.

        Returns:
            The new deployment.
        """
        body: dict[str, Any] = {}
        if source_deployment_id is not None:
            body["source_deployment_id"] = str(source_deployment_id)
        if description is not None:
            body["description"] = description
        return self._client._request(
            "POST",
            f"apps/{path_segment(app_id)}/environments/{path_segment(environment_id)}/promote",
            Promotion,
            json=body,
        )

    def copy_missing_secrets(
        self, app_id: uuid.UUID | str, environment_id: uuid.UUID | str
    ) -> CopiedSecrets:
        """Copy the secrets the previous environment has and this one lacks.

        Secrets the environment already has are left as they are. The copies take
        effect from the environment's next deployment or promotion.

        Args:
            app_id: The app.
            environment_id: The environment to copy secrets into; not the first one.

        Returns:
            The secrets copied.
        """
        body = self._client._request(  # ty:ignore[no-matching-overload]
            "POST",
            f"apps/{path_segment(app_id)}/environments/{path_segment(environment_id)}/copy-missing-secrets",
            _NamedCopiedSecrets | _CountedCopiedSecrets,
            idempotent=True,
        )
        if isinstance(body, _NamedCopiedSecrets):
            return CopiedSecrets(
                source=body.source, names=body.copied, count=len(body.copied)
            )
        return CopiedSecrets(source=body.source, names=None, count=body.copied_count)

    def delete(self, app_id: uuid.UUID | str, environment_id: uuid.UUID | str) -> None:
        """Delete an environment, with its hosted app, secrets and hostnames.

        The environment must not be running, deploying or paused; stop it first.
        Production cannot be deleted, and neither can an app's last environment.

        Args:
            app_id: The app.
            environment_id: The environment.
        """
        self._client._request(
            "DELETE",
            f"apps/{path_segment(app_id)}/environments/{path_segment(environment_id)}",
            None,
        )
