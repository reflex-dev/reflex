from __future__ import annotations

import datetime
import json
import uuid
from collections.abc import AsyncIterator

import pytest
from reflex_build_sdk import AsyncReflexBuild
from reflex_build_sdk.types import (
    CloudRunManifest,
    GcpBlockingApp,
    GcpCheck,
    GcpConnection,
    GcpKeyRotation,
    GcpStatus,
    GcpVerification,
    ProviderAccount,
)

from tests.units.reflex_build_sdk.conftest import (
    AsyncMockTransport,
    MockAPI,
    json_body,
    reply,
)

ORG_ID = "1f6c1d0e-6f59-4d2b-a0f1-0f4e4a3b2c19"
GCP_PATH = f"/api/v1/orgs/{ORG_ID}/provider-accounts/gcp"
KEY = {"type": "service_account", "project_id": "acme-prod", "private_key": "..."}
ACCOUNT_ID = "2b7c9d1e-3f4a-4b5c-8d6e-7f8091a2b3c4"
USER_ID = "8b0f4a52-3a8a-4c43-9d7e-2f0c7d2a4b11"


@pytest.fixture
async def client(mock_api: MockAPI) -> AsyncIterator[AsyncReflexBuild]:
    """A client talking to the mock API.

    Args:
        mock_api: The mock API.

    Yields:
        The client.
    """
    async with AsyncReflexBuild(
        token="test-token", transport=AsyncMockTransport(mock_api)
    ) as client:
        yield client


async def test_gcp_status(client: AsyncReflexBuild, mock_api: MockAPI):
    body = {
        "configured": True,
        "allowed": True,
        "project_id": "acme-prod",
        "region": "us-central1",
        "connections": [
            {
                "id": ACCOUNT_ID,
                "name": "production",
                "is_default": True,
                "project_id": "acme-prod",
                "region": "us-central1",
            }
        ],
    }
    mock_api.add(
        "GET",
        f"/api/v1/orgs/{ORG_ID}/provider-accounts/gcp/status",
        reply(200, json=body),
    )
    assert await client.providers.gcp_status(ORG_ID) == GcpStatus(
        configured=True,
        allowed=True,
        project_id="acme-prod",
        region="us-central1",
        connections=[
            GcpConnection(
                id=uuid.UUID(ACCOUNT_ID),
                name="production",
                is_default=True,
                project_id="acme-prod",
                region="us-central1",
            )
        ],
    )


async def test_gcp_status_unconfigured(client: AsyncReflexBuild, mock_api: MockAPI):
    body = {
        "configured": False,
        "allowed": False,
        "project_id": None,
        "region": None,
        "connections": [],
    }
    mock_api.add(
        "GET",
        f"/api/v1/orgs/{ORG_ID}/provider-accounts/gcp/status",
        reply(200, json=body),
    )
    assert await client.providers.gcp_status(uuid.UUID(ORG_ID)) == GcpStatus(
        configured=False,
        allowed=False,
        project_id=None,
        region=None,
        connections=[],
    )


async def test_accounts(client: AsyncReflexBuild, mock_api: MockAPI):
    account = {
        "id": ACCOUNT_ID,
        "provider": "gcp",
        "name": "production",
        "is_default": True,
        "config": {"project_id": "acme-prod", "region": "us-central1"},
        "created_by": USER_ID,
        "created_at": "2026-09-16T10:00:00+00:00",
        "updated_at": "2026-09-16T11:00:00+00:00",
    }
    mock_api.add(
        "GET", f"/api/v1/orgs/{ORG_ID}/provider-accounts", reply(200, json=[account])
    )
    utc = datetime.timezone.utc
    assert await client.providers.accounts(ORG_ID) == [
        ProviderAccount(
            id=uuid.UUID(ACCOUNT_ID),
            provider="gcp",
            name="production",
            is_default=True,
            config={"project_id": "acme-prod", "region": "us-central1"},
            created_by=uuid.UUID(USER_ID),
            created_at=datetime.datetime(2026, 9, 16, 10, tzinfo=utc),
            updated_at=datetime.datetime(2026, 9, 16, 11, tzinfo=utc),
        )
    ]


async def test_cloud_run_manifest(client: AsyncReflexBuild, mock_api: MockAPI):
    body = {"dockerfile": "FROM python:3.13", "deploy_command": "gcloud run deploy"}
    mock_api.add("GET", "/api/v1/cli/gcp-cloud-run-manifest", reply(200, json=body))
    assert await client.providers.cloud_run_manifest() == CloudRunManifest(**body)


async def test_connect_gcp(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "PUT",
        GCP_PATH,
        reply(200, json={"status": "ok", "skipped_checks": ["public access policy"]}),
    )
    relocation = {
        "project_id": "acme-old",
        "region": "us-east1",
        "project_number": "123456",
        "artifact_repo": "reflex-build-apps",
    }
    assert await client.providers.connect_gcp(
        ORG_ID,
        service_account_key=KEY,
        project_number="987654",
        region="us-central1",
        ingress="",
        relocate_from=relocation,
    ) == ["public access policy"]
    body = json_body(mock_api.requests[0])
    # The key file's contents are sent as a string.
    assert json.loads(body.pop("service_account_key")) == KEY
    assert body == {
        "project_number": "987654",
        "region": "us-central1",
        # Omitted settings are sent as null: the runtime service account resets,
        # and network settings are kept.
        "runtime_service_account": None,
        "ingress": "",
        "vpc_connector": None,
        "vpc_egress": None,
        "acknowledge_relocation": True,
        "acknowledged_from": relocation,
    }


async def test_disconnect_gcp(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add("DELETE", GCP_PATH, reply(200, json={"status": "deleted"}))
    assert await client.providers.disconnect_gcp(ORG_ID) is None


async def test_gcp_blocking_apps(client: AsyncReflexBuild, mock_api: MockAPI):
    app_id = str(uuid.uuid4())
    mock_api.add(
        "GET",
        f"{GCP_PATH}/blocking-apps",
        reply(
            200,
            json=[
                {
                    "app_id": app_id,
                    "name": "dashboard",
                    "project_name": "default",
                    "is_deleted": True,
                    "project_is_deleted": False,
                    "release_unconfirmed": True,
                    "awaiting_provisioning": False,
                }
            ],
        ),
    )
    assert await client.providers.gcp_blocking_apps(ORG_ID) == [
        GcpBlockingApp(
            app_id=uuid.UUID(app_id),
            name="dashboard",
            project_name="default",
            is_deleted=True,
            project_is_deleted=False,
            release_unconfirmed=True,
            awaiting_provisioning=False,
        )
    ]


async def test_gcp_connections_create(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "POST",
        f"{GCP_PATH}/connections",
        reply(200, json={"status": "ok", "skipped_checks": []}),
    )
    key_text = json.dumps(KEY)
    assert (
        await client.providers.gcp_connections.create(
            ORG_ID,
            "staging",
            service_account_key=key_text,
            project_number="987654",
            region="us-central1",
            artifact_repo="apps",
        )
        == []
    )
    assert json_body(mock_api.requests[0]) == {
        "name": "staging",
        "service_account_key": key_text,
        "project_number": "987654",
        "region": "us-central1",
        "artifact_repo": "apps",
        "runtime_service_account": None,
        "ingress": None,
        "vpc_connector": None,
        "vpc_egress": None,
    }


async def test_gcp_connections_update(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "PATCH",
        f"{GCP_PATH}/connections/{ACCOUNT_ID}",
        reply(200, json={"status": "ok", "skipped_checks": []}),
    )
    assert (
        await client.providers.gcp_connections.update(
            ORG_ID,
            ACCOUNT_ID,
            expected_project_id="acme-prod",
            expected_region="us-central1",
            vpc_connector="",
        )
        == []
    )
    # Only the settings passed are sent; the rest are kept.
    assert json_body(mock_api.requests[0]) == {
        "expected_project_id": "acme-prod",
        "expected_region": "us-central1",
        "vpc_connector": "",
    }


async def test_gcp_connections_rotate_key(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "POST",
        f"{GCP_PATH}/connections/{ACCOUNT_ID}/rotate-key",
        reply(
            200,
            json={
                "status": "ok",
                "connection_name": "default",
                "project_id": "acme-prod",
                "client_email": "deployer@acme-prod.iam.gserviceaccount.com",
                "new_key_id": "new",
                "old_key_id": None,
                "old_client_email": None,
                "repinned_debts": 0,
                "skipped_checks": [],
            },
        ),
    )
    assert await client.providers.gcp_connections.rotate_key(
        ORG_ID, ACCOUNT_ID, KEY
    ) == GcpKeyRotation(
        connection_name="default",
        project_id="acme-prod",
        client_email="deployer@acme-prod.iam.gserviceaccount.com",
        new_key_id="new",
        old_key_id=None,
        old_client_email=None,
        skipped_checks=[],
    )
    body = json_body(mock_api.requests[0])
    assert json.loads(body["service_account_key"]) == KEY


async def test_gcp_connections_verify(client: AsyncReflexBuild, mock_api: MockAPI):
    # Problems are reported in a 200.
    mock_api.add(
        "POST",
        f"{GCP_PATH}/connections/{ACCOUNT_ID}/verify",
        reply(
            200,
            json={
                "ok": False,
                "connection_name": "default",
                "project_id": "acme-prod",
                "client_email": "",
                "problems": ["the stored service-account key cannot be read"],
                "checks": [
                    {
                        "check": "stored credentials",
                        "outcome": "failed",
                        "detail": "the stored key can no longer be read",
                    }
                ],
            },
        ),
    )
    assert await client.providers.gcp_connections.verify(
        ORG_ID, ACCOUNT_ID
    ) == GcpVerification(
        ok=False,
        connection_name="default",
        project_id="acme-prod",
        client_email="",
        problems=["the stored service-account key cannot be read"],
        checks=[
            GcpCheck(
                check="stored credentials",
                outcome="failed",
                detail="the stored key can no longer be read",
            )
        ],
    )


async def test_gcp_connections_set_default_is_retried(
    client: AsyncReflexBuild, mock_api: MockAPI
):
    mock_api.add(
        "POST",
        f"{GCP_PATH}/connections/{ACCOUNT_ID}/default",
        reply(503),
        reply(200, json={"status": "ok"}),
    )
    await client.providers.gcp_connections.set_default(ORG_ID, ACCOUNT_ID)
    first, retry = mock_api.requests
    assert first.headers["X-Request-ID"] == retry.headers["X-Request-ID"]


async def test_gcp_connections_delete(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "DELETE",
        f"{GCP_PATH}/connections/{ACCOUNT_ID}",
        reply(200, json={"status": "deleted"}),
    )
    assert await client.providers.gcp_connections.delete(ORG_ID, ACCOUNT_ID) is None
