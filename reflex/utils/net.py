"""Helpers for downloading files from the network."""

import httpx

from ..config import environment
from . import console


def _httpx_verify_kwarg() -> bool:
    """Get the value of the HTTPX verify keyword argument.

    Returns:
        True if SSL verification is enabled, False otherwise
    """
    return not environment.SSL_NO_VERIFY.get()


def get(url: str, **kwargs) -> httpx.Response:
    """Make an HTTP GET request.

    Args:
        url: The URL to request.
        **kwargs: Additional keyword arguments to pass to httpx.get.

    Returns:
        The response object.

    Raises:
        httpx.ConnectError: If the connection cannot be established.
    """
    kwargs.setdefault("verify", _httpx_verify_kwarg())
    try:
        return httpx.get(url, **kwargs)
    except httpx.ConnectError as err:
        if "CERTIFICATE_VERIFY_FAILED" in str(err):
            # If the error is a certificate verification error, recommend mitigating steps.
            console.error(
                f"Certificate verification failed for {url}. Set environment variable SSL_CERT_FILE to the "
                "path of the certificate file or SSL_NO_VERIFY=1 to disable verification."
            )
        raise
