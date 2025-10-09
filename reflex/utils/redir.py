"""Utilities to handle redirection to browser UI."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from urllib.parse import SplitResult


def open_browser(target_url: "SplitResult") -> None:
    """Open a browser window to target_url.

    Args:
        target_url: The URL to open in the browser.
    """
    import webbrowser

    from reflex.utils import console

    if not webbrowser.open(target_url.geturl()):
        console.warn(
            f"Unable to automatically open the browser. Please navigate to {target_url} in your browser."
        )
    else:
        simplified_url = target_url._replace(path="", query="", fragment="").geturl()
        console.info(f"Opened browser to {simplified_url}")


def reflex_build_redirect() -> None:
    """Open the browser window to reflex.build."""
    from urllib.parse import urlsplit

    from reflex import constants

    open_browser(urlsplit(constants.Templates.REFLEX_BUILD_FRONTEND_WITH_REFERRER))


def reflex_templates():
    """Open the browser window to reflex.build/templates."""
    from urllib.parse import urlsplit

    from reflex import constants

    open_browser(urlsplit(constants.Templates.REFLEX_TEMPLATES_URL))
