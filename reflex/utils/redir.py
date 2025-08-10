"""Utilities to handle redirection to browser UI."""

import time
import webbrowser

from reflex import constants
from reflex.utils import net

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
    else:
        console.info(f"Opening browser to {target_url}.")


def open_browser_and_wait(target_url: str, poll_url: str, interval: int = 2):
    """Open a browser window to target_url and request poll_url until it returns successfully.

    Args:
        target_url: The URL to open in the browser.
        poll_url: The URL to poll for success.
        interval: The interval in seconds to wait between polling.

    Returns:
        The response from the poll_url.
    """
    import httpx

    open_browser(target_url)
    console.info("[b]Complete the workflow in the browser to continue.[/b]")
    while True:
        try:
            response = net.get(poll_url, follow_redirects=True)
            if response.is_success:
                break
        except httpx.RequestError as err:
            console.info(f"Will retry after error occurred while polling: {err}.")
        time.sleep(interval)
    return response


def reflex_build_redirect() -> None:
    """Open the browser window to reflex.build."""
    open_browser(constants.Templates.REFLEX_BUILD_FRONTEND)


def reflex_templates():
    """Open the browser window to reflex.build/templates."""
    open_browser(constants.Templates.REFLEX_TEMPLATES_URL)
