from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from reflex_sdk._base import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    BaseClient,
    decode_response,
)
from reflex_sdk._errors import APIResponseValidationError, MissingTokenError
from reflex_sdk.types import Me


def _client(**kwargs: Any) -> BaseClient:
    settings = {
        "token": None,
        "base_url": None,
        "timeout": None,
        "max_retries": DEFAULT_MAX_RETRIES,
    }
    return BaseClient(**(settings | kwargs))


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


def test_build_request():
    client = _client(
        token="secret", base_url="https://example.com/prefix/", timeout=5.0
    )
    request = client._build_request(
        httpx.Client(),
        "GET",
        "apps/a%2Fb",
        params={"project": "p"},
        json=None,
        authenticated=True,
    )
    assert str(request.url) == "https://example.com/prefix/api/v1/apps/a%2Fb?project=p"
    assert request.headers["X-API-TOKEN"] == "secret"
    assert request.headers["User-Agent"].startswith("reflex-sdk/")
    assert len(request.headers["X-Request-ID"]) == 32
    assert request.extensions["timeout"] == httpx.Timeout(5.0).as_dict()


def test_build_request_defaults_to_http_client_timeout():
    http_client = httpx.Client(timeout=httpx.Timeout(3.0, connect=1.0))
    request = _client(token="secret")._build_request(
        http_client,
        "GET",
        "apps",
        params=None,
        json=None,
        authenticated=True,
    )
    assert request.extensions["timeout"] == http_client.timeout.as_dict()


@pytest.mark.parametrize("setting", ["token", "base_url", "max_retries"])
def test_settings_are_read_only(setting: str):
    with pytest.raises(AttributeError):
        setattr(_client(), setting, None)


def test_build_unauthenticated_request_without_token():
    request = _client()._build_request(
        httpx.Client(),
        "POST",
        "cli/token",
        params=None,
        json={"a": 1},
        authenticated=False,
    )
    assert "X-API-TOKEN" not in request.headers
    assert json.loads(request.content) == {"a": 1}


def test_build_authenticated_request_without_token():
    with pytest.raises(MissingTokenError, match="REFLEX_ACCESS_TOKEN"):
        _client()._build_request(
            httpx.Client(),
            "GET",
            "apps",
            params=None,
            json=None,
            authenticated=True,
        )


def _retry_delay(
    method: str,
    attempt: int = 0,
    status_code: int | None = None,
    headers: dict[str, str] | None = None,
    *,
    sent: bool = True,
) -> float | None:
    request = httpx.Request(method, "https://example.com")
    response = (
        None
        if status_code is None
        else httpx.Response(status_code, headers=headers, request=request)
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


@pytest.mark.parametrize(
    ("retry_after", "expected"),
    [("3", 3.0), ("0.5", 0.5), ("61", 0.0), ("-1", 0.0), ("soon", 0.0)],
)
def test_retry_after_header(retry_after: str, expected: float):
    delay = _retry_delay("GET", status_code=429, headers={"Retry-After": retry_after})
    assert delay == expected


def test_decode_response():
    request = httpx.Request("POST", "https://example.com/api/v1/authenticate/me")
    body = {
        "user_id": "12345678-1234-5678-1234-567812345678",
        "org_id": "12345678-1234-5678-1234-567812345678",
        "email": "a@b.c",
        "tier": "pro",
    }
    response = httpx.Response(200, json=body, request=request)
    assert decode_response(response, Me).email == "a@b.c"
    assert decode_response(response, None) is None


@pytest.mark.parametrize("kwargs", [{"text": "<html>"}, {"json": {"email": 1}}])
def test_decode_response_invalid_body(kwargs: dict[str, Any]):
    request = httpx.Request("POST", "https://example.com/api/v1/authenticate/me")
    response = httpx.Response(200, request=request, **kwargs)
    with pytest.raises(APIResponseValidationError) as exc_info:
        decode_response(response, Me)
    assert exc_info.value.response is response
    assert "POST https://example.com/api/v1/authenticate/me" in str(exc_info.value)
