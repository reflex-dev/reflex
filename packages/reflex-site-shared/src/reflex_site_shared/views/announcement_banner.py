"""Site-wide announcement banner for reflex.dev."""

import reflex_components_internal as ui

import reflex as rx
from reflex_site_shared.views.hosting_banner import HostingBannerState

XY_IN_REFLEX_BUILD_URL = "https://reflex.dev/blog/xy-in-reflex-build/"


def announcement_banner() -> rx.Component:
    """Render the linked announcement using the neutral brand palette.

    Returns:
        The rendered component.
    """
    # Keep banner geometry stable when navigating between marketing routes.
    height_class = "h-10"
    return rx.el.div(
        rx.cond(
            HostingBannerState.is_banner_visible,
            rx.el.div(
                rx.el.elements.a(
                    rx.el.span(
                        rx.el.span(
                            "New",
                            class_name=(
                                "inline-flex h-5 shrink-0 items-center justify-center rounded-full "
                                "border border-white/20 bg-white/10 dark:border-black/10 dark:bg-black/[0.02] px-2 "
                                "text-micro font-medium uppercase leading-none "
                                "tracking-[0.04em] text-primary-foreground/85"
                            ),
                        ),
                        rx.el.span(
                            "xy is now in Reflex Build",
                            class_name="announcement-shimmer relative inline-block whitespace-nowrap text-xs font-normal leading-5 text-primary-foreground/75 sm:text-xs",
                            custom_attrs={
                                "data-shimmer-text": "xy is now in Reflex Build"
                            },
                        ),
                        rx.el.span(
                            rx.el.span("Read more", class_name="hidden sm:inline"),
                            ui.icon(
                                "ArrowRight01Icon",
                                aria_hidden=True,
                                class_name=(
                                    "size-3.5 shrink-0 transition-transform duration-200 "
                                    "group-hover:translate-x-0.5 group-focus-visible:translate-x-0.5 "
                                    "motion-reduce:transform-none motion-reduce:transition-none"
                                ),
                            ),
                            class_name=(
                                "text-primary-foreground/85 group-hover:text-primary-foreground group-focus-visible:text-primary-foreground inline-flex shrink-0 "
                                "items-center gap-1.5 whitespace-nowrap text-xs font-normal leading-5 "
                                "transition-colors motion-reduce:transition-none sm:text-xs"
                            ),
                        ),
                        class_name=(
                            "mx-auto flex h-full w-full max-w-[105rem] items-center "
                            "justify-center gap-2 px-10 sm:gap-3 sm:px-12"
                        ),
                    ),
                    rx.el.span(" (opens in a new tab)", class_name="sr-only"),
                    href=XY_IN_REFLEX_BUILD_URL,
                    target="_blank",
                    rel="noopener noreferrer",
                    class_name=(
                        "group block h-full w-full bg-primary text-primary-foreground hover:bg-primary-hover focus-visible:outline-2 focus-visible:-outline-offset-4 focus-visible:outline-primary-foreground "
                        "transition-colors duration-200 motion-reduce:transition-none"
                    ),
                ),
                rx.el.button(
                    ui.icon("Cancel01Icon", class_name="size-4", aria_hidden=True),
                    type="button",
                    aria_label="Dismiss announcement",
                    on_click=HostingBannerState.hide_banner,
                    class_name=(
                        "bg-transparent text-primary-foreground hover:bg-white/15 focus-visible:outline-2 focus-visible:outline-primary-foreground focus-visible:outline-offset-2 absolute right-2 top-1/2 "
                        "-translate-y-1/2 inline-flex size-7 items-center justify-center "
                        "rounded-full sm:right-4"
                    ),
                ),
                custom_attrs={"data-announcement": ""},
                role="region",
                aria_label="Latest announcement",
                class_name=(
                    f"bg-primary text-primary-foreground border-primary-foreground/10 transition-[height,opacity,visibility] duration-200 motion-reduce:transition-none relative order-first {height_class} "
                    "w-full overflow-hidden border-b"
                ),
            ),
        ),
        on_mount=HostingBannerState.show_agent_toolkit_banner,
    )
