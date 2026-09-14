"""Interactive framework overview with editorial product diagrams."""

import reflex as rx
import reflex_components_internal as ui

from reflex_docs.pages.docs import database, enterprise, getting_started
from reflex_docs.pages.docs.library import library
from reflex_docs.pages.docs_landing.views.artwork import artwork

CAPABILITIES = (
    (
        "how",
        "How It Works",
        "Define your interface and state in Python. Reflex connects them into a reactive web application.",
        "From Python to a live interface",
        "Read the introduction",
        getting_started.introduction.path,
        "blue",
    ),
    (
        "components",
        "Components",
        "Each component creates a part of your interface. Nest headings, inputs, and buttons inside layout components to build a page.",
        "Python components. A complete interface.",
        "Browse all components",
        library.path,
        "lavender",
    ),
    (
        "auth",
        "Auth",
        "Connect your identity provider and control who can access your application with enterprise authentication.",
        "Your identity. Your access rules.",
        "Explore authentication",
        enterprise.auth.overview.path,
        "peach",
    ),
    (
        "database",
        "Database",
        "Define typed models, query your database, and bring live data into your application with Python.",
        "One model, from database to interface",
        "Explore databases",
        database.overview.path,
        "mint",
    ),
)


class FrameworkCounterState(rx.State):
    """Keep the landing-page counter in real server-side Python state."""

    count: int = 0

    @rx.event
    def increment(self):
        """Increase the displayed count by one."""
        self.count += 1


def example_window_header(title: str) -> rx.Component:
    """Render the shared chrome of the code and preview windows."""
    return rx.el.div(
        rx.el.span("•••", aria_hidden=True, class_name="tracking-[3px]"),
        rx.el.span(title),
        class_name="flex items-center gap-5 border-b border-border px-5 py-3 text-xs text-muted-foreground",
    )


def live_counter_diagram() -> rx.Component:
    """Connect a readable Python example to a working counter interface."""
    return rx.el.div(
        rx.el.div(
            example_window_header("app.py"),
            rx.el.pre(
                rx.el.code(
                    "import reflex as rx\n\n"
                    "class State(rx.State):\n"
                    "    count: int = 0\n\n"
                    "    @rx.event\n"
                    "    def increment(self):\n"
                    "        self.count += 1",
                ),
                class_name="m-0 px-5 py-5 font-mono text-[11px] leading-6 text-foreground sm:text-[13px]",
            ),
            class_name="docs-framework-live-code w-full overflow-hidden rounded-xl border border-border bg-background",
        ),
        rx.el.div(class_name="docs-framework-live-connector", aria_hidden=True),
        rx.el.div(
            example_window_header("Live preview"),
            rx.el.div(
                rx.el.h3(
                    "Your first Reflex app",
                    class_name="text-xl font-book tracking-tight text-foreground",
                ),
                rx.el.div(
                    rx.el.output(
                        FrameworkCounterState.count,
                        aria_label="Counter value",
                        aria_live="polite",
                        aria_atomic=True,
                        class_name="docs-framework-counter-value flex min-h-16 min-w-20 items-center justify-center rounded-lg px-4 text-3xl tabular-nums",
                    ),
                    rx.el.button(
                        "Increment",
                        rx.icon("plus", size=16, aria_hidden=True),
                        type="button",
                        on_click=FrameworkCounterState.increment,
                        class_name="inline-flex min-h-11 items-center justify-center gap-2 rounded-full bg-foreground px-5 text-sm text-background transition-opacity hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
                    ),
                    class_name="flex flex-wrap items-center justify-between gap-4",
                ),
                class_name="flex flex-col gap-5 p-5 sm:p-6",
            ),
            class_name="docs-framework-live-app w-full overflow-hidden rounded-xl border border-border bg-background",
        ),
        class_name="docs-framework-live mx-auto flex w-full max-w-[30rem] flex-col items-center py-4",
    )


def framework_tab(value: str, title: str, description: str) -> rx.Component:
    """Select a diagram with a keyboard-accessible vertical tab."""
    return ui.tabs.tab(
        rx.el.span(
            rx.el.span(
                title, class_name="text-xl font-book tracking-tight sm:text-2xl"
            ),
            rx.el.span(
                "Enterprise-only",
                class_name="rounded-full border border-border bg-muted px-2 py-0.5 text-xs font-normal tracking-normal text-muted-foreground",
            )
            if value == "auth"
            else None,
            class_name="flex flex-wrap items-center gap-3",
        ),
        rx.el.span(description, class_name="docs-framework-tab-description"),
        value=value,
        aria_label=title,
        unstyled=True,
        class_name="docs-framework-tab w-full text-left text-foreground focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
    )


def framework_panel(
    value: str, caption: str, link: str, href: str, tone: str
) -> rx.Component:
    """Pair an interactive example or illustration with its documentation link."""
    return ui.tabs.panel(
        rx.el.div(
            live_counter_diagram()
            if value == "how"
            else artwork(f"framework_{value}", class_name="docs-framework-diagram"),
            class_name="docs-framework-stage",
        ),
        rx.el.div(
            rx.el.p(caption, class_name="text-base font-book text-foreground"),
            rx.el.a(
                link,
                rx.icon("arrow-right", class_name="size-4", aria_hidden=True),
                href=href,
                class_name="inline-flex min-h-10 w-fit items-center gap-2 rounded-full border border-border bg-background px-4 text-sm font-book text-foreground transition-colors hover:border-border-strong focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
            ),
            class_name="docs-framework-caption flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-border bg-muted px-6 py-5 sm:px-8",
        ),
        value=value,
        unstyled=True,
        custom_attrs={"data-tone": tone},
        class_name="docs-framework-panel min-w-0 overflow-hidden rounded-panel border border-border-subtle",
    )


def framework() -> rx.Component:
    """Explore framework capabilities through tabs and product diagrams."""
    return rx.el.section(
        ui.tabs.root(
            rx.el.div(
                rx.el.div(
                    rx.el.h2(
                        "Framework",
                        id="docs-framework-title",
                        class_name="text-foreground text-3xl font-book tracking-tight",
                    ),
                    rx.el.p(
                        "Learn how to build applications with Reflex Framework.",
                        class_name="text-muted-foreground text-sm font-normal",
                    ),
                    class_name="flex flex-col gap-4",
                ),
                ui.tabs.list(
                    *[
                        framework_tab(value, title, description)
                        for value, title, description, *_ in CAPABILITIES
                    ],
                    activate_on_focus=True,
                    aria_label="Framework capabilities",
                    unstyled=True,
                    class_name="docs-framework-tabs flex min-w-0 flex-col w-full",
                ),
                class_name="docs-framework-navigation flex min-w-0 flex-col gap-6",
            ),
            rx.el.div(
                *[
                    framework_panel(value, caption, link, href, tone)
                    for value, _, _, caption, link, href, tone in CAPABILITIES
                ],
                class_name="min-w-0",
            ),
            default_value="how",
            orientation="vertical",
            unstyled=True,
            class_name="grid grid-cols-1 items-center gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] lg:gap-12",
        ),
        aria_labelledby="docs-framework-title",
        class_name="docs-framework-section flex flex-col gap-10 max-w-(--landing-layout-max-width) mx-auto w-full lg:pt-24 pt-10 lg:mb-24 mb-10 max-xl:px-6",
    )
