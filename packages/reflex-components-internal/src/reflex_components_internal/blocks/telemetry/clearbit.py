"""Clearbit analytics tracking integration for Reflex applications."""

import reflex as rx

CLEARBIT_SCRIPT_URL_TEMPLATE: str = (
    "https://tag.clearbitscripts.com/v1/{public_key}/tags.js"
)


def get_clearbit_trackers(public_key: str) -> rx.Component:
    """Generate Clearbit tracking component for a Reflex application.

    Args:
        public_key: Clearbit public key (defaults to app's public key)

    Returns:
        rx.Component: Script component needed for Clearbit tracking
    """
    return rx.el.script(
        src=CLEARBIT_SCRIPT_URL_TEMPLATE.format(public_key=public_key),
        referrer_policy="strict-origin-when-cross-origin",
    )
