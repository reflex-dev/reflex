"""Utilities to handle redirection to browser UI."""

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from urllib.parse import SplitResult


def open_browser(target_url: "SplitResult") -> None:
    """Open a browser window to target_url.

    Args:
        target_url: The URL to open in the browser.
    """
    import webbrowser

    if not webbrowser.open(target_url.geturl()):
        logger.warning(
            f"Unable to automatically open the browser. Please navigate to {target_url} in your browser."
        )
    else:
        simplified_url = target_url._replace(path="", query="", fragment="").geturl()
        logger.info(f"Opened browser to {simplified_url}")


def reflex_build_redirect() -> None:
    """Open the browser window to reflex.build."""
    from urllib.parse import urlsplit

    from reflex_base import constants

    open_browser(urlsplit(constants.Templates.REFLEX_BUILD_FRONTEND_WITH_REFERRER))
