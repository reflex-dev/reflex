"""Choose a workflow for building Reflex apps with AI."""

import reflex as rx
import reflex_components_internal as ui

from reflex_docs.pages.docs import ai_builder
from reflex_docs.templates.docpage import docpage, h1_comp, text_comp_2


def _agent_logos() -> rx.Component:
    """Group the coding-agent marks at a consistent size."""
    return rx.el.div(
        *[
            rx.image(
                src=rx.asset(f"agent-logos/{filename}.svg"),
                alt=label,
                title=label,
                class_name="size-5 shrink-0 object-contain"
                + (" dark:invert" if filename != "claude-code" else ""),
            )
            for filename, label in (
                ("claude-code", "Claude Code"),
                ("codex", "Codex"),
                ("cursor", "Cursor"),
            )
        ],
        class_name="docs-agent-logos flex items-center gap-4",
    )


def _workflow_preview(icon: rx.Component, labels: tuple[str, ...]) -> rx.Component:
    """Illustrate the tools available in each workflow."""
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                icon,
                ui.icon(
                    "MoreHorizontalIcon", size=20, class_name="text-subtle-foreground"
                ),
                class_name="flex items-center justify-between border-b border-border px-5 py-4",
            ),
            rx.el.div(
                *[
                    rx.el.div(
                        ui.icon(symbol, size=16, class_name="text-[var(--ai-accent)]"),
                        rx.el.span(label, class_name="text-sm text-foreground"),
                        class_name="flex items-center gap-3 rounded-sm bg-[var(--ai-tint)] px-4 py-3",
                    )
                    for symbol, label in zip(
                        ("Message01Icon", "Layout02Icon", "Layers01Icon"),
                        labels,
                        strict=True,
                    )
                ],
                class_name="flex flex-col gap-2 p-4",
            ),
            class_name="w-full max-w-xs overflow-hidden rounded-xl border border-border bg-background",
        ),
        aria_hidden=True,
        class_name="docs-workflow-preview flex items-center justify-center p-7 sm:p-9",
    )


def _workflow_card(
    title: str,
    description: str,
    action: str,
    href: str,
    tone: str,
    preview: rx.Component,
    recommended: bool = False,
) -> rx.Component:
    """Present one native link with a visual summary and clear destination."""
    return rx.el.a(
        preview,
        rx.el.div(
            rx.el.div(
                rx.el.h2(
                    title,
                    class_name="text-2xl font-book tracking-tight text-foreground",
                ),
                rx.el.span(
                    "Recommended",
                    class_name="rounded-full bg-foreground px-2.5 py-1 text-xs font-book leading-4 text-background",
                )
                if recommended
                else rx.fragment(),
                class_name="flex flex-wrap items-center gap-x-3 gap-y-2",
            ),
            rx.el.p(
                description, class_name="mt-3 text-base leading-7 text-muted-foreground"
            ),
            rx.el.div(
                action,
                ui.icon("ArrowRight01Icon", size=16, aria_hidden=True),
                class_name="mt-auto flex items-center gap-2 pt-7 text-sm font-book text-foreground",
            ),
            class_name="flex flex-1 flex-col border-t border-border bg-background p-6 sm:p-8",
        ),
        href=href,
        aria_label=title,
        aria_description="Recommended way to build Reflex apps"
        if recommended
        else None,
        custom_attrs={"data-tone": tone},
        class_name="docs-ai-workflow-card docs-ai-card flex min-w-0 flex-col overflow-hidden rounded-panel border border-border shadow-small dark:shadow-none transition-colors hover:border-border-strong focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
    )


@docpage(
    set_path="/ai/",
    t="Build with AI",
    right_sidebar=False,
    show_breadcrumb=False,
    description="Build in your browser with Reflex Build, or use Agent Toolkit with your own coding agent.",
)
def ai_landing() -> rx.Component:
    """Offer both AI workflows within the shared documentation layout."""
    return rx.el.section(
        h1_comp(text="Build with AI"),
        text_comp_2(
            text="Use Reflex's integrated builder or work with your own coding agent.",
        ),
        rx.el.div(
            _workflow_card(
                "Use Reflex Build",
                "The most powerful way to build Reflex apps. Bring AI generation, live previews, testing, integrations, and deployment together in one workspace.",
                "Explore Reflex Build",
                ai_builder.overview.what_is_reflex_build.path,
                "blue",
                _workflow_preview(
                    rx.image(src=rx.asset("favicon.svg"), alt="", class_name="size-5"),
                    (
                        "Plan and build with AI",
                        "Preview and test your app",
                        "Connect data and deploy",
                    ),
                ),
                recommended=True,
            ),
            _workflow_card(
                "Bring your own agent",
                "Give your preferred coding agent Reflex documentation, skills, and tools with Agent Toolkit.",
                "Explore Agent Toolkit",
                ai_builder.integrations.agent_toolkit.path,
                "mint",
                _workflow_preview(
                    _agent_logos(),
                    ("Documentation for agents", "Reflex skills", "MCP tools"),
                ),
            ),
            class_name="mt-10 grid grid-cols-1 gap-6 md:grid-cols-2",
        ),
        aria_label="Choose your AI workflow",
        class_name="docs-ai-overview min-w-0 pb-8",
    )
