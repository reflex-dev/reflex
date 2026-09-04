"""Ahrefs analytics tracking integration for Reflex applications."""

import reflex as rx

# Ahrefs analytics script URL
AHREFS_SCRIPT_URL: str = "https://analytics.ahrefs.com/analytics.js"


def get_ahrefs_trackers(data_key: str) -> rx.Component:
    """Generate the Ahrefs analytics tracking component.

    Args:
        data_key: The Ahrefs analytics data key.

    Returns:
        rx.Component: The Ahrefs script component.
    """
    return rx.el.script(
        src=AHREFS_SCRIPT_URL,
        async_=True,
        custom_attrs={"data-key": data_key},
    )
