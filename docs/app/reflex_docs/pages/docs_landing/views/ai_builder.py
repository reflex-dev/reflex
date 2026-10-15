import os

import frontmatter
import reflex as rx
import reflex_components_internal as ui
from reflex_site_shared.integrations import get_integration_logo_url

from reflex_docs.pages.docs import ai_builder as ai_builder_pages
from reflex_docs.pages.docs_landing.views.artwork import artwork
from reflex_docs.pages.docs_landing.views.layout import SECTION, section_heading
from reflex_docs.pages.docs_landing.views.mcp_artwork import mcp_artwork


def get_integration_path() -> list:
    from integrations_docs import DOCS_DIR

    base_dir = str(DOCS_DIR)
    web_path_prefix = "/ai/integrations"
    result = []

    exclude_files = [
        "mcp_installation",
        "mcp_overview",
        "overview",
        "skills",
        "snowflake",
    ]  # without .md extension

    for filename in os.listdir(base_dir):
        if filename.endswith(".md"):
            name_without_ext = filename[:-3]
            if name_without_ext in exclude_files:
                continue

            key = name_without_ext.lower()
            slug = key.replace("_", "-")
            file_path = os.path.join(base_dir, filename)

            with open(file_path, "r", encoding="utf-8") as f:
                post = frontmatter.load(f)

                # Handle tags as a string (get first tag, or empty)
                raw_tags = post.get("tags", [])
                if isinstance(raw_tags, list) and raw_tags:
                    tag = raw_tags[0]
                elif isinstance(raw_tags, str):
                    tag = raw_tags
                else:
                    tag = ""

                description = post.get("description", "").strip()
                title = key.replace("_", " ").title()

                if title == "Open Ai":
                    title = "Open AI"

            result.append({
                key: {
                    "path": f"{web_path_prefix}/{slug}",
                    "tags": tag,
                    "description": description,
                    "name": key,
                    "title": title,
                }
            })

    return result


def card(
    title: str,
    description: str,
    content: rx.Component,
    href: str,
    tone: str,
    enterprise_only: bool = False,
) -> rx.Component:
    """Render a linked guide with a matching editorial illustration panel."""
    return rx.el.a(
        rx.el.div(
            rx.el.div(content, class_name="flex w-full max-w-[18rem] justify-center"),
            class_name="hidden h-44 items-center justify-center overflow-hidden border-b border-border-subtle bg-muted px-6 sm:flex",
            aria_hidden=True,
        ),
        rx.el.div(
            rx.el.div(
                rx.el.h3(
                    title,
                    class_name="font-heading text-2xl font-normal leading-8 tracking-[-0.025em]",
                ),
                rx.el.span(
                    "Enterprise-only",
                    class_name="w-fit rounded-full border border-border px-2.5 py-1 text-xs font-normal text-muted-foreground",
                )
                if enterprise_only
                else None,
                class_name="flex w-full flex-wrap items-center gap-x-3 gap-y-2 text-foreground",
            ),
            rx.el.p(
                description,
                class_name="text-sm font-normal leading-6 text-muted-foreground",
            ),
            rx.el.span(
                "Read the guide",
                ui.icon("ArrowRight01Icon", size=16, aria_hidden=True),
                class_name="mt-auto inline-flex items-center gap-2 pt-4 text-sm font-normal text-foreground",
            ),
            class_name="flex flex-1 flex-col items-start gap-3 p-6 sm:p-7",
        ),
        href=href,
        aria_label=title,
        data_tone=tone,
        style={"--ai-accent": "var(--foreground)", "--ai-tint": "var(--accent)"},
        class_name="group flex min-w-0 flex-col overflow-hidden rounded-[20px] border border-border-subtle bg-background text-left transition-colors hover:bg-muted hover:border-border motion-reduce:transition-none focus-visible:outline-2 focus-visible:-outline-offset-4 focus-visible:outline-ring",
    )


def integration_icon_marquee(integration_name: str) -> rx.Component:
    return ui.avatar.root(
        ui.avatar.image(
            src=rx.color_mode_cond(
                get_integration_logo_url(integration_name, "light"),
                get_integration_logo_url(integration_name, "dark"),
            ),
            alt=f"{integration_name} logo",
            unstyled=True,
            class_name="size-6 object-contain",
        ),
        ui.avatar.fallback(
            integration_name[0],
            class_name="text-foreground text-base font-normal uppercase size-full",
            unstyled=True,
        ),
        unstyled=True,
        class_name="flex aspect-square w-full items-center justify-center rounded-xl border border-border-subtle bg-background",
    )


@rx.memo
def integrations_marquee() -> rx.Component:
    """Show a quiet sample of integration marks without continuous motion.

    Returns:
        A decorative grid of supported integration logos.
    """
    integration_names = [
        next(iter(item.values()))["name"] for item in get_integration_path()
    ]
    return rx.el.div(
        *[integration_icon_marquee(name) for name in sorted(integration_names)[:8]],
        class_name="grid w-full max-w-[228px] grid-cols-4 gap-3",
    )


def ai_builder_section() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            section_heading(
                "AI Builder", "Learn how to build applications with Reflex AI."
            ),
            rx.el.div(
                card(
                    title="Getting Started",
                    description="A comprehensive guide to working effectively with AI Builder. The key to success is clarity, structure, and iteration.",
                    content=artwork(
                        "ai_getting_started",
                        "w-full",
                    ),
                    href=ai_builder_pages.overview.best_practices.path,
                    tone="blue",
                ),
                card(
                    title="Integrations",
                    description="Easily connect with the tools your team already uses or extend your app with any Python SDK, library, or API.",
                    content=integrations_marquee(),
                    href=ai_builder_pages.integrations.overview.path,
                    tone="peach",
                ),
                card(
                    title="MCP",
                    description="The Reflex Model Context Protocol (MCP) provides AI assistants and coding tools with structured access to Reflex documentation and component information.",
                    content=mcp_artwork(),
                    href=ai_builder_pages.integrations.mcp_overview.path,
                    tone="mint",
                    enterprise_only=True,
                ),
                class_name="grid grid-cols-1 gap-4 md:grid-cols-3",
            ),
            class_name=SECTION,
        ),
        class_name="w-full border-b border-border-subtle bg-background",
    )
