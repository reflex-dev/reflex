"""Test utilities for reflex-web tests."""

from urllib.parse import urljoin

from reflex.testing import AppHarness


def get_full_url(app_harness: AppHarness, path: str) -> str:
    """Properly join the app's frontend URL with a path.

    This ensures proper URL construction without double slashes,
    which is important since React Router is stricter than Next.js
    about URL formatting.

    Args:
        app_harness: The AppHarness instance
        path: The path to join (should start with /)

    Returns:
        The properly joined full URL
    """
    if not app_harness.frontend_url:
        raise ValueError("App harness frontend_url is None")

    return urljoin(app_harness.frontend_url, path)
