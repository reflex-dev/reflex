"""Unit tests for scripts/pr_bot/github.py (the GitHub API client)."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from email.message import Message
from typing import Any

import pytest

from scripts.pr_bot import github as github_module
from scripts.pr_bot.github import GitHub, GitHubError


class Response:
    """A stand-in for what urlopen returns."""

    def __init__(self, payload: Any, headers: dict[str, str] | None = None):
        """Create the response.

        Args:
            payload: The body: bytes, or anything JSON-serializable.
            headers: The response headers.
        """
        self._payload = (
            payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        )
        self.headers = Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value

    def read(self) -> bytes:
        """Return the body.

        Returns:
            The body.
        """
        return self._payload

    def __enter__(self) -> Response:
        """Use the response as a context manager, as urlopen's is.

        Returns:
            The response.
        """
        return self

    def __exit__(self, *args: object) -> None:
        """Close nothing.

        Args:
            *args: The exception details, if any.
        """


def http_error(
    status: int, message: str, headers: dict[str, str] | None = None
) -> urllib.error.HTTPError:
    """Build the error urlopen raises for an HTTP error status.

    Args:
        status: The HTTP status.
        message: GitHub's error message.
        headers: The response headers.

    Returns:
        The error.
    """
    header = Message()
    for key, value in (headers or {}).items():
        header[key] = value
    body = io.BytesIO(json.dumps({"message": message}).encode())
    return urllib.error.HTTPError(
        "https://api.github.com/x", status, message, header, body
    )


class Transport:
    """Queued responses for urlopen, and the requests it received."""

    def __init__(self):
        """Start with nothing queued."""
        self.responses: list[Any] = []
        self.requests: list[urllib.request.Request] = []

    def append(self, response: Any) -> None:
        """Queue a response.

        Args:
            response: A Response, or an exception to raise.
        """
        self.responses.append(response)

    def extend(self, responses: list[Any]) -> None:
        """Queue several responses.

        Args:
            responses: Responses or exceptions, in order.
        """
        self.responses.extend(responses)

    def urlopen(self, request: urllib.request.Request, timeout: float) -> Response:
        """Answer a request with the next queued response.

        Args:
            request: The request.
            timeout: Ignored.

        Returns:
            The response.

        Raises:
            Exception: When the queued response is one.
        """
        self.requests.append(request)
        outcome = self.responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> Transport:
    """Replace the network, and skip the waits between retries.

    Args:
        monkeypatch: The monkeypatch fixture.

    Returns:
        The fake transport.
    """
    fake = Transport()
    monkeypatch.setattr(github_module.urllib.request, "urlopen", fake.urlopen)
    monkeypatch.setattr(github_module.time, "sleep", lambda seconds: None)
    return fake


def test_rest_sends_auth_and_json(transport: Transport):
    transport.append(Response({"ok": True}))
    client = GitHub("secret", "reflex-dev/reflex")
    assert client.rest(
        "POST", "repos/reflex-dev/reflex/issues/1/labels", {"labels": ["x"]}
    ) == {"ok": True}
    (request,) = transport.requests
    assert (
        request.full_url
        == "https://api.github.com/repos/reflex-dev/reflex/issues/1/labels"
    )
    assert request.get_header("Authorization") == "Bearer secret"
    assert request.data == b'{"labels": ["x"]}'


def test_paginate_follows_next_links(transport: Transport):
    transport.append(
        Response(
            [1, 2],
            {
                "Link": '<https://api.github.com/next?page=2>; rel="next", <https://api.github.com/last>; rel="last"'
            },
        )
    )
    transport.append(Response([3]))
    client = GitHub("t", "reflex-dev/reflex")
    assert list(client.paginate("repos/reflex-dev/reflex/labels")) == [1, 2, 3]
    first, second = transport.requests
    assert first.full_url.endswith("/labels?per_page=100")
    assert second.full_url == "https://api.github.com/next?page=2"


def test_graphql_errors_raise(transport: Transport):
    transport.append(
        Response({"data": None, "errors": [{"message": "Field 'x' doesn't exist"}]})
    )
    with pytest.raises(GitHubError, match="Field 'x' doesn't exist"):
        GitHub("t", "o/r").graphql("query { x }")


def test_server_errors_are_retried(transport: Transport):
    transport.extend([http_error(502, "bad gateway"), Response({"ok": True})])
    assert GitHub("t", "o/r").rest("GET", "x") == {"ok": True}


def test_permission_errors_are_not_retried(transport: Transport):
    transport.append(http_error(403, "Resource not accessible by integration"))
    with pytest.raises(GitHubError, match="403: Resource not accessible") as caught:
        GitHub("t", "o/r").rest("GET", "x")
    assert caught.value.status == 403


def test_rate_limits_wait_for_retry_after(transport: Transport):
    transport.extend([
        http_error(403, "secondary rate limit", {"retry-after": "3"}),
        Response([]),
    ])
    assert GitHub("t", "o/r").rest("GET", "x") == []


def test_retries_give_up(transport: Transport):
    transport.extend([http_error(503, "unavailable")] * 4)
    with pytest.raises(GitHubError, match="503"):
        GitHub("t", "o/r").rest("GET", "x")


@pytest.mark.parametrize(
    ("status", "headers", "expected"),
    [
        (502, {}, 1.0),
        (404, {}, None),
        (429, {"retry-after": "5"}, 5.0),
        (403, {"retry-after": "600"}, None),
        (403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "0"}, 1.0),
        (403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "99999999999"}, None),
    ],
)
def test_retry_delay(status: int, headers: dict[str, str], expected: float | None):
    message = Message()
    for key, value in headers.items():
        message[key] = value
    assert github_module._retry_delay(status, message, 0) == expected


def test_pull_diff_is_none_when_github_will_not_render_it(transport: Transport):
    transport.append(http_error(406, "diff too large"))
    assert GitHub("t", "o/r").pull_diff(1) is None
    (request,) = transport.requests
    assert request.get_header("Accept") == "application/vnd.github.diff"


def test_remove_label_escapes_the_name(transport: Transport):
    transport.append(Response(b""))
    GitHub("t", "reflex-dev/reflex").remove_label(5, "status: ready to merge")
    (request,) = transport.requests
    assert request.full_url.endswith("/issues/5/labels/status%3A%20ready%20to%20merge")
    assert request.get_method() == "DELETE"
