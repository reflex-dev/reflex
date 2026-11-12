"""Logic for the sidebar component."""

from __future__ import annotations

import reflex as rx
from reflex.vars import VarData
from reflex_base.utils.imports import ImportVar
from reflex_site_shared.components.docs_shell import (
    docs_left_sidebar,
    docs_sidebar_group,
    docs_sidebar_section,
)
from reflex_site_shared.components.docs_shell import (
    docs_sidebar_category as sidebar_category,
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

# Normalize the client-side route the same way docpage routes are registered:
# drop the /docs frontend path, fold component "/low" pages onto their parent,
# and end with a single trailing slash.
_SIDEBAR_URL_HOOK = r"""const docsSidebarUrl = useLocation()
  .pathname.replace(/\/+$/, "")
  .replace(/^\/docs(?=\/|$)/, "")
  .replace(/^(\/library(?=\/).*)\/low$/, "$1") + "/";"""

# Scroll the active link into view only when it falls outside the sidebar's
# viewport, so clicking a visible link never moves the sidebar.
_SIDEBAR_SCROLL_HOOK = """useEffect(() => {
  for (const scroller of document.querySelectorAll(".docs-sidebar-scroll")) {
    const active = scroller.querySelector('a[aria-current="page"]');
    if (!active) continue;
    const link = active.getBoundingClientRect();
    const box = scroller.getBoundingClientRect();
    const offset = link.top < box.top ? link.top - box.top : Math.max(0, link.bottom - box.bottom);
    if (offset) scroller.scrollBy({ top: offset, behavior: "instant" });
  }
}, [docsSidebarUrl]);"""

SIDEBAR_URL: rx.vars.StringVar[str] = rx.Var(
    _js_expr="docsSidebarUrl",
    _var_type=str,
    _var_data=VarData(
        imports={
            "react": [ImportVar(tag="useEffect")],
            "react-router": [ImportVar(tag="useLocation")],
        },
        hooks={_SIDEBAR_URL_HOOK: None, _SIDEBAR_SCROLL_HOOK: None},
    ),
).to(str)


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
            aria_current=rx.cond(is_active, "page", "false"),
            class_name="block w-full",
        ),
        class_name="m-0 p-0 !overflow-visible w-full list-none",
    )


def _descendant_links(item: SideBarBase) -> list[str]:
    """Collect the links of every leaf below an item."""
    links = []
    for child in item.children:
        if child.children:
            links.extend(_descendant_links(child))
        elif child.link:
            links.append(child.link)
    return links


def sidebar_item_comp(
    item: SideBarItem,
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
                rx.el.p(
                    item.names, class_name="m-0 text-sm font-[475] text-foreground"
                ),
                href=child.link,
                aria_current=rx.cond(url == child.link, "page", "false"),
                class_name="flex min-h-8 w-full items-center rounded-lg py-1 pl-[2.5rem] text-foreground hover:!text-foreground transition-colors [&[aria-current=page]]:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
            ),
            class_name="m-0 p-0 w-full list-none",
        )

    return docs_sidebar_group(
        item.names,
        *(
            sidebar_item_comp(item=child, url=url, guide_margin_class="ml-[2.5rem]")
            for child in item.children
        ),
        open_=rx.Var.create(_descendant_links(item)).contains(url),
    )


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
    url: rx.vars.StringVar[str],
    connected_line: bool = False,
    guide_margin_class: str = "ml-[2.5rem]",
) -> rx.Component:
    """Render a titled section of the sidebar."""
    return docs_sidebar_section(
        section_title,
        section_url,
        *(
            sidebar_item_comp(item=item, url=url, guide_margin_class=guide_margin_class)
            for item in items
        ),
        connected_line=connected_line,
    )


@rx.memo
def sidebar_comp() -> rx.Component:
    """Render the docs sidebar for the current client-side route.

    The sidebar reads the route from react-router rather than from props, so a
    single mounted instance follows navigation without being rebuilt per page.
    """
    from reflex_docs.pages.docs import ai_builder as ai_builder_pages
    from reflex_docs.pages.docs import enterprise, getting_started, state, ui
    from reflex_docs.pages.docs import hosting as hosting_page
    from reflex_docs.pages.docs.library import library
    from reflex_docs.pages.docs.recipes_overview import overview

    url = SIDEBAR_URL
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
            url,
        ),
        create_sidebar_section(
            "MCP",
            ai_builder_pages.integrations.mcp_overview.path,
            mcp_items,
            url,
            connected_line=True,
        ),
        create_sidebar_section(
            "Skills",
            ai_builder_pages.integrations.skills.path,
            skills_items,
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
            url,
        ),
        create_sidebar_section(
            "Integrations",
            ai_builder_pages.integrations.overview.path,
            ai_builder_integrations,
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
            url,
        ),
        create_sidebar_section(
            "Graphing",
            library.path,
            graphing_libs,
            url,
        ),
        create_sidebar_section(
            "Other",
            "/library/html/",
            html_lib,
            url,
        ),
        class_name="m-0 p-0 flex flex-col items-start gap-8  w-full list-none list-style-none",
    )
    api_reference_content = rx.el.ul(
        create_sidebar_section(
            "Reference",
            api_reference[0].link,
            api_reference,
            url,
            guide_margin_class="ml-[1.5rem] [&_.pointer-events-none]:hidden",
        ),
        create_sidebar_section(
            "Changelog",
            "/changelog/",
            changelog_items,
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
            url,
        ),
        create_sidebar_section(
            "Components",
            enterprise.components.path,
            enterprise_component_items,
            url,
        ),
        class_name="m-0 p-0 flex flex-col items-start gap-8  w-full list-none list-style-none",
    )
    default_docs_content = rx.el.ul(
        create_sidebar_section(
            "Onboarding",
            getting_started.introduction.path,
            learn,
            url,
        ),
        create_sidebar_section(
            "User Interface",
            ui.overview.path,
            filter_out_non_sidebar_items(frontend),
            url,
        ),
        create_sidebar_section(
            "State",
            state.overview.path,
            filter_out_non_sidebar_items(backend),
            url,
        ),
        create_sidebar_section(
            "Recipes",
            overview.path,
            recipes,
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
        class_name="docs-sidebar-scroll flex flex-col pb-24 gap-8 items-start h-full pt-8 pr-4 scroll-p-4 overflow-y-scroll overflow-x-hidden hidden-scrollbar w-full 3xl:pl-0 pl-6",
    )


def sidebar() -> rx.Component:
    """Render the sidebar navigation for the current route."""
    return rx.box(
        sidebar_comp(),
        id="sidebar-container",
        class_name="flex justify-end w-full h-full",
    )


def persistent_sidebar() -> rx.Component:
    """Render the desktop sidebar once, outside of every page's route component.

    Mounted as an app wrap, it survives client-side navigation, so it keeps its
    scroll position and expanded groups instead of being rebuilt per page. It
    overlays the ``docs-sidebar-slot`` spacer each docpage reserves, and CSS
    hides it on pages without that slot.
    """
    return rx.fragment(
        rx.el.div(
            rx.el.div(
                docs_left_sidebar(sidebar()),
                class_name="docs-persistent-sidebar-frame mx-auto flex w-full [&_.docs-sidebar]:pointer-events-auto",
            ),
            class_name="docs-persistent-sidebar pointer-events-none fixed inset-x-0 top-[var(--docs-header-height)] z-10",
        )
    )
