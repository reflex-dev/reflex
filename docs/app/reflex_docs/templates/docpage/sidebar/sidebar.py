"""Logic for the sidebar component."""

from __future__ import annotations

import reflex as rx
import reflex_components_internal as ui
from reflex_site_shared.styles.colors import c_color

from reflex_docs.templates.docpage.state import NavbarState

from .sidebar_items.ai import (
    ai_builder_integrations,
    ai_builder_overview_items,
    ai_onboarding_items,
    mcp_items,
    skills_items,
)
from .sidebar_items.component_lib import component_lib, graphing_libs
from .sidebar_items.enterprise import (
    enterprise_component_items,
    enterprise_items,
    enterprise_usage_items,
)
from .sidebar_items.learn import backend, cli_ref, frontend, hosting, learn
from .sidebar_items.recipes import recipes
from .sidebar_items.reference import api_reference
from .state import SideBarBase, SideBarItem, SidebarState

Scrollable_SideBar = """
function scrollToActiveSidebarLink() {
  const sidebarContainer = document.getElementById('sidebar-container');
  if (!sidebarContainer) return;

  const currentPath = window.location.pathname.replace(/\\/+$|\\/$/g, "") + "/";

  const activeLink = sidebarContainer.querySelector(`a[href="${currentPath}"]`) ||
                    sidebarContainer.querySelector(`a[href="${currentPath.slice(0, -1)}"]`);

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
    """Create a sidebar link that closes the sidebar when clicked."""
    return rx.link(
        *children,
        on_click=props.pop("on_click", NavbarState.set_sidebar_open(False)),
        underline="none",
        **props,
    )


def sidebar_leaf(
    item_index: str,
    item: SideBarItem,
    url: str,
) -> rx.Component:
    """Get the leaf node of the sidebar."""
    item.link = item.link.replace("_", "-").rstrip("/") + "/"
    return (
        rx.accordion.item(
            rx.accordion.header(
                sidebar_link(
                    rx.flex(
                        rx.text(
                            item.names,
                            color=rx.cond(
                                item.link == url,
                                c_color("violet", 9),
                                c_color("slate", 9),
                            ),
                            _hover={
                                "color": c_color("slate", 11),
                            },
                            margin="0.5em 0.5em 0.2em 0.5em",
                            width="100%",
                            class_name="transition-color",
                        ),
                    ),
                    href=item.link,
                ),
            ),
            value=item_index,
            border="none",
            width="100%",
            class_name="!overflow-visible",
        )
        if item.outer
        else rx.accordion.item(
            rx.accordion.header(
                rx.cond(
                    item.link == url,
                    sidebar_link(
                        rx.el.div(
                            class_name="absolute left-0 top-1/2 -translate-y-1/2 w-full h-8 rounded-lg bg-m-slate-2 dark:bg-m-slate-10 z-[-1]",
                        ),
                        rx.flex(
                            rx.text(
                                item.names,
                                class_name="text-sm text-primary-10 font-[525] transition-color pl-4",
                            ),
                            class_name="border-l-[1.5px] border-primary-10 relative ml-[2.5rem] max-w-[14rem] h-8 flex items-center",
                        ),
                        href=item.link,
                        class_name="w-full relative",
                    ),
                    sidebar_link(
                        rx.flex(
                            rx.text(
                                item.names,
                                class_name="text-sm text-secondary-11 hover:text-secondary-12 transition-color w-full font-[525]",
                            ),
                            class_name="border-l-[1.5px] border-m-slate-4 dark:border-m-slate-9 hover:border-m-slate-8 dark:hover:border-m-slate-5 pl-4 h-8 flex items-center",
                        ),
                        href=item.link,
                        class_name="w-full ml-[2.5rem]",
                    ),
                ),
            ),
            border="none",
            value=item_index,
            width="100%",
            class_name="!overflow-visible",
        )
    )


def sidebar_icon(name):
    icon_map = {
        "Getting Started": "rocket",
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

    return (
        rx.icon(tag=icon_map.get(name), size=16, class_name="mr-4")
        if name in icon_map
        else rx.fragment()
    )


def sidebar_item_comp(
    item_index: str,
    item: SideBarItem,
    index: list[int],
    url: str,
):
    index = rx.Var.create(index)
    return (
        sidebar_leaf(item_index=item_index, item=item, url=url)
        if not item.children
        else rx.accordion.item(
            rx.accordion.header(
                rx.accordion.trigger(
                    sidebar_icon(item.names),
                    rx.text(
                        item.names,
                        class_name="text-sm font-[525]",
                    ),
                    rx.box(class_name="flex-grow"),
                    ui.icon(
                        "ArrowDown01Icon",
                        class_name="size-4 group-data-[state=open]:rotate-180 transition-transform",
                    ),
                    class_name="!px-0 flex items-center !bg-transparent !hover:bg-transparent !py-1 !pr-0 w-full !text-m-slate-7 hover:!text-m-slate-11 dark:hover:!text-m-slate-5 dark:!text-m-slate-6 transition-color group xl:max-w-[14rem]",
                ),
                class_name="justify-start !ml-[2.5rem]",
            ),
            rx.accordion.content(
                rx.accordion.root(
                    rx.accordion.item(
                        class_name="absolute left-[2.5rem] size-full !shadow-[1.5px_0_0_0_var(--m-slate-4)_inset] dark:!shadow-[1.5px_0_0_0_var(--m-slate-9)_inset] z-[-1] pointer-events-none !rounded-none",
                    ),
                    *[
                        sidebar_item_comp(
                            item_index="index" + str(child_index),
                            item=child,
                            index=index[1:],
                            url=url,
                        )
                        for child_index, child in enumerate(item.children)
                    ],
                    type="multiple",
                    collapsible=True,
                    default_value=index[:1].foreach(lambda x: "index" + x.to_string()),
                    class_name="!my-1 flex flex-col items-start gap-1 list-none !bg-transparent !rounded-none !shadow-none relative",
                ),
                class_name="!p-0 w-full !bg-transparent before:!h-0 after:!h-0",
            ),
            value=item_index,
            class_name="border-none w-full !bg-transparent",
        )
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


def sidebar_category(name: str, url: str, icon: str, index: int):
    return rx.el.li(
        rx.el.div(
            rx.box(
                rx.box(
                    rx.icon(
                        tag=icon,
                        size=16,
                    ),
                    rx.el.h3(
                        name,
                        class_name=ui.cn(
                            "w-full font-[525]",
                        ),
                    ),
                    class_name=ui.cn(
                        "flex flex-row justify-start items-center gap-2.5 w-full text-sm text-secondary-11 hover:text-secondary-12 h-8",
                        rx.cond(
                            SidebarState.sidebar_index == index,
                            "text-primary-10 dark:text-primary-9",
                            "",
                        ),
                    ),
                ),
                class_name="cursor-pointer flex flex-row items-center gap-2.5",
            ),
            rx.cond(
                SidebarState.sidebar_index == index,
                rx.el.div(
                    class_name="absolute left-0 top-0 w-full h-full bg-m-slate-2 dark:bg-m-slate-10 rounded-lg z-[-1]",
                ),
            ),
            rx.el.a(
                to=url,
                on_click=rx.prevent_default,
                class_name="inset-0 absolute z-[-1]",
                aria_label=f"Navigate to {name}",
            ),
            class_name="w-full",
            on_click=[SidebarState.set_sidebar_index(index), rx.redirect(url)],
        ),
        class_name="w-full pl-[2.5rem] relative",
    )


def create_sidebar_section(
    section_title: str,
    section_url: str,
    items: list[SideBarItem],
    index: rx.Var[list[str]] | list[str],
    url: rx.Var[str] | str,
    connected_line: bool = False,
) -> rx.Component:
    # Check if the section has any nested sections (Like the Other Libraries Section)
    nested = any(len(child.children) > 0 for item in items for child in item.children)
    # Make sure the index is a list
    index = index.to(list)
    return rx.el.li(
        rx.link(
            rx.el.h2(
                section_title,
                class_name="font-mono text-m-slate-12 dark:text-m-slate-3 hover:text-primary-10 dark:hover:text-primary-9 uppercase text-[0.8125rem] leading-6 font-medium",
            ),
            underline="none",
            href=section_url,
            class_name="h-8 mb-2 flex items-center justify-start ml-[2.5rem]",
        ),
        rx.accordion.root(
            *[
                sidebar_item_comp(
                    item_index="index" + str(item_index),
                    item=item,
                    index=index[1:] if nested else [],
                    url=url,
                )
                for item_index, item in enumerate(items)
            ],
            type="multiple",
            collapsible=True,
            default_value=index[:1].foreach(lambda x: "index" + x.to_string()),
            class_name=ui.cn(
                "ml-0 pl-0 w-full !bg-transparent !shadow-none rounded-[0px] flex flex-col",
                "gap-0" if connected_line else "gap-1",
            ),
        ),
        class_name="flex flex-col items-start ml-0 w-full",
    )


@rx.memo
def sidebar_comp(
    url: str,
    learn_index: list[int],
    component_lib_index: list[int],
    frontend_index: list[int],
    backend_index: list[int],
    hosting_index: list[int],
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
    tutorials_index: list[int],
    width: str = "100%",
):
    from reflex_docs.pages.docs import ai_builder as ai_builder_pages
    from reflex_docs.pages.docs import enterprise, getting_started, state, ui
    from reflex_docs.pages.docs import hosting as hosting_page
    from reflex_docs.pages.docs.apiref import pages
    from reflex_docs.pages.docs.custom_components import custom_components
    from reflex_docs.pages.docs.library import library
    from reflex_docs.pages.docs.recipes_overview import overview

    _path = rx.State.router.page.path
    _is_docs_hosting = _path.startswith("/docs/hosting/") | _path.startswith(
        "/hosting/"
    )
    _is_docs_ai_builder = _path.startswith("/docs/ai/") | _path.startswith("/ai/")

    return rx.box(  # pyright: ignore [reportCallIssue]
        # Handle sidebar categories for docs/cloud first
        rx.cond(  # pyright: ignore [reportCallIssue]
            _is_docs_hosting,
            rx.el.ul(
                sidebar_category(
                    "Cloud", hosting_page.deploy_quick_start.path, "cloud", 0
                ),
                # sidebar_category(
                #     "CLI Reference", cloud_pages[0].path, "book-marked", 1
                # ),
                class_name="flex flex-col items-start gap-2 w-full list-none",
            ),
            rx.cond(  # pyright: ignore [reportCallIssue]
                _is_docs_ai_builder,
                rx.el.ul(
                    sidebar_category(
                        "AI Builder",
                        ai_builder_pages.overview.best_practices.path,
                        "bot",
                        0,
                    ),
                    sidebar_category(
                        "MCP/Skills",
                        ai_builder_pages.integrations.ai_onboarding.path,
                        "plug",
                        1,
                    ),
                    # sidebar_category(
                    #     "Integrations",
                    #     ai_builder_pages.integrations.overview.path,
                    #     "codesandbox",
                    #     2,
                    # ),
                    class_name="flex flex-col items-start gap-2 w-full list-none",
                ),
                rx.el.ul(
                    sidebar_category(
                        "Learn",
                        getting_started.introduction.path,
                        "graduation-cap",
                        0,
                    ),
                    sidebar_category(
                        "Components",
                        library.path,
                        "layout-panel-left",
                        1,
                    ),
                    sidebar_category(
                        "API Reference",
                        pages[0].path,
                        "book-text",
                        2,
                    ),
                    sidebar_category(
                        "Enterprise",
                        enterprise.overview.path,
                        "building-2",
                        3,
                    ),
                    class_name="flex flex-col items-start gap-2 w-full list-none",
                ),
            ),
        ),
        # Handle the sidebar content based on docs/cloud or docs
        rx.cond(  # pyright: ignore [reportCallIssue]
            _is_docs_hosting,
            rx.match(  # pyright: ignore [reportCallIssue]
                SidebarState.sidebar_index,
                (
                    0,
                    rx.el.ul(
                        create_sidebar_section(
                            "Cloud",
                            hosting_page.deploy_quick_start.path,
                            hosting,
                            hosting_index,
                            url,
                        ),
                        class_name="flex flex-col items-start gap-8  w-full list-none list-style-none",
                    ),
                ),
                # (
                #     1,
                #     rx.el.ul(
                #         create_sidebar_section(
                #             "CLI Reference",
                #             cloud_pages[0].path,
                #             cli_ref,
                #             cli_ref_index,
                #             url,
                #         ),
                #         class_name="flex flex-col items-start gap-8  w-full list-none list-style-none",
                #     ),
                # ),
            ),
            rx.cond(  # pyright: ignore [reportCallIssue]
                _is_docs_ai_builder,
                rx.match(  # pyright: ignore [reportCallIssue]
                    SidebarState.sidebar_index,
                    (
                        0,
                        rx.el.ul(
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
                            class_name="flex flex-col items-start gap-8  w-full list-none list-style-none",
                        ),
                    ),
                    (
                        1,
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
                            class_name="flex flex-col items-start gap-8  w-full list-none list-style-none",
                        ),
                    ),
                    # (
                    #     2,
                    #     rx.el.ul(
                    #         create_sidebar_section(
                    #             "Integration",
                    #             ai_builder_pages.integrations.overview.path,
                    #             ai_builder_integrations,
                    #             ai_builder_integrations_index,
                    #             url,
                    #         ),
                    #         class_name="flex flex-col items-start gap-6  w-full list-none list-style-none",
                    #     ),
                    # ),
                ),
                rx.match(  # pyright: ignore [reportCallIssue]
                    SidebarState.sidebar_index,
                    (
                        0,
                        rx.el.ul(
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
                            class_name="flex flex-col items-start gap-8  w-full list-none list-style-none",
                        ),
                    ),
                    (
                        1,
                        rx.el.ul(
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
                            class_name="flex flex-col items-start gap-8  w-full list-none list-style-none",
                        ),
                    ),
                    (
                        2,
                        rx.el.ul(
                            create_sidebar_section(
                                "Reference",
                                pages[0].path,
                                api_reference,
                                api_reference_index,
                                url,
                            ),
                            class_name="flex flex-col items-start gap-8  w-full list-none list-style-none",
                        ),
                    ),
                    (
                        3,
                        rx.el.ul(
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
                            class_name="flex flex-col items-start gap-8  w-full list-none list-style-none",
                        ),
                    ),
                ),
            ),
        ),
        # Handle general docs sections
        style={
            "&::-webkit-scrollbar-thumb": {
                "background_color": "transparent",
            },
            "&::-webkit-scrollbar": {
                "background_color": "transparent",
            },
        },
        class_name="flex flex-col pb-24 gap-8 items-start h-full pt-8 pr-4 scroll-p-4 overflow-y-scroll hidden-scrollbar w-full 3xl:pl-0 pl-6",
    )


def sidebar(url=None, width: str = "100%") -> rx.Component:
    """Render the sidebar."""
    learn_index = calculate_index(learn, url)
    component_lib_index = calculate_index(component_lib, url)
    frontend_index = calculate_index(frontend, url)
    backend_index = calculate_index(backend, url)
    hosting_index = calculate_index(hosting, url)
    graphing_libs_index = calculate_index(graphing_libs, url)
    api_reference_index = calculate_index(api_reference, url)
    recipes_index = calculate_index(recipes, url)
    enterprise_usage_index = calculate_index(enterprise_usage_items, url)
    enterprise_component_index = calculate_index(enterprise_component_items, url)

    cli_ref_index = calculate_index(cli_ref, url)
    ai_builder_overview_index = calculate_index(ai_builder_overview_items, url)
    ai_builder_integrations_index = calculate_index(ai_builder_integrations, url)
    ai_onboarding_index = calculate_index(ai_onboarding_items, url)
    mcp_index = calculate_index(mcp_items, url)
    skills_index = calculate_index(skills_items, url)

    return rx.box(
        sidebar_comp(
            url=url,
            learn_index=learn_index,
            component_lib_index=component_lib_index,
            frontend_index=frontend_index,
            backend_index=backend_index,
            hosting_index=hosting_index,
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


sb = sidebar(width="100%")
