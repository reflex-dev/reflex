from __future__ import annotations

import json

from click.testing import CliRunner
from pytest_mock import MockFixture
from reflex_build_sdk.types import GcpStatus
from reflex_cli.v2.providers import providers_cli

from .utils import api_error, fake_client, gcp_connection, provider_account

runner = CliRunner()

_CLIENT = fake_client(org_id="org-1", tier="Enterprise")


def _authed(mocker: MockFixture, client=_CLIENT):
    """Patch the client lookup and hand the client back, with a fresh API mock.

    Args:
        mocker: The pytest-mock fixture.
        client: The client to return; defaults to the module's Enterprise one.

    Returns:
        The client every command under test will receive.
    """
    client.api.reset_mock(return_value=True, side_effect=True)
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client", return_value=client
    )
    return client


def _status(**fields) -> GcpStatus:
    """Build an org's GCP status.

    Args:
        fields: Overrides for the status fields.

    Returns:
        The status.
    """
    return GcpStatus(**{
        "configured": True,
        "allowed": True,
        "project_id": None,
        "region": None,
        "connections": [],
        **fields,
    })


def test_providers_status_ready(mocker: MockFixture):
    """A connected + allowed org reports GCP as ready with project/region."""
    client = _authed(mocker)
    client.api.providers.gcp_status.return_value = _status(
        project_id="my-proj", region="us-central1"
    )

    result = runner.invoke(providers_cli, ["status"])

    assert result.exit_code == 0, result.output
    assert "ready" in result.output.lower()
    assert "us-central1" in result.output
    # Defaults to the token's org when --org-id is omitted.
    assert client.api.providers.gcp_status.call_args.args[0] == "org-1"


def test_providers_status_not_configured(mocker: MockFixture):
    """An allowed-but-unconnected org is told to connect from the dashboard."""
    client = _authed(mocker)
    client.api.providers.gcp_status.return_value = _status(configured=False)

    result = runner.invoke(providers_cli, ["status"])

    assert result.exit_code == 0, result.output
    assert "not connected" in result.output.lower()


def test_providers_status_json(mocker: MockFixture):
    """--json emits the status as the API reports it."""
    client = _authed(mocker)
    client.api.providers.gcp_status.return_value = _status(
        project_id="my-proj", region="us-central1"
    )

    result = runner.invoke(providers_cli, ["status", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "configured": True,
        "allowed": True,
        "project_id": "my-proj",
        "region": "us-central1",
        "connections": [],
    }


def test_providers_status_error_exits_nonzero(mocker: MockFixture):
    """A 403 (not a member) surfaces the detail and exits non-zero."""
    client = _authed(mocker)
    client.api.providers.gcp_status.side_effect = api_error(403, "Not a member")

    result = runner.invoke(providers_cli, ["status"])

    assert result.exit_code == 1


def test_providers_list(mocker: MockFixture):
    """Listing renders a row per connected provider account."""
    client = _authed(mocker)
    client.api.providers.accounts.return_value = [provider_account("us-prod")]

    result = runner.invoke(providers_cli, ["list"])

    assert result.exit_code == 0, result.output
    assert "gcp" in result.output
    assert "my-proj" in result.output


def test_providers_list_empty(mocker: MockFixture):
    """An org with no providers gets a connect hint, not a table."""
    client = _authed(mocker)
    client.api.providers.accounts.return_value = []

    result = runner.invoke(providers_cli, ["list"])

    assert result.exit_code == 0, result.output
    assert "No cloud providers connected" in result.output


# Wide enough that a service account email is not wrapped across table rows.
_WIDE = {"COLUMNS": "200"}


def test_providers_list_shows_the_runtime_service_account(mocker: MockFixture):
    """A connection's runtime identity is listed; without one, the default is."""
    client = _authed(mocker)
    client.api.providers.accounts.return_value = [
        provider_account(
            "us-prod",
            is_default=True,
            config={
                "project_id": "my-proj",
                "region": "us-central1",
                "runtime_service_account": "apps@my-proj.iam.gserviceaccount.com",
            },
        ),
        provider_account(
            "eu-prod", config={"project_id": "eu-proj", "region": "europe-west1"}
        ),
    ]

    result = runner.invoke(providers_cli, ["list"], env=_WIDE)

    assert result.exit_code == 0, result.output
    assert "us-prod" in result.output
    assert "eu-prod" in result.output
    assert "apps@my-proj.iam.gserviceaccount.com" in result.output
    # The connection that names none runs as the project's default, which is
    # not the same as one whose identity could not be read.
    assert "(project default)" in result.output


def test_providers_list_falls_back_for_a_non_admin(mocker: MockFixture):
    """A member who cannot read the accounts still gets the connection names."""
    client = _authed(mocker)
    client.api.providers.accounts.side_effect = api_error(403, "no permission")
    connections = mocker.patch(
        "reflex_cli.utils.hosting.list_gcp_connections",
        return_value=[gcp_connection("us-prod", is_default=True)],
    )

    result = runner.invoke(providers_cli, ["list"], env=_WIDE)

    assert result.exit_code == 0, result.output
    assert "us-prod" in result.output
    # Not "(project default)": the runtime identity was unreadable, which is a
    # different answer from a connection that names none.
    assert "(needs org admin)" in result.output
    assert connections.call_args.kwargs["org_id"] == "org-1"


def test_providers_status_separates_a_refusal_from_a_failed_read(
    mocker: MockFixture,
):
    """A 5xx is a broken minute, not a standing permissions fact."""
    client = _authed(mocker)
    client.api.providers.gcp_status.return_value = _status(
        connections=[gcp_connection("us-prod", is_default=True)]
    )
    client.api.providers.accounts.side_effect = api_error(500, "boom")

    result = runner.invoke(providers_cli, ["status"], env=_WIDE)

    assert result.exit_code == 0, result.output
    assert "(unavailable)" in result.output
    assert "(needs org admin)" not in result.output
    # Warned rather than swallowed, but the status itself still answers.
    assert "Could not read the runtime service accounts" in result.output
    assert "ready for deploys" in result.output


def test_providers_status_names_a_permission_gap_as_one(mocker: MockFixture):
    """A 403 is exactly the case the "needs org admin" label is for."""
    client = _authed(mocker)
    client.api.providers.gcp_status.return_value = _status(
        connections=[gcp_connection("us-prod", is_default=True)]
    )
    client.api.providers.accounts.side_effect = api_error(403, "no permission")

    result = runner.invoke(providers_cli, ["status"], env=_WIDE)

    assert result.exit_code == 0, result.output
    assert "(needs org admin)" in result.output
    assert "(unavailable)" not in result.output
    # Not a warning: a member who is not an admin is not a problem to report.
    assert "Could not read" not in result.output


def test_providers_list_json_has_one_shape_either_way(mocker: MockFixture):
    """The fallback emits the released row shape, not a second one."""
    client = _authed(mocker)
    client.api.providers.accounts.side_effect = api_error(403, "no permission")
    connection = gcp_connection("us-prod", is_default=True)
    mocker.patch(
        "reflex_cli.utils.hosting.list_gcp_connections", return_value=[connection]
    )

    result = runner.invoke(providers_cli, ["list", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == [
        {
            "id": str(connection.id),
            "provider": "gcp",
            "name": "us-prod",
            "is_default": True,
            # Nested like the account listing's, so one schema comes out of the
            # command; the runtime service account is absent because it is what
            # the caller could not read.
            "config": {"project_id": "my-proj", "region": "us-central1"},
        }
    ]


def test_providers_list_reports_the_fallback_failure(mocker: MockFixture):
    """A failed fallback says what failed, not the refusal that led to it."""
    client = _authed(mocker)
    client.api.providers.accounts.side_effect = api_error(403, "no permission")
    mocker.patch(
        "reflex_cli.utils.hosting.list_gcp_connections",
        side_effect=RuntimeError("gateway timeout"),
    )

    result = runner.invoke(providers_cli, ["list"], env=_WIDE)

    assert result.exit_code == 1
    assert "gateway timeout" in result.output


def test_providers_list_other_error_exits_nonzero(mocker: MockFixture):
    """A server error is not a permissions problem, so nothing is guessed at."""
    client = _authed(mocker)
    client.api.providers.accounts.side_effect = api_error(500, "boom")
    fallback = mocker.patch("reflex_cli.utils.hosting.list_gcp_connections")

    result = runner.invoke(providers_cli, ["list"])

    assert result.exit_code == 1
    fallback.assert_not_called()


def test_providers_connections_is_the_same_listing(mocker: MockFixture):
    """`providers connections` is the name the deploy flag points at."""
    client = _authed(mocker)
    client.api.providers.accounts.return_value = [
        provider_account("us-prod", is_default=True)
    ]

    result = runner.invoke(providers_cli, ["connections"], env=_WIDE)

    assert result.exit_code == 0, result.output
    assert "us-prod" in result.output


def test_providers_status_lists_the_connections(mocker: MockFixture):
    """Status names the connections a deploy can select between."""
    client = _authed(mocker)
    connection = gcp_connection("us-prod", is_default=True)
    client.api.providers.gcp_status.return_value = _status(
        project_id="my-proj", region="us-central1", connections=[connection]
    )
    client.api.providers.accounts.return_value = [
        provider_account(
            "us-prod",
            id=connection.id,
            config={"runtime_service_account": "apps@my-proj.iam.gserviceaccount.com"},
        )
    ]

    result = runner.invoke(providers_cli, ["status"], env=_WIDE)

    assert result.exit_code == 0, result.output
    assert "us-prod" in result.output
    assert "apps@my-proj.iam.gserviceaccount.com" in result.output


def test_providers_status_requires_org(mocker: MockFixture):
    """With no token org and no --org-id, the command errors out."""
    _authed(mocker, fake_client(org_id=""))

    result = runner.invoke(providers_cli, ["status"])

    assert result.exit_code == 1
