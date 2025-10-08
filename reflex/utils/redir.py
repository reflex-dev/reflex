"""Utilities to handle redirection to browser UI."""

from reflex import constants
from reflex.utils import console


def open_browser(target_url: str) -> None:
    """Open a browser window to target_url.

    Args:
        target_url: The URL to open in the browser.
    """
    import webbrowser

    if not webbrowser.open(target_url):
        console.warn(
            f"Unable to automatically open the browser. Please navigate to {target_url} in your browser."
        )
    else:
        console.info(f"Opening browser to {target_url}.")


def reflex_build_redirect() -> None:
    """Open the browser window to reflex.build."""
    open_browser(constants.Templates.REFLEX_BUILD_FRONTEND)


def reflex_templates():
    """Open the browser window to reflex.build/templates."""
    open_browser(constants.Templates.REFLEX_TEMPLATES_URL)
