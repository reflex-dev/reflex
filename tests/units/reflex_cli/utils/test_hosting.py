from __future__ import annotations

import json
import logging
import uuid
from unittest.mock import MagicMock, mock_open

import click
import pytest
from pytest_mock import MockerFixture, MockFixture
from reflex_build_sdk.types import DeploymentReport, GcpConnection, GcpStatus
from reflex_cli import constants
from reflex_cli.utils.exceptions import TokenAccessDeniedError, TokenValidationError
from reflex_cli.utils.hosting import (
    ScaleParams,
    ScaleType,
    TokenSource,
    _report_deployment_failure,
    _strip_terminal_controls,
    as_json_document,
    authenticated_token,
    delete_token_from_config,
    deployment_status_failed,
    find_gcp_connection,
    gcp_deploy_available,
    get_auth_request_id,
    get_authenticated_client,
    get_existing_access_token,
    get_existing_access_token_with_source,
    get_selected_project,
    get_token_org_id,
    get_token_tier,
    list_gcp_connections,
    normalize_project_id,
    normalize_provider,
    provider_display_name,
    save_token_to_config,
    set_instance_bounds,
    stored_access_token,
    validate_token,
    validate_token_with_retries,
)

from tests.units.reflex_cli.sdk import api_error, fake_client

_client = fake_client


@pytest.mark.parametrize(
    "config_content, expected_token",
    [
        ('{"access_token": "valid_token"}', "valid_token"),
        ("{}", ""),
        (None, ""),
    ],
)
def test_get_existing_access_token(
    mocker: MockerFixture, config_content: str | None, expected_token: str
):
    mocker.patch("os.environ.get", return_value="")
    mocker.patch("pathlib.Path.open", mock_open(read_data=config_content))
    assert get_existing_access_token() == expected_token

    mocker.patch("pathlib.Path.open", side_effect=FileNotFoundError("Test exception"))
    assert get_existing_access_token() == ""


def test_get_existing_access_token_prefers_the_environment(
    monkeypatch: pytest.MonkeyPatch,
):
    """An exported token is an explicit choice; the config file is ambient state.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    monkeypatch.setenv("REFLEX_ACCESS_TOKEN", "env_token")
    constants.Hosting.HOSTING_JSON.write_text('{"access_token": "config_token"}')

    assert get_existing_access_token_with_source() == (
        "env_token",
        TokenSource.ENVIRONMENT,
    )


def test_get_existing_access_token_falls_back_to_the_config_file(
    monkeypatch: pytest.MonkeyPatch,
):
    """Without the environment variable the stored token is used.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    monkeypatch.delenv("REFLEX_ACCESS_TOKEN", raising=False)
    constants.Hosting.HOSTING_JSON.write_text('{"access_token": "config_token"}')

    assert get_existing_access_token_with_source() == (
        "config_token",
        TokenSource.CONFIG,
    )


def test_get_existing_access_token_ignores_an_empty_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
):
    """An empty export is not a token and must not shadow the config file.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    monkeypatch.setenv("REFLEX_ACCESS_TOKEN", "")
    constants.Hosting.HOSTING_JSON.write_text('{"access_token": "config_token"}')

    assert get_existing_access_token_with_source() == (
        "config_token",
        TokenSource.CONFIG,
    )


def test_get_existing_access_token_with_no_token_anywhere(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("REFLEX_ACCESS_TOKEN", raising=False)
    mocker.patch("pathlib.Path.open", side_effect=FileNotFoundError("Test exception"))

    assert get_existing_access_token_with_source() == ("", TokenSource.NONE)


@pytest.mark.parametrize(
    "config_content, expected",
    [
        ('{"access_token": "valid_token"}', {}),
        ('{"access_token": "valid_token", "project": "p1"}', {"project": "p1"}),
        ('{"another_key": "value"}', {"another_key": "value"}),
    ],
)
def test_delete_token_from_config(config_content: str, expected: dict):
    """Only the token is removed; everything else in the config survives.

    Args:
        config_content: The starting contents of the config file.
        expected: The config expected to remain afterwards.
    """
    constants.Hosting.HOSTING_JSON.write_text(config_content)

    delete_token_from_config()

    assert json.loads(constants.Hosting.HOSTING_JSON.read_text()) == expected


def test_delete_token_from_config_without_a_config_file():
    """Deleting when no config exists is a no-op rather than an error."""
    assert not constants.Hosting.HOSTING_JSON.exists()

    delete_token_from_config()

    assert not constants.Hosting.HOSTING_JSON.exists()


def test_delete_token_from_config_keeps_the_config_when_the_write_fails(
    mocker: MockerFixture,
):
    """A failed delete must leave the existing config readable, not truncated.

    Args:
        mocker: Pytest mocker fixture.
    """
    original = '{"access_token": "good_token", "project": "p1"}'
    constants.Hosting.HOSTING_JSON.write_text(original)
    mocker.patch("json.dump", side_effect=OSError("disk full"))

    delete_token_from_config()

    assert constants.Hosting.HOSTING_JSON.read_text() == original
    assert list(constants.Hosting.HOSTING_JSON.parent.iterdir()) == [
        constants.Hosting.HOSTING_JSON
    ]


def test_delete_token_from_config_keeps_an_unreadable_config(
    mocker: MockerFixture,
):
    """A config that cannot be parsed is left alone rather than replaced.

    Args:
        mocker: Pytest mocker fixture.
    """
    malformed = '{"access_token": "good_token", "project": "p1"'
    constants.Hosting.HOSTING_JSON.write_text(malformed)

    delete_token_from_config()

    assert constants.Hosting.HOSTING_JSON.read_text() == malformed


def test_save_token_to_config_recovers_from_an_unreadable_config():
    """Re-authenticating still works when the config is malformed."""
    constants.Hosting.HOSTING_JSON.write_text('{"access_token": "good_token"')

    save_token_to_config("new_token")

    assert json.loads(constants.Hosting.HOSTING_JSON.read_text()) == {
        "access_token": "new_token"
    }


def test_stored_access_token_distinguishes_absent_from_unreadable():
    """A missing config reads as no token; a malformed one is an error."""
    assert stored_access_token() == ""

    constants.Hosting.HOSTING_JSON.write_text('{"project": "p1"}')
    assert stored_access_token() == ""

    constants.Hosting.HOSTING_JSON.write_text('{"access_token": "tok"}')
    assert stored_access_token() == "tok"

    constants.Hosting.HOSTING_JSON.write_text("{not json")
    with pytest.raises(ValueError):
        stored_access_token()

    # Valid JSON that is not an object is still unusable, not empty.
    constants.Hosting.HOSTING_JSON.write_text('["not", "an", "object"]')
    with pytest.raises(ValueError):
        stored_access_token()


def test_delete_token_from_config_tolerates_an_unremovable_legacy_file(
    mocker: MockerFixture,
):
    """The legacy cleanup must not abort the token removal it follows.

    Args:
        mocker: Pytest mocker fixture.
    """
    constants.Hosting.HOSTING_JSON.write_text('{"access_token": "valid_token"}')
    constants.Hosting.HOSTING_JSON_V0.write_text("{}")
    mocker.patch("pathlib.Path.unlink", side_effect=PermissionError("denied"))

    delete_token_from_config()

    assert json.loads(constants.Hosting.HOSTING_JSON.read_text()) == {}


def test_delete_token_from_config_removes_the_legacy_file():
    """The pre-v1 hosting file is removed alongside the token."""
    constants.Hosting.HOSTING_JSON.write_text('{"access_token": "valid_token"}')
    constants.Hosting.HOSTING_JSON_V0.write_text("{}")

    delete_token_from_config()

    assert not constants.Hosting.HOSTING_JSON_V0.exists()


def test_save_token_to_config_creates_the_config():
    """Saving works when neither the directory nor the file exists yet."""
    save_token_to_config("test_token")

    assert json.loads(constants.Hosting.HOSTING_JSON.read_text()) == {
        "access_token": "test_token"
    }


def test_save_token_to_config_preserves_other_keys():
    """Saving a token leaves unrelated config entries untouched."""
    constants.Hosting.HOSTING_JSON.write_text(
        '{"access_token": "old_token", "project": "p1"}'
    )

    save_token_to_config("new_token")

    assert json.loads(constants.Hosting.HOSTING_JSON.read_text()) == {
        "access_token": "new_token",
        "project": "p1",
    }


def test_save_token_to_config_keeps_the_old_token_when_the_write_fails(
    mocker: MockerFixture,
):
    """A failed write must not truncate the credentials already on disk.

    Args:
        mocker: Pytest mocker fixture.
    """
    original = '{"access_token": "good_token", "project": "p1"}'
    constants.Hosting.HOSTING_JSON.write_text(original)
    mocker.patch("json.dump", side_effect=OSError("disk full"))

    save_token_to_config("new_token")

    assert constants.Hosting.HOSTING_JSON.read_text() == original
    # The temporary file used for the atomic replace is cleaned up.
    assert list(constants.Hosting.HOSTING_JSON.parent.iterdir()) == [
        constants.Hosting.HOSTING_JSON
    ]


def test_authenticated_token_found_and_valid(mocker: MockFixture):
    """A stored token that validates comes back with the identity behind it.

    Args:
        mocker: Pytest mocker fixture.
    """
    mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token", return_value="valid_token"
    )
    mocker.patch("reflex_cli.utils.hosting._validate", return_value=_client().me)

    token, info = authenticated_token()

    assert token == "valid_token"
    assert info["tier"] == "Pro"
    assert info["user_id"] == str(uuid.UUID(int=1))


def test_authenticated_token_not_found(mocker: MockFixture):
    """With nothing stored there is nothing to validate.

    Args:
        mocker: Pytest mocker fixture.
    """
    mocker.patch("reflex_cli.utils.hosting.get_existing_access_token", return_value="")

    assert authenticated_token() == ("", {})


def test_authenticated_token_found_but_invalid(mocker: MockFixture):
    """A refused token is reported as no token at all, and is discarded.

    Args:
        mocker: Pytest mocker fixture.
    """
    mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token", return_value="bad_token"
    )
    mocker.patch(
        "reflex_cli.utils.hosting._validate",
        side_effect=TokenAccessDeniedError("access denied", request_id="req-1"),
    )
    delete_token = mocker.patch("reflex_cli.utils.hosting.delete_token_from_config")

    assert authenticated_token() == ("", {})
    delete_token.assert_called_once()


def test_authenticated_token_found_but_validation_fails(mocker: MockFixture):
    """A validation that could not be completed is not an identity.

    Args:
        mocker: Pytest mocker fixture.
    """
    mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token", return_value="some_token"
    )
    mocker.patch(
        "reflex_cli.utils.hosting._validate",
        side_effect=TokenValidationError("server error", request_id="req-1"),
    )

    assert authenticated_token() == ("", {})


def test_authenticate_without_token_in_non_interactive_mode(mocker: MockerFixture):
    """Non-interactive with nothing to authenticate with is an error, not a prompt.

    Args:
        mocker: Pytest mocker fixture.
    """
    mocker.patch("reflex_cli.utils.hosting.get_existing_access_token", return_value="")
    with pytest.raises(click.exceptions.Exit):
        get_authenticated_client(token=None, interactive=False)


def test_authenticate_with_env_token_in_non_interactive_mode(mocker: MockerFixture):
    """An exported token is enough to authenticate without a browser.

    Args:
        mocker: Pytest mocker fixture.
    """
    mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token", return_value="env_token"
    )
    client = _client()
    get_auth_client = mocker.patch(
        "reflex_cli.utils.hosting.get_authentication_client", return_value=client
    )

    assert get_authenticated_client(token=None, interactive=False) is client
    get_auth_client.assert_called_once_with(None)


def test_scale_arguments_are_pure_when_type_is_unspecified():
    """Reading the scale arguments must not settle the type on the object."""
    scale_params = ScaleParams(vm_type="shared-1x")

    first = scale_params.as_scale_arguments()
    second = scale_params.as_scale_arguments()

    assert scale_params.type is None
    assert first == second == {"regions": {}}


def test_scale_arguments_by_size():
    """A size scale names the machine rather than the regions."""
    scale_params = ScaleParams(type=ScaleType.SIZE, vm_type="c1m1")

    assert scale_params.as_scale_arguments() == {"vm_type": "c1m1"}


def test_normalize_provider():
    """User-facing provider names map to backend values (or None if unknown)."""
    from reflex_cli.utils.hosting import PROVIDER_GCP, PROVIDER_REFLEX_CLOUD

    assert normalize_provider("reflex-cloud") == PROVIDER_REFLEX_CLOUD
    assert normalize_provider("Reflex") == PROVIDER_REFLEX_CLOUD
    assert normalize_provider("GCP") == PROVIDER_GCP
    assert normalize_provider("google-cloud") == PROVIDER_GCP
    assert normalize_provider("aws") is None
    # The backend wire value is not exposed as a user-facing name.
    assert normalize_provider("fly") is None


def test_provider_display_name():
    """Backend provider values render human-facing labels, defaulting to Cloud."""
    assert provider_display_name("gcp") == "Google Cloud (GCP)"
    assert provider_display_name("fly") == "Reflex Cloud"
    assert provider_display_name(None) == "Reflex Cloud"


def test_get_token_org_and_tier():
    """org_id/tier come from the identity behind the token, None when absent."""
    client = _client(org_id="org-1", tier="Enterprise")
    assert get_token_org_id(client) == "org-1"
    assert get_token_tier(client) == "Enterprise"
    assert get_token_org_id(_client(org_id="")) is None
    assert get_token_tier(_client(tier="")) is None


def _status(**fields: object) -> GcpStatus:
    """Build an org's GCP status.

    Args:
        fields: Overrides for the status fields.

    Returns:
        The status.
    """
    defaults: dict[str, object] = {
        "configured": True,
        "allowed": True,
        "project_id": None,
        "region": None,
        "connections": [],
    }
    defaults.update(fields)
    return GcpStatus(**defaults)  # pyright: ignore[reportArgumentType]


def test_gcp_deploy_available_configured_and_allowed():
    """GCP is offered only when it's both connected and tier-allowed."""
    client = _client(org_id="o")
    status = _status(region="us-central1")
    client.api.providers.gcp_status.return_value = status

    assert gcp_deploy_available(client) is status


def test_gcp_deploy_available_not_allowed():
    """A connected-but-not-allowed org does not get GCP offered."""
    client = _client(org_id="o")
    client.api.providers.gcp_status.return_value = _status(allowed=False)

    assert gcp_deploy_available(client) is None


def test_gcp_deploy_available_swallows_errors():
    """A lookup failure falls back to no GCP rather than aborting the deploy."""
    client = _client(org_id="o")
    client.api.providers.gcp_status.side_effect = api_error(500, "boom")

    assert gcp_deploy_available(client) is None


def test_gcp_deploy_available_without_org():
    """No resolvable org id means GCP cannot be offered."""
    assert gcp_deploy_available(_client(org_id="")) is None


def _connection(name: str, number: int) -> GcpConnection:
    """Build a GCP connection.

    Args:
        name: The connection's name.
        number: Seeds its id.

    Returns:
        The connection.
    """
    return GcpConnection(
        id=uuid.UUID(int=number),
        name=name,
        is_default=False,
        project_id="p",
        region="us-central1",
    )


def test_list_gcp_connections_reads_the_status():
    """Connections come from the member-visible GCP status."""
    client = _client(org_id="org-1")
    connection = _connection("prod", 1)
    client.api.providers.gcp_status.return_value = _status(connections=[connection])

    assert list_gcp_connections(client) == [connection]


def test_list_gcp_connections_without_org():
    """No resolvable org id means there is nothing to list."""
    assert list_gcp_connections(_client(org_id="")) == []


def test_list_gcp_connections_explicit_org():
    """An explicit org id wins over the token's own."""
    client = _client(org_id="token-org")
    client.api.providers.gcp_status.return_value = _status()

    assert list_gcp_connections(client, org_id="other-org") == []
    client.api.providers.gcp_status.assert_called_once_with("other-org")


@pytest.mark.parametrize(
    ("wanted", "expected"),
    [
        ("prod", 1),
        ("PROD", 1),
        ("  prod  ", 1),
        ("staging", 2),
        ("nope", None),
    ],
)
def test_find_gcp_connection(wanted: str, expected: int | None):
    """Connections match on id first, then on name, case-insensitively.

    Args:
        wanted: The name or id the user asked for.
        expected: The seed of the connection that should match, if any.
    """
    connections = [_connection("prod", 1), _connection("Staging", 2)]
    match = find_gcp_connection(connections, wanted)

    assert (match.id if match else None) == (
        uuid.UUID(int=expected) if expected else None
    )


def test_find_gcp_connection_by_id():
    """A connection is found by its id as well as by its name."""
    connections = [_connection("prod", 1), _connection("Staging", 2)]

    match = find_gcp_connection(connections, str(uuid.UUID(int=2)))

    assert match is not None
    assert match.name == "Staging"


@pytest.mark.parametrize(
    ("min_instances", "max_instances", "expected"),
    [
        (0, 5, {"min_instances": 0, "max_instances": 5}),
        (2, None, {"min_instances": 2, "max_instances": 9}),
        (None, 10, {"min_instances": 3, "max_instances": 10}),
    ],
)
def test_set_instance_bounds_keeps_the_bound_it_was_not_given(
    min_instances: int | None,
    max_instances: int | None,
    expected: dict[str, int],
):
    """The endpoint replaces both bounds, so the app supplies the missing one.

    Args:
        min_instances: The minimum the caller asked for, if any.
        max_instances: The maximum the caller asked for, if any.
        expected: The bounds that should be sent.
    """
    client = _client()
    client.api.apps.get.return_value.min_instances = 3
    client.api.apps.get.return_value.max_instances = 9

    assert (
        set_instance_bounds(
            "app-1",
            client,
            min_instances=min_instances,
            max_instances=max_instances,
        )
        is None
    )
    client.api.apps.set_instance_bounds.assert_called_once_with("app-1", **expected)


@pytest.mark.parametrize(
    ("status_code", "detail"),
    [
        (400, "min_instances must be less than or equal to max_instances"),
        (400, "platform does not support instance bounds"),
        (409, "a scale operation is already running for this app"),
    ],
)
def test_set_instance_bounds_error(status_code: int, detail: str):
    """Validation, unsupported-platform and conflict details reach the caller.

    Args:
        status_code: The status the API refused with.
        detail: The API's explanation.
    """
    client = _client()
    client.api.apps.set_instance_bounds.side_effect = api_error(status_code, detail)

    result = set_instance_bounds("app-1", client, min_instances=1, max_instances=0)

    assert result is not None
    assert result.startswith("set instance bounds failed")
    assert detail in result


def test_validate_token_names_the_product_it_logs_in_through(
    mocker: MockerFixture,
):
    """The identity call records which product the login came from.

    Args:
        mocker: Pytest mocker fixture.
    """
    client = MagicMock()
    client.__enter__.return_value = client
    client.auth.me.return_value = _client(tier="Enterprise").me
    mocker.patch("reflex_cli.utils.hosting.new_client", return_value=client)

    assert validate_token("some-token")["tier"] == "Enterprise"
    client.auth.me.assert_called_once_with(source="reflex")


def test_validate_token_with_retries_warns_with_request_id(
    mocker: MockerFixture, caplog: pytest.LogCaptureFixture
):
    """A failed validation surfaces the request id for support correlation.

    Args:
        mocker: Pytest mocker fixture.
        caplog: Pytest log capture fixture.
    """
    client = MagicMock()
    client.__enter__.return_value = client
    client.auth.me.side_effect = api_error(500, "boom")
    mocker.patch("reflex_cli.utils.hosting.new_client", return_value=client)

    assert validate_token_with_retries("some-token") == {}

    request_id = get_auth_request_id()
    assert request_id
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings
    assert request_id in warnings[-1]


def test_validate_token_with_retries_access_denied_reports_request_id(
    mocker: MockerFixture, caplog: pytest.LogCaptureFixture
):
    """The access denied error message includes the auth request id.

    Args:
        mocker: Pytest mocker fixture.
        caplog: Pytest log capture fixture.
    """
    client = MagicMock()
    client.__enter__.return_value = client
    client.auth.me.side_effect = api_error(403, "denied")
    mocker.patch("reflex_cli.utils.hosting.new_client", return_value=client)
    mocker.patch("reflex_cli.utils.hosting.delete_token_from_config")

    assert validate_token_with_retries("some-token") == {}

    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors
    assert get_auth_request_id() in errors[-1]


def test_validate_token_failure_carries_request_id_on_exception(
    mocker: MockerFixture,
):
    """Validation errors carry the request id of their own request.

    Args:
        mocker: Pytest mocker fixture.
    """
    client = MagicMock()
    client.__enter__.return_value = client
    client.auth.me.side_effect = api_error(500, "boom")
    mocker.patch("reflex_cli.utils.hosting.new_client", return_value=client)

    with pytest.raises(TokenValidationError) as exc_info:
        validate_token("some-token")

    assert exc_info.value.request_id == get_auth_request_id() != ""


@pytest.mark.parametrize(
    ("status", "failed"),
    [
        ("deployment completed successfully", False),
        ("AwaitingApproval", False),
        ("bad response. received a bad response from cloud service.", False),
        ("Deployment is running smoothly.", False),
        ("build error", True),
        ("deployment failed", True),
        ("error: something went wrong", True),
        ("unable to find status for given id", True),
    ],
)
def test_deployment_status_failed(status: str, failed: bool):
    """A status is classified the same way wherever it is read.

    Args:
        status: The status string the hosting service returned.
        failed: Whether it should read as a failure.
    """
    assert deployment_status_failed(status) is failed


def test_as_json_document_renders_ids_and_timestamps_as_strings():
    """A document keeps the shape it had when response bodies were printed."""
    import datetime

    connection = _connection("prod", 1)
    when = datetime.datetime(2026, 7, 1, tzinfo=datetime.timezone.utc)

    assert as_json_document(connection) == {
        "id": str(uuid.UUID(int=1)),
        "name": "prod",
        "is_default": False,
        "project_id": "p",
        "region": "us-central1",
    }
    assert as_json_document({"at": when}) == {"at": "2026-07-01T00:00:00+00:00"}
    assert as_json_document([connection.id]) == [str(uuid.UUID(int=1))]


def _log_messages(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    """Return the captured log messages emitted at the given level.

    Args:
        caplog: The pytest log capture fixture.
        level: The numeric log level to filter records by.

    Returns:
        The formatted messages of the matching records.
    """
    return [r.getMessage() for r in caplog.records if r.levelno == level]


def _report(**fields: object) -> DeploymentReport:
    """Build a deployment's final report.

    Args:
        fields: Overrides for the report's fields.

    Returns:
        The report.
    """
    report: dict[str, object] = {
        "status": "Failed",
        "code": None,
        "fault": None,
        "reason": "",
        "guidance": "",
        "build_log_excerpt": None,
    }
    report.update(fields)
    return DeploymentReport(**report)  # pyright: ignore[reportArgumentType]


def test_failure_report_prints_reason_and_build_log(
    caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
):
    """A build failure shows its reason, its guidance and the log's tail.

    Args:
        caplog: Pytest log capture fixture.
        capsys: Pytest stdout capture fixture.
    """
    report = _report(
        code="build_failed",
        fault="customer",
        reason="Deployment error: the build failed",
        guidance="Your app failed to build.",
        build_log_excerpt="ERROR: no matching distribution for pandas==9.9",
    )

    _report_deployment_failure("dep-1", report)

    assert "Deployment error: the build failed" in _log_messages(caplog, logging.ERROR)
    assert "Your app failed to build." in _log_messages(caplog, logging.WARNING)
    printed = capsys.readouterr().out
    assert "no matching distribution for pandas==9.9" in printed
    assert "reflex cloud apps build-logs dep-1" in printed


def test_failure_report_falls_back_when_no_reason_was_recorded(
    caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
):
    """A report with nothing to say still reports what the watch ended on.

    Args:
        caplog: Pytest log capture fixture.
        capsys: Pytest stdout capture fixture.
    """
    _report_deployment_failure("dep-1", _report(), "deployment dep-1 failed")

    assert _log_messages(caplog, logging.ERROR) == ["deployment dep-1 failed"]
    assert capsys.readouterr().out == ""


def test_an_unreadable_log_is_reported_rather_than_passed_over(
    caplog: pytest.LogCaptureFixture,
):
    """A log the server holds but could not read is not a build without one.

    Args:
        caplog: Pytest log capture fixture.
    """
    report = _report(
        reason="Deployment error: the build failed",
        build_log_excerpt=None,
        build_log_unreadable=True,
    )

    _report_deployment_failure("dep-1", report)

    assert "could not be read" in _log_messages(caplog, logging.WARNING)[-1]


def test_a_build_that_stored_no_log_says_nothing_extra(
    caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
):
    """A failure before the build ran has no log to point at.

    Args:
        caplog: Pytest log capture fixture.
        capsys: Pytest stdout capture fixture.
    """
    _report_deployment_failure("dep-1", _report(reason="Quota exceeded"))

    assert "Quota exceeded" in _log_messages(caplog, logging.ERROR)
    assert _log_messages(caplog, logging.WARNING) == []
    assert capsys.readouterr().out == ""


def test_the_printed_excerpt_is_stripped(capsys: pytest.CaptureFixture[str]):
    """The excerpt is printed without the sequences the build wrote into it.

    Args:
        capsys: Pytest stdout capture fixture.
    """
    report = _report(
        code="build_failed",
        reason="Deployment error: the build failed",
        build_log_excerpt="\x1b]52;c;cHduZWQ=\x07ERROR: \x1b[31mno such package\x1b[0m",
    )

    _report_deployment_failure("dep-1", report)

    printed = capsys.readouterr().out
    assert "ERROR: no such package" in printed
    assert "\x1b" not in printed


@pytest.mark.parametrize(
    "config_content, expected",
    [
        ('{"project": "abc-uuid"}', "abc-uuid"),
        ('{"project": ""}', None),
        ('{"project": "   "}', None),
        ('{"project": null}', None),
        ('{"project": 123}', None),
        ('{"project": []}', None),
        ("{}", None),
    ],
)
def test_get_selected_project_normalizes_empty_to_none(
    mocker: MockerFixture, config_content: str, expected: str | None
):
    mocker.patch("pathlib.Path.open", mock_open(read_data=config_content))
    assert get_selected_project() == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("abc-uuid", "abc-uuid"),
        ("  abc-uuid  ", "abc-uuid"),
        ("", None),
        ("   ", None),
        (None, None),
        (123, None),
        ([], None),
        ({}, None),
    ],
)
def test_normalize_project_id(value: object, expected: str | None):
    assert normalize_project_id(value) == expected


@pytest.mark.parametrize(
    "hostile, banned",
    [
        # OSC 52: writes the reader's clipboard.
        ("\x1b]52;c;bWFsaWNpb3Vz\x07error: build failed", "\x1b]52"),
        # OSC 8: renders as one destination and links to another.
        ("\x1b]8;;https://evil.example\x07docs\x1b]8;;\x07", "\x1b]8"),
        # CSI: erases the lines above it, hiding what really happened.
        ("done\x1b[2J\x1b[1;1Hbuild succeeded", "\x1b["),
        # A carriage return overwrites the line in place.
        ("real error\rbuild succeeded", "\r"),
    ],
)
def test_a_build_log_cannot_drive_the_terminal(hostile: str, banned: str):
    """Build output is the app's own dependencies, printed without being asked for.

    Args:
        hostile: Build output carrying a terminal control sequence.
        banned: The sequence that must not survive.
    """
    cleaned = _strip_terminal_controls(hostile)

    assert banned not in cleaned
    assert "\x1b" not in cleaned


def test_stripping_keeps_the_text_worth_reading():
    """Colour is dropped; the words, newlines and tabs that carry the answer stay."""
    log = "\x1b[31mERROR\x1b[0m: no matching distribution\n\tfor pandas==9.9\n"

    assert (
        _strip_terminal_controls(log)
        == "ERROR: no matching distribution\n\tfor pandas==9.9\n"
    )


@pytest.mark.parametrize(
    "hostile",
    [
        "A\x1b7B",  # DECSC: final byte 0x37, outside the CSI and OSC shapes
        "A\x1b=B",  # DECKPAM
        "A\x1bcB",  # RIS: a full terminal reset
        "A\x1b(0B",  # a designator with an intermediate byte
    ],
)
def test_a_two_character_escape_leaves_no_stray_byte(hostile: str):
    """The final byte goes with the ESC, rather than printing as garbage.

    Args:
        hostile: Build output carrying a non-CSI escape sequence.
    """
    cleaned = _strip_terminal_controls(hostile)

    assert cleaned == "AB"
