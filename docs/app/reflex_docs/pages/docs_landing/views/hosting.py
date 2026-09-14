"""A connected overview of the Reflex Cloud hosting guides."""

import reflex as rx

from reflex_docs.pages.docs import hosting as hosting_page


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


def hosting_service(icon: str, title: str) -> rx.Component:
    """Show one part of the deployed full-stack application."""
    return rx.el.div(
        rx.icon(icon, size=24, aria_hidden=True),
        rx.el.span(title, class_name="text-sm font-book text-foreground"),
        class_name="docs-cloud-service flex min-w-0 flex-1 flex-col items-center gap-3 rounded-lg px-3 py-5",
    )


def hosting_application() -> rx.Component:
    """Place the hosted frontend and backend at the center of the diagram."""
    return rx.el.div(
        rx.el.div(
            rx.icon("cloud", size=18, aria_hidden=True, class_name="docs-cloud-icon"),
            rx.el.span("Reflex Cloud", class_name="text-sm text-foreground"),
            class_name="flex items-center gap-3 border-b border-border px-6 py-4",
        ),
        rx.el.div(
            rx.el.h3(
                "Your application",
                class_name="text-xl font-book tracking-tight text-foreground",
            ),
            rx.el.div(
                hosting_service("panels-top-left", "Frontend"),
                rx.el.div(class_name="docs-cloud-service-line", aria_hidden=True),
                hosting_service("code-xml", "Backend"),
                class_name="flex items-center",
            ),
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
