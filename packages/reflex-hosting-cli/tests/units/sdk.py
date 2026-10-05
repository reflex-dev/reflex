"""Shared helpers for building the SDK results the hosting CLI tests drive."""

from __future__ import annotations

import datetime
import json
import uuid
from typing import Any
from unittest.mock import MagicMock

from reflex_build_sdk import APIStatusError
from reflex_build_sdk._errors import status_error_from_response
from reflex_build_sdk.transports import Request, Response
from reflex_build_sdk.types import GcpConnection, Me, ProviderAccount
from reflex_cli.utils import hosting


class FakeClient(hosting.AuthenticatedClient):
    """An authenticated client whose API calls reach a mock rather than the API.

    ``api`` is typed loosely so a test can both drive it
    (``client.api.apps.get.return_value = ...``) and assert on it.
    """

    api: Any


def fake_client(**identity: Any) -> FakeClient:
    """Build an authenticated client whose API calls reach a mock.

    Drive and assert on ``client.api``, e.g.
    ``client.api.apps.get.return_value = ...`` and
    ``client.api.apps.stop.assert_called_once_with(app_id)``.

    Args:
        identity: Overrides for the identity behind the token, e.g.
            ``tier="Enterprise"`` or ``org_id=uuid.UUID(...)``.

    Returns:
        The client.
    """
    fields: dict[str, Any] = {
        "user_id": uuid.UUID(int=1),
        "org_id": uuid.UUID(int=2),
        "email": "someone@example.com",
        "tier": "Pro",
    }
    fields.update(identity)
    return FakeClient(api=MagicMock(), me=Me(**fields))


def patch_upload_client(mocker: Any, client: FakeClient) -> None:
    """Make the deploy's upload-sized client the one the test is driving.

    ``deployments.create`` runs on a client of its own, built for the timeouts
    an archive upload needs; a test wants that to be the same mock as the rest.

    Args:
        mocker: The pytest-mock fixture.
        client: The client the command under test receives.
    """
    uploader = MagicMock()
    uploader.__enter__.return_value = client.api
    mocker.patch("reflex_cli.utils.hosting.upload_client", return_value=uploader)


def api_error(status_code: int, detail: str) -> APIStatusError:
    """Build the error the SDK raises for a refused request.

    Args:
        status_code: The status the API answered with.
        detail: The API's explanation, which the CLI reports.

    Returns:
        The error, to raise from a mocked call.
    """
    request = Request(
        method="GET",
        url="https://build.reflex.dev/api/v1/test",
        headers={"X-Request-ID": uuid.uuid4().hex},
    )
    response = Response(
        status_code=status_code,
        reason_phrase="",
        headers={},
        content=json.dumps({"detail": detail}).encode(),
        request=request,
    )
    return status_error_from_response(response)


def gcp_connection(name: str, **fields: Any) -> GcpConnection:
    """Build a GCP connection the way the org's status reports one.

    Args:
        name: The connection's name.
        fields: Overrides for its other fields.

    Returns:
        The connection.
    """
    return GcpConnection(**{
        "id": uuid.uuid5(uuid.NAMESPACE_OID, name),
        "name": name,
        "is_default": False,
        "project_id": "my-proj",
        "region": "us-central1",
        **fields,
    })


def provider_account(name: str, **fields: Any) -> ProviderAccount:
    """Build a provider account the way the account listing reports one.

    Args:
        name: The account's name, which also seeds its id.
        fields: Overrides for its other fields; ``config`` replaces the default.

    Returns:
        The provider account.
    """
    created = datetime.datetime(2026, 7, 1, tzinfo=datetime.timezone.utc)
    return ProviderAccount(**{
        "id": uuid.uuid5(uuid.NAMESPACE_OID, name),
        "provider": "gcp",
        "name": name,
        "is_default": False,
        "config": {"project_id": "my-proj", "region": "us-central1"},
        "created_by": uuid.UUID(int=3),
        "created_at": created,
        "updated_at": created,
        **fields,
    })
