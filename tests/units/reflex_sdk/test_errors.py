from __future__ import annotations

from typing import Any

import httpx
import pytest
from reflex_sdk._errors import (
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    UnprocessableEntityError,
    status_error_from_response,
)


def _response(status_code: int, **kwargs: Any) -> httpx.Response:
    request = httpx.Request(
        "GET", "https://build.reflex.dev/api/v1/apps", headers={"X-Request-ID": "abc"}
    )
    return httpx.Response(status_code, request=request, **kwargs)


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (400, BadRequestError),
        (401, AuthenticationError),
        (403, PermissionDeniedError),
        (404, NotFoundError),
        (409, ConflictError),
        (422, UnprocessableEntityError),
        (429, RateLimitError),
        (500, InternalServerError),
        (503, InternalServerError),
        (418, APIStatusError),
    ],
)
def test_status_error_type(status_code: int, error_type: type[APIStatusError]):
    error = status_error_from_response(_response(status_code))
    assert type(error) is error_type
    assert error.status_code == status_code
    assert error.request_id == "abc"


def test_status_error_detail_from_json_object():
    response = _response(401, json={"detail": "Token not found or is inactive"})
    error = status_error_from_response(response)
    assert error.detail == "Token not found or is inactive"
    assert error.response is response
    assert str(error) == "401 Unauthorized: Token not found or is inactive"


def test_status_error_validation_detail():
    detail = [{"loc": ["body", "name"], "msg": "Field required", "type": "missing"}]
    error = status_error_from_response(_response(422, json={"detail": detail}))
    assert error.detail == detail


@pytest.mark.parametrize(
    ("kwargs", "detail", "message"),
    [
        ({"json": ["a"]}, ["a"], "500 Internal Server Error: ['a']"),
        (
            {"json": {"error": "x"}},
            {"error": "x"},
            "500 Internal Server Error: {'error': 'x'}",
        ),
        (
            {"text": "Bad gateway"},
            "Bad gateway",
            "500 Internal Server Error: Bad gateway",
        ),
        ({}, "", "500 Internal Server Error"),
    ],
)
def test_status_error_detail_without_detail_field(
    kwargs: dict[str, Any], detail: Any, message: str
):
    error = status_error_from_response(_response(500, **kwargs))
    assert error.detail == detail
    assert str(error) == message
