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
    enteprise_only: bool = False,
) -> rx.Component:
    return rx.el.div(
        rx.el.span(
            "Enterprise-only",
            class_name="text-secondary-12 text-xs font-medium bg-secondary-1 px-2.5 h-7 absolute top-0 right-0 border-b border-l rounded-bl-lg border-secondary-4 flex justify-center items-center",
        )
        if enteprise_only
        else None,
        rx.el.div(
            rx.el.span(
                title,
                class_name="text-secondary-12 text-xl font-book tracking-tight",
            ),
            rx.el.span(
                description,
                class_name="text-secondary-11 text-sm font-normal",
            ),
            class_name="flex flex-col gap-2 p-8",
        ),
        content,
        rx.el.a(
            href=href,
            aria_label=title,
            class_name="absolute inset-0 rounded-card focus-visible:outline-2 focus-visible:-outline-offset-4 focus-visible:outline-primary-9",
        ),
        class_name="docs-resource-card flex flex-col bg-background rounded-card border border-border-subtle relative transition-colors hover:border-border-strong overflow-hidden",
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
            class_name="size-full",
        ),
        ui.avatar.fallback(
            integration_name[0],
            class_name="text-secondary-12 text-base font-semibold uppercase size-full",
            unstyled=True,
        ),
        unstyled=True,
        class_name="size-6.5 flex items-center justify-center mx-3",
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
            gradient_color="var(--background)",
            class_name="h-auto w-full overflow-hidden",
            gradient_width=65,
            speed=25,
            pause_on_hover=False,
        ),
        marquee(
            *[integration_icon_marquee(name) for name in integration_names],
            direction="right",
            gradient_color="var(--background)",
            class_name="h-auto w-full overflow-hidden",
            gradient_width=65,
            speed=25,
            pause_on_hover=False,
        ),
        class_name="flex flex-col gap-6.5 px-8 mt-auto py-8",
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
                        "getting_started_illustration",
                        "w-full mt-auto py-8",
                    ),
                    href=ai_builder_pages.overview.best_practices.path,
                ),
                card(
                    title="Integrations",
                    description="Easily connect with the tools your team already uses or extend your app with any Python SDK, library, or API.",
                    content=integrations_marquee(),
                    href=ai_builder_pages.integrations.overview.path,
                ),
                card(
                    title="MCP",
                    description="The Reflex Model Context Protocol (MCP) provides AI assistants and coding tools with structured access to Reflex documentation and component information.",
                    content=artwork(
                        "mcp_illustration",
                        "w-full mt-auto py-8",
                    ),
                    href=ai_builder_pages.integrations.mcp_overview.path,
                    enteprise_only=True,
                ),
                class_name="grid grid-cols-1 lg:grid-cols-3 gap-6",
            ),
            class_name="flex flex-col gap-10 max-lg:text-center relative max-w-(--landing-layout-max-width) mx-auto",
        ),
        class_name="bg-muted w-full lg:pt-24 lg:pb-24 pb-10 max-xl:px-6 max-lg:pt-10",
    )
