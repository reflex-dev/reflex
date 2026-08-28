from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any
from unittest.mock import mock_open

import click
import httpx
import pytest
from pytest_mock import MockerFixture, MockFixture
from reflex_cli import constants
from reflex_cli.utils.exceptions import NotAuthenticatedError, TokenValidationError
from reflex_cli.utils.hosting import (
    UPLOAD_CHUNK_SIZE,
    AuthenticatedClient,
    ScaleParams,
    ScaleType,
    SecurityReviewError,
    TokenSource,
    _archive_chunks,
    _report_deployment_failure,
    _strip_terminal_controls,
    _UploadAbandonedError,
    authenticated_token,
    create_app,
    create_deployment,
    delete_token_from_config,
    find_gcp_connection,
    gcp_deploy_available,
    get_app_history,
    get_auth_request_id,
    get_authenticated_client,
    get_existing_access_token,
    get_existing_access_token_with_source,
    get_gcp_provider_status,
    get_security_review,
    get_selected_project,
    get_token_org_id,
    get_token_tier,
    list_gcp_connections,
    list_provider_accounts,
    normalize_project_id,
    normalize_provider,
    provider_display_name,
    rollback_deployment,
    save_token_to_config,
    set_app_full_deploy,
    set_app_provider,
    set_instance_bounds,
    stored_access_token,
    submit_security_review,
    update_deployment_description,
    validate_token,
    validate_token_with_retries,
)

_CLIENT = AuthenticatedClient(token="fake-token", validated_data={})


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
    mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token",
        return_value="valid_token",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.validate_token", return_value={"user_info": True}
    )

    token = authenticated_token()

    assert token == ("valid_token", {"user_info": True})


def test_authenticated_token_not_found(mocker: MockFixture):
    mocker.patch("reflex_cli.utils.hosting.get_existing_access_token", return_value="")

    token = authenticated_token()
    assert token == ("", {})


def test_authenticated_token_found_but_invalid(mocker: MockFixture):
    mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token",
        return_value="invalid_token",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.validate_token",
        side_effect=ValueError("access denied"),
    )
    mocker.patch(
        "reflex_cli.constants.hosting.Hosting.AUTH_RETRY_LIMIT", return_value=1
    )

    token = authenticated_token()
    assert token == ("", {})


def test_authenticated_token_found_but_validation_fails(mocker: MockFixture):
    mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token",
        return_value="invalid_token",
    )
    mocker.patch(
        "reflex_cli.utils.hosting.validate_token",
        side_effect=ValueError("server error"),
    )
    mocker.patch(
        "reflex_cli.utils.hosting.authenticate_on_browser",
        return_value="new_valid_token",
    )
    mock_delete_token = mocker.patch(
        "reflex_cli.utils.hosting.delete_token_from_config"
    )

    token = authenticated_token()

    assert token == ("", {})
    mock_delete_token.assert_called_once()


def test_authenticate_without_token_in_non_interactive_mode(mocker: MockerFixture):
    mocker.patch("reflex_cli.utils.hosting.get_existing_access_token", return_value="")
    with pytest.raises(click.exceptions.Exit):
        get_authenticated_client(token=None, interactive=False)


def test_authenticate_with_env_token_in_non_interactive_mode(mocker: MockerFixture):
    mocker.patch(
        "reflex_cli.utils.hosting.get_existing_access_token", return_value="env_token"
    )
    mock_get_auth_client = mocker.patch(
        "reflex_cli.utils.hosting.get_authentication_client"
    )
    mock_authenticated_client = mocker.MagicMock()
    mock_get_auth_client.return_value = mock_authenticated_client

    result = get_authenticated_client(token=None, interactive=False)

    assert result == mock_authenticated_client
    mock_get_auth_client.assert_called_once_with(None)


def test_scale_params_as_json_is_pure_when_type_is_unspecified():
    """ScaleParams.as_json should not mutate type when defaulting scale type."""
    scale_params = ScaleParams(vm_type="shared-1x")

    first = scale_params.as_json()
    second = scale_params.as_json()

    assert scale_params.type is None
    assert first == second == {"type": ScaleType.REGION.value, "regions": {}}


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


def _ok(mocker: MockerFixture, payload: dict | None = None):
    """Build a mock 2xx response returning ``payload`` from ``.json()``."""
    response = mocker.Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload or {}
    return response


def _error(mocker: MockerFixture, status_code: int, detail: str):
    """Build a mock response whose ``raise_for_status`` raises with ``detail``."""
    response = mocker.Mock()
    response.status_code = status_code
    response.json.return_value = {"detail": detail}
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "error", request=mocker.Mock(), response=response
    )
    return response


def test_submit_security_review_uploads_then_submits(mocker: MockerFixture):
    """The three-step flow requests a URL, PUTs the bytes, then submits the key."""
    upload_url = _ok(
        mocker,
        {
            "key": "staging/security-review/u/abc.zip",
            "url": "https://bucket.s3/abc?sig=1",
            "headers": {"Content-Type": "application/zip"},
        },
    )
    submit = _ok(mocker, {"job_id": "job-1"})
    mock_post = mocker.patch("httpx.post", side_effect=[upload_url, submit])
    mock_put = mocker.patch("httpx.put", return_value=_ok(mocker))

    assert submit_security_review(b"zip-bytes", _CLIENT) == "job-1"

    # Presigned URL requested with the exact content length.
    assert (
        mock_post
        .call_args_list[0]
        .args[0]
        .endswith("/api/v1/agents/security-review/jobs/upload-url")
    )
    assert mock_post.call_args_list[0].kwargs["json"] == {
        "content_length": len(b"zip-bytes"),
        "content_type": "application/zip",
    }
    # Bytes PUT straight to storage with the returned headers, no auth header,
    # carrying the exact length the signature pins.
    assert mock_put.call_args.args[0] == "https://bucket.s3/abc?sig=1"
    assert mock_put.call_args.kwargs["content"] == b"zip-bytes"
    assert mock_put.call_args.kwargs["headers"] == {
        "Content-Type": "application/zip",
        "Content-Length": str(len(b"zip-bytes")),
    }
    assert "X-API-TOKEN" not in mock_put.call_args.kwargs["headers"]
    # Job submitted by key, not by raw bytes.
    assert (
        mock_post
        .call_args_list[1]
        .args[0]
        .endswith("/api/v1/agents/security-review/jobs")
    )
    assert mock_post.call_args_list[1].kwargs["json"] == {
        "key": "staging/security-review/u/abc.zip"
    }


def test_submit_security_review_surfaces_server_detail(mocker: MockerFixture):
    """A 403 on the URL request surfaces the server's detail verbatim."""
    mocker.patch(
        "httpx.post",
        return_value=_error(mocker, 403, "This feature requires the Enterprise tier."),
    )

    with pytest.raises(
        SecurityReviewError, match="This feature requires the Enterprise tier"
    ):
        submit_security_review(b"zip-bytes", _CLIENT)


def test_submit_security_review_upload_failure(mocker: MockerFixture):
    """A storage PUT failure is reported and the job is never submitted."""
    upload_url = _ok(mocker, {"key": "k", "url": "https://bucket.s3/k", "headers": {}})
    mock_post = mocker.patch("httpx.post", side_effect=[upload_url])
    mocker.patch("httpx.put", return_value=_error(mocker, 403, "signature expired"))

    with pytest.raises(SecurityReviewError, match="failed to upload app source"):
        submit_security_review(b"zip-bytes", _CLIENT)

    # Only the upload-url call happened; the job submit was never reached.
    assert mock_post.call_count == 1


def test_submit_security_review_submit_failure(mocker: MockerFixture):
    """A 404 (object not uploaded / not owned) on submit surfaces the detail."""
    upload_url = _ok(mocker, {"key": "k", "url": "https://bucket.s3/k", "headers": {}})
    submit = _error(mocker, 404, "Job not found.")
    mocker.patch("httpx.post", side_effect=[upload_url, submit])
    mocker.patch("httpx.put", return_value=_ok(mocker))

    with pytest.raises(SecurityReviewError, match="Job not found"):
        submit_security_review(b"zip-bytes", _CLIENT)


def test_get_security_review_returns_payload(mocker: MockerFixture):
    """Polling returns the parsed job status payload."""
    response = mocker.Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"job_id": "job-1", "status": "pending"}
    mock_get = mocker.patch("httpx.get", return_value=response)

    assert get_security_review("job-1", _CLIENT) == {
        "job_id": "job-1",
        "status": "pending",
    }
    assert mock_get.call_args.args[0].endswith(
        "/api/v1/agents/security-review/jobs/job-1"
    )


def _client(**data: object) -> AuthenticatedClient:
    """Build an authenticated client with the given validated token data."""
    return AuthenticatedClient(token="fake-token", validated_data=data)


def _ok_body(mocker: MockerFixture, body: object):
    """Build a mock 2xx response whose ``.json()`` returns an arbitrary body.

    ``_ok`` only accepts dict payloads; use this for list/str JSON responses.

    Args:
        mocker: The pytest-mock fixture.
        body: The value ``response.json()`` should return.

    Returns:
        A mock response object.

    """
    response = mocker.Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = body
    return response


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
    """org_id/tier come from the validated token data, None when absent."""
    client = _client(org_id="org-1", tier="Enterprise")
    assert get_token_org_id(client) == "org-1"
    assert get_token_tier(client) == "Enterprise"
    assert get_token_org_id(_client()) is None
    assert get_token_tier(_client()) is None


def test_gcp_deploy_available_configured_and_allowed(mocker: MockerFixture):
    """GCP is offered only when it's both connected and tier-allowed."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_gcp_provider_status",
        return_value={"configured": True, "allowed": True, "region": "us-central1"},
    )
    assert gcp_deploy_available(_client(org_id="o")) == {
        "configured": True,
        "allowed": True,
        "region": "us-central1",
    }


def test_gcp_deploy_available_not_allowed(mocker: MockerFixture):
    """A connected-but-not-allowed org does not get GCP offered."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_gcp_provider_status",
        return_value={"configured": True, "allowed": False},
    )
    assert gcp_deploy_available(_client(org_id="o")) is None


def test_gcp_deploy_available_swallows_errors(mocker: MockerFixture):
    """A lookup failure falls back to no GCP rather than aborting the deploy."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_gcp_provider_status",
        side_effect=Exception("boom"),
    )
    assert gcp_deploy_available(_client(org_id="o")) is None


def test_gcp_deploy_available_without_org():
    """No resolvable org id means GCP is not offered."""
    assert gcp_deploy_available(_client()) is None


def test_get_gcp_provider_status_hits_endpoint(mocker: MockerFixture):
    """The status call targets the org-scoped GCP status endpoint."""
    mock_get = mocker.patch(
        "httpx.get", return_value=_ok(mocker, {"configured": True, "allowed": True})
    )
    assert get_gcp_provider_status("org-1", _CLIENT) == {
        "configured": True,
        "allowed": True,
    }
    assert mock_get.call_args.args[0].endswith(
        "/api/v1/orgs/org-1/provider-accounts/gcp/status"
    )


def test_list_provider_accounts_hits_endpoint(mocker: MockerFixture):
    """Listing connected providers targets the org provider-accounts endpoint."""
    mock_get = mocker.patch(
        "httpx.get", return_value=_ok_body(mocker, [{"provider": "gcp"}])
    )
    assert list_provider_accounts("org-1", _CLIENT) == [{"provider": "gcp"}]
    assert mock_get.call_args.args[0].endswith("/api/v1/orgs/org-1/provider-accounts")


def test_set_app_provider_success(mocker: MockerFixture):
    """A successful switch posts the provider and returns the new value."""
    mock_post = mocker.patch(
        "httpx.post", return_value=_ok(mocker, {"provider": "gcp"})
    )
    assert set_app_provider("app-1", "gcp", _CLIENT) == "gcp"
    assert mock_post.call_args.args[0].endswith("/api/v1/apps/app-1/provider")
    assert mock_post.call_args.kwargs["json"] == {"provider": "gcp"}


def test_set_app_provider_forwards_connection(mocker: MockerFixture):
    """A named connection rides along as provider_account_id."""
    mock_post = mocker.patch(
        "httpx.post", return_value=_ok(mocker, {"provider": "gcp"})
    )
    assert set_app_provider("app-1", "gcp", _CLIENT, provider_account_id="conn-1") == (
        "gcp"
    )
    assert mock_post.call_args.kwargs["json"] == {
        "provider": "gcp",
        "provider_account_id": "conn-1",
    }


def test_set_app_provider_forwards_service_name(mocker: MockerFixture):
    """A requested Cloud Run service name rides along as service_name."""
    mock_post = mocker.patch(
        "httpx.post", return_value=_ok(mocker, {"provider": "gcp"})
    )
    assert set_app_provider(
        "app-1", "gcp", _CLIENT, service_name="sales-dashboard"
    ) == ("gcp")
    assert mock_post.call_args.kwargs["json"] == {
        "provider": "gcp",
        "service_name": "sales-dashboard",
    }


def test_set_app_full_deploy_success(mocker: MockerFixture):
    """The mode change posts to the app's full_deploy endpoint."""
    mock_post = mocker.patch(
        "httpx.post",
        return_value=_ok(
            mocker, {"full_deploy": True, "stopped": True, "stop_confirmed": True}
        ),
    )
    result = set_app_full_deploy("app-1", True, _CLIENT)
    assert result == {"full_deploy": True, "stopped": True, "stop_confirmed": True}
    assert mock_post.call_args.args[0].endswith("/api/v1/apps/app-1/full_deploy")
    assert mock_post.call_args.kwargs["json"] == {"full_deploy": True}


def test_set_app_full_deploy_error(mocker: MockerFixture):
    """A refused mode change surfaces the server detail as an error string."""
    mocker.patch(
        "httpx.post", return_value=_error(mocker, 400, "full deploy requires GCP")
    )
    result = set_app_full_deploy("app-1", True, _CLIENT)
    assert isinstance(result, str)
    assert result.startswith("set full deploy failed")
    assert "full deploy requires GCP" in result


def test_list_gcp_connections_reads_the_status(mocker: MockerFixture):
    """Connections come from the member-visible GCP status."""
    mocker.patch(
        "httpx.get",
        return_value=_ok(
            mocker,
            {"configured": True, "connections": [{"id": "c1", "name": "prod"}, "junk"]},
        ),
    )
    assert list_gcp_connections(_client(org_id="org-1")) == [
        {"id": "c1", "name": "prod"}
    ]


def test_list_gcp_connections_refuses_an_unauthenticated_client():
    """The docstring promises NotAuthenticatedError, not an AttributeError."""
    with pytest.raises(NotAuthenticatedError):
        list_gcp_connections(None)  # pyright: ignore[reportArgumentType]


def test_list_gcp_connections_without_org():
    """No resolvable org id means there is nothing to list."""
    assert list_gcp_connections(_client()) == []


def test_list_gcp_connections_explicit_org(mocker: MockerFixture):
    """An explicit org id wins over the token's own."""
    mock_get = mocker.patch("httpx.get", return_value=_ok(mocker, {"connections": []}))
    assert list_gcp_connections(_client(org_id="token-org"), org_id="other-org") == []
    assert "other-org" in mock_get.call_args.args[0]


@pytest.mark.parametrize(
    ("wanted", "expected"),
    [
        ("prod", "c1"),
        ("PROD", "c1"),
        ("  prod  ", "c1"),
        ("c2", "c2"),
        ("staging", "c2"),
        ("nope", None),
    ],
)
def test_find_gcp_connection(wanted: str, expected: str | None):
    """Connections match on id first, then on name, case-insensitively."""
    connections = [
        {"id": "c1", "name": "prod"},
        {"id": "c2", "name": "Staging"},
    ]
    match = find_gcp_connection(connections, wanted)
    assert (match or {}).get("id") == expected


def test_set_app_provider_error(mocker: MockerFixture):
    """A rejected switch surfaces the server detail as an error string."""
    mocker.patch("httpx.post", return_value=_error(mocker, 403, "Enterprise required"))
    result = set_app_provider("app-1", "gcp", _CLIENT)
    assert result.startswith("set provider failed")
    assert "Enterprise required" in result


@pytest.mark.parametrize(
    ("min_instances", "max_instances", "expected_body"),
    [
        (0, 5, {"min_instances": 0, "max_instances": 5}),
        (2, None, {"min_instances": 2}),
        (None, 10, {"max_instances": 10}),
    ],
)
def test_set_instance_bounds_sends_only_given_bounds(
    mocker: MockerFixture,
    min_instances: int | None,
    max_instances: int | None,
    expected_body: dict[str, int],
):
    """Only the bounds the caller passed are sent; the rest keep their value."""
    mock_post = mocker.patch("httpx.post", return_value=_ok(mocker))
    assert (
        set_instance_bounds(
            "app-1",
            _CLIENT,
            min_instances=min_instances,
            max_instances=max_instances,
        )
        is None
    )
    assert mock_post.call_args.args[0].endswith("/api/v1/apps/app-1/instance_bounds")
    assert mock_post.call_args.kwargs["json"] == expected_body
    assert mock_post.call_args.kwargs["headers"]["X-API-TOKEN"] == "fake-token"


@pytest.mark.parametrize(
    ("status_code", "detail"),
    [
        (400, "min_instances must be less than or equal to max_instances"),
        (400, "platform does not support instance bounds"),
        (409, "a scale operation is already running for this app"),
    ],
)
def test_set_instance_bounds_error(
    mocker: MockerFixture, status_code: int, detail: str
):
    """Validation, unsupported-platform and conflict details reach the caller."""
    mocker.patch("httpx.post", return_value=_error(mocker, status_code, detail))
    result = set_instance_bounds("app-1", _CLIENT, min_instances=1, max_instances=0)
    assert result is not None
    assert result.startswith("set instance bounds failed")
    assert detail in result


def test_rollback_deployment_success(mocker: MockerFixture):
    """A successful rollback returns None and targets the rollback endpoint."""
    mock_post = mocker.patch("httpx.post", return_value=_ok(mocker))
    assert rollback_deployment("app-1", "dep-1", _CLIENT) is None
    assert mock_post.call_args.args[0].endswith(
        "/api/v1/apps/app-1/deployments/dep-1/rollback"
    )


def test_rollback_deployment_error(mocker: MockerFixture):
    """A rejected rollback surfaces the server detail as an error string."""
    mocker.patch("httpx.post", return_value=_error(mocker, 400, "no image"))
    result = rollback_deployment("app-1", "dep-1", _CLIENT)
    assert result is not None
    assert result.startswith("rollback failed")
    assert "no image" in result


def test_update_deployment_description_success(mocker: MockerFixture):
    """Setting a note posts the description to the deployment description endpoint."""
    mock_post = mocker.patch("httpx.post", return_value=_ok(mocker))
    assert update_deployment_description("app-1", "dep-1", "note", _CLIENT) is None
    assert mock_post.call_args.args[0].endswith(
        "/api/v1/apps/app-1/deployments/dep-1/description"
    )
    assert mock_post.call_args.kwargs["json"] == {"description": "note"}


def test_update_deployment_description_error(mocker: MockerFixture):
    """A missing deployment surfaces the server detail as an error string."""
    mocker.patch("httpx.post", return_value=_error(mocker, 404, "no deployment"))
    result = update_deployment_description("app-1", "dep-1", "note", _CLIENT)
    assert result is not None
    assert result.startswith("update description failed")


def test_create_app_forwards_provider(mocker: MockerFixture):
    """create_app forwards a provider when given one."""
    response = _ok(mocker, {"id": "app-1", "name": "n"})
    response.status_code = 200
    mock_post = mocker.patch("httpx.post", return_value=response)
    create_app("n", _CLIENT, "desc", "proj-1", provider="gcp")
    assert mock_post.call_args.kwargs["json"]["provider"] == "gcp"


def test_create_app_omits_provider_when_none(mocker: MockerFixture):
    """create_app omits the provider field when none is requested."""
    response = _ok(mocker, {"id": "app-1", "name": "n"})
    response.status_code = 200
    mock_post = mocker.patch("httpx.post", return_value=response)
    create_app("n", _CLIENT, "desc", "proj-1")
    assert "provider" not in mock_post.call_args.kwargs["json"]


def _reservation(deployment_id: str, suffix: str = "") -> dict[str, Any]:
    """Build a ``/deployments/reserve`` response body.

    Args:
        deployment_id: The id the reservation minted.
        suffix: Appended to both signed URLs, to tell one reservation's targets
            from another's within a test.

    Returns:
        The response body the reserve endpoint would return.
    """
    return {
        "deployment_id": deployment_id,
        "backend": {
            "url": f"https://storage.invalid/backend{suffix}",
            "headers": {"Content-Type": "application/zip"},
        },
        "frontend": {
            "url": f"https://storage.invalid/frontend{suffix}",
            "headers": {"Content-Type": "application/zip"},
        },
        "expires_in": 1800,
    }


def _put_response(mocker: MockerFixture, status_code: int):
    """Build a mock storage response for a signed archive PUT.

    Args:
        mocker: The pytest-mock fixture.
        status_code: The status the storage service answered with.

    Returns:
        A mock response, raising on ``raise_for_status`` when it is a refusal.
    """
    response = mocker.Mock()
    response.status_code = status_code
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "refused", request=mocker.Mock(), response=response
        )
    else:
        response.raise_for_status.return_value = None
    return response


@pytest.fixture
def zip_dir(tmp_path: Path) -> Path:
    """A directory holding a build's two archives.

    Args:
        tmp_path: The pytest temporary directory.

    Returns:
        The directory, with ``backend.zip`` and ``frontend.zip`` written.
    """
    (tmp_path / "backend.zip").write_bytes(b"backend archive " * 300)
    (tmp_path / "frontend.zip").write_bytes(b"frontend archive " * 5000)
    return tmp_path


def _deploy(zip_dir: Path, app_id: str | None = "app-1", **kwargs: Any) -> str:
    """Run ``create_deployment`` over ``zip_dir`` with the boilerplate filled in.

    Args:
        zip_dir: The directory holding the archives.
        app_id: The app to deploy, or None to leave the CLI without one.
        **kwargs: Overrides for any other ``create_deployment`` argument.

    Returns:
        Whatever ``create_deployment`` returned.
    """
    return create_deployment(**{
        "zip_dir": zip_dir,
        "client": _CLIENT,
        "app_name": "n",
        "project_id": None,
        "regions": None,
        "hostname": None,
        "vmtype": None,
        "secrets": None,
        "packages": None,
        "strategy": None,
        "app_id": app_id,
        **kwargs,
    })


def _capturing_put(
    mocker: MockerFixture, uploaded: dict[str, bytes], expired: str = ""
) -> Any:
    """A stand-in for httpx.put that drains the streamed body it is handed.

    Args:
        mocker: The pytest-mock fixture.
        uploaded: Filled in with each URL's uploaded bytes.
        expired: URLs *not* containing this marker answer 403, the way a
            presigned URL past its window does. Empty means every URL works.

    Returns:
        A side effect for a patched ``httpx.put``.
    """

    def put(url: str, **kwargs: Any):
        body = b"".join(kwargs["content"])
        if expired and expired not in url:
            return _put_response(mocker, 403)
        uploaded[url] = body
        return _put_response(mocker, 200)

    return put


@pytest.fixture
def deploy_env(mocker: MockerFixture):
    """Pin the version strings ``create_deployment`` stamps onto a submission.

    Args:
        mocker: The pytest-mock fixture.
    """
    mocker.patch("importlib.metadata.version", return_value="0.1.99")
    mocker.patch("reflex_cli.utils.dependency.get_reflex_version", return_value="1.0")


@pytest.mark.usefixtures("deploy_env")
def test_create_deployment_forwards_description(mocker: MockerFixture, zip_dir: Path):
    """A per-deployment note is sent as the submit description field."""
    mock_post = mocker.patch(
        "httpx.post",
        side_effect=[
            _ok_body(mocker, _reservation("dep-1")),
            _ok_body(mocker, "dep-1"),
        ],
    )
    mocker.patch("httpx.put", side_effect=_capturing_put(mocker, {}))

    _deploy(zip_dir, description="my note")

    assert mock_post.call_args.kwargs["data"]["description"] == "my note"


@pytest.mark.usefixtures("deploy_env")
@pytest.mark.parametrize("vmtype", ["c2m2", None])
def test_create_deployment_forwards_vmtype(
    mocker: MockerFixture, zip_dir: Path, vmtype: str | None
):
    """A requested VM type reaches the submit body; nothing is sent otherwise."""
    mock_post = mocker.patch(
        "httpx.post",
        side_effect=[
            _ok_body(mocker, _reservation("dep-1")),
            _ok_body(mocker, "dep-1"),
        ],
    )
    mocker.patch("httpx.put", side_effect=_capturing_put(mocker, {}))

    _deploy(zip_dir, vmtype=vmtype)

    data = mock_post.call_args.kwargs["data"]
    if vmtype is None:
        assert "vm_type" not in data
    else:
        assert data["vm_type"] == vmtype


@pytest.mark.usefixtures("deploy_env")
def test_create_deployment_uploads_archives_directly(
    mocker: MockerFixture, zip_dir: Path
):
    """The archives go straight to storage and only their id is submitted."""
    post = mocker.patch(
        "httpx.post",
        side_effect=[
            _ok_body(mocker, _reservation("dep-1")),
            _ok_body(mocker, "dep-1"),
        ],
    )
    uploaded: dict[str, bytes] = {}
    put = mocker.patch("httpx.put", side_effect=_capturing_put(mocker, uploaded))

    assert _deploy(zip_dir) == "dep-1"

    reserve = post.call_args_list[0]
    assert reserve.args[0].endswith("/api/v1/deployments/reserve")
    assert reserve.kwargs["json"] == {
        "app_id": "app-1",
        "backend_size": (zip_dir / "backend.zip").stat().st_size,
        "frontend_size": (zip_dir / "frontend.zip").stat().st_size,
    }

    # Every byte, and only those bytes: the size is signed into the URL, so a
    # body that does not match it exactly is a signature the store will refuse.
    assert uploaded == {
        "https://storage.invalid/backend": (zip_dir / "backend.zip").read_bytes(),
        "https://storage.invalid/frontend": (zip_dir / "frontend.zip").read_bytes(),
    }
    for call in put.call_args_list:
        name = call.args[0].rsplit("/", 1)[-1] + ".zip"
        assert call.kwargs["headers"] == {
            "Content-Type": "application/zip",
            "Content-Length": str((zip_dir / name).stat().st_size),
        }

    submit = post.call_args_list[1]
    assert submit.args[0].endswith("/api/v1/deployments")
    assert submit.kwargs["data"]["stored_build_id"] == "dep-1"
    assert submit.kwargs["files"] is None


@pytest.mark.usefixtures("deploy_env")
def test_create_deployment_reserves_again_when_the_window_expires(
    mocker: MockerFixture, zip_dir: Path
):
    """A lapsed signature is recovered by reserving, and re-uploading both."""
    post = mocker.patch(
        "httpx.post",
        side_effect=[
            _ok_body(mocker, _reservation("dep-1")),
            _ok_body(mocker, _reservation("dep-2", suffix="-retry")),
            _ok_body(mocker, "dep-2"),
        ],
    )
    uploaded: dict[str, bytes] = {}
    mocker.patch(
        "httpx.put", side_effect=_capturing_put(mocker, uploaded, expired="-retry")
    )

    assert _deploy(zip_dir) == "dep-2"

    # The second reservation minted a new id naming a new prefix, so both
    # archives went up under it -- not just the one whose PUT expired.
    assert set(uploaded) == {
        "https://storage.invalid/backend-retry",
        "https://storage.invalid/frontend-retry",
    }
    assert post.call_args_list[2].kwargs["data"]["stored_build_id"] == "dep-2"


@pytest.mark.usefixtures("deploy_env")
def test_create_deployment_gives_up_after_one_more_window(
    mocker: MockerFixture, zip_dir: Path
):
    """Past two signed windows the link is the problem, and the user is told."""
    post = mocker.patch(
        "httpx.post",
        side_effect=[
            _ok_body(mocker, _reservation("dep-1")),
            _ok_body(mocker, _reservation("dep-2", suffix="-retry")),
        ],
    )
    mocker.patch("httpx.put", side_effect=_capturing_put(mocker, {}, expired="never"))

    result = _deploy(zip_dir)

    assert "deployment failed" in result
    assert "too slow" in result
    # Two reservations and no submission: nothing was ever in the bucket.
    assert post.call_count == 2


@pytest.mark.usefixtures("deploy_env")
def test_create_deployment_relays_when_the_control_plane_cannot_reserve(
    mocker: MockerFixture, zip_dir: Path
):
    """A 404 is the route being absent, so the archives are relayed instead."""
    missing = mocker.Mock()
    missing.status_code = 404
    post = mocker.patch("httpx.post", side_effect=[missing, _ok_body(mocker, "dep-1")])
    put = mocker.patch("httpx.put")

    assert _deploy(zip_dir) == "dep-1"

    put.assert_not_called()
    submit = post.call_args_list[1]
    assert "stored_build_id" not in submit.kwargs["data"]
    assert [name for _, (name, _) in submit.kwargs["files"]] == [
        "backend.zip",
        "frontend.zip",
    ]


@pytest.mark.usefixtures("deploy_env")
def test_create_deployment_relays_without_an_app_id(
    mocker: MockerFixture, zip_dir: Path
):
    """With no app id there is nothing to reserve against, so nothing is."""
    post = mocker.patch("httpx.post", return_value=_ok_body(mocker, "dep-1"))
    put = mocker.patch("httpx.put")

    assert _deploy(zip_dir, app_id=None) == "dep-1"

    put.assert_not_called()
    post.assert_called_once()
    assert post.call_args.kwargs["files"] is not None


@pytest.mark.usefixtures("deploy_env")
def test_create_deployment_surfaces_a_refused_reservation(
    mocker: MockerFixture, zip_dir: Path
):
    """What the control plane said about the refusal is what the user reads."""
    detail = "backend.zip is 0 bytes; an archive must be between 1 byte and 5 GiB"
    post = mocker.patch("httpx.post", return_value=_error(mocker, 400, detail))
    put = mocker.patch("httpx.put")

    assert _deploy(zip_dir) == f"deployment failed: {detail}"

    put.assert_not_called()
    post.assert_called_once()


@pytest.mark.usefixtures("deploy_env")
def test_create_deployment_surfaces_an_unreachable_control_plane(
    mocker: MockerFixture, zip_dir: Path
):
    """A reserve that never gets an answer is reported, not raised at the user."""
    mocker.patch("httpx.post", side_effect=httpx.ConnectError("no route to host"))
    put = mocker.patch("httpx.put")

    result = _deploy(zip_dir)

    assert result.startswith(
        "deployment failed: could not reach the deployment service"
    )
    put.assert_not_called()


def test_archive_chunks_stop_once_the_other_upload_failed(tmp_path: Path):
    """The stream ends at the next chunk boundary, not at the end of the file."""
    archive = tmp_path / "frontend.zip"
    archive.write_bytes(b"f" * (4 * UPLOAD_CHUNK_SIZE))
    abandoned = threading.Event()

    chunks = _archive_chunks(archive, lambda _n: None, abandoned)
    first = next(chunks)
    abandoned.set()
    with pytest.raises(_UploadAbandonedError):
        next(chunks)

    # One chunk off disk, not the other three: the point of abandoning is the
    # bytes that never go up.
    assert len(first) == UPLOAD_CHUNK_SIZE


@pytest.mark.usefixtures("deploy_env")
def test_an_abandoned_archive_does_not_mask_the_real_failure(
    mocker: MockerFixture, zip_dir: Path
):
    """The archive that actually failed is the one whose error reaches the user."""
    mocker.patch("httpx.post", return_value=_ok_body(mocker, _reservation("dep-1")))

    def put(url: str, **kwargs: Any):
        if "backend" in url:
            return _put_response(mocker, 500)
        # What the frontend's stream does once the backend has set the flag.
        # Raised here rather than raced into, so the assertion below does not
        # depend on which thread the scheduler runs first.
        raise _UploadAbandonedError

    mocker.patch("httpx.put", side_effect=put)

    assert (
        _deploy(zip_dir)
        == "deployment failed: could not upload the build to storage: HTTP 500"
    )


def test_get_app_history_includes_description_and_can_rollback(mocker: MockerFixture):
    """History rows carry the deployment note and rollback eligibility."""
    payload = [
        {
            "id": "d1",
            "status": "Running",
            "hostname": "h",
            "python_version": "3.11",
            "reflex_version": "1.0",
            "vm_type": "c1",
            "timestamp": "t",
            "description": "hotfix",
            "can_rollback": True,
        },
        {
            "id": "d2",
            "status": "Historical",
            "hostname": "h2",
            "python_version": "3.11",
            "reflex_version": "1.0",
            "vm_type": "c1",
            "timestamp": "t2",
        },
    ]
    mocker.patch("httpx.get", return_value=_ok_body(mocker, payload))
    history = get_app_history("app-1", _CLIENT)
    assert history[0]["description"] == "hotfix"
    assert history[0]["can rollback"] is True
    assert history[1]["description"] == ""
    assert history[1]["can rollback"] is False


def test_validate_token_sends_request_id_header(mocker: MockerFixture):
    """Each validation request carries a fresh X-Request-ID header."""
    mock_post = mocker.patch(
        "httpx.post", return_value=_ok(mocker, {"tier": "enterprise"})
    )

    assert validate_token("some-token") == {"tier": "enterprise"}

    headers = mock_post.call_args.kwargs["headers"]
    assert headers["X-API-TOKEN"] == "some-token"
    assert headers["X-Request-ID"] == get_auth_request_id() != ""

    first_request_id = get_auth_request_id()
    validate_token("some-token")
    assert get_auth_request_id() != first_request_id


def test_validate_token_with_retries_warns_with_request_id(
    mocker: MockerFixture, caplog: pytest.LogCaptureFixture
):
    """A failed validation surfaces the request id for support correlation.

    Args:
        mocker: Pytest mocker fixture.
        caplog: Pytest log capture fixture.
    """
    mocker.patch("httpx.post", return_value=_error(mocker, 500, "boom"))

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
    response = mocker.Mock()
    response.raise_for_status.return_value = None
    response.json.side_effect = ValueError("bad json")
    mocker.patch("httpx.post", return_value=response)
    mocker.patch("reflex_cli.utils.hosting.delete_token_from_config")

    assert validate_token_with_retries("some-token") == {}

    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors
    assert get_auth_request_id() in errors[-1]


def test_validate_token_failure_carries_request_id_on_exception(mocker: MockerFixture):
    """Validation errors carry the request id of their own request."""
    mocker.patch("httpx.post", return_value=_error(mocker, 500, "boom"))

    with pytest.raises(TokenValidationError) as exc_info:
        validate_token("some-token")

    assert exc_info.value.request_id == get_auth_request_id() != ""


def _log_messages(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    """Return the captured log messages emitted at the given level.

    Args:
        caplog: The pytest log capture fixture.
        level: The numeric log level to filter records by.

    Returns:
        The formatted messages of the matching records.
    """
    return [r.getMessage() for r in caplog.records if r.levelno == level]


def _failure_report(mocker: MockerFixture, **fields: object):
    """A mock 2xx /failure response carrying the given report fields.

    Args:
        mocker: Pytest mocker fixture.
        **fields: Failure-report fields to override on the default report.

    Returns:
        A mocked successful HTTP response containing the failure report.
    """
    report = {
        "status": "Failed",
        "code": None,
        "fault": None,
        "reason": "",
        "guidance": "",
        "build_log_excerpt": None,
    }
    report.update(fields)
    return _ok(mocker, report)


def test_failure_report_prints_reason_and_build_log(
    mocker: MockerFixture, caplog: pytest.LogCaptureFixture, capsys
):
    """A build failure shows its reason, its guidance and the log's tail.

    Args:
        mocker: Pytest mocker fixture.
        caplog: Pytest log capture fixture.
        capsys: Pytest stdout capture fixture.
    """
    mocker.patch(
        "httpx.get",
        return_value=_failure_report(
            mocker,
            code="build_failed",
            fault="customer",
            reason="Deployment error: the build failed",
            guidance="Your app failed to build.",
            build_log_excerpt="ERROR: no matching distribution for pandas==9.9",
        ),
    )

    _report_deployment_failure(
        "dep-1", "fake-token", "build error", offer_build_logs=True
    )

    assert "Deployment error: the build failed" in _log_messages(caplog, logging.ERROR)
    assert "Your app failed to build." in _log_messages(caplog, logging.WARNING)
    printed = capsys.readouterr().out
    assert "no matching distribution for pandas==9.9" in printed
    assert "reflex cloud apps build-logs dep-1" in printed


def test_failure_report_withholds_build_log_when_the_fault_is_ours(
    mocker: MockerFixture, caplog: pytest.LogCaptureFixture, capsys
):
    """A platform failure says so and never sends the reader to their build.

    Args:
        mocker: Pytest mocker fixture.
        caplog: Pytest log capture fixture.
        capsys: Pytest stdout capture fixture.
    """
    mocker.patch(
        "httpx.get",
        return_value=_failure_report(
            mocker,
            code="image_push_failed",
            fault="platform",
            reason="Deployment error: could not push the image",
            guidance="This failure is on Reflex's side, not in your app.",
        ),
    )

    _report_deployment_failure(
        "dep-1", "fake-token", "deployment error", offer_build_logs=False
    )

    assert "Deployment error: could not push the image" in _log_messages(
        caplog, logging.ERROR
    )
    assert "not in your app" in " ".join(_log_messages(caplog, logging.WARNING))
    assert "build-logs" not in capsys.readouterr().out


def test_failure_report_falls_back_when_the_endpoint_is_absent(
    mocker: MockerFixture, caplog: pytest.LogCaptureFixture
):
    """An older control plane 404s, and the status string is reported as before.

    Args:
        mocker: Pytest mocker fixture.
        caplog: Pytest log capture fixture.
    """
    mocker.patch("httpx.get", return_value=_error(mocker, 404, "Not Found"))

    _report_deployment_failure(
        "dep-1", "fake-token", "build error: something broke", offer_build_logs=True
    )

    warnings = _log_messages(caplog, logging.WARNING)
    assert "build error: something broke" in warnings
    assert any("reflex cloud apps build-logs dep-1" in w for w in warnings)


def test_failure_report_fallback_respects_the_arm_that_asked(
    mocker: MockerFixture, caplog: pytest.LogCaptureFixture
):
    """With no report, a generic failure offers no build log, as before.

    Args:
        mocker: Pytest mocker fixture.
        caplog: Pytest log capture fixture.
    """
    mocker.patch("httpx.get", side_effect=httpx.RequestError("down"))

    _report_deployment_failure(
        "dep-1", "fake-token", "deployment error", offer_build_logs=False
    )

    warnings = _log_messages(caplog, logging.WARNING)
    assert warnings == ["deployment error"]


def test_failure_report_falls_back_to_the_status_when_no_reason_was_recorded(
    mocker: MockerFixture, caplog: pytest.LogCaptureFixture
):
    """A row that recorded no reason still reports something.

    Args:
        mocker: Pytest mocker fixture.
        caplog: Pytest log capture fixture.
    """
    mocker.patch("httpx.get", return_value=_failure_report(mocker))

    _report_deployment_failure(
        "dep-1", "fake-token", "deployment error", offer_build_logs=False
    )

    assert "deployment error" in _log_messages(caplog, logging.ERROR)


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


def test_the_printed_excerpt_is_stripped(
    mocker: MockerFixture, caplog: pytest.LogCaptureFixture, capsys
):
    """The sanitiser is actually on the path the excerpt takes to the terminal.

    Args:
        mocker: Pytest mocker fixture.
        caplog: Pytest log capture fixture.
        capsys: Pytest stdout capture fixture.
    """
    mocker.patch(
        "httpx.get",
        return_value=_failure_report(
            mocker,
            code="build_failed",
            reason="Deployment error: the build failed",
            build_log_excerpt="\x1b]52;c;cHduZWQ=\x07ERROR: \x1b[31mno such package\x1b[0m",
        ),
    )

    _report_deployment_failure(
        "dep-1", "fake-token", "build error", offer_build_logs=True
    )

    printed = capsys.readouterr().out
    assert "ERROR: no such package" in printed
    assert "\x1b" not in printed


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


def test_an_undecodable_body_falls_back_rather_than_raising(
    mocker: MockerFixture, caplog: pytest.LogCaptureFixture
):
    """A 2xx body httpx cannot decode is not an answer, and must not end the watch.

    Args:
        mocker: Pytest mocker fixture.
        caplog: Pytest log capture fixture.
    """
    response = mocker.Mock()
    response.raise_for_status.return_value = None
    response.json.side_effect = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid")
    mocker.patch("httpx.get", return_value=response)

    _report_deployment_failure(
        "dep-1", "fake-token", "build error", offer_build_logs=True
    )

    assert "build error" in _log_messages(caplog, logging.WARNING)


def test_a_non_string_excerpt_is_ignored(
    mocker: MockerFixture, caplog: pytest.LogCaptureFixture, capsys
):
    """The CLI ships apart from the server, so the excerpt's type is not a given.

    Args:
        mocker: Pytest mocker fixture.
        caplog: Pytest log capture fixture.
        capsys: Pytest stdout capture fixture.
    """
    mocker.patch(
        "httpx.get",
        return_value=_failure_report(
            mocker,
            code="build_failed",
            reason="Deployment error: the build failed",
            build_log_excerpt={"unexpected": "shape"},
        ),
    )

    _report_deployment_failure(
        "dep-1", "fake-token", "build error", offer_build_logs=True
    )

    assert "Deployment error: the build failed" in _log_messages(caplog, logging.ERROR)
    assert "the end of the build log" not in capsys.readouterr().out


def test_an_unreadable_log_is_reported_rather_than_passed_over(
    mocker: MockerFixture, caplog: pytest.LogCaptureFixture
):
    """A log the server could not read is not a build that produced none.

    Args:
        mocker: Pytest mocker fixture.
        caplog: Pytest log capture fixture.
    """
    mocker.patch(
        "httpx.get",
        return_value=_failure_report(
            mocker,
            code="build_failed",
            reason="Deployment error: the build failed",
            build_log_excerpt=None,
            build_log_unreadable=True,
        ),
    )

    _report_deployment_failure(
        "dep-1", "fake-token", "build error", offer_build_logs=True
    )

    warnings = " ".join(_log_messages(caplog, logging.WARNING))
    assert "could not be read" in warnings
    assert "reflex cloud apps build-logs dep-1" in warnings


def test_a_build_that_stored_no_log_says_nothing_extra(
    mocker: MockerFixture, caplog: pytest.LogCaptureFixture, capsys
):
    """Absence is not an outage, and there is nothing to send the reader to.

    The reason stands alone: no excerpt, no header over one, and no command to
    go and fetch a log that was never stored. The command is what separates
    this path from the unreadable one, which does offer it.

    Args:
        mocker: Pytest mocker fixture.
        caplog: Pytest log capture fixture.
        capsys: Pytest stdout capture fixture.
    """
    mocker.patch(
        "httpx.get",
        return_value=_failure_report(
            mocker,
            code="build_failed",
            reason="Deployment error: the build failed",
            build_log_excerpt=None,
        ),
    )

    _report_deployment_failure(
        "dep-1", "fake-token", "build error", offer_build_logs=True
    )

    assert "Deployment error: the build failed" in _log_messages(caplog, logging.ERROR)
    said = " ".join(_log_messages(caplog, logging.WARNING)) + capsys.readouterr().out
    assert "could not be read" not in said
    assert "the end of the build log" not in said
    assert "reflex cloud apps build-logs" not in said


@pytest.mark.parametrize(
    "failure",
    [
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid"),
        # A deeply nested document: a RuntimeError, so a ValueError catch misses it.
        RecursionError("maximum recursion depth exceeded"),
    ],
)
def test_a_malformed_body_falls_back_however_it_is_malformed(
    mocker: MockerFixture, caplog: pytest.LogCaptureFixture, failure: Exception
):
    """Not getting an answer costs nothing, whichever way the answer is broken.

    Args:
        mocker: Pytest mocker fixture.
        caplog: Pytest log capture fixture.
        failure: What `.json()` raises on this body.
    """
    response = mocker.Mock()
    response.raise_for_status.return_value = None
    response.json.side_effect = failure
    mocker.patch("httpx.get", return_value=response)

    _report_deployment_failure(
        "dep-1", "fake-token", "build error", offer_build_logs=True
    )

    assert "build error" in _log_messages(caplog, logging.WARNING)
