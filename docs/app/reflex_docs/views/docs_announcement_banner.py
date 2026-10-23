"""Docs announcement using the marketing site's opal glass artwork."""

import reflex as rx
import reflex_components_internal as ui
from reflex_site_shared.views.announcement_banner import XY_IN_REFLEX_BUILD_URL
from reflex_site_shared.views.hosting_banner import HostingBannerState


def docs_announcement_banner() -> rx.Component:
    """Render the shared announcement content with docs-local presentation.

    Returns:
        A wrapper that shows the dismissible announcement while the banner is visible.
    """
    return rx.el.div(
        rx.cond(
            HostingBannerState.is_banner_visible,
            rx.el.div(
                rx.el.div(
                    *[rx.el.span() for _ in range(5)],
                    aria_hidden=True,
                    class_name="docs-announcement-glass",
                ),
                rx.el.elements.a(
                    rx.el.span(
                        rx.el.span(
                            "New",
                            aria_hidden=True,
                            class_name="docs-announcement-badge",
                        ),
                        rx.el.span(
                            "XY is now in Reflex Build",
                            class_name="docs-announcement-message",
                        ),
                        rx.el.span("Read more", class_name="docs-announcement-cta"),
                        class_name="docs-announcement-content",
                    ),
                    href=XY_IN_REFLEX_BUILD_URL,
                    target="_blank",
                    rel="noopener noreferrer",
                    aria_label="New: XY is now in Reflex Build — Read more (opens in a new tab)",
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
