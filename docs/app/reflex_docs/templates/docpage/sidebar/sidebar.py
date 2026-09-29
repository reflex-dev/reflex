"""Logic for the sidebar component."""

from __future__ import annotations

import reflex as rx
from reflex_site_shared.components.docs_shell import (
    docs_sidebar_category as sidebar_category,
)
from reflex_site_shared.components.docs_shell import (
    docs_sidebar_group,
    docs_sidebar_section,
)
from reflex_site_shared.components.docs_shell import docs_sidebar_leaf as sidebar_leaf

from .sidebar_items.ai import (
    agent_toolkit_items,
    ai_builder_integrations,
    ai_builder_overview_items,
    mcp_items,
    skills_items,
)
from .sidebar_items.component_lib import component_lib, graphing_libs, html_lib
from .sidebar_items.enterprise import (
    enterprise_component_items,
    enterprise_items,
    enterprise_usage_items,
)
from .sidebar_items.learn import backend, frontend, hosting, learn
from .sidebar_items.recipes import recipes
from .sidebar_items.reference import api_reference, changelog_items
from .state import SideBarBase, SideBarItem

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

    let offset = 0;
    if (linkRect.top < containerRect.top) {
      offset = linkRect.top - containerRect.top;
    } else if (linkRect.bottom > containerRect.bottom) {
      offset = linkRect.bottom - containerRect.bottom;
    }
    if (offset !== 0) {
      scrollableParent.scrollBy({ top: offset, behavior: 'instant' });
    }
  }
}

setTimeout(scrollToActiveSidebarLink, 100);

window.addEventListener("popstate", () => {
  setTimeout(scrollToActiveSidebarLink, 100);
});
"""


def sidebar_link(*children, **props):
    """Create a sidebar link."""
    return rx.link(
        *children,
        underline="none",
        **props,
    )


@rx.memo
def sidebar_leaf_outer(
    item_names: rx.vars.StringVar[str],
    item_link: rx.vars.StringVar[str],
    is_active: rx.vars.BooleanVar,
    guide_margin_class: rx.vars.StringVar[str],
) -> rx.Component:
    """Get the leaf node of the sidebar."""
    return rx.el.li(
        sidebar_link(
            rx.flex(
                rx.text(
                    item_names,
                    margin="0.5em 0.5em 0.2em 0.5em",
                    width="100%",
                    class_name=rx.cond(
                        is_active,
                        "m-0 transition-color text-primary-hover",
                        "m-0 transition-color text-muted-foreground hover:text-foreground",
                    ),
                ),
            ),
            href=item_link,
            class_name="block w-full",
        ),
        class_name="m-0 p-0 !overflow-visible w-full list-none",
    )


def sidebar_item_comp(
    item_index: int,
    item: SideBarItem,
    index: rx.vars.ArrayVar[list[int]],
    url: rx.vars.StringVar[str],
    guide_margin_class: str = "ml-[2.5rem]",
) -> rx.Component:
    """Render an item in the sidebar, recursing into its children."""
    if not item.children:
        if item.outer:
            return sidebar_leaf_outer(
                item_names=item.names,
                item_link=item.link,
                is_active=(url == item.link),
                guide_margin_class=guide_margin_class,
            )
        else:
            return sidebar_leaf(
                title=item.names,
                href=item.link,
                active=(url == item.link),
                guide_margin_class=guide_margin_class,
            )

    if len(item.children) == 1 and not item.children[0].children:
        child = item.children[0]
        return rx.el.li(
            sidebar_link(
                rx.el.p(item.names, class_name="m-0 text-sm font-[475]"),
                href=child.link,
                aria_current=rx.cond(url == child.link, "page", "false"),
                class_name="flex min-h-8 w-full items-center rounded-lg py-1 pl-[2.5rem] text-foreground hover:!text-foreground transition-colors [&[aria-current=page]]:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
            ),
            class_name="m-0 p-0 w-full list-none",
        )

    is_open = (index.length() > 0) & (index[0] == item_index)
    nested_index = rx.cond(is_open, index[1:], []).to(list[int])
    return docs_sidebar_group(
        item.names,
        *(
            sidebar_item_comp(
                item_index=child_index,
                item=child,
                index=nested_index,
                url=url,
                guide_margin_class="ml-[2.5rem]",
            )
            for child_index, child in enumerate(item.children)
        ),
        open_=is_open,
    )


def calculate_index(sidebar_items, url: str) -> list[int]:
    sidebar_items = (
        sidebar_items if isinstance(sidebar_items, list) else [sidebar_items]
    )
    index_list = []

    if not url:
        return index_list

    url = url.rstrip("/") + "/"
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
        if not item.children and not item.exclude_from_prev_next:
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
    + agent_toolkit_items
    + mcp_items
    + skills_items
    + api_reference
    + changelog_items
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


def create_sidebar_section(
    section_title: str,
    section_url: str,
    items: list[SideBarItem],
    index: rx.vars.ArrayVar[list[int]],
    url: rx.vars.StringVar[str],
    connected_line: bool = False,
    guide_margin_class: str = "ml-[2.5rem]",
) -> rx.Component:
    """Render a titled section of the sidebar."""
    return docs_sidebar_section(
        section_title,
        section_url,
        *(
            sidebar_item_comp(
                item_index=item_index,
                item=item,
                index=index,
                url=url,
                guide_margin_class=guide_margin_class,
            )
            for item_index, item in enumerate(items)
        ),
        connected_line=connected_line,
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


@rx.memo
def sidebar_comp(
    url: rx.vars.StringVar[str],
    learn_index: rx.vars.ArrayVar[list[int]],
    component_lib_index: rx.vars.ArrayVar[list[int]],
    frontend_index: rx.vars.ArrayVar[list[int]],
    backend_index: rx.vars.ArrayVar[list[int]],
    hosting_index: rx.vars.ArrayVar[list[int]],
    html_lib_index: rx.vars.ArrayVar[list[int]],
    graphing_libs_index: rx.vars.ArrayVar[list[int]],
    api_reference_index: rx.vars.ArrayVar[list[int]],
    changelog_index: rx.vars.ArrayVar[list[int]],
    recipes_index: rx.vars.ArrayVar[list[int]],
    enterprise_usage_index: rx.vars.ArrayVar[list[int]],
    enterprise_component_index: rx.vars.ArrayVar[list[int]],
    agent_toolkit_index: rx.vars.ArrayVar[list[int]],
    mcp_index: rx.vars.ArrayVar[list[int]],
    skills_index: rx.vars.ArrayVar[list[int]],
    ai_builder_overview_index: rx.vars.ArrayVar[list[int]],
    ai_builder_integrations_index: rx.vars.ArrayVar[list[int]],
) -> rx.Component:
    """Render the docs sidebar.

    The function is decorated with ``rx.memo`` so the rendered tree compiles
    to a single React component that receives the runtime ``url`` and per-section
    indices as props. ``url`` is expected to be pre-normalized by the caller
    (see ``sidebar`` below).
    """
    from reflex_docs.pages.docs import ai_builder as ai_builder_pages
    from reflex_docs.pages.docs import enterprise, getting_started, state, ui
    from reflex_docs.pages.docs import hosting as hosting_page
    from reflex_docs.pages.docs.library import library
    from reflex_docs.pages.docs.recipes_overview import overview

    is_docs_hosting = url.startswith("/hosting/")
    is_docs_ai_builder = url.startswith("/ai/")
    is_ai_mcp_or_skills = (
        url.startswith("/ai/integrations/agent-toolkit/")
        | url.startswith("/ai/integrations/skills/")
        | url.startswith("/ai/integrations/agents-md/")
        | url.startswith("/ai/integrations/mcp")
    )

    is_library = url.contains("library") | url.contains("/mcp-")
    is_api_reference = url.contains("api-reference") | url.startswith("/changelog/")
    is_enterprise = url.contains("enterprise")
    is_default_docs = ~is_library & ~is_api_reference & ~is_enterprise

    hosting_categories = rx.el.ul(
        sidebar_category(
            "Cloud",
            hosting_page.deploy_quick_start.path,
            None,
            True,
        ),
        class_name="flex flex-col items-start gap-2 w-full list-none",
    )
    hosting_content = rx.el.ul(
        create_sidebar_section(
            "Cloud",
            hosting_page.deploy_quick_start.path,
            hosting,
            hosting_index,
            url,
        ),
        class_name="m-0 p-0 flex flex-col items-start gap-8  w-full list-none list-style-none",
    )

    ai_builder_categories = rx.el.ul(
        sidebar_category("Build with AI", "/ai/", None, url == "/ai/"),
        sidebar_category(
            "AI Builder",
            ai_builder_pages.overview.best_practices.path,
            None,
            ~is_ai_mcp_or_skills & (url != "/ai/"),
        ),
        sidebar_category(
            "Agent Toolkit",
            ai_builder_pages.integrations.agent_toolkit.path,
            None,
            is_ai_mcp_or_skills,
        ),
        class_name="flex flex-col items-start gap-2 w-full list-none",
    )
    ai_mcp_skills_content = rx.el.ul(
        create_sidebar_section(
            "Overview",
            ai_builder_pages.integrations.agent_toolkit.path,
            agent_toolkit_items,
            agent_toolkit_index,
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
    ai_builder_overview_content = rx.el.ul(
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
    ai_builder_content = rx.cond(
        is_ai_mcp_or_skills,
        ai_mcp_skills_content,
        ai_builder_overview_content,
    )

    docs_categories = rx.el.ul(
        sidebar_category(
            "Learn",
            getting_started.introduction.path,
            "graduation-cap",
            is_default_docs,
        ),
        sidebar_category(
            "Components",
            library.path,
            "layout-panel-left",
            is_library,
        ),
        sidebar_category(
            "API Reference",
            api_reference[0].link,
            "book-text",
            ~is_library & is_api_reference,
        ),
        sidebar_category(
            "Enterprise",
            enterprise.overview.path,
            "building-2",
            ~is_library & ~is_api_reference & is_enterprise,
        ),
        class_name="flex flex-col items-start gap-2 w-full list-none",
    )
    library_content = rx.el.ul(
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
        class_name="m-0 p-0 flex flex-col items-start gap-8  w-full list-none list-style-none",
    )
    api_reference_content = rx.el.ul(
        create_sidebar_section(
            "Reference",
            api_reference[0].link,
            api_reference,
            api_reference_index,
            url,
            guide_margin_class="ml-[1.5rem] [&_.pointer-events-none]:hidden",
        ),
        create_sidebar_section(
            "Changelog",
            "/changelog/",
            changelog_items,
            changelog_index,
            url,
            guide_margin_class="ml-[1.5rem] [&_.pointer-events-none]:hidden",
        ),
        class_name="m-0 p-0 flex flex-col items-start gap-8  w-full list-none list-style-none",
    )
    enterprise_content = rx.el.ul(
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
    default_docs_content = rx.el.ul(
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
    docs_content = rx.cond(
        is_library,
        library_content,
        rx.cond(
            is_api_reference,
            api_reference_content,
            rx.cond(
                is_enterprise,
                enterprise_content,
                default_docs_content,
            ),
        ),
    )

    categories = rx.cond(
        is_docs_hosting,
        hosting_categories,
        rx.cond(is_docs_ai_builder, ai_builder_categories, docs_categories),
    )
    content = rx.cond(
        is_docs_hosting,
        hosting_content,
        rx.cond(is_docs_ai_builder, ai_builder_content, docs_content),
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
    """Render the sidebar.

    ``sidebar`` stays as a regular function (rather than a memo) because its
    body invokes Python-only helpers like ``normalize_url`` and
    ``calculate_index`` that aren't expressible as Var operations.
    """
    normalized_url = normalize_url(url)
    return rx.box(
        sidebar_comp(
            url=normalized_url,
            learn_index=calculate_index(learn, normalized_url),
            component_lib_index=calculate_index(component_lib, normalized_url),
            frontend_index=calculate_index(frontend, normalized_url),
            backend_index=calculate_index(backend, normalized_url),
            hosting_index=calculate_index(hosting, normalized_url),
            html_lib_index=calculate_index(html_lib, normalized_url),
            graphing_libs_index=calculate_index(graphing_libs, normalized_url),
            api_reference_index=calculate_index(api_reference, normalized_url),
            changelog_index=calculate_index(changelog_items, normalized_url),
            recipes_index=calculate_index(recipes, normalized_url),
            enterprise_usage_index=calculate_index(
                enterprise_usage_items, normalized_url
            ),
            enterprise_component_index=calculate_index(
                enterprise_component_items, normalized_url
            ),
            agent_toolkit_index=calculate_index(agent_toolkit_items, normalized_url),
            ai_builder_overview_index=calculate_index(
                ai_builder_overview_items, normalized_url
            ),
            ai_builder_integrations_index=calculate_index(
                ai_builder_integrations, normalized_url
            ),
            mcp_index=calculate_index(mcp_items, normalized_url),
            skills_index=calculate_index(skills_items, normalized_url),
        ),
        on_mount=rx.call_script(Scrollable_SideBar),
        id=rx.Var.create("sidebar-container"),
        class_name="flex justify-end w-full h-full",
    )
