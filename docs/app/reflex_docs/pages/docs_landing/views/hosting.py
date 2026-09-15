"""A connected overview of the Reflex Cloud hosting guides."""

import reflex as rx
from reflex_site_shared.constants import REFLEX_ASSETS_CDN

from reflex_docs.pages.docs import hosting as hosting_page
from reflex_docs.pages.docs_landing.views.artwork import artwork


def hosting_guide(icon: str, title: str, description: str, href: str) -> rx.Component:
    """Link a hosting capability into the shared application diagram."""
    return rx.el.a(
        rx.el.div(
            rx.icon(icon, size=20, aria_hidden=True, class_name="docs-cloud-icon"),
            rx.icon("arrow-up-right", size=16, aria_hidden=True),
            class_name="flex items-center justify-between text-muted-foreground",
        ),
        rx.el.h3(
            title, class_name="text-base font-book tracking-tight text-foreground"
        ),
        rx.el.p(description, class_name="text-sm leading-6 text-muted-foreground"),
        href=href,
        aria_label=title,
        class_name="docs-cloud-guide relative flex min-w-0 flex-1 flex-col gap-3 rounded-xl border border-border bg-background p-6 text-left transition-colors hover:border-border-strong focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
    )


def application_preview() -> rx.Component:
    """Illustrate one complete hosted application in a single window."""
    return rx.el.div(
        rx.el.div(
            rx.el.span("Overview", class_name="text-xs text-foreground"),
            rx.el.span("•••", class_name="text-muted-foreground tracking-[2px]"),
            class_name="flex items-center justify-between border-b border-border px-4 py-2",
        ),
        rx.el.div(
            rx.el.div(
                *[rx.icon(icon, size=14) for icon in ("layout-grid", "files", "users")],
                class_name="flex w-10 shrink-0 flex-col items-center gap-5 border-r border-border bg-muted py-4 text-muted-foreground",
            ),
            rx.el.div(
                rx.el.div(
                    *[
                        rx.el.div(
                            rx.el.span(
                                value, class_name="text-lg font-book text-foreground"
                            ),
                            rx.el.span(
                                label, class_name="text-[10px] text-muted-foreground"
                            ),
                            class_name="flex flex-1 flex-col rounded-md border border-border px-3 py-2",
                        )
                        for value, label in (("12", "Projects"), ("24", "Members"))
                    ],
                    class_name="flex gap-2",
                ),
                rx.el.div(
                    *[
                        rx.el.div(
                            style={"height": f"{height}%"},
                            class_name="docs-cloud-chart-bar min-w-0 flex-1 rounded-t-[2px]",
                        )
                        for height in (28, 44, 36, 61, 52, 73, 65, 92)
                    ],
                    class_name="flex h-16 items-end gap-2 border-b border-border pt-2",
                ),
                class_name="flex min-w-0 flex-1 flex-col gap-4 p-3",
            ),
            class_name="flex",
        ),
        aria_hidden=True,
        class_name="overflow-hidden rounded-lg border border-border bg-background text-left",
    )


def hosting_application() -> rx.Component:
    """Place one unified hosted application at the center of the diagram."""
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                "Deploy anywhere",
                class_name="whitespace-nowrap text-sm text-foreground",
            ),
            rx.el.div(
                rx.el.div(
                    artwork("reflex_mark", class_name="w-4 text-foreground sm:w-5"),
                    role="img",
                    aria_label="Reflex",
                    title="Reflex",
                    class_name="shrink-0",
                ),
                *[
                    rx.el.img(
                        src=rx.color_mode_cond(
                            f"{REFLEX_ASSETS_CDN}landing/integrations/light/{provider}.svg",
                            f"{REFLEX_ASSETS_CDN}landing/integrations/dark/{provider}.svg",
                        ),
                        alt=label,
                        title=label,
                        class_name="size-4 object-contain sm:size-5",
                    )
                    for provider, label in (
                        ("aws", "AWS"),
                        ("azure", "Microsoft Azure"),
                        ("gcp", "Google Cloud"),
                    )
                ],
                class_name="flex shrink-0 items-center gap-1.5",
            ),
            class_name="flex items-center justify-between gap-2 border-b border-border px-4 py-4 sm:px-6",
        ),
        rx.el.div(
            rx.el.h3(
                "Your application",
                class_name="text-xl font-book tracking-tight text-foreground",
            ),
            application_preview(),
            class_name="flex flex-col gap-6 p-6 text-center",
        ),
        class_name="docs-cloud-hub relative min-w-0 self-center rounded-panel border border-border bg-background",
    )


def hosting_section() -> rx.Component:
    """Explore the connected deployment, security, and operations guides."""
    return rx.el.section(
        rx.el.div(
            rx.el.h2(
                "Cloud",
                id="docs-cloud-title",
                class_name="text-foreground text-3xl font-book tracking-tight",
            ),
            rx.el.p(
                "Learn how to host your applications with Reflex Hosting.",
                class_name="text-muted-foreground text-sm font-normal",
            ),
            class_name="flex flex-col gap-4",
        ),
        rx.el.div(
            rx.el.div(
                hosting_guide(
                    "cloud-upload",
                    "Deployment",
                    "Take your Python app from local development to the cloud.",
                    hosting_page.deploy_quick_start.path,
                ),
                hosting_guide(
                    "key-round",
                    "Secret Management",
                    "Securely provide API keys and environment variables to your app.",
                    hosting_page.secrets_environment_vars.path,
                ),
                class_name="docs-cloud-guides docs-cloud-inputs",
            ),
            hosting_application(),
            rx.el.div(
                hosting_guide(
                    "activity",
                    "Observability",
                    "View logs and monitor your application's health.",
                    hosting_page.logs.path,
                ),
                hosting_guide(
                    "settings-2",
                    "Custom Headers and Advanced Options",
                    "Set HTTP headers, caching policies, and hosting configuration.",
                    hosting_page.deploy_quick_start.path,
                ),
                class_name="docs-cloud-guides docs-cloud-outputs",
            ),
            class_name="docs-cloud-diagram rounded-panel border border-border",
        ),
        aria_labelledby="docs-cloud-title",
        class_name="flex flex-col gap-10 max-lg:text-center relative max-w-(--landing-layout-max-width) mx-auto w-full justify-start max-xl:px-6 lg:mb-24",
    )
