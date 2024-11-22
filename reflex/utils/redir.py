"""Utilities to handle redirection to browser UI."""

import time
import uuid
import webbrowser

import httpx

from .. import constants
from . import console


def open_browser(target_url: str) -> None:
    """Open a browser window to target_url.

    Args:
        target_url: The URL to open in the browser.
    """
    if not webbrowser.open(target_url):
        console.warn(
            f"Unable to automatically open the browser. Please navigate to {target_url} in your browser."
        )


def open_browser_and_wait(
    target_url: str, poll_url: str, interval: int = 2
) -> httpx.Response:
    """Open a browser window to target_url and request poll_url until it returns successfully.

    Args:
        target_url: The URL to open in the browser.
        poll_url: The URL to poll for success.
        interval: The interval in seconds to wait between polling.

    Returns:
        The response from the poll_url.
    """
    open_browser(target_url)
    console.info("[b]Complete the workflow in the browser to continue.[/b]")
    while True:
        try:
            response = httpx.get(poll_url, follow_redirects=True)
            if response.is_success:
                break
        except httpx.RequestError as err:
            console.info(f"Will retry after error occurred while polling: {err}.")
        time.sleep(interval)
    return response


def reflex_build_redirect() -> str:
    """Open the browser window to reflex.build and wait for the user to select a generation.

    Returns:
        The selected generation hash.
    """
    token = str(uuid.uuid4())
    target_url = constants.Templates.REFLEX_BUILD_URL.format(reflex_init_token=token)
    poll_url = constants.Templates.REFLEX_BUILD_POLL_URL.format(reflex_init_token=token)
    response = open_browser_and_wait(target_url, poll_url)
    return response.json()["generation_hash"]
