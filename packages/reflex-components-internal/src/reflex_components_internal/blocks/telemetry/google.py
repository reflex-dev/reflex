"""Google Analytics tracking integration for Reflex applications."""

import reflex as rx

# Google Tag Manager script template
GTAG_SCRIPT_TEMPLATE: str = """
window.dataLayer = window.dataLayer || [];
function gtag() {{
    window.dataLayer.push(arguments);
}}
gtag('js', new Date());
gtag('config', '{tracking_id}');
"""

# Google Tag Manager script URL template
GTAG_SCRIPT_URL_TEMPLATE: str = (
    "https://www.googletagmanager.com/gtag/js?id={tracking_id}"
)


def get_google_analytics_trackers(
    tracking_id: str,
) -> list[rx.Component]:
    """Generate Google Analytics tracking components for a Reflex application.

    Args:
        tracking_id: Google Analytics tracking ID (defaults to app's tracking ID)

    Returns:
        list[rx.Component]: Script components needed for Google Analytics tracking
    """
    # Load Google Tag Manager script
    return [
        rx.script(src=GTAG_SCRIPT_URL_TEMPLATE.format(tracking_id=tracking_id)),
        rx.script(GTAG_SCRIPT_TEMPLATE.format(tracking_id=tracking_id)),
    ]


def gtag_report_conversion(conversion_id_and_label: str) -> rx.Component:
    """Generate a script component to report a conversion to Google Ads.

    Args:
        conversion_id_and_label: The conversion label for the Google Ads conversion.

    Returns:
        rx.Component: Script component to report the conversion.
    """
    return rx.script(
        f"""function gtag_report_conversion() {{
            var callback = function () {{
                console.log('Conversion recorded!');
            }};
            gtag('event', 'conversion', {{
                'send_to': '{conversion_id_and_label}',
                'event_callback': callback
            }});
            return false;
        }}"""
    )
