"""Docs announcement using the current marketing text treatment."""

import reflex as rx
import reflex_components_internal as ui
from reflex_site_shared.views.hosting_banner import HostingBannerState

ANNOUNCEMENT_TITLE = "Announcing our $14M Series A"
ANNOUNCEMENT_URL = "https://reflex.dev/blog/series-a-announcement/"


def _announcement_line(*, highlight: bool = False) -> rx.Component:
    """Render matching text geometry for the readable row and decorative shine.

    Args:
        highlight: Whether this is the hidden decorative highlight layer.

    Returns:
        The announcement text and arrow, sharing the same layout in both layers.
    """
    return rx.el.span(
        rx.el.span("New", aria_hidden=True, class_name="docs-announcement-new"),
        rx.el.span(ANNOUNCEMENT_TITLE, class_name="docs-announcement-message"),
        rx.el.span(
            "Read more",
            ui.icon("ArrowRight01Icon", class_name="size-3.5", aria_hidden=True),
            class_name="docs-announcement-cta",
        ),
        aria_hidden=highlight,
        class_name="docs-announcement-line docs-announcement-shine"
        if highlight
        else "docs-announcement-line",
    )


def docs_announcement_banner() -> rx.Component:
    """Render the shared announcement content with docs-local presentation.

    Returns:
        A wrapper that shows the dismissible announcement while the banner is visible.
    """
    return rx.el.div(
        rx.cond(
            HostingBannerState.is_banner_visible,
            rx.el.div(
                rx.el.elements.a(
                    rx.el.span(
                        rx.el.span(
                            _announcement_line(),
                            _announcement_line(highlight=True),
                            class_name="docs-announcement-copy",
                        ),
                        class_name="docs-announcement-content",
                    ),
                    href=ANNOUNCEMENT_URL,
                    target="_blank",
                    rel="noopener noreferrer",
                    aria_label=f"New: {ANNOUNCEMENT_TITLE} — Read more (opens in a new tab)",
                    class_name="docs-announcement-link",
                ),
                rx.el.button(
                    ui.icon("Cancel01Icon", class_name="size-4", aria_hidden=True),
                    type="button",
                    aria_label="Dismiss announcement",
                    on_click=HostingBannerState.hide_banner,
                    class_name="docs-announcement-dismiss",
                ),
                custom_attrs={"data-announcement": ""},
                role="region",
                aria_label="Latest announcement",
                class_name="docs-announcement",
            ),
        ),
        on_mount=HostingBannerState.show_agent_toolkit_banner,
    )
