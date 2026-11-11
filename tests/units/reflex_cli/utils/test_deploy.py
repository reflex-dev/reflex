"""Retries of confirmed deployment scaling refusals preserve uploaded builds."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Literal
from unittest.mock import MagicMock, call
from urllib.parse import parse_qs

import pytest
from reflex_build_sdk import APIConnectionError, ConflictError, ReflexBuild
from reflex_build_sdk.transports import Request, Response, TransportError
from reflex_cli.utils.deploy import _DeploymentRetryTransport, _retry_scaling_conflicts

from tests.units.reflex_cli.sdk import api_error

_URL = "https://build.reflex.dev/api/v1/deployments"
_DETAIL = (
    "the app is currently being scaled; wait for the scale to finish, then deploy again"
)


def _request() -> Request:
    """Build a replayable deployment submission.

    Returns:
        The request with its stored build id and trace id.
    """
    return Request(
        method="POST",
        url=_URL,
        headers={"X-Request-ID": "trace-id"},
        content=b"stored_build_id=original-build&app_id=app-1",
    )


def _response(
    request: Request,
    status: int = 409,
    *,
    detail: object = _DETAIL,
    code: str = "app_busy",
) -> Response:
    """Build an API response tied to its request.

    Args:
        request: The request being answered.
        status: The response status.
        detail: The refusal's body detail.
        code: The refusal's condition code.

    Returns:
        The response.
    """
    return Response(
        request=request,
        status_code=status,
        reason_phrase="Conflict" if status == 409 else "",
        headers={"x-reflex-error-code": code},
        content=json.dumps({"detail": detail}).encode(),
    )


@pytest.mark.parametrize(
    ("code", "detail"),
    [
        ("app_busy", _DETAIL),
        ("app_scaling", "The scale is finishing."),
        ("app_scaling", None),
    ],
)
def test_deployment_retry_preserves_request(mocker, code: str, detail: object):
    """A confirmed refusal repeats the same stored build and trace id."""
    request = _request()
    success = _response(request, 200)
    transport = MagicMock()
    transport.send.side_effect = [
        _response(request, code=code, detail=detail),
        success,
    ]
    sleep = mocker.patch("reflex_cli.utils.deploy.time.sleep")

    assert _DeploymentRetryTransport(transport, url=_URL).send(request) is success

    assert transport.send.call_args_list == [call(request), call(request)]
    sleep.assert_called_once_with(15)


def test_deployment_retry_does_not_upload_archives_again(mocker, tmp_path: Path):
    """The real SDK reserves and uploads once while its submit waits for scaling."""
    sleep = mocker.patch("reflex_cli.utils.deploy.time.sleep")
    deployment_id = uuid.UUID(int=31)
    requests: list[Request] = []
    submissions: list[Request] = []

    def send(request: Request) -> Response:
        requests.append(request)
        if request.url == f"{_URL}/reserve":
            body = {
                "deployment_id": str(deployment_id),
                "backend": {"url": "https://storage.test/backend", "headers": {}},
                "frontend": {"url": "https://storage.test/frontend", "headers": {}},
            }
        elif request.method == "PUT":
            body = None
        else:
            assert request.url == _URL
            submissions.append(request)
            if len(submissions) == 1:
                return _response(request)
            body = str(deployment_id)
        return replace(_response(request, 200), content=json.dumps(body).encode())

    transport = MagicMock()
    transport.send.side_effect = send
    backend, frontend = tmp_path / "backend.zip", tmp_path / "frontend.zip"
    backend.write_bytes(b"backend")
    frontend.write_bytes(b"frontend")
    with ReflexBuild(
        token="test-token",
        transport=_DeploymentRetryTransport(transport, url=_URL),
        max_retries=0,
    ) as client:
        result = client.deployments.create(
            uuid.UUID(int=2), backend=backend, frontend=frontend
        )

    assert result == deployment_id
    assert sum(request.url == f"{_URL}/reserve" for request in requests) == 1
    assert sum(request.method == "PUT" for request in requests) == 2
    assert len(submissions) == 2
    assert (
        submissions[0].headers["X-Request-ID"] == submissions[1].headers["X-Request-ID"]
    )
    assert submissions[0].content == submissions[1].content
    assert isinstance(submissions[0].content, bytes)
    assert parse_qs(submissions[0].content.decode())["stored_build_id"] == [
        str(deployment_id)
    ]
    sleep.assert_called_once_with(15)


def test_deployment_retry_exhaustion_preserves_final_error(mocker):
    """Twelve refused submissions sleep eleven times and surface the last refusal."""
    request = _request()
    response = _response(request)
    transport = MagicMock()
    transport.send.return_value = response
    sleep = mocker.patch("reflex_cli.utils.deploy.time.sleep")

    with pytest.raises(ConflictError) as exc:
        _DeploymentRetryTransport(transport, url=_URL).send(request)

    assert exc.value.response is response
    assert exc.value.detail == _DETAIL
    assert transport.send.call_count == 12
    assert sleep.call_args_list == [call(15)] * 11


@pytest.mark.parametrize("safe_failure", [408, 429, "unsent"])
def test_deployment_retry_budget_survives_sdk_retries(
    mocker, caplog, safe_failure: int | Literal["unsent"]
):
    """Safe SDK retries cannot restart the submission's scaling wait budget."""
    sleep = mocker.patch("reflex_cli.utils.deploy.time.sleep")
    caplog.set_level(logging.INFO, logger="reflex_cli.utils.deploy")
    transport = MagicMock()
    submissions: list[Request] = []

    def send(request: Request) -> Response:
        """Interleave safe SDK failures with confirmed scaling refusals.

        Args:
            request: The attempted submission.

        Returns:
            A safe refusal or scaling conflict.

        Raises:
            TransportError: For the known-unsent failure case.
        """
        submissions.append(request)
        if len(submissions) in (6, 12):
            if safe_failure == "unsent":
                message = "not connected"
                raise TransportError(message, request=request, sent=False)
            return _response(request, safe_failure)
        return _response(request)

    transport.send.side_effect = send
    with (
        ReflexBuild(
            token="test-token", transport=_DeploymentRetryTransport(transport, url=_URL)
        ) as client,
        pytest.raises(ConflictError),
    ):
        client._request("POST", "deployments", str, form={"stored_build_id": "build"})

    assert len(submissions) == 14
    assert len({request.headers["X-Request-ID"] for request in submissions}) == 1
    assert all(request.content == submissions[0].content for request in submissions)
    assert sleep.call_args_list.count(call(15)) == 11
    assert len(sleep.call_args_list) == 13
    assert caplog.messages[-1].endswith("(scaling retry 11/11).")
    assert len(caplog.messages) == 11


def test_deployment_retry_sdk_stops_after_uncertain_submission(mocker):
    """A lost response after a scaling retry never grants another SDK attempt."""
    sleep = mocker.patch("reflex_cli.utils.deploy.time.sleep")
    transport = MagicMock()

    def send(request: Request) -> Response:
        """Lose the response after one explicit scaling refusal.

        Args:
            request: The attempted submission.

        Returns:
            The first scaling refusal.

        Raises:
            TransportError: When the second submission's outcome is unknown.
        """
        if transport.send.call_count == 1:
            return _response(request)
        message = "connection lost"
        raise TransportError(message, request=request, sent=True)

    transport.send.side_effect = send
    with (
        ReflexBuild(
            token="test-token", transport=_DeploymentRetryTransport(transport, url=_URL)
        ) as client,
        pytest.raises(APIConnectionError),
    ):
        client._request("POST", "deployments", str, form={"stored_build_id": "build"})

    assert transport.send.call_count == 2
    sleep.assert_called_once_with(15)


@pytest.mark.parametrize(
    ("status", "code", "detail"),
    [
        (400, "app_busy", _DETAIL),
        (401, "app_busy", _DETAIL),
        (403, "app_busy", _DETAIL),
        (500, "app_busy", _DETAIL),
        (400, "app_scaling", "The scale is finishing."),
        (500, "app_scaling", "The scale is finishing."),
        (409, "", _DETAIL),
        (409, "unclassified", _DETAIL),
        (409, "other_conflict", _DETAIL),
        (409, "app_busy", "the app is currently being stopped"),
        (409, "app_busy", "a deployment is already in progress for this app"),
        (409, "app_busy", {"message": _DETAIL}),
    ],
)
def test_deployment_retry_leaves_unrelated_responses_to_sdk(
    mocker, status: int, code: str, detail: object
):
    """Only the exact confirmed scaling refusal grants replay."""
    request = _request()
    response = _response(request, status, code=code, detail=detail)
    transport = MagicMock()
    transport.send.return_value = response
    sleep = mocker.patch("reflex_cli.utils.deploy.time.sleep")

    assert _DeploymentRetryTransport(transport, url=_URL).send(request) is response

    transport.send.assert_called_once_with(request)
    sleep.assert_not_called()


@pytest.mark.parametrize(
    "sdk_request",
    [
        replace(_request(), url=f"{_URL}/reserve"),
        replace(_request(), url="https://storage.test/api/v1/deployments"),
        replace(_request(), url="https://build.reflex.dev/proxy/api/v1/deployments"),
        replace(_request(), url=f"{_URL}?upload=true"),
        replace(_request(), method="PUT"),
        replace(_request(), content=iter([b"archive"])),
        replace(_request(), content=None),
    ],
)
def test_deployment_retry_does_not_replay_other_requests(mocker, sdk_request: Request):
    """Reserve, storage, and streamed requests stay outside the retry boundary."""
    response = _response(sdk_request)
    transport = MagicMock()
    transport.send.return_value = response
    sleep = mocker.patch("reflex_cli.utils.deploy.time.sleep")

    assert _DeploymentRetryTransport(transport, url=_URL).send(sdk_request) is response

    transport.send.assert_called_once_with(sdk_request)
    sleep.assert_not_called()


@pytest.mark.parametrize("body", [b"not json", b"[]", b"null", b'"scaling"'])
def test_deployment_retry_leaves_malformed_refusal_to_sdk(mocker, body: bytes):
    """An unrecognized refusal body cannot prove the submission was rejected."""
    request = _request()
    response = replace(_response(request), content=body)
    transport = MagicMock()
    transport.send.return_value = response
    sleep = mocker.patch("reflex_cli.utils.deploy.time.sleep")

    assert _DeploymentRetryTransport(transport, url=_URL).send(request) is response

    transport.send.assert_called_once_with(request)
    sleep.assert_not_called()


def test_deployment_retry_propagates_uncertain_transport_error(mocker):
    """A lost response could hide an accepted submit and must never be replayed."""
    request = _request()
    error = TransportError("connection lost", request=request, sent=True)
    transport = MagicMock()
    transport.send.side_effect = error
    sleep = mocker.patch("reflex_cli.utils.deploy.time.sleep")

    with pytest.raises(TransportError) as exc:
        _DeploymentRetryTransport(transport, url=_URL).send(request)

    assert exc.value is error
    transport.send.assert_called_once_with(request)
    sleep.assert_not_called()


def test_deployment_retry_interrupt_stops_before_another_submit(mocker):
    """Interrupting a scaling wait does not send another submission."""
    request = _request()
    transport = MagicMock()
    transport.send.return_value = _response(request)
    mocker.patch("reflex_cli.utils.deploy.time.sleep", side_effect=KeyboardInterrupt)

    with pytest.raises(KeyboardInterrupt):
        _DeploymentRetryTransport(transport, url=_URL).send(request)

    transport.send.assert_called_once_with(request)


def test_deployment_retry_close_delegates():
    """The caller can release the transport the decorator owns."""
    transport = MagicMock()

    _DeploymentRetryTransport(transport, url=_URL).close()

    transport.close.assert_called_once_with()


def test_bounds_retry_uses_typed_scaling_refusal(mocker):
    """A bounds retry accepts its dedicated code without matching prose."""
    path = "apps/app-1/instance_bounds"
    refusal = api_error(
        409,
        "The scale is finishing.",
        code="instance_bounds_scale_conflict",
        method="POST",
        path=path,
    )
    operation = MagicMock(side_effect=[refusal, "updated"])
    sleep = mocker.patch("reflex_cli.utils.deploy.time.sleep")

    assert (
        _retry_scaling_conflicts(
            operation,
            url=f"https://build.reflex.dev/api/v1/{path}",
            code="instance_bounds_scale_conflict",
            action="instance bounds",
            attempts=8,
        )
        == "updated"
    )

    assert operation.call_count == 2
    sleep.assert_called_once_with(15)
