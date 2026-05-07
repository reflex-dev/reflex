"""Koala analytics tracking integration for Reflex applications."""

import reflex as rx

# Koala tracking configuration
KOALA_SCRIPT_URL_TEMPLATE: str = "https://cdn.getkoala.com/v1/{public_api_key}/sdk.js"

# Koala initialization script template
KOALA_SCRIPT_TEMPLATE: str = """
!function(t) {{
    if (window.ko) return;
    window.ko = [];
    [
        "identify",
        "track",
        "removeListeners",
        "on",
        "off",
        "qualify",
        "ready"
    ].forEach(function(t) {{
        ko[t] = function() {{
            var n = [].slice.call(arguments);
            return n.unshift(t), ko.push(n), ko;
        }};
    }});
    var n = document.createElement("script");
    n.async = !0;
    n.setAttribute("src", "{script_url}");
    (document.body || document.head).appendChild(n);
}}();
"""


def get_koala_trackers(public_api_key: str) -> rx.Component:
    """Generate Koala tracking component for a Reflex application.

    Args:
        public_api_key: Koala public API key

    Returns:
        rx.Component: Script component needed for Koala tracking
    """
    script_url = KOALA_SCRIPT_URL_TEMPLATE.format(public_api_key=public_api_key)

    return rx.script(KOALA_SCRIPT_TEMPLATE.format(script_url=script_url))
