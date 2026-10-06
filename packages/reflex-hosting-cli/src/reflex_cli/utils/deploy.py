"""Wait for confirmed scaling refusals without repeating build uploads."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from http import HTTPStatus
from threading import local
from typing import TypeVar
from urllib.parse import urlsplit

from reflex_build_sdk import APIStatusError, ConflictError
from reflex_build_sdk.transports import Request, Response, Transport

logger = logging.getLogger(__name__)

_T = TypeVar("_T")
_SCALING_RETRY_DELAY = 15


def _is_scaling_conflict(error: APIStatusError, path: str) -> bool:
    """Identify a refusal that guarantees a write was blocked by scaling.

    Args:
        error: The SDK's typed refusal.
        path: The expected endpoint below ``/api/v1/``.

    Returns:
        Whether this request was explicitly refused before applying its write.
    """
    if (
        error.status_code != HTTPStatus.CONFLICT
        or error.request.method != "POST"
        or urlsplit(error.request.url).path != f"/api/v1/{path}"
    ):
        return False
    if path == "deployments":
        # app_busy also covers stopping and another deployment, so its code
        # alone does not identify the scale that this retry waits for.
        return error.code == "app_busy" and error.detail == (
            "the app is currently being scaled; wait for the scale to finish, "
            "then deploy again"
        )
    return error.code == "instance_bounds_scale_conflict"


def _retry_scaling_conflicts(
    operation: Callable[[], _T], *, path: str, action: str, attempts: int
) -> _T:
    """Retry only writes the server explicitly refused because of scaling.

    Args:
        operation: The SDK operation to attempt.
        path: The expected endpoint below ``/api/v1/``.
        action: The action described in progress messages.
        attempts: The maximum number of calls, including the initial attempt.

    Returns:
        The successful operation's result.

    Raises:
        APIStatusError: If scaling persists or the refusal is unrelated.
    """
    return _ScalingRetryBudget(attempts=attempts).run(
        operation, path=path, action=action
    )


class _ScalingRetryBudget:
    """Keep scaling waits bounded across the SDK's own safe request retries."""

    def __init__(self, *, attempts: int) -> None:
        """Create the scaling retry budget.

        Args:
            attempts: The initial attempt plus the permitted scaling retries.
        """
        self._retries = attempts - 1
        self._used = 0

    def run(self, operation: Callable[[], _T], *, path: str, action: str) -> _T:
        """Retry a refused operation within the remaining scaling wait budget.

        Args:
            operation: The operation to attempt.
            path: The expected endpoint below ``/api/v1/``.
            action: The action described in progress messages.

        Returns:
            The successful operation's result.

        Raises:
            APIStatusError: If scaling persists or the refusal is unrelated.
        """
        while True:
            try:
                return operation()
            except APIStatusError as ex:
                if self._used >= self._retries or not _is_scaling_conflict(ex, path):
                    raise
            self._used += 1
            logger.info(
                f"App is being scaled; waiting {_SCALING_RETRY_DELAY} seconds before "
                f"retrying {action} (scaling retry {self._used}/{self._retries})."
            )
            time.sleep(_SCALING_RETRY_DELAY)


class _SubmissionRetryState(local):
    """Retain at most one submission's budget per calling thread."""

    submission: tuple[Request, _ScalingRetryBudget] | None = None


class _DeploymentRetryTransport:
    """Retry refused submissions while preserving their uploaded archive reservation."""

    def __init__(self, transport: Transport, *, url: str) -> None:
        """Wrap the transport used by a deployment's upload client.

        Args:
            transport: The underlying transport, closed by ``close``.
            url: The exact control-plane deployment submission URL.
        """
        self._transport = transport
        self._url = url
        self._state = _SubmissionRetryState()

    def send(self, request: Request) -> Response:
        """Send a request, waiting only when a deployment is refused for scaling.

        Args:
            request: The SDK's request, including its serialized body.

        Returns:
            The response for the SDK to decode.

        Raises:
            ConflictError: If scaling persists after eleven scaling waits.
        """
        if (
            request.method != "POST"
            or request.url != self._url
            or not isinstance(request.content, bytes)
        ):
            return self._transport.send(request)
        # Submit bodies are immutable bytes. Replaying this request keeps the
        # stored_build_id and avoids reserving and uploading the archives again.
        # The SDK reuses this Request for its own safe retries. Those must not
        # restart the scaling budget, and concurrent submissions need separate budgets.
        submission = self._state.submission
        if submission is None or submission[0] is not request:
            submission = (request, _ScalingRetryBudget(attempts=12))
            self._state.submission = submission
        return submission[1].run(
            lambda: self._send_submission(request),
            path="deployments",
            action="deployment",
        )

    def _send_submission(self, request: Request) -> Response:
        """Turn only a confirmed scaling response into a retryable SDK error.

        Args:
            request: The replayable submission request.

        Returns:
            Any response other than a confirmed scaling refusal.

        Raises:
            ConflictError: If the server refused this submission for scaling.
        """
        response = self._transport.send(request)
        if response.status_code != HTTPStatus.CONFLICT:
            return response
        try:
            body = response.json()
        except ValueError:
            return response
        if not isinstance(body, dict):
            return response
        detail = body.get("detail")
        error = ConflictError(
            f"409 {response.reason_phrase}: {detail}",
            response=response,
            detail=detail,
        )
        if _is_scaling_conflict(error, "deployments"):
            raise error
        return response

    def close(self) -> None:
        """Release the wrapped transport's connections."""
        self._transport.close()
