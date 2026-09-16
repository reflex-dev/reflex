# Generated from tests/units/reflex_sdk/_async/resources/test_providers.py by packages/reflex-sdk/scripts/unasync.py. Do not edit.
from __future__ import annotations

import datetime
import uuid
from collections.abc import Iterator

import pytest
from reflex_sdk import ReflexCloud
from reflex_sdk.types import CloudRunManifest, GcpConnection, GcpStatus, ProviderAccount

from tests.units.reflex_sdk.conftest import MockAPI, MockTransport, reply

ORG_ID = "1f6c1d0e-6f59-4d2b-a0f1-0f4e4a3b2c19"
ACCOUNT_ID = "2b7c9d1e-3f4a-4b5c-8d6e-7f8091a2b3c4"
USER_ID = "8b0f4a52-3a8a-4c43-9d7e-2f0c7d2a4b11"


@pytest.fixture
def client(mock_api: MockAPI) -> Iterator[ReflexCloud]:
    """A client talking to the mock API.

    Args:
        mock_api: The mock API.

    Yields:
        The client.
    """
    with ReflexCloud(token="test-token", transport=MockTransport(mock_api)) as client:
        yield client


def test_gcp_status(client: ReflexCloud, mock_api: MockAPI):
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
    assert client.providers.gcp_status(ORG_ID) == GcpStatus(
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


def test_gcp_status_unconfigured(client: ReflexCloud, mock_api: MockAPI):
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
    status = client.providers.gcp_status(uuid.UUID(ORG_ID))
    assert not status.configured
    assert status.connections == []


def test_accounts(client: ReflexCloud, mock_api: MockAPI):
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
    assert client.providers.accounts(ORG_ID) == [
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


def test_cloud_run_manifest(client: ReflexCloud, mock_api: MockAPI):
    body = {"dockerfile": "FROM python:3.13", "deploy_command": "gcloud run deploy"}
    mock_api.add("GET", "/api/v1/cli/gcp-cloud-run-manifest", reply(200, json=body))
    assert client.providers.cloud_run_manifest() == CloudRunManifest(**body)
