"""Common Room website visitor tracking integration for Reflex applications."""

import json

import reflex as rx

# Common Room tracking configuration
COMMON_ROOM_CDN_URL_TEMPLATE: str = (
    "https://cdn.cr-relay.com/v1/site/{site_id}/signals.js"
)

# Common Room tracking script template
COMMON_ROOM_SCRIPT_TEMPLATE: str = """
(function() {{
    if (typeof window === 'undefined') return;
    if (typeof window.signals !== 'undefined') return;
    var script = document.createElement('script');
    script.src = '{cdn_url}';
    script.async = true;
    window.signals = Object.assign(
        [],
        ['page', 'identify', 'form', 'track'].reduce(function (acc, method) {{
            acc[method] = function () {{
                acc.push([method, arguments]);
                return acc;
            }};
            return acc;
        }}, [])
    );
    document.head.appendChild(script);
}})();
"""


def get_common_room_trackers(site_id: str) -> rx.Component:
    """Generate Common Room tracking component for a Reflex application.

    Args:
        site_id: Your Common Room site ID (found in your tracking snippet)

    Returns:
        rx.Component: Script component needed for Common Room tracking
    """
    cdn_url = COMMON_ROOM_CDN_URL_TEMPLATE.format(site_id=site_id)

    return rx.script(COMMON_ROOM_SCRIPT_TEMPLATE.format(cdn_url=cdn_url))


def identify_common_room_user(
    email: str, name: str | None = None
) -> rx.event.EventSpec:
    """Identify a user in Common Room analytics after form submission or login.

    This should be called when you have user identity information available,
    such as after a form submission or user login.

    Args:
        email: User's email address
        name: User's full name (optional)

    Returns:
        rx.Component: Script component that identifies the user in Common Room
    """
    identify_data = {"email": email}
    if name:
        identify_data["name"] = name

    js_data = json.dumps(identify_data)

    return rx.call_script(
        f"""
        // Identify user in Common Room after form submission or login
        if (typeof window.signals !== 'undefined' && window.signals.identify) {{
            window.signals.identify({js_data});
        }}
        """
    )
