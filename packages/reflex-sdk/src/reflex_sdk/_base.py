"""Configuration and request handling shared by the sync and async clients."""

from __future__ import annotations

import functools
import logging
import os
import platform
import random
import uuid
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import httpx

from reflex_sdk._credentials import load_stored_token
from reflex_sdk._decode import decode
from reflex_sdk._errors import APIResponseValidationError, MissingTokenError

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://build.reflex.dev"
# The timeout of the HTTP client a Reflex Cloud client creates for itself.
DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
DEFAULT_MAX_RETRIES = 2

# Transport errors raised before the request left the client, so the server
# never saw it and any request can be sent again.
UNSENT_REQUEST_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)
# Statuses meaning the server turned the request away without processing it.
_REJECTED_STATUS_CODES = frozenset({408, 429})
# Statuses meaning the request may or may not have been processed.
_TRANSIENT_STATUS_CODES = frozenset({500, 502, 503, 504})
# Methods whose repetition has no further effect when the first attempt was
# processed after all. DELETE is left out: repeating a delete that went through
# responds 404, reporting a failure for a request that succeeded.
_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "PUT"})
_INITIAL_RETRY_DELAY = 0.5
_MAX_RETRY_DELAY = 8.0
_MAX_RETRY_AFTER = 60.0


@functools.cache
def _user_agent() -> str:
    try:
        sdk_version = version("reflex-sdk")
    except PackageNotFoundError:
        sdk_version = "unknown"
    return f"reflex-sdk/{sdk_version} python/{platform.python_version()} httpx/{httpx.__version__}"


class BaseClient:
    """Settings and request building shared by the sync and async clients."""

    def __init__(
        self,
        *,
        token: str | None,
        base_url: str | None,
        timeout: float | httpx.Timeout | None,
        max_retries: int,
    ) -> None:
        """Resolve the client settings.

        Args:
            token: The access token. Defaults to the ``REFLEX_ACCESS_TOKEN`` environment
                variable, then to the token saved by ``reflex login``.
            base_url: The Reflex Cloud URL. Defaults to the ``REFLEX_CLOUD_BACKEND_URL``
                environment variable, then to ``https://build.reflex.dev``.
            timeout: The timeout of each request attempt, in seconds, or None to use
                the timeout of the HTTP client.
            max_retries: How many times a failed request that is safe to repeat is retried.
        """
        self._token = (
            token or os.environ.get("REFLEX_ACCESS_TOKEN") or load_stored_token()
        )
        self._base_url = (
            base_url or os.environ.get("REFLEX_CLOUD_BACKEND_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        # The trailing slash makes relative paths join below the prefix.
        self._api_url = httpx.URL(f"{self._base_url}/api/v1/")

    @property
    def token(self) -> str | None:
        """The access token sent with authenticated requests, if one was found.

        Returns:
            The access token, or None.
        """
        return self._token

    @property
    def base_url(self) -> str:
        """The Reflex Cloud URL requests are sent to, without a trailing slash.

        Returns:
            The base URL.
        """
        return self._base_url

    @property
    def max_retries(self) -> int:
        """How many times a failed request that is safe to repeat is retried.

        Returns:
            The maximum number of retries.
        """
        return self._max_retries

    def _build_request(
        self,
        http_client: httpx.Client | httpx.AsyncClient,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None,
        json: Any,
        authenticated: bool,
    ) -> httpx.Request:
        """Build an API request.

        Args:
            http_client: The HTTP client that will send the request.
            method: The HTTP method.
            path: The endpoint path relative to ``/api/v1/``, with path parameters
                already quoted.
            params: The query parameters.
            json: The JSON body, if any.
            authenticated: Whether to send the access token.

        Returns:
            The request, carrying a fresh ``X-Request-ID``.

        Raises:
            MissingTokenError: If the request needs a token and the client has none.
        """
        headers = {"User-Agent": _user_agent(), "X-Request-ID": uuid.uuid4().hex}
        if authenticated:
            if not self._token:
                msg = "No Reflex Cloud access token: pass token=, set REFLEX_ACCESS_TOKEN, or run `reflex login`."
                raise MissingTokenError(msg)
            headers["X-API-TOKEN"] = self._token
        return http_client.build_request(
            method,
            self._api_url.join(path),
            params=params,
            json=json,
            headers=headers,
            timeout=httpx.USE_CLIENT_DEFAULT
            if self._timeout is None
            else self._timeout,
        )

    def _retry_delay(
        self,
        request: httpx.Request,
        attempt: int,
        response: httpx.Response | None = None,
        *,
        sent: bool = True,
    ) -> float | None:
        """Decide whether and when to retry a failed request.

        A request is only retried when repeating it cannot apply it twice: when the
        server never received or processed it, or when the method is idempotent.

        Args:
            request: The failed request.
            attempt: How many retries were already made.
            response: The error response, or None if the request did not get one.
            sent: Whether the request may have reached the server, for a request
                without a response.

        Returns:
            The delay in seconds before retrying, or None to give up.
        """
        if attempt >= self._max_retries:
            return None
        if response is None:
            retryable = not sent or request.method in _IDEMPOTENT_METHODS
        elif response.status_code in _REJECTED_STATUS_CODES:
            retryable = True
        else:
            retryable = (
                response.status_code in _TRANSIENT_STATUS_CODES
                and request.method in _IDEMPOTENT_METHODS
            )
        if not retryable:
            return None
        if response is not None:
            try:
                retry_after = float(response.headers.get("Retry-After", ""))
            except ValueError:
                pass
            else:
                if 0 <= retry_after <= _MAX_RETRY_AFTER:
                    return retry_after
        delay = min(_INITIAL_RETRY_DELAY * 2**attempt, _MAX_RETRY_DELAY)
        return delay * random.uniform(0.75, 1.0)


def decode_response(response: httpx.Response, cast: Any) -> Any:
    """Decode a successful response body.

    Args:
        response: The successful response.
        cast: The type to decode the JSON body into, or None to ignore the body.

    Returns:
        The decoded body, or None when ``cast`` is None.

    Raises:
        APIResponseValidationError: If the body is not JSON of the expected type.
    """
    if cast is None:
        return None
    try:
        return decode(cast, response.json())
    except ValueError as ex:
        msg = f"Unexpected response body from {response.request.method} {response.request.url}: {ex}"
        raise APIResponseValidationError(msg, response=response) from ex
