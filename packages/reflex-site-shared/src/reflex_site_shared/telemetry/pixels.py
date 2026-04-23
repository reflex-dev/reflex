"""This module contains the pixel trackers for the website."""

from reflex_components_internal.blocks.telemetry import (
    get_default_telemetry_script,
    get_google_analytics_trackers,
    get_posthog_trackers,
    get_unify_trackers,
    gtag_report_conversion,
)

import reflex as rx


def get_pixel_website_trackers() -> list[rx.Component]:
    """Get the pixel trackers for the website.

    Returns:
        The component.
    """
    return [
        *get_google_analytics_trackers(tracking_id="G-4T7C8ZD9TR"),
        gtag_report_conversion(
            conversion_id_and_label="AW-11360851250/ASB4COvpisIbELKqo6kq"
        ),
        get_unify_trackers(),
        get_default_telemetry_script(),
        get_posthog_trackers(
            project_id="phc_JoMo0fOyi0GQAooY3UyO9k0hebGkMyFJrrCw1Gt5SGb"
        ),
    ]
