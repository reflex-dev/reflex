"""Default.com telemetry integration script."""

import reflex as rx

DEFAULT_TELEMETRY_SCRIPT = """
!function(e,t){var _=0;e.__default__=e.__default__||{},e.__default__.form_id=268792,e.__default__.team_id=654,e.__default__.listenToIds=[965991],function e(){var o=t.createElement("script");o.async=!0,o.src="https://import-cdn.default.com",o.onload=function(){!0},o.onerror=function(){++_<=3&&setTimeout(e,1e3*_)},t.head.appendChild(o)}()}(window,document);
"""


def get_default_telemetry_script() -> rx.Component:
    """Get the Default.com telemetry script.

    Returns:
        The component.
    """
    return rx.el.script(DEFAULT_TELEMETRY_SCRIPT)
