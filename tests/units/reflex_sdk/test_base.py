from __future__ import annotations

import datetime
import email.utils
import uuid
from pathlib import Path
from typing import Any

import pytest
from reflex_sdk._base import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    BaseClient,
    connection_error,
    decode_response,
    path_segment,
)
from reflex_sdk._errors import (
    APIConnectionError,
    APIResponseValidationError,
    APITimeoutError,
    MissingTokenError,
)
from reflex_sdk.transports import Request, TransportError
from reflex_sdk.types import Me

from tests.units.reflex_sdk.conftest import json_body, reply


def _client(**kwargs: Any) -> BaseClient:
    settings = {
        "token": None,
        "base_url": None,
        "timeout": None,
        "max_retries": DEFAULT_MAX_RETRIES,
    }
    return BaseClient(**(settings | kwargs))


def _request(method: str = "GET") -> Request:
    return Request(
        method=method, url="https://example.com/api/v1/authenticate/me", headers={}
    )


def test_token_precedence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    assert _client().token is None
    (tmp_path / "hosting_v1.json").write_text('{"access_token": "stored"}')
    assert _client().token == "stored"
    monkeypatch.setenv("REFLEX_ACCESS_TOKEN", "env")
    assert _client().token == "env"
    assert _client(token="explicit").token == "explicit"


def test_base_url_precedence(monkeypatch: pytest.MonkeyPatch):
    assert _client().base_url == DEFAULT_BASE_URL
    monkeypatch.setenv("REFLEX_CLOUD_BACKEND_URL", "https://cloud.example.com/")
    assert _client().base_url == "https://cloud.example.com"
    assert _client(base_url="https://explicit.example.com").base_url == (
        "https://explicit.example.com"
    )


@pytest.mark.parametrize("setting", ["token", "base_url", "max_retries"])
def test_settings_are_read_only(setting: str):
    with pytest.raises(AttributeError):
        setattr(_client(), setting, None)


def test_build_request():
    client = _client(
        token="secret", base_url="https://example.com/prefix/", timeout=5.0
    )
    request = client._build_request(
        "GET",
        "apps/a%2Fb",
        params={"project": "p q", "cursor": None, "regions": ["sjc", "ams"]},
        json=None,
        authenticated=True,
    )
    assert request.method == "GET"
    assert request.url == (
        "https://example.com/prefix/api/v1/apps/a%2Fb"
        "?project=p+q&regions=sjc&regions=ams"
    )
    assert request.headers["X-API-TOKEN"] == "secret"
    assert request.headers["User-Agent"].startswith("reflex-sdk/")
    assert len(request.headers["X-Request-ID"]) == 32
    assert "Content-Type" not in request.headers
    assert request.content is None
    assert request.timeout == pytest.approx(5.0)


def test_build_request_boolean_params():
    request = _client(token="secret")._build_request(
        "POST",
        "apps/a/secrets",
        params={"reboot": True, "dry_run": False},
        json=None,
        authenticated=True,
    )
    assert request.url.endswith("?reboot=true&dry_run=false")


@pytest.mark.parametrize(
    ("value", "segment"),
    [
        ("plain", "plain"),
        ("a/b c?d#e", "a%2Fb%20c%3Fd%23e"),
        (
            uuid.UUID("12345678-1234-5678-1234-567812345678"),
            "12345678-1234-5678-1234-567812345678",
        ),
    ],
)
def test_path_segment(value: str | uuid.UUID, segment: str):
    assert path_segment(value) == segment


def test_build_request_without_query():
    request = _client(token="secret")._build_request(
        "GET", "apps", params={"cursor": None}, json=None, authenticated=True
    )
    assert request.url == f"{DEFAULT_BASE_URL}/api/v1/apps"
    assert request.timeout is None


def test_build_unauthenticated_request_without_token():
    request = _client()._build_request(
        "POST", "cli/token", params=None, json={"a": 1}, authenticated=False
    )
    assert "X-API-TOKEN" not in request.headers
    assert request.headers["Content-Type"] == "application/json"
    assert json_body(request) == {"a": 1}


def test_build_authenticated_request_without_token():
    with pytest.raises(MissingTokenError, match="REFLEX_ACCESS_TOKEN"):
        _client()._build_request(
            "GET", "apps", params=None, json=None, authenticated=True
        )


def _retry_delay(
    method: str,
    attempt: int = 0,
    status_code: int | None = None,
    headers: dict[str, str] | None = None,
    *,
    sent: bool = True,
) -> float | None:
    request = _request(method)
    response = (
        None if status_code is None else reply(status_code, headers=headers)(request)
    )
    return _client(max_retries=2)._retry_delay(request, attempt, response, sent=sent)


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS", "PUT"])
@pytest.mark.parametrize("status_code", [None, 500, 502, 503, 504])
def test_retry_idempotent_methods_after_ambiguous_failures(
    method: str, status_code: int | None
):
    assert _retry_delay(method, status_code=status_code) is not None


@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE"])
@pytest.mark.parametrize("status_code", [None, 500, 502, 503, 504])
def test_no_retry_non_idempotent_methods_after_ambiguous_failures(
    method: str, status_code: int | None
):
    assert _retry_delay(method, status_code=status_code) is None


@pytest.mark.parametrize("method", ["GET", "POST", "PATCH", "DELETE"])
def test_retry_any_method_the_server_did_not_process(method: str):
    assert _retry_delay(method, sent=False) is not None
    assert _retry_delay(method, status_code=408) is not None
    assert _retry_delay(method, status_code=429) is not None


def test_no_retry_after_max_retries():
    assert _retry_delay("GET", attempt=1) is not None
    assert _retry_delay("GET", attempt=2) is None
    assert _retry_delay("POST", attempt=2, sent=False) is None


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 409, 422, 501])
def test_no_retry_status_codes(status_code: int):
    assert _retry_delay("GET", status_code=status_code) is None


def test_retry_backoff(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("reflex_sdk._base._INITIAL_RETRY_DELAY", 0.5)
    first, second = _retry_delay("GET", attempt=0), _retry_delay("GET", attempt=1)
    assert first is not None
    assert 0.375 <= first <= 0.5
    assert second is not None
    assert 0.75 <= second <= 1.0


@pytest.mark.parametrize(("retry_after", "expected"), [("3", 3.0), ("0.5", 0.5)])
def test_retry_after_seconds(retry_after: str, expected: float):
    delay = _retry_delay("GET", status_code=429, headers={"retry-after": retry_after})
    assert delay == expected


def test_retry_after_http_date():
    retry_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        seconds=30
    )
    header = email.utils.format_datetime(retry_at, usegmt=True)
    delay = _retry_delay("GET", status_code=429, headers={"retry-after": header})
    assert delay is not None
    # The header has whole-second precision.
    assert 28 <= delay <= 30


def test_retry_after_past_http_date():
    header = "Wed, 21 Oct 2015 07:28:00 GMT"
    delay = _retry_delay("GET", status_code=429, headers={"retry-after": header})
    assert delay == pytest.approx(0.0)


@pytest.mark.parametrize(
    "retry_after", ["61", "-1", "soon", "Wed, 21 Oct 2099 07:28:00 GMT"]
)
def test_retry_after_falls_back_to_backoff(
    monkeypatch: pytest.MonkeyPatch, retry_after: str
):
    monkeypatch.setattr("reflex_sdk._base._INITIAL_RETRY_DELAY", 0.5)
    delay = _retry_delay("GET", status_code=429, headers={"retry-after": retry_after})
    assert delay is not None
    assert 0.375 <= delay <= 0.5


@pytest.mark.parametrize(
    ("timed_out", "error_type"),
    [(True, APITimeoutError), (False, APIConnectionError)],
)
def test_connection_error_leaves_out_the_query(
    timed_out: bool, error_type: type[APIConnectionError]
):
    request = Request(
        method="PUT",
        url="https://storage.example.com/app/backend.zip?X-Amz-Signature=secret",
        headers={},
    )
    error = connection_error(
        TransportError("reset", request=request, sent=True, timed_out=timed_out)
    )
    assert type(error) is error_type
    assert error.request is request
    assert str(error) == "PUT https://storage.example.com/app/backend.zip failed: reset"


def test_decode_response():
    body = {
        "user_id": "12345678-1234-5678-1234-567812345678",
        "org_id": "12345678-1234-5678-1234-567812345678",
        "email": "a@b.c",
        "tier": "pro",
    }
    response = reply(200, json=body)(_request("POST"))
    assert decode_response(response, Me).email == "a@b.c"
    assert decode_response(response, None) is None


@pytest.mark.parametrize("kwargs", [{"text": "<html>"}, {"json": {"email": 1}}])
def test_decode_response_invalid_body(kwargs: dict[str, Any]):
    response = reply(200, **kwargs)(_request("POST"))
    with pytest.raises(APIResponseValidationError) as exc_info:
        decode_response(response, Me)
    assert exc_info.value.response is response
    assert "POST https://example.com/api/v1/authenticate/me" in str(exc_info.value)
