"""Configuration and request handling shared by the sync and async clients."""

from __future__ import annotations

import datetime
import email.utils
import functools
import json as json_module
import logging
import os
import platform
import random
import uuid
from collections.abc import Mapping
from importlib.metadata import PackageNotFoundError, version
from typing import Any
from urllib.parse import quote, urlencode

from reflex_build_sdk._decode import decode
from reflex_build_sdk._errors import (
    APIConnectionError,
    APIResponseValidationError,
    APITimeoutError,
    MissingTokenError,
)
from reflex_build_sdk.credentials import load_token
from reflex_build_sdk.transports._base import Request, Response, TransportError

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://build.reflex.dev"
DEFAULT_MAX_RETRIES = 2

# Statuses meaning the server turned the request away without processing it.
_REJECTED_STATUS_CODES = frozenset({408, 429})
# Statuses meaning the request may or may not have been processed.
_TRANSIENT_STATUS_CODES = frozenset({500, 502, 503, 504})
# Methods whose repetition has no further effect when the first attempt was
# processed after all. DELETE is left out: repeating a delete that went through
# responds 404, reporting a failure for a request that succeeded.
_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "PUT"})
# Exponential backoff between retries, in seconds: half a second before the first
# retry, doubling each time, never more than 8 seconds.
_INITIAL_RETRY_DELAY = 0.5
_MAX_RETRY_DELAY = 8.0
# The longest server-requested wait honored, in seconds (one minute). A longer
# Retry-After falls back to the exponential backoff rather than stalling the caller.
_MAX_RETRY_AFTER = 60.0


def path_segment(value: str | uuid.UUID) -> str:
    """Quote a value for use as one segment of a request path.

    Args:
        value: The path parameter.

    Returns:
        The value with every reserved character, ``/`` included, percent-encoded.
    """
    return quote(str(value), safe="")


@functools.cache
def sdk_version() -> str:
    """Get the installed version of the SDK.

    Returns:
        The version, or ``"unknown"`` when the package metadata is missing.
    """
    try:
        return version("reflex-build-sdk")
    except PackageNotFoundError:
        return "unknown"


@functools.cache
def user_agent() -> str:
    """Get the ``User-Agent`` the SDK sends.

    Returns:
        The SDK and Python versions.
    """
    return f"reflex-build-sdk/{sdk_version()} python/{platform.python_version()}"


def connection_error(error: TransportError) -> APIConnectionError:
    """Convert a transport failure into the error the SDK raises for it.

    Args:
        error: The failure, raised by a transport.

    Returns:
        An ``APITimeoutError`` for a timeout, an ``APIConnectionError`` otherwise.
    """
    request = error.request
    error_type = APITimeoutError if error.timed_out else APIConnectionError
    # The query is left out: a signed upload URL carries its credential there.
    url = request.url.partition("?")[0]
    return error_type(f"{request.method} {url} failed: {error}", request=request)


def _retry_after(response: Response) -> float | None:
    """Read how long the server asks the client to wait before retrying.

    Args:
        response: The error response.

    Returns:
        The wait in seconds, or None when the header is absent, invalid or asks
        for longer than the client waits.
    """
    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        delay = float(value)
    except ValueError:
        try:
            retry_at = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=datetime.timezone.utc)
        # A date already past means retry now.
        delay = max(
            (retry_at - datetime.datetime.now(datetime.timezone.utc)).total_seconds(),
            0.0,
        )
    return delay if 0 <= delay <= _MAX_RETRY_AFTER else None


class BaseClient:
    """Settings and request building shared by the sync and async clients."""

    def __init__(
        self,
        *,
        token: str | None,
        base_url: str | None,
        timeout: float | None,
        max_retries: int,
    ) -> None:
        """Resolve the client settings.

        Args:
            token: The access token. Defaults to the ``REFLEX_ACCESS_TOKEN`` environment
                variable, then to the token saved by ``reflex login``.
            base_url: The Reflex Cloud URL. Defaults to the ``REFLEX_CLOUD_BACKEND_URL``
                environment variable, then to ``https://build.reflex.dev``.
            timeout: The timeout of each network operation in seconds, or None for the
                transport's defaults.
            max_retries: How many times a failed request that is safe to repeat is retried.
        """
        self._token = token or os.environ.get("REFLEX_ACCESS_TOKEN") or load_token()
        self._base_url = (
            base_url or os.environ.get("REFLEX_CLOUD_BACKEND_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._api_url = f"{self._base_url}/api/v1/"

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
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None,
        json: Any,
        authenticated: bool,
        form: Mapping[str, str] | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> Request:
        """Build an API request.

        Args:
            method: The HTTP method.
            path: The endpoint path relative to ``/api/v1/``, with path parameters
                already quoted.
            params: The query parameters; None values are left out, and booleans are
                sent as ``true`` or ``false``.
            json: The JSON body, if any.
            authenticated: Whether to send the access token.
            form: A form-encoded body, sent instead of ``json``.
            extra_headers: Headers to send beside the ones every request carries.

        Returns:
            The request, carrying a fresh ``X-Request-ID``.

        Raises:
            MissingTokenError: If the request needs a token and the client has none.
        """
        headers = {
            "Accept": "application/json",
            "User-Agent": user_agent(),
            "X-Request-ID": uuid.uuid4().hex,
            **(extra_headers or {}),
        }
        if authenticated:
            if not self._token:
                msg = "No Reflex Cloud access token: pass token=, set REFLEX_ACCESS_TOKEN, or run `reflex login`."
                raise MissingTokenError(msg)
            headers["X-API-TOKEN"] = self._token
        url = self._api_url + path
        if params:
            query = urlencode(
                {
                    name: ("true" if value else "false")
                    if type(value) is bool
                    else value
                    for name, value in params.items()
                    if value is not None
                },
                doseq=True,
            )
            if query:
                url = f"{url}?{query}"
        content = None
        if form is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            content = urlencode(form).encode()
        elif json is not None:
            headers["Content-Type"] = "application/json"
            content = json_module.dumps(json, separators=(",", ":")).encode()
        return Request(
            method=method,
            url=url,
            headers=headers,
            content=content,
            timeout=self._timeout,
        )

    def _retry_delay(
        self,
        request: Request,
        attempt: int,
        response: Response | None = None,
        *,
        sent: bool = True,
        idempotent: bool | None = None,
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
            idempotent: Whether repeating the request is harmless. Defaults to
                whether the method is idempotent.

        Returns:
            The delay in seconds before retrying, or None to give up.
        """
        if attempt >= self._max_retries:
            return None
        if idempotent is None:
            idempotent = request.method in _IDEMPOTENT_METHODS
        if response is None:
            retryable = not sent or idempotent
        elif response.status_code in _REJECTED_STATUS_CODES:
            retryable = True
        else:
            retryable = response.status_code in _TRANSIENT_STATUS_CODES and idempotent
        if not retryable:
            return None
        if response is not None:
            retry_after = _retry_after(response)
            if retry_after is not None:
                return retry_after
        delay = min(_INITIAL_RETRY_DELAY * 2**attempt, _MAX_RETRY_DELAY)
        return delay * random.uniform(0.75, 1.0)


def decode_response(response: Response, cast: Any) -> Any:
    """Decode a successful response body.

    Args:
        response: The successful response.
        cast: The type to decode the JSON body into, None to ignore the body, or
            ``Response`` for the response itself, e.g. for a body that is not JSON.

    Returns:
        The decoded body, None when ``cast`` is None, or the response when ``cast`` is
        ``Response``.

    Raises:
        APIResponseValidationError: If the body is not JSON of the expected type.
    """
    if cast is None:
        return None
    if cast is Response:
        return response
    try:
        return decode(cast, response.json())
    except ValueError as ex:
        msg = f"Unexpected response body from {response.request.method} {response.request.url}: {ex}"
        raise APIResponseValidationError(msg, response=response) from ex
