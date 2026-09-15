import os

import frontmatter
import reflex as rx
import reflex_components_internal as ui
from reflex_site_shared.components.marquee import marquee
from reflex_site_shared.integrations import get_integration_logo_url

from reflex_docs.pages.docs import ai_builder as ai_builder_pages
from reflex_docs.pages.docs_landing.views.artwork import artwork


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
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.h3(
                    title,
                    class_name="docs-ai-card-title text-xl font-book tracking-tight",
                ),
                rx.el.span(
                    "Enterprise-only",
                    class_name="w-fit rounded-full border border-border bg-muted px-2.5 py-1 text-xs text-muted-foreground",
                )
                if enterprise_only
                else None,
                rx.icon(
                    "arrow-up-right",
                    size=18,
                    aria_hidden=True,
                    class_name="ml-auto shrink-0",
                ),
                class_name="flex w-full items-center gap-3 text-foreground",
            ),
            rx.el.p(
                description,
                class_name="text-sm font-normal leading-6 text-muted-foreground",
            ),
            class_name="flex flex-1 flex-col items-start gap-3 p-7 sm:p-8",
        ),
        rx.el.div(content, class_name="docs-ai-card-art", aria_hidden=True),
        rx.el.a(
            href=href,
            aria_label=title,
            class_name="docs-ai-card-link absolute inset-0 rounded-panel focus-visible:outline-2 focus-visible:-outline-offset-4 focus-visible:outline-foreground",
        ),
        data_tone=tone,
        class_name="docs-ai-card flex min-w-0 flex-col overflow-hidden rounded-panel border border-border bg-background relative text-left transition-colors hover:border-border-strong",
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
            class_name="text-secondary-12 text-base font-semibold uppercase size-full",
            unstyled=True,
        ),
        unstyled=True,
        class_name="docs-ai-integration flex size-14 shrink-0 items-center justify-center rounded-xl border border-border bg-background mx-2",
    )


@rx.memo
def integrations_marquee() -> rx.Component:
    integration_names = [
        next(iter(item.values()))["name"] for item in get_integration_path()
    ]
    return rx.el.div(
        marquee(
            *[integration_icon_marquee(name) for name in reversed(integration_names)],
            direction="left",
            gradient=False,
            class_name="h-auto w-full overflow-hidden",
            speed=25,
            pause_on_hover=True,
        ),
        marquee(
            *[integration_icon_marquee(name) for name in integration_names],
            direction="right",
            gradient=False,
            class_name="h-auto w-full overflow-hidden",
            speed=25,
            pause_on_hover=True,
        ),
        class_name="docs-ai-integrations flex w-full flex-col gap-4",
    )


def ai_builder_section() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.div(
                rx.el.h2(
                    "AI Builder",
                    class_name="text-secondary-12 text-3xl font-book tracking-tight",
                ),
                rx.el.p(
                    "Learn how to build applications with Reflex AI.",
                    class_name="text-secondary-11 text-sm font-normal",
                ),
                class_name="flex flex-col gap-4",
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
                    content=artwork(
                        "ai_mcp",
                        "w-full",
                    ),
                    href=ai_builder_pages.integrations.mcp_overview.path,
                    tone="mint",
                    enterprise_only=True,
                ),
                class_name="grid grid-cols-1 lg:grid-cols-3 gap-6",
            ),
            class_name="flex flex-col gap-10 max-lg:text-center relative max-w-(--landing-layout-max-width) mx-auto",
        ),
        class_name="bg-muted w-full lg:pt-24 lg:pb-24 pb-10 max-xl:px-6 max-lg:pt-10",
    )
