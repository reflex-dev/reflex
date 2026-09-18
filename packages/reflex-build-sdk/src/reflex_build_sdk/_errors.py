"""Exceptions raised by the Reflex Cloud client."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from reflex_build_sdk.transports._base import Request, Response

if TYPE_CHECKING:
    from reflex_build_sdk.types import DeploymentReport


class ReflexCloudError(Exception):
    """Base class for every error raised by the Reflex Cloud client."""


class MissingTokenError(ReflexCloudError):
    """Raised when an authenticated endpoint is called without an access token."""


class DeploymentFailedError(ReflexCloudError):
    """A deployment ended without going live: it failed, or was rejected, cancelled
    or replaced before it did.
    """

    deployment_id: uuid.UUID
    # Why it failed: ``reason``, ``guidance`` and, for a failed build, the end of
    # the build log.
    report: DeploymentReport

    def __init__(self, deployment_id: uuid.UUID, report: DeploymentReport) -> None:
        """Initialize the error.

        Args:
            deployment_id: The deployment.
            report: The deployment's final report.
        """
        super().__init__(
            f"deployment {deployment_id} {report.status.lower()}: {report.reason}"
            if report.reason
            else f"deployment {deployment_id} {report.status.lower()}"
        )
        self.deployment_id = deployment_id
        self.report = report


class DeploymentTimeoutError(ReflexCloudError, TimeoutError):
    """A deployment was still in progress when waiting for it timed out."""


class LoginDeniedError(ReflexCloudError):
    """The user denied a browser login."""


class LoginTimeoutError(ReflexCloudError, TimeoutError):
    """A browser login was not approved before waiting for it timed out."""


class SecurityReviewFailedError(ReflexCloudError):
    """A security review could not be completed."""

    job_id: str

    def __init__(self, job_id: str, error: str | None) -> None:
        """Initialize the error.

        Args:
            job_id: The security review.
            error: Why it failed, as the API reports it.
        """
        super().__init__(f"security review {job_id} failed: {error or 'unknown error'}")
        self.job_id = job_id


class SecurityReviewTimeoutError(ReflexCloudError, TimeoutError):
    """A security review was still running when waiting for it timed out."""


class APIError(ReflexCloudError):
    """An error tied to a request sent to the Reflex Cloud API."""

    request: Request
    request_id: str

    def __init__(self, message: str, *, request: Request) -> None:
        """Initialize the error.

        Args:
            message: The error message.
            request: The request that failed.
        """
        super().__init__(message)
        self.request = request
        self.request_id = request.headers.get("X-Request-ID", "")


class APIConnectionError(APIError):
    """The request could not reach the API or the connection broke mid-request."""


class APITimeoutError(APIConnectionError):
    """The request timed out."""


class APIResponseValidationError(APIError):
    """The API responded successfully with a body the client could not decode."""

    response: Response

    def __init__(self, message: str, *, response: Response) -> None:
        """Initialize the error.

        Args:
            message: The error message.
            response: The response whose body could not be decoded.
        """
        super().__init__(message, request=response.request)
        self.response = response


# The header naming the condition a refusal reports, beside its prose ``detail``.
REFUSAL_CODE_HEADER = "x-reflex-error-code"


class APIStatusError(APIError):
    """The API responded with a 4xx or 5xx status code."""

    response: Response
    status_code: int
    detail: Any
    # What the API called the refusal, e.g. ``"not_connected"``, or an empty string
    # when it did not name one. More stable than ``detail``, which is prose.
    code: str

    def __init__(self, message: str, *, response: Response, detail: Any) -> None:
        """Initialize the error.

        Args:
            message: The error message.
            response: The error response.
            detail: The ``detail`` field of the response body, or the raw body text
                when it is not a JSON object with one.
        """
        super().__init__(message, request=response.request)
        self.response = response
        self.status_code = response.status_code
        self.detail = detail
        self.code = response.headers.get(REFUSAL_CODE_HEADER, "")


class BadRequestError(APIStatusError):
    """The API responded with 400 Bad Request."""


class AuthenticationError(APIStatusError):
    """The API responded with 401 Unauthorized: the token is invalid, expired or revoked."""


class PermissionDeniedError(APIStatusError):
    """The API responded with 403 Forbidden."""


class NotFoundError(APIStatusError):
    """The API responded with 404 Not Found."""


class ConflictError(APIStatusError):
    """The API responded with 409 Conflict."""


class UnprocessableEntityError(APIStatusError):
    """The API responded with 422 Unprocessable Entity; ``detail`` lists the invalid fields."""


class RateLimitError(APIStatusError):
    """The API responded with 429 Too Many Requests."""


class InternalServerError(APIStatusError):
    """The API responded with a 5xx status code."""


_STATUS_ERRORS: dict[int, type[APIStatusError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    422: UnprocessableEntityError,
    429: RateLimitError,
}


def status_error_from_response(response: Response) -> APIStatusError:
    """Build the exception matching an error response.

    Args:
        response: A response with a 4xx or 5xx status code.

    Returns:
        The most specific status error for the response.
    """
    try:
        body = response.json()
    except ValueError:
        detail = response.text
    else:
        detail = body.get("detail", body) if isinstance(body, dict) else body
    status_code = response.status_code
    error_type = _STATUS_ERRORS.get(status_code) or (
        InternalServerError if status_code >= 500 else APIStatusError
    )
    message = f"{status_code} {response.reason_phrase}"
    if detail:
        message = f"{message}: {detail}"
    return error_type(message, response=response, detail=detail)
