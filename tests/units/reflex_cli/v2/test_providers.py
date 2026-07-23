from __future__ import annotations

import json

import httpx
from click.testing import CliRunner
from pytest_mock import MockFixture
from reflex_cli.utils import hosting
from reflex_cli.v2.providers import providers_cli

runner = CliRunner()

_CLIENT = hosting.AuthenticatedClient(
    token="fake-token", validated_data={"org_id": "org-1", "tier": "Enterprise"}
)


def test_providers_status_ready(mocker: MockFixture):
    """A connected + allowed org reports GCP as ready with project/region."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client", return_value=_CLIENT
    )
    mock_status = mocker.patch(
        "reflex_cli.utils.hosting.get_gcp_provider_status",
        return_value={
            "configured": True,
            "allowed": True,
            "project_id": "my-proj",
            "region": "us-central1",
        },
    )

    result = runner.invoke(providers_cli, ["status"])

    assert result.exit_code == 0, result.output
    assert "ready" in result.output.lower()
    assert "us-central1" in result.output
    # Defaults to the token's org when --org-id is omitted.
    assert mock_status.call_args.args[0] == "org-1"


def test_providers_status_not_configured(mocker: MockFixture):
    """An allowed-but-unconnected org is told to connect from the dashboard."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client", return_value=_CLIENT
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_gcp_provider_status",
        return_value={"configured": False, "allowed": True},
    )

    result = runner.invoke(providers_cli, ["status"])

    assert result.exit_code == 0, result.output
    assert "not connected" in result.output.lower()


def test_providers_status_json(mocker: MockFixture):
    """--json emits the raw status payload."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client", return_value=_CLIENT
    )
    payload = {
        "configured": True,
        "allowed": True,
        "project_id": "my-proj",
        "region": "us-central1",
    }
    mocker.patch(
        "reflex_cli.utils.hosting.get_gcp_provider_status", return_value=payload
    )

    result = runner.invoke(providers_cli, ["status", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == payload


def test_providers_status_error_exits_nonzero(mocker: MockFixture):
    """A 403 (not a member) surfaces the detail and exits non-zero."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client", return_value=_CLIENT
    )
    response = httpx.Response(
        403, json={"detail": "Not a member"}, request=httpx.Request("GET", "https://x")
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_gcp_provider_status",
        side_effect=httpx.HTTPStatusError(
            "e", request=response.request, response=response
        ),
    )

    result = runner.invoke(providers_cli, ["status"])

    assert result.exit_code == 1


def test_providers_list(mocker: MockFixture):
    """Listing renders a row per connected provider account."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client", return_value=_CLIENT
    )
    mocker.patch(
        "reflex_cli.utils.hosting.list_provider_accounts",
        return_value=[
            {
                "provider": "gcp",
                "config": {"project_id": "my-proj", "region": "us-central1"},
                "created_at": "2026-07-01T00:00:00Z",
            }
        ],
    )

    result = runner.invoke(providers_cli, ["list"])

    assert result.exit_code == 0, result.output
    assert "gcp" in result.output
    assert "my-proj" in result.output


def test_providers_list_empty(mocker: MockFixture):
    """An org with no providers gets a connect hint, not a table."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client", return_value=_CLIENT
    )
    mocker.patch("reflex_cli.utils.hosting.list_provider_accounts", return_value=[])

    result = runner.invoke(providers_cli, ["list"])

    assert result.exit_code == 0, result.output
    assert "No cloud providers connected" in result.output


def test_providers_status_requires_org(mocker: MockFixture):
    """With no token org and no --org-id, the command errors out."""
    client = hosting.AuthenticatedClient(token="fake-token", validated_data={})
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client", return_value=client
    )

    result = runner.invoke(providers_cli, ["status"])

    assert result.exit_code == 1
