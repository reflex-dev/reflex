"""Helpers for downloading files from the network."""

import functools
import time
from collections.abc import Callable
from typing import ParamSpec, TypeVar

import httpx

from reflex.utils.decorator import once
from reflex.utils.types import Unset

from . import console


def _httpx_verify_kwarg() -> bool:
    """Get the value of the HTTPX verify keyword argument.

    Returns:
        True if SSL verification is enabled, False otherwise
    """
    from reflex.environment import environment

    return not environment.SSL_NO_VERIFY.get()


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
            raise
        else:
            console.debug(
                f"Received response from {url} in {time.time() - initial_time:.3f} seconds"
            )
            return response

    return wrapper


def _wrap_https_lazy_func(
    func: Callable[[], Callable[_P, _T]],
) -> Callable[_P, _T]:
    """Wrap an HTTPS function with logging.

    Args:
        func: The function to wrap.

    Returns:
        The wrapped function.
    """
    unset = Unset()
    f: Callable[_P, _T] | Unset = unset

    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _T:
        nonlocal f
        if isinstance(f, Unset):
            f = _wrap_https_func(func())
            functools.update_wrapper(wrapper, f)
        return f(*args, **kwargs)

    return wrapper


def _is_ipv4_supported() -> bool:
    """Determine if the system supports IPv4.

    Returns:
        True if the system supports IPv4, False otherwise.
    """
    try:
        httpx.head("http://1.1.1.1", timeout=3)
    except httpx.RequestError:
        return False
    else:
        return True


def _is_ipv6_supported() -> bool:
    """Determine if the system supports IPv6.

    Returns:
        True if the system supports IPv6, False otherwise.
    """
    try:
        httpx.head("http://[2606:4700:4700::1111]", timeout=3)
    except httpx.RequestError:
        return False
    else:
        return True


def _should_use_ipv6() -> bool:
    """Determine if the system supports IPv6.

    Returns:
        True if the system supports IPv6, False otherwise.
    """
    return not _is_ipv4_supported() and _is_ipv6_supported()


def _httpx_local_address_kwarg() -> str:
    """Get the value of the HTTPX local_address keyword argument.

    Returns:
        The local address to bind to
    """
    from reflex.environment import environment

    return environment.REFLEX_HTTP_CLIENT_BIND_ADDRESS.get() or (
        "::" if _should_use_ipv6() else "0.0.0.0"
    )


@once
def _httpx_client() -> httpx.Client:
    """Get an HTTPX client.

    Returns:
        An HTTPX client.
    """
    from httpx._utils import get_environment_proxies

    return httpx.Client(
        transport=httpx.HTTPTransport(
            local_address=_httpx_local_address_kwarg(),
            verify=_httpx_verify_kwarg(),
        ),
        mounts={
            key: (
                None if url is None else httpx.HTTPTransport(proxy=httpx.Proxy(url=url))
            )
            for key, url in get_environment_proxies().items()
        },
    )


get = _wrap_https_lazy_func(lambda: _httpx_client().get)
