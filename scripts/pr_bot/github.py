"""A small client for the GitHub REST and GraphQL APIs.

Standard library only: every call is a JSON request with a token, and the bot's
workflows install nothing but the Anthropic SDK.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from email.message import Message
from typing import Any

API_URL = "https://api.github.com"
# How long a rate-limited request may wait before it is retried rather than failed.
_MAX_WAIT_SECONDS = 90.0
_ATTEMPTS = 4
_NEXT_LINK = re.compile(r'<([^>]+)>;\s*rel="next"')


class GitHubError(RuntimeError):
    """A GitHub API request failed."""

    def __init__(self, status: int, message: str):
        """Create the error.

        Args:
            status: The HTTP status, or 200 for a GraphQL response carrying errors.
            message: What GitHub said went wrong.
        """
        super().__init__(f"GitHub API error {status}: {message}")
        self.status = status


def _retry_delay(status: int, headers: Message, attempt: int) -> float | None:
    """Return how long to wait before retrying a failed request.

    Args:
        status: The HTTP status of the failure.
        headers: The response headers.
        attempt: How many attempts have failed so far, starting at 0.

    Returns:
        Seconds to wait, or None when the request should not be retried.
    """
    retry_after = headers.get("retry-after")
    if retry_after is not None:
        delay = float(retry_after)
        return delay if delay <= _MAX_WAIT_SECONDS else None
    if status in (403, 429) and headers.get("x-ratelimit-remaining") == "0":
        delay = float(headers.get("x-ratelimit-reset", "0")) - time.time()
        return max(delay, 1.0) if delay <= _MAX_WAIT_SECONDS else None
    if status >= 500:
        return 2.0**attempt
    return None


def _error_message(payload: bytes) -> str:
    """Extract GitHub's error message from a response body.

    Args:
        payload: The raw response body.

    Returns:
        The message field when the body is a JSON error, else the body as text.
    """
    text = payload.decode(errors="replace")
    try:
        return str(json.loads(text).get("message", text))
    except (ValueError, AttributeError):
        return text


def _attempt(
    request: urllib.request.Request,
) -> tuple[bytes, Message] | urllib.error.HTTPError:
    """Send a request once.

    Args:
        request: The request.

    Returns:
        The response body and headers, or the error GitHub answered with.
    """
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read(), response.headers
    except urllib.error.HTTPError as error:
        return error


class GitHub:
    """Authenticated access to one repository's REST and GraphQL APIs."""

    def __init__(self, token: str, repository: str, api_url: str = API_URL):
        """Create a client.

        Args:
            token: A token with access to the repository.
            repository: The repository as ``owner/name``.
            api_url: The REST API root; GraphQL lives at ``{api_url}/graphql``.
        """
        self.repository = repository
        self.owner, self.name = repository.split("/")
        self._token = token
        self._api_url = api_url.rstrip("/")

    @classmethod
    def from_env(cls) -> GitHub:
        """Create a client from the variables a workflow step provides.

        Returns:
            A client for ``GITHUB_REPOSITORY`` authenticated with ``GITHUB_TOKEN``.
        """
        return cls(
            os.environ["GITHUB_TOKEN"],
            os.environ["GITHUB_REPOSITORY"],
            os.environ.get("GITHUB_API_URL", API_URL),
        )

    def _send(
        self, method: str, url: str, body: Any, accept: str
    ) -> tuple[bytes, Message]:
        """Send one request, retrying rate limits and server errors.

        Args:
            method: The HTTP method.
            url: An absolute URL, or a path under the API root.
            body: A JSON-serializable request body, or None.
            accept: The Accept header.

        Returns:
            The response body and headers.

        Raises:
            GitHubError: If GitHub answers with an error that retrying won't fix.
        """
        if not url.startswith("https://"):
            url = f"{self._api_url}/{url.lstrip('/')}"
        data = None if body is None else json.dumps(body).encode()
        headers = {
            "Accept": accept,
            "Authorization": f"Bearer {self._token}",
            "User-Agent": "reflex-pr-bot",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        attempt = 0
        while isinstance(outcome := _attempt(request), urllib.error.HTTPError):
            payload = outcome.read()
            delay = _retry_delay(outcome.code, outcome.headers, attempt)
            attempt += 1
            if delay is None or attempt == _ATTEMPTS:
                raise GitHubError(outcome.code, _error_message(payload))
            time.sleep(delay)
        return outcome

    def rest(self, method: str, path: str, body: Any = None) -> Any:
        """Call a REST endpoint.

        Args:
            method: The HTTP method.
            path: The path under the API root, such as ``repos/o/r/pulls/1``.
            body: A JSON-serializable request body, or None.

        Returns:
            The decoded JSON response, or None for an empty one.
        """
        payload, _ = self._send(method, path, body, "application/vnd.github+json")
        return json.loads(payload) if payload else None

    def paginate(self, path: str) -> Iterator[Any]:
        """Iterate over every item of a paginated REST list.

        Args:
            path: The path under the API root, optionally with a query string.

        Yields:
            Each item of every page.
        """
        separator = "&" if "?" in path else "?"
        url: str | None = f"{path}{separator}per_page=100"
        while url is not None:
            payload, headers = self._send(
                "GET", url, None, "application/vnd.github+json"
            )
            yield from json.loads(payload)
            match = _NEXT_LINK.search(headers.get("link") or "")
            url = match.group(1) if match else None

    def graphql(self, query: str, **variables: Any) -> Any:
        """Run a GraphQL query.

        Args:
            query: The query document.
            **variables: The query's variables.

        Returns:
            The ``data`` member of the response.

        Raises:
            GitHubError: If the response carries errors.
        """
        payload, _ = self._send(
            "POST",
            "graphql",
            {"query": query, "variables": variables},
            "application/json",
        )
        response = json.loads(payload)
        if response.get("errors"):
            messages = "; ".join(error["message"] for error in response["errors"])
            raise GitHubError(200, messages)
        return response["data"]

    def graphql_nodes(self, query: str, *path: str, **variables: Any) -> Iterator[Any]:
        """Iterate over every node of a paginated GraphQL connection.

        The query takes an ``$after`` cursor, and selects ``nodes`` and
        ``pageInfo { hasNextPage endCursor }`` on the connection.

        Args:
            query: The query document.
            *path: The keys leading from ``data`` to the connection.
            **variables: The query's other variables.

        Yields:
            Each node of every page.
        """
        after = None
        while True:
            connection = self.graphql(query, **variables, after=after)
            for key in path:
                connection = connection[key]
            yield from connection["nodes"]
            if not connection["pageInfo"]["hasNextPage"]:
                return
            after = connection["pageInfo"]["endCursor"]

    def repo_path(self, suffix: str) -> str:
        """Return the REST path of something in this repository.

        Args:
            suffix: The path below ``repos/{owner}/{name}/``.

        Returns:
            The full path under the API root.
        """
        return f"repos/{self.repository}/{suffix}"

    def pull_diff(self, number: int) -> str | None:
        """Return a pull request's unified diff.

        Args:
            number: The pull request number.

        Returns:
            The diff, or None when GitHub declines to render it (too large).

        Raises:
            GitHubError: If the request fails for another reason.
        """
        try:
            payload, _ = self._send(
                "GET",
                self.repo_path(f"pulls/{number}"),
                None,
                "application/vnd.github.diff",
            )
        except GitHubError as error:
            if error.status in (406, 422):
                return None
            raise
        return payload.decode(errors="replace")

    def pull_files(self, number: int) -> list[dict[str, Any]]:
        """List the files a pull request changes (GitHub caps this at 3000).

        Args:
            number: The pull request number.

        Returns:
            The pulls files API entries.
        """
        return list(self.paginate(self.repo_path(f"pulls/{number}/files")))

    def create_comment(self, number: int, body: str) -> None:
        """Comment on an issue or pull request.

        Args:
            number: The issue or pull request number.
            body: The comment's Markdown.
        """
        self.rest("POST", self.repo_path(f"issues/{number}/comments"), {"body": body})

    def update_comment(self, comment_id: int, body: str) -> None:
        """Replace a comment's text.

        Args:
            comment_id: The comment's REST id.
            body: The new Markdown.
        """
        self.rest(
            "PATCH", self.repo_path(f"issues/comments/{comment_id}"), {"body": body}
        )

    def delete_comment(self, comment_id: int) -> None:
        """Delete a comment.

        Args:
            comment_id: The comment's REST id.
        """
        self.rest("DELETE", self.repo_path(f"issues/comments/{comment_id}"))

    def add_labels(self, number: int, labels: list[str]) -> None:
        """Add labels to an issue or pull request.

        Args:
            number: The issue or pull request number.
            labels: The label names.
        """
        self.rest("POST", self.repo_path(f"issues/{number}/labels"), {"labels": labels})

    def remove_label(self, number: int, label: str) -> None:
        """Remove a label from an issue or pull request.

        Args:
            number: The issue or pull request number.
            label: The label name.
        """
        name = urllib.parse.quote(label, safe="")
        self.rest("DELETE", self.repo_path(f"issues/{number}/labels/{name}"))

    def label_names(self) -> set[str]:
        """Return the names of every label defined in the repository.

        Returns:
            The label names.
        """
        return {label["name"] for label in self.paginate(self.repo_path("labels"))}

    def create_label(self, name: str, color: str, description: str) -> None:
        """Define a new label in the repository.

        Args:
            name: The label name.
            color: Its color as six hex digits.
            description: Its description.
        """
        self.rest(
            "POST",
            self.repo_path("labels"),
            {"name": name, "color": color, "description": description},
        )
