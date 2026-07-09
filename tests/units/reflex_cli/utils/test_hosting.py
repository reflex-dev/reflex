from __future__ import annotations

import json
from unittest.mock import mock_open

import click
import httpx
import pytest
from pytest_mock import MockerFixture, MockFixture
from reflex_cli.utils.hosting import (
    AuthenticatedClient,
    ScaleParams,
    ScaleType,
    SecurityReviewError,
    authenticated_token,
    delete_token_from_config,
    get_authenticated_client,
    get_existing_access_token,
    get_security_review,
    get_selected_project,
    normalize_project_id,
    save_token_to_config,
    submit_security_review,
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


@pytest.mark.parametrize(
    "file_exists, config_content",
    [
        (True, '{"access_token": "valid_token"}'),
        (True, '{"another_key": "value"}'),
        (False, ""),
    ],
)
def test_delete_token_from_config(
    mocker: MockerFixture,
    file_exists: bool,
    config_content: str,
):
    mocker.patch("pathlib.Path.exists", return_value=file_exists)
    mock_os_remove = mocker.patch("pathlib.Path.unlink")

    mocked_open = mock_open(read_data=config_content)
    mocker.patch("pathlib.Path.open", mocked_open)
    mock_json_load = mocker.patch(
        "json.load", return_value=json.loads(config_content or "{}")
    )
    mock_json_dump = mocker.patch("json.dump")

    delete_token_from_config()

    if file_exists:
        assert mocked_open.call_count == 2
        mock_json_load.assert_called_once()
        mock_json_dump.assert_called_once()
        assert "access_token" not in mock_json_dump.call_args.args[0]
        mock_os_remove.assert_called_once()
    else:
        mocked_open.assert_not_called()
        mock_os_remove.assert_not_called()


def test_save_token_to_config(mocker: MockFixture):
    mocker.patch("pathlib.Path.exists", return_value=False)
    mock_makedirs = mocker.patch("pathlib.Path.mkdir")
    save_token_to_config("test_token")
    mock_makedirs.assert_called_once()

    mocker.patch("pathlib.Path.exists", return_value=True)
    mock_json_dump = mocker.patch("json.dump")
    mocker.patch("pathlib.Path.open", mock_open())
    save_token_to_config("test_token")
    mock_json_dump.assert_called_once()


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
    # Bytes PUT straight to storage with the returned headers, no auth header.
    assert mock_put.call_args.args[0] == "https://bucket.s3/abc?sig=1"
    assert mock_put.call_args.kwargs["content"] == b"zip-bytes"
    assert mock_put.call_args.kwargs["headers"] == {"Content-Type": "application/zip"}
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
