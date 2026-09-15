"""Choose a workflow for building Reflex apps with AI."""

import reflex as rx

from reflex_docs.pages.docs import ai_builder
from reflex_docs.pages.docs_landing.views.artwork import artwork
from reflex_docs.views.docs_navbar import docs_navbar
from reflex_docs.views.editorial_footer import editorial_footer


def _workflow_preview(icon: rx.Component, labels: tuple[str, ...]) -> rx.Component:
    """Illustrate the tools available in each workflow."""
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                icon,
                rx.el.div(
                    *[
                        rx.el.span(
                            class_name="size-1 rounded-full bg-subtle-foreground"
                        )
                        for _ in range(3)
                    ],
                    class_name="flex gap-1",
                ),
                class_name="flex items-center justify-between border-b border-border px-5 py-4",
            ),
            rx.el.div(
                *[
                    rx.el.div(
                        rx.icon(symbol, size=16, class_name="text-[var(--fw-accent)]"),
                        rx.el.span(label, class_name="text-sm text-foreground"),
                        class_name="flex items-center gap-3 rounded-sm bg-[var(--fw-tint)] px-4 py-3",
                    )
                    for symbol, label in zip(
                        ("message-square", "panels-top-left", "layers"),
                        labels,
                        strict=True,
                    )
                ],
                class_name="flex flex-col gap-2 p-4",
            ),
            class_name="w-full max-w-xs overflow-hidden rounded-xl border border-border bg-background",
        ),
        aria_hidden=True,
        class_name="docs-framework-stage !p-7 sm:!p-9",
    )


def _workflow_card(
    title: str,
    description: str,
    action: str,
    href: str,
    tone: str,
    preview: rx.Component,
) -> rx.Component:
    """Present one native link with a visual summary and clear destination."""
    return rx.el.a(
        preview,
        rx.el.div(
            rx.el.h2(
                title, class_name="text-2xl font-book tracking-tight text-foreground"
            ),
            rx.el.p(
                description, class_name="mt-3 text-base leading-7 text-muted-foreground"
            ),
            rx.el.div(
                action,
                rx.icon("arrow-right", size=16, aria_hidden=True),
                class_name="mt-7 flex items-center gap-2 text-sm font-book text-foreground",
            ),
            class_name="flex-1 border-t border-border bg-background p-6 sm:p-8",
        ),
        href=href,
        aria_label=title,
        custom_attrs={"data-tone": tone},
        class_name="docs-ai-workflow-card docs-framework-panel flex min-w-0 flex-col overflow-hidden rounded-panel border border-border transition-colors hover:border-border-strong focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
    )


@rx.page(
    route="/ai/",
    title="Build with AI · Reflex Docs",
    description="Build in your browser with Reflex Build, or use Agent Toolkit with your own coding agent.",
)
def ai_landing() -> rx.Component:
    """Offer Reflex Build and Agent Toolkit as distinct documentation paths."""
    return rx.el.div(
        docs_navbar(),
        rx.el.main(
            rx.el.section(
                rx.el.a(
                    rx.icon("arrow-left", size=14, aria_hidden=True),
                    "Documentation",
                    href="/",
                    class_name="mb-7 inline-flex items-center gap-2 rounded-sm text-sm text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
                ),
                rx.el.h1(
                    "Build with AI",
                    class_name="text-4xl font-book leading-tight tracking-tight text-foreground sm:text-5xl",
                ),
                rx.el.p(
                    "Use Reflex's integrated builder or work with your own coding agent.",
                    class_name="mt-5 max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg",
                ),
                rx.el.div(
                    _workflow_card(
                        "Use Reflex Build",
                        "Create, preview, and deploy your app in the browser with an integrated AI agent.",
                        "Explore Reflex Build",
                        ai_builder.overview.what_is_reflex_build.path,
                        "lavender",
                        _workflow_preview(
                            artwork("reflex_mark", class_name="w-5"),
                            (
                                "Describe your app",
                                "Review the live preview",
                                "Deploy when you're ready",
                            ),
                        ),
                    ),
                    _workflow_card(
                        "Bring your own agent",
                        "Give your preferred coding agent Reflex documentation, skills, and tools with Agent Toolkit.",
                        "Explore Agent Toolkit",
                        ai_builder.integrations.agent_toolkit.path,
                        "mint",
                        _workflow_preview(
                            rx.icon("terminal", size=20, class_name="text-foreground"),
                            ("Documentation for agents", "Reflex skills", "MCP tools"),
                        ),
                    ),
                    class_name="mt-10 grid grid-cols-1 gap-6 md:grid-cols-2",
                ),
                aria_label="Choose your AI workflow",
                class_name="mx-auto w-full max-w-5xl px-6 pb-20 pt-[calc(var(--docs-header-height)+3rem)] sm:pb-24 sm:pt-[calc(var(--docs-header-height)+4rem)]",
            ),
        ),
        editorial_footer(),
        class_name="min-h-screen bg-background",
    )
