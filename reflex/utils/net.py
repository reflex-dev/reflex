"""Helpers for downloading files from the network."""

import functools
import logging
import time
from collections.abc import Callable
from typing import ParamSpec, TypeVar

from reflex_base.utils.decorator import once
from reflex_base.utils.types import Unset

logger = logging.getLogger(__name__)


def _httpx_verify_kwarg() -> bool:
    """Get the value of the HTTPX verify keyword argument.

    Returns:
        True if SSL verification is enabled, False otherwise
    """
    from reflex_base.environment import environment

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
        try:
            import httpx2 as httpx
        except ModuleNotFoundError:
            import httpx

        url = args[0]
        logger.debug(f"Sending HTTPS request to {args[0]}")
        initial_time = time.time()
        try:
            response = func(*args, **kwargs)
        except httpx.ConnectError as err:
            if "CERTIFICATE_VERIFY_FAILED" in str(err):
                # If the error is a certificate verification error, recommend mitigating steps.
                logger.error(
                    f"Certificate verification failed for {url}. Set environment variable SSL_CERT_FILE to the "
                    "path of the certificate file or SSL_NO_VERIFY=1 to disable verification."
                )
            raise
        else:
            logger.debug(
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
        import httpx2 as httpx
    except ModuleNotFoundError:
        import httpx

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
        import httpx2 as httpx
    except ModuleNotFoundError:
        import httpx

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
    from reflex_base.environment import environment

    return environment.REFLEX_HTTP_CLIENT_BIND_ADDRESS.get() or (
        "::" if _should_use_ipv6() else "0.0.0.0"
    )


@once
def _httpx_client():
    """Get an HTTPX client.

    Returns:
        An HTTPX client.
    """
    # Resolve the active HTTP library at call time. Prefer httpx2 when
    # available, fall back to real httpx on Python 3.8/3.9 (which httpx2
    # cannot run on). Bind the classes to local names so pyright does not
    # infer a union of `httpx2.HTTPTransport | httpx.HTTPTransport` —
    # that union is not assignable to `Client(mounts=...)` because the
    # two transport classes are unrelated.
    try:
        import httpx2
        from httpx2._utils import get_environment_proxies
    except ModuleNotFoundError:
        import httpx as httpx2  # noqa: F401 — local name `httpx2` bound to the real httpx
        from httpx._utils import get_environment_proxies  # noqa: F811

    verify_setting = _httpx_verify_kwarg()
    # `httpx2` is a union of the two modules here (httpx2 in the try
    # branch, real httpx in the except branch). The two HTTPTransport
    # / Proxy / Client classes share compatible shapes but pyright in
    # min-version mode still infers a union and rejects the assignment
    # to `BaseTransport` / `ProxyTypes`. In practice only one branch
    # runs per process; the `# type: ignore` below is the smallest way
    # to tell pyright that, suppressing the no-real-error warnings.
    return httpx2.Client(  # type: ignore[call-overload]
        transport=httpx2.HTTPTransport(  # type: ignore[arg-type]
            local_address=_httpx_local_address_kwarg(),
            verify=verify_setting,
        ),
        mounts={
            key: (
                None
                if url is None
                else httpx2.HTTPTransport(  # type: ignore[arg-type]
                    proxy=httpx2.Proxy(url=url),  # type: ignore[arg-type]
                    verify=verify_setting,
                )
            )
            for key, url in get_environment_proxies().items()
        },
    )


get = _wrap_https_lazy_func(lambda: _httpx_client().get)  # type: ignore[arg-type]
