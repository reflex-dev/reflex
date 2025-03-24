"""Helpers for downloading files from the network."""

import functools
import time
from typing import Callable, ParamSpec, TypeVar

import httpx

from reflex.utils.decorator import once

from . import console


def _httpx_verify_kwarg() -> bool:
    """Get the value of the HTTPX verify keyword argument.

    Returns:
        True if SSL verification is enabled, False otherwise
    """
    from ..config import environment

    return not environment.SSL_NO_VERIFY.get()


@once
def _httpx_local_address_kwarg() -> str:
    """Get the value of the HTTPX local_address keyword argument.

    Returns:
        The local address to bind to
    """
    from ..config import environment

    return environment.REFLEX_HTTP_CLIENT_BIND_ADDRESS.get()


_P = ParamSpec("_P")
_T = TypeVar("_T")


def _wrap_https_func(
    func: Callable[_P, _T],
) -> Callable[_P, _T]:
    """Wrap an HTTPS function with logging.

    Args:
        func: The function to wrap.

    Returns:
        The wrapped function.
    """

    @functools.wraps(func)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _T:
        url = args[0]
        console.debug(f"Sending HTTPS request to {args[0]}")
        initial_time = time.time()
        try:
            response = func(*args, **kwargs)
        except httpx.ConnectError as err:
            if "CERTIFICATE_VERIFY_FAILED" in str(err):
                # If the error is a certificate verification error, recommend mitigating steps.
                console.error(
                    f"Certificate verification failed for {url}. Set environment variable SSL_CERT_FILE to the "
                    "path of the certificate file or SSL_NO_VERIFY=1 to disable verification."
                )
            if "Temporary failure in name resolution" in str(err):
                console.error(
                    f"DNS resolution failed for {url}. Check your network connection.\n\nIf your access to the internet "
                    "can only be done over IPv6, set environment variable REFLEX_HTTP_CLIENT_BIND_ADDRESS to `::`."
                )
            raise
        else:
            console.debug(
                f"Received response from {url} in {time.time() - initial_time:.3f} seconds"
            )
            return response

    return wrapper


@once
def _httpx_client() -> httpx.Client:
    """Get an HTTPX client.

    Returns:
        An HTTPX client.
    """
    return httpx.Client(
        transport=httpx.HTTPTransport(
            local_address=_httpx_local_address_kwarg(),
            verify=_httpx_verify_kwarg(),
        )
    )


get = _wrap_https_func(_httpx_client().get)
