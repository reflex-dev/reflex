"""Server status badge component used in site footers."""

from typing import Literal

import reflex as rx
from reflex_site_shared.components.icons import get_icon
from reflex_site_shared.constants import STATUS_WEB_URL

StatusVariant = Literal["Success", "Warning", "Critical"]

DEFAULT_CLASS_NAME = "inline-flex flex-row gap-1.5 items-center font-medium text-sm px-2.5 rounded-[10px] h-9 hover:bg-secondary-3 transition-bg"

STATUS_TEXT_COLORS: dict[StatusVariant, str] = {
    "Success": "text-success-9",
    "Warning": "text-warning-11",
    "Critical": "text-destructive-10",
}


STATUS_VARIANT_TEXT: dict[StatusVariant, str] = {
    "Success": "All servers are operational",
    "Warning": "Some servers are unavailable",
    "Critical": "All servers are down",
}

STATUS_ICON_COLORS: dict[StatusVariant, str] = {
    "Success": "!text-success-8",
    "Warning": "!text-warning-8",
    "Critical": "!text-destructive-9",
}


def _status_icon(color: str) -> rx.Component:
    """Create a fresh status icon component for each render branch.

    Returns:
        A new circle icon component with the given color class.
    """
    return get_icon("circle", class_name=color)


def server_status(status: StatusVariant | rx.Var[str]) -> rx.Component:
    """Create a server status component.

    Args:
        status: The status of the server.

    Returns:
        A linked status badge that points to the public status page.

    """
    return rx.el.a(
        rx.match(
            status,
            (
                "Success",
                rx.el.div(
                    _status_icon(STATUS_ICON_COLORS["Success"]),
                    STATUS_VARIANT_TEXT["Success"],
                    class_name=f"{DEFAULT_CLASS_NAME} {STATUS_TEXT_COLORS['Success']}",
                ),
            ),
            (
                "Warning",
                rx.el.div(
                    _status_icon(STATUS_ICON_COLORS["Warning"]),
                    STATUS_VARIANT_TEXT["Warning"],
                    class_name=f"{DEFAULT_CLASS_NAME} {STATUS_TEXT_COLORS['Warning']}",
                ),
            ),
            (
                "Critical",
                rx.el.div(
                    _status_icon(STATUS_ICON_COLORS["Critical"]),
                    STATUS_VARIANT_TEXT["Critical"],
                    class_name=f"{DEFAULT_CLASS_NAME} {STATUS_TEXT_COLORS['Critical']}",
                ),
            ),
            rx.el.div(
                _status_icon(STATUS_ICON_COLORS["Success"]),
                STATUS_VARIANT_TEXT["Success"],
                class_name=f"{DEFAULT_CLASS_NAME} {STATUS_TEXT_COLORS['Success']}",
            ),
        ),
        href=STATUS_WEB_URL,
        target="_blank",
        rel="noopener noreferrer",
    )
