"""Logic for the sidebar component."""

from __future__ import annotations

import reflex as rx
import reflex_components_internal as ui
from reflex_site_shared.styles.colors import c_color

from .sidebar_items.ai import (
    ai_builder_integrations,
    ai_builder_overview_items,
    ai_onboarding_items,
    mcp_items,
    skills_items,
)
from .sidebar_items.component_lib import component_lib, graphing_libs, html_lib
from .sidebar_items.enterprise import (
    enterprise_component_items,
    enterprise_items,
    enterprise_usage_items,
)
from .sidebar_items.learn import backend, cli_ref, frontend, hosting, learn
from .sidebar_items.recipes import recipes
from .sidebar_items.reference import api_reference
from .state import SideBarBase, SideBarItem

SIDEBAR_ICON_MAP = {
    "Getting Started": "rocket",
    "Tutorials": "graduation-cap",
    "Advanced Onboarding": "newspaper",
    "Components": "layers",
    "Pages": "sticky-note",
    "Styling": "palette",
    "Assets": "folder-open-dot",
    "Wrapping React": "atom",
    "Vars": "variable",
    "Events": "arrow-left-right",
    "State Structure": "boxes",
    "API Routes": "route",
    "Client Storage": "package-open",
    "Database": "database",
    "Authentication": "lock-keyhole",
    "Utility Methods": "cog",
    "Deploy Quick Start": "earth",
    "CLI Reference": "square-terminal",
    "App": "blocks",
    "Project": "server",
    "Self Hosting": "server",
    "Custom Components": "blocks",
    "Usage": "chart-column",
}

Scrollable_SideBar = """
function scrollToActiveSidebarLink() {
  const sidebarContainer = document.getElementById('sidebar-container');
  if (!sidebarContainer) return;

  const currentPath = window.location.pathname.replace(/\\/+$|\\/$/g, "") + "/";
  const baseComponentPath = currentPath.replace(/\\/low\\/$/, "/");
  const baseComponentPathWithoutDocs = baseComponentPath.replace(/^\\/docs\\//, "/");

  const activeLink = sidebarContainer.querySelector(`a[href="${currentPath}"]`) ||
                    sidebarContainer.querySelector(`a[href="${currentPath.slice(0, -1)}"]`) ||
                    sidebarContainer.querySelector(`a[href="${baseComponentPath}"]`) ||
                    sidebarContainer.querySelector(`a[href="${baseComponentPath.slice(0, -1)}"]`) ||
                    sidebarContainer.querySelector(`a[href="${baseComponentPathWithoutDocs}"]`) ||
                    sidebarContainer.querySelector(`a[href="${baseComponentPathWithoutDocs.slice(0, -1)}"]`);

  if (activeLink) {
    // Get the scrollable parent within the sidebar
    const scrollableParent = activeLink.closest('[class*="overflow-y-scroll"]') || sidebarContainer;
    const linkRect = activeLink.getBoundingClientRect();
    const containerRect = scrollableParent.getBoundingClientRect();

    // Calculate the scroll position to center the link
    const scrollTop = scrollableParent.scrollTop + (linkRect.top - containerRect.top) - (containerRect.height / 2) + (linkRect.height / 2);

    scrollableParent.scrollTo({
      top: scrollTop,
      behavior: 'instant'
    });
  }
}

setTimeout(scrollToActiveSidebarLink, 100);

window.addEventListener("popstate", () => {
  setTimeout(scrollToActiveSidebarLink, 100);
});

document.addEventListener('click', (e) => {
  const link = e.target.closest('#sidebar-container a[href]');
  if (link && !link.getAttribute('href')?.startsWith('http')) {
    setTimeout(scrollToActiveSidebarLink, 200);
  }
});
"""


def sidebar_link(*children, **props):
    """Create a sidebar link."""
    return rx.link(
        *children,
        underline="none",
        **props,
    )


def sidebar_leaf_guide(is_active: bool) -> rx.Component:
    """Render the active sidebar leaf guide segment."""
    return (
        rx.el.div(
            class_name="absolute left-0 -top-1 -bottom-1 w-px bg-primary-10 pointer-events-none",
        )
        if is_active
        else rx.fragment()
    )


def sidebar_leaf(
    item_index: str,
    item: SideBarItem,
    url: str,
    guide_margin_class: str = "ml-[3rem]",
) -> rx.Component:
    """Get the leaf node of the sidebar."""
    item.link = item.link.replace("_", "-").rstrip("/") + "/"
    is_active = item.link == url
    if item.outer:
        return rx.el.li(
            sidebar_link(
                rx.flex(
                    rx.text(
                        item.names,
                        color=c_color("violet", 9)
                        if is_active
                        else c_color("slate", 9),
                        _hover={
                            "color": c_color("slate", 11),
                        },
                        margin="0.5em 0.5em 0.2em 0.5em",
                        width="100%",
                        class_name="m-0 transition-color",
                    ),
                ),
                href=item.link,
                class_name="block w-full",
            ),
            class_name="m-0 p-0 !overflow-visible w-full list-none",
        )

    active_background = (
        [
            rx.el.div(
                class_name="absolute left-0 top-1/2 -translate-y-1/2 w-full h-8 rounded-lg bg-m-slate-2 dark:bg-slate-3 z-[-1]",
            )
        ]
        if is_active
        else []
    )
    return rx.el.li(
        sidebar_link(
            *active_background,
            rx.flex(
                sidebar_leaf_guide(is_active),
                rx.text(
                    item.names,
                    class_name=(
                        "m-0 text-sm text-primary-10 font-[525] transition-color pl-4"
                        if is_active
                        else "m-0 text-sm text-secondary-11 hover:text-secondary-12 transition-color w-full font-[525]"
                    ),
                ),
                class_name=(
                    f"relative {guide_margin_class} max-w-[14rem] h-8 flex items-center"
                    if is_active
                    else "relative pl-4 h-8 flex items-center"
                ),
            ),
            href=item.link,
            class_name=(
                "block w-full relative"
                if is_active
                else f"block w-full {guide_margin_class}"
            ),
        ),
        class_name="m-0 p-0 !overflow-visible w-full relative list-none",
    )


def sidebar_item_comp(
    item_index: str,
    item: SideBarItem,
    index: list[int],
    url: str,
    guide_margin_class: str = "ml-[3rem]",
):
    if not item.children:
        return sidebar_leaf(
            item_index=item_index,
            item=item,
            url=url,
            guide_margin_class=guide_margin_class,
        )

    is_open = bool(index) and item_index == f"index{index[0]}"
    nested_index = index[1:] if is_open else []
    child_guide_left_class = (
        "left-[3rem]" if has_sidebar_icon(item.names) else "left-[2.5rem]"
    )
    child_guide_margin_class = (
        "ml-[3rem]" if has_sidebar_icon(item.names) else "ml-[2.5rem]"
    )
    return rx.el.li(
        rx.el.details(
            rx.el.summary(
                sidebar_icon(item.names),
                rx.text(
                    item.names,
                    class_name="m-0 text-sm font-[525]",
                ),
                rx.box(class_name="flex-grow"),
                ui.icon(
                    "ArrowDown01Icon",
                    class_name="size-4 group-open/details:rotate-180 transition-transform",
                ),
                class_name="!px-0 m-0 flex items-center justify-start !ml-[2.5rem] !bg-transparent !hover:bg-transparent !py-1 !pr-0 w-[calc(100%-2.5rem)] !text-m-slate-7 hover:!text-m-slate-11 dark:hover:!text-m-slate-5 dark:!text-m-slate-6 transition-color group xl:max-w-[14rem] cursor-pointer list-none [&::-webkit-details-marker]:hidden [&::marker]:hidden",
            ),
            rx.el.ul(
                rx.el.li(
                    class_name=f"m-0 p-0 absolute {child_guide_left_class} top-0 bottom-0 w-px bg-m-slate-4 dark:bg-m-slate-9 z-[-1] pointer-events-none !rounded-none list-none",
                ),
                *[
                    sidebar_item_comp(
                        item_index="index" + str(child_index),
                        item=child,
                        index=nested_index,
                        url=url,
                        guide_margin_class=child_guide_margin_class,
                    )
                    for child_index, child in enumerate(item.children)
                ],
                class_name="!my-1 p-0 flex flex-col items-start gap-1 list-none !bg-transparent !rounded-none !shadow-none relative",
            ),
            open=is_open,
            class_name="group/details m-0 p-0 w-full !bg-transparent border-none",
        ),
        class_name="m-0 p-0 border-none w-full !bg-transparent list-none",
    )


def has_sidebar_icon(name):
    return name in SIDEBAR_ICON_MAP


def sidebar_icon(name):
    return (
        rx.icon(tag=SIDEBAR_ICON_MAP.get(name), size=16, class_name="mr-4")
        if has_sidebar_icon(name)
        else rx.fragment()
    )


def calculate_index(sidebar_items, url: str) -> list[int]:
    sidebar_items = (
        sidebar_items if isinstance(sidebar_items, list) else [sidebar_items]
    )
    index_list = []

    if not url:
        return index_list

    url = url.rstrip("/") + "/"
    for item in sidebar_items:
        item.link = item.link.rstrip("/") + "/"
    sub = 0
    for i, item in enumerate(sidebar_items):
        if not item.children:
            sub += 1
        if item.link == url:
            return [i - sub]
        index = calculate_index(item.children, url)
        if index:
            return [i - sub, *index]

    return index_list


def append_to_items(items, flat_items):
    for item in items:
        if not item.children:
            flat_items.append(item)
        append_to_items(item.children, flat_items)


flat_items = []
append_to_items(
    learn
    + frontend
    + backend
    + hosting
    + component_lib
    + graphing_libs
    + html_lib
    + recipes
    + ai_builder_overview_items
    + ai_builder_integrations
    + ai_onboarding_items
    + mcp_items
    + skills_items
    + api_reference
    + enterprise_items,
    flat_items,
)


def get_prev_next(url):
    """Get the previous and next links in the sidebar."""
    url = url.strip("/")
    for i, item in enumerate(flat_items):
        if item.link.strip("/") == url:
            prev_link = flat_items[i - 1] if i > 0 else None
            next_link = flat_items[i + 1] if i < len(flat_items) - 1 else None
            return prev_link, next_link
    return None, None


def filter_out_non_sidebar_items(items: list[SideBarBase]) -> list[SideBarItem]:
    """Filter out non-sidebar items making sure only SideBarItems are present.

    Args:
        items: The items to filter.

    Return:
        The filtered side bar items.
    """
    return [item for item in items if isinstance(item, SideBarItem)]


def sidebar_category(name: str, url: str, icon: str, active: bool):
    active_background = (
        [
            rx.el.div(
                class_name="absolute left-0 top-1/2 -translate-y-1/2 w-full h-8 rounded-lg bg-m-slate-2 dark:bg-slate-3 z-[-1]",
            )
        ]
        if active
        else []
    )
    return rx.el.li(
        rx.link(
            *active_background,
            rx.box(
                rx.icon(
                    tag=icon,
                    size=16,
                ),
                rx.el.h3(
                    name,
                    class_name="m-0 w-full font-[525]",
                ),
                class_name=ui.cn(
                    "cursor-pointer flex flex-row justify-start items-center gap-2.5 ml-[3rem] text-sm text-secondary-11 hover:text-secondary-12 h-8",
                    "text-slate-12" if active else "",
                ),
            ),
            href=url,
            underline="none",
            class_name="block w-full relative no-underline",
            custom_attrs={"aria-label": f"Navigate to {name}"},
        ),
        class_name="m-0 p-0 w-full relative list-none",
    )


def create_sidebar_section(
    section_title: str,
    section_url: str,
    items: list[SideBarItem],
    index: list[int],
    url: str,
    connected_line: bool = False,
) -> rx.Component:
    return rx.el.li(
        rx.link(
            rx.el.h2(
                section_title,
                class_name="m-0 font-mono text-m-slate-12 dark:text-m-slate-3 hover:text-primary-10 dark:hover:text-primary-9 uppercase text-[0.8125rem] leading-6 font-medium",
            ),
            underline="none",
            href=section_url,
            class_name="h-8 mb-2 flex items-center justify-start ml-[2.5rem]",
        ),
        rx.el.ul(
            *[
                sidebar_item_comp(
                    item_index="index" + str(item_index),
                    item=item,
                    index=index,
                    url=url,
                )
                for item_index, item in enumerate(items)
            ],
            class_name=ui.cn(
                "m-0 ml-0 p-0 pl-0 w-full !bg-transparent !shadow-none rounded-[0px] flex flex-col list-none",
                "gap-0" if connected_line else "gap-1",
            ),
        ),
        class_name="m-0 p-0 flex flex-col items-start ml-0 w-full list-none",
    )


def normalize_url(url: str | None) -> str:
    """Normalize a docs route for static sidebar selection."""
    if not url:
        return "/"
    path = str(url).split("#", 1)[0].split("?", 1)[0]
    if not path.startswith("/"):
        path = f"/{path}"
    path = path.rstrip("/")
    if path == "/docs":
        path = "/"
    elif path.startswith("/docs/"):
        path = path.removeprefix("/docs")
    if path.startswith("/library/") and path.endswith("/low"):
        path = path.removesuffix("/low")
    return path.rstrip("/") + "/"


def sidebar_comp(
    url: str,
    learn_index: list[int],
    component_lib_index: list[int],
    frontend_index: list[int],
    backend_index: list[int],
    hosting_index: list[int],
    html_lib_index: list[int],
    graphing_libs_index: list[int],
    api_reference_index: list[int],
    recipes_index: list[int],
    enterprise_usage_index: list[int],
    enterprise_component_index: list[int],
    ai_onboarding_index: list[int],
    mcp_index: list[int],
    skills_index: list[int],
    #
    cli_ref_index: list[int],
    ai_builder_overview_index: list[int],
    ai_builder_integrations_index: list[int],
    width: str = "100%",
):
    from reflex_docs.pages.docs import ai_builder as ai_builder_pages
    from reflex_docs.pages.docs import enterprise, getting_started, state, ui
    from reflex_docs.pages.docs import hosting as hosting_page
    from reflex_docs.pages.docs.apiref import pages
    from reflex_docs.pages.docs.custom_components import custom_components
    from reflex_docs.pages.docs.library import library
    from reflex_docs.pages.docs.recipes_overview import overview

    path = normalize_url(url)
    is_docs_hosting = path.startswith("/hosting/")
    is_docs_ai_builder = path.startswith("/ai/")
    is_ai_mcp_or_skills = path.startswith((
        "/ai/integrations/ai-onboarding/",
        "/ai/integrations/skills/",
        "/ai/integrations/agents-md/",
        "/ai/integrations/mcp",
    ))

    ai_category = 1 if is_ai_mcp_or_skills else 0
    docs_category = 0
    if "library" in path or "/mcp-" in path:
        docs_category = 1
    elif "api-reference" in path:
        docs_category = 2
    elif "enterprise" in path:
        docs_category = 3

    if is_docs_hosting:
        categories = rx.el.ul(
            sidebar_category(
                "Cloud",
                hosting_page.deploy_quick_start.path,
                "cloud",
                True,
            ),
            class_name="flex flex-col items-start gap-2 w-full list-none",
        )
        content = rx.el.ul(
            create_sidebar_section(
                "Cloud",
                hosting_page.deploy_quick_start.path,
                hosting,
                hosting_index,
                url,
            ),
            class_name="m-0 p-0 flex flex-col items-start gap-8  w-full list-none list-style-none",
        )
    elif is_docs_ai_builder:
        categories = rx.el.ul(
            sidebar_category(
                "AI Builder",
                ai_builder_pages.overview.best_practices.path,
                "bot",
                ai_category == 0,
            ),
            sidebar_category(
                "MCP/Skills",
                ai_builder_pages.integrations.ai_onboarding.path,
                "plug",
                ai_category == 1,
            ),
            class_name="flex flex-col items-start gap-2 w-full list-none",
        )
        content = (
            rx.el.ul(
                create_sidebar_section(
                    "Overview",
                    ai_builder_pages.integrations.ai_onboarding.path,
                    ai_onboarding_items,
                    ai_onboarding_index,
                    url,
                ),
                create_sidebar_section(
                    "MCP",
                    ai_builder_pages.integrations.mcp_overview.path,
                    mcp_items,
                    mcp_index,
                    url,
                    connected_line=True,
                ),
                create_sidebar_section(
                    "Skills",
                    ai_builder_pages.integrations.skills.path,
                    skills_items,
                    skills_index,
                    url,
                    connected_line=True,
                ),
                class_name="m-0 p-0 flex flex-col items-start gap-8  w-full list-none list-style-none",
            )
            if ai_category == 1
            else rx.el.ul(
                create_sidebar_section(
                    "Overview",
                    ai_builder_pages.overview.best_practices.path,
                    ai_builder_overview_items,
                    ai_builder_overview_index,
                    url,
                ),
                create_sidebar_section(
                    "Integrations",
                    ai_builder_pages.integrations.overview.path,
                    ai_builder_integrations,
                    ai_builder_integrations_index,
                    url,
                ),
                class_name="m-0 p-0 flex flex-col items-start gap-8  w-full list-none list-style-none",
            )
        )
    else:
        categories = rx.el.ul(
            sidebar_category(
                "Learn",
                getting_started.introduction.path,
                "graduation-cap",
                docs_category == 0,
            ),
            sidebar_category(
                "Components",
                library.path,
                "layout-panel-left",
                docs_category == 1,
            ),
            sidebar_category(
                "API Reference",
                pages[0].path,
                "book-text",
                docs_category == 2,
            ),
            sidebar_category(
                "Enterprise",
                enterprise.overview.path,
                "building-2",
                docs_category == 3,
            ),
            class_name="flex flex-col items-start gap-2 w-full list-none",
        )
        if docs_category == 1:
            content = rx.el.ul(
                create_sidebar_section(
                    "Core",
                    library.path,
                    component_lib,
                    component_lib_index,
                    url,
                ),
                create_sidebar_section(
                    "Graphing",
                    library.path,
                    graphing_libs,
                    graphing_libs_index,
                    url,
                ),
                create_sidebar_section(
                    "Other",
                    "/library/html/",
                    html_lib,
                    html_lib_index,
                    url,
                ),
                rx.link(  # pyright: ignore [reportCallIssue]
                    rx.box(  # pyright: ignore [reportCallIssue]
                        rx.box(  # pyright: ignore [reportCallIssue]
                            rx.icon("atom", size=16),  # pyright: ignore [reportCallIssue]
                            rx.el.h5(
                                "Custom Components",
                                class_name="font-smbold text-[0.875rem] text-slate-12 leading-5 tracking-[-0.01313rem] transition-color",
                            ),
                            class_name="flex flex-row items-center gap-3 text-slate-12",
                        ),
                        rx.text(  # pyright: ignore [reportCallIssue]
                            "See what components people have made with Reflex!",
                            class_name="font-small text-slate-9",
                        ),
                        class_name="flex flex-col gap-2 border-slate-5 bg-slate-1 hover:bg-slate-3 shadow-large px-3.5 py-2 border rounded-xl transition-bg",
                    ),
                    underline="none",
                    href=custom_components.path,
                    class_name="w-fit lg:ml-[2.5rem]",
                ),
                class_name="m-0 p-0 flex flex-col items-start gap-8  w-full list-none list-style-none",
            )
        elif docs_category == 2:
            content = rx.el.ul(
                create_sidebar_section(
                    "Reference",
                    pages[0].path,
                    api_reference,
                    api_reference_index,
                    url,
                ),
                class_name="m-0 p-0 flex flex-col items-start gap-8  w-full list-none list-style-none",
            )
        elif docs_category == 3:
            content = rx.el.ul(
                create_sidebar_section(
                    "Enterprise Usage",
                    enterprise.overview.path,
                    enterprise_usage_items,
                    enterprise_usage_index,
                    url,
                ),
                create_sidebar_section(
                    "Components",
                    enterprise.components.path,
                    enterprise_component_items,
                    enterprise_component_index,
                    url,
                ),
                class_name="m-0 p-0 flex flex-col items-start gap-8  w-full list-none list-style-none",
            )
        else:
            content = rx.el.ul(
                create_sidebar_section(
                    "Onboarding",
                    getting_started.introduction.path,
                    learn,
                    learn_index,
                    url,
                ),
                create_sidebar_section(
                    "User Interface",
                    ui.overview.path,
                    filter_out_non_sidebar_items(frontend),
                    frontend_index,
                    url,
                ),
                create_sidebar_section(
                    "State",
                    state.overview.path,
                    filter_out_non_sidebar_items(backend),
                    backend_index,
                    url,
                ),
                create_sidebar_section(
                    "Recipes",
                    overview.path,
                    recipes,
                    recipes_index,
                    url,
                ),
                class_name="m-0 p-0 flex flex-col items-start gap-8  w-full list-none list-style-none",
            )

    return rx.box(  # pyright: ignore [reportCallIssue]
        categories,
        content,
        style={
            "&::-webkit-scrollbar-thumb": {
                "background_color": "transparent",
            },
            "&::-webkit-scrollbar": {
                "background_color": "transparent",
            },
        },
        class_name="flex flex-col pb-24 gap-8 items-start h-full pt-8 pr-4 scroll-p-4 overflow-y-scroll overflow-x-hidden hidden-scrollbar w-full 3xl:pl-0 pl-6",
    )


def sidebar(url=None, width: str = "100%") -> rx.Component:
    """Render the sidebar."""
    normalized_url = normalize_url(url)
    learn_index = calculate_index(learn, normalized_url)
    component_lib_index = calculate_index(component_lib, normalized_url)
    frontend_index = calculate_index(frontend, normalized_url)
    backend_index = calculate_index(backend, normalized_url)
    hosting_index = calculate_index(hosting, normalized_url)
    html_lib_index = calculate_index(html_lib, normalized_url)
    graphing_libs_index = calculate_index(graphing_libs, normalized_url)
    api_reference_index = calculate_index(api_reference, normalized_url)
    recipes_index = calculate_index(recipes, normalized_url)
    enterprise_usage_index = calculate_index(enterprise_usage_items, normalized_url)
    enterprise_component_index = calculate_index(
        enterprise_component_items, normalized_url
    )

    cli_ref_index = calculate_index(cli_ref, normalized_url)
    ai_builder_overview_index = calculate_index(
        ai_builder_overview_items, normalized_url
    )
    ai_builder_integrations_index = calculate_index(
        ai_builder_integrations, normalized_url
    )
    ai_onboarding_index = calculate_index(ai_onboarding_items, normalized_url)
    mcp_index = calculate_index(mcp_items, normalized_url)
    skills_index = calculate_index(skills_items, normalized_url)

    return rx.box(
        sidebar_comp(
            url=normalized_url,
            learn_index=learn_index,
            component_lib_index=component_lib_index,
            frontend_index=frontend_index,
            backend_index=backend_index,
            hosting_index=hosting_index,
            html_lib_index=html_lib_index,
            graphing_libs_index=graphing_libs_index,
            api_reference_index=api_reference_index,
            recipes_index=recipes_index,
            enterprise_usage_index=enterprise_usage_index,
            enterprise_component_index=enterprise_component_index,
            ai_onboarding_index=ai_onboarding_index,
            ai_builder_overview_index=ai_builder_overview_index,
            ai_builder_integrations_index=ai_builder_integrations_index,
            cli_ref_index=cli_ref_index,
            mcp_index=mcp_index,
            skills_index=skills_index,
            width=width,
        ),
        on_mount=rx.call_script(Scrollable_SideBar),
        id=rx.Var.create("sidebar-container"),
        class_name="flex justify-end w-full h-full",
    )
