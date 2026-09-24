# Generated from tests/units/reflex_build_sdk/_async/resources/test_environments.py by packages/reflex-build-sdk/scripts/unasync.py. Do not edit.
from __future__ import annotations

import datetime
import uuid
from collections.abc import Iterator

import pytest
from reflex_build_sdk import APIResponseValidationError, ReflexBuild
from reflex_build_sdk.types import (
    CopiedSecrets,
    Environment,
    EnvironmentDeployment,
    EnvironmentsEnabled,
    NewEnvironment,
    Promotion,
)

from tests.units.reflex_build_sdk.conftest import (
    MockAPI,
    MockTransport,
    json_body,
    reply,
)

APP_ID = "5f0c5e0e-8f6a-4d57-9a55-3c1c1d7b6a01"
DEV_ID = "9d4c2b1a-7e6f-4a5b-8c9d-0e1f2a3b4c5d"
DEPLOYMENT_ID = "0e7b9d2c-5a4f-4c3b-8e1d-6f2a9b8c7d10"
SOURCE_DEPLOYMENT_ID = "3c2b1a09-8f7e-4d6c-9b5a-4a3b2c1d0e9f"
ENVIRONMENTS_PATH = f"/api/v1/apps/{APP_ID}/environments"
UTC = datetime.timezone.utc


@pytest.fixture
def client(mock_api: MockAPI) -> Iterator[ReflexBuild]:
    """A client talking to the mock API.

    Args:
        mock_api: The mock API.

    Yields:
        The client.
    """
    with ReflexBuild(token="test-token", transport=MockTransport(mock_api)) as client:
        yield client


def test_list(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "GET",
        ENVIRONMENTS_PATH,
        reply(
            200,
            json={
                "environments": [
                    {
                        "id": DEV_ID,
                        "name": "dev",
                        "position": 0,
                        "requires_approval": False,
                        "default_hostname": "dashboard-dev",
                        "running": None,
                        "has_in_flight": True,
                        "has_pending_promotion": False,
                        "has_pending_deploy": False,
                    },
                    {
                        "id": APP_ID,
                        "name": "prd",
                        "position": 1,
                        "requires_approval": True,
                        "default_hostname": None,
                        "running": {
                            "deployment_id": DEPLOYMENT_ID,
                            "url": "dashboard.reflex.run",
                            "status": "Running",
                            "deployment_ts": "2026-09-16T10:00:00+00:00",
                            "description": "Promoted from dev",
                            "promoted_from_deployment_id": SOURCE_DEPLOYMENT_ID,
                        },
                        "has_in_flight": False,
                        "has_pending_promotion": True,
                        "has_pending_deploy": False,
                    },
                ],
                "project_promotion_policy": False,
                "pipelines_allowed": True,
                "pending_approvals": 0,
            },
        ),
    )
    dev, production = client.apps.environments.list(APP_ID)
    assert dev == Environment(
        id=uuid.UUID(DEV_ID),
        name="dev",
        position=0,
        requires_approval=False,
        default_hostname="dashboard-dev",
        running=None,
        has_in_flight=True,
        has_pending_promotion=False,
        has_pending_deploy=False,
    )
    assert production.running == EnvironmentDeployment(
        id=uuid.UUID(DEPLOYMENT_ID),
        url="dashboard.reflex.run",
        status="Running",
        created_at=datetime.datetime(2026, 9, 16, 10, tzinfo=UTC),
        description="Promoted from dev",
        promoted_from_id=uuid.UUID(SOURCE_DEPLOYMENT_ID),
    )


def test_enable(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "POST",
        f"{ENVIRONMENTS_PATH}/enable",
        reply(
            200,
            json={
                "dev_environment_id": DEV_ID,
                "prod_environment_id": APP_ID,
                "backfilled_deployments": 12,
                "secrets_copied": True,
            },
        ),
    )
    assert client.apps.environments.enable(APP_ID) == EnvironmentsEnabled(
        dev_environment_id=uuid.UUID(DEV_ID),
        production_environment_id=uuid.UUID(APP_ID),
        backfilled_deployments=12,
        secrets_copied=True,
    )
    assert mock_api.requests[0].content is None


def test_create(client: ReflexBuild, mock_api: MockAPI):
    staging_id = "1f2e3d4c-5b6a-4978-8695-a4b3c2d1e0f9"
    mock_api.add(
        "POST",
        ENVIRONMENTS_PATH,
        reply(201, json={"id": staging_id, "secrets_copied": True}),
    )
    assert client.apps.environments.create(
        APP_ID, "staging", position=1, copy_secrets_from=uuid.UUID(DEV_ID)
    ) == NewEnvironment(id=uuid.UUID(staging_id), secrets_copied=True)
    assert json_body(mock_api.requests[0]) == {
        "name": "staging",
        "position": 1,
        "copy_secrets_from": DEV_ID,
    }


def test_update_sends_only_the_changed_settings(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "PATCH", f"{ENVIRONMENTS_PATH}/{DEV_ID}", reply(200, json={"id": DEV_ID})
    )
    client.apps.environments.update(APP_ID, DEV_ID, requires_approval=False)
    assert json_body(mock_api.requests[0]) == {"requires_approval": False}


def test_update_is_retried(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "PATCH",
        f"{ENVIRONMENTS_PATH}/{DEV_ID}",
        reply(503),
        reply(200, json={"id": DEV_ID}),
    )
    client.apps.environments.update(APP_ID, DEV_ID, name="qa")
    first, retry = mock_api.requests
    # The retry is the same request, identified by the same request id.
    assert first.headers["X-Request-ID"] == retry.headers["X-Request-ID"]


def test_reorder(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "POST",
        f"{ENVIRONMENTS_PATH}/reorder",
        reply(200, json={"ordered_environment_ids": [APP_ID, DEV_ID]}),
    )
    client.apps.environments.reorder(APP_ID, [uuid.UUID(APP_ID), DEV_ID])
    assert json_body(mock_api.requests[0]) == {
        "ordered_environment_ids": [APP_ID, DEV_ID]
    }


PROMOTION = {
    "deployment_id": DEPLOYMENT_ID,
    "environment_id": APP_ID,
    "source_deployment_id": SOURCE_DEPLOYMENT_ID,
    "url": "dashboard.reflex.run",
    "status": "AwaitingApproval",
}


def test_promote(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "POST", f"{ENVIRONMENTS_PATH}/{APP_ID}/promote", reply(202, json=PROMOTION)
    )
    assert client.apps.environments.promote(
        APP_ID,
        APP_ID,
        source_deployment_id=uuid.UUID(SOURCE_DEPLOYMENT_ID),
        description="release 12",
    ) == Promotion(
        deployment_id=uuid.UUID(DEPLOYMENT_ID),
        environment_id=uuid.UUID(APP_ID),
        source_deployment_id=uuid.UUID(SOURCE_DEPLOYMENT_ID),
        url="dashboard.reflex.run",
        status="AwaitingApproval",
    )
    assert json_body(mock_api.requests[0]) == {
        "source_deployment_id": SOURCE_DEPLOYMENT_ID,
        "description": "release 12",
    }


def test_promote_sends_an_object_without_options(
    client: ReflexBuild, mock_api: MockAPI
):
    # The route requires a JSON object body.
    mock_api.add(
        "POST", f"{ENVIRONMENTS_PATH}/{APP_ID}/promote", reply(202, json=PROMOTION)
    )
    client.apps.environments.promote(APP_ID, APP_ID)
    assert json_body(mock_api.requests[0]) == {}


@pytest.mark.parametrize(
    ("body", "copied"),
    [
        (
            {"copied": ["API_KEY", "SENTRY_DSN"], "source": "dev"},
            CopiedSecrets(source="dev", names=["API_KEY", "SENTRY_DSN"], count=2),
        ),
        # Callers who cannot see secret names only get a count.
        (
            {"copied_count": 2, "source": "dev"},
            CopiedSecrets(source="dev", names=None, count=2),
        ),
    ],
)
def test_copy_missing_secrets(
    client: ReflexBuild,
    mock_api: MockAPI,
    body: dict,
    copied: CopiedSecrets,
):
    mock_api.add(
        "POST",
        f"{ENVIRONMENTS_PATH}/{APP_ID}/copy-missing-secrets",
        reply(200, json=body),
    )
    assert client.apps.environments.copy_missing_secrets(APP_ID, APP_ID) == copied


def test_copy_missing_secrets_rejects_a_body_without_a_count(
    client: ReflexBuild, mock_api: MockAPI
):
    mock_api.add(
        "POST",
        f"{ENVIRONMENTS_PATH}/{APP_ID}/copy-missing-secrets",
        reply(200, json={"source": "dev"}),
    )
    with pytest.raises(APIResponseValidationError):
        client.apps.environments.copy_missing_secrets(APP_ID, APP_ID)


def test_delete(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "DELETE", f"{ENVIRONMENTS_PATH}/{DEV_ID}", reply(200, json={"id": DEV_ID})
    )
    assert client.apps.environments.delete(APP_ID, DEV_ID) is None
