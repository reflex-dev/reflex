"""Leadpipe analytics tracking integration for Reflex applications."""

import reflex as rx

# Leadpipe tracking script URL
LEADPIPE_SCRIPT_URL: str = (
    "https://leadpipe.aws53.cloud/p/5aa37432-2448-4320-b3d5-93e27fcb6041.js"
)


def get_leadpipe_trackers() -> rx.Component:
    """Generate the Leadpipe tracking component.

    Returns:
        rx.Component: The Leadpipe script component.
    """
    return rx.el.script(src=LEADPIPE_SCRIPT_URL, async_=True)
