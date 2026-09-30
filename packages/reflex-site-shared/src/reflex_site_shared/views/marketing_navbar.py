"""Marketing navbar for reflex.dev, with the site-wide announcement banner."""

import reflex_components_internal as ui

import reflex as rx
from reflex_site_shared.backend.get_blogs import BlogPostDict, RecentBlogsState
from reflex_site_shared.components.icons import get_icon
from reflex_site_shared.components.marketing_button import Button, button
from reflex_site_shared.components.marketing_date import marketing_date
from reflex_site_shared.constants import (
    DISCORD_URL,
    GITHUB_ORG_URL,
    GITHUB_STARS,
    GITHUB_URL,
    JOBS_BOARD_URL,
    REFLEX_ASSETS_CDN,
    REFLEX_BUILD_LOGIN_URL,
    XY_GITHUB_STARS,
    XY_GITHUB_URL,
)
from reflex_site_shared.views.announcement_banner import announcement_banner

FOCUS_RING = (
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
)


def site_anchor(href: str):
    """Resolve marketing destinations independently of a consuming app's base path.

    Returns:
        The rendered component.
    """
    return rx.el.elements.a, f"https://reflex.dev{href}" if href.startswith(
        "/"
    ) else href


def button_link(*children, href: str, **props) -> rx.Component:
    """Render a marketing action as a native navigation link.

    Returns:
        The rendered component.
    """
    anchor, href = site_anchor(href)
    return anchor(button(*children, native_button=False, **props), href=href)


def demo_link(*children, **props) -> rx.Component:
    """Open the marketing booking page.

    Returns:
        The rendered component.
    """
    return button_link(*children, href="/demo/", **props)


_MCP_DOCS_URL = "/docs/ai/integrations/mcp-overview/"

# Public repository counts checked on 2026-09-08.
_REFLEX_GITHUB_STARS = GITHUB_STARS
_XY_GITHUB_STARS = XY_GITHUB_STARS
_TOTAL_GITHUB_STARS = _REFLEX_GITHUB_STARS + _XY_GITHUB_STARS
_TOTAL_GITHUB_STARS_LABEL = f"{(_TOTAL_GITHUB_STARS + 999) // 1000}K"
_REFLEX_GITHUB_STARS_LABEL = f"{round(_REFLEX_GITHUB_STARS / 1000)}K"
_XY_GITHUB_STARS_LABEL = f"{_XY_GITHUB_STARS / 1000:.1f}K"

_FRAMEWORK_OVERVIEW_ITEM = (
    "Framework Overview",
    "The open-source Python framework behind your apps.",
    "/open-source/",
)

_DEVELOPER_TOOL_ITEMS = (
    (
        "Documentation",
        "Explore guides, components, APIs, and examples.",
        "/docs/",
    ),
    (
        "MCP",
        "Connect coding agents to current documentation and components.",
        _MCP_DOCS_URL,
    ),
    (
        "Skills",
        "Give coding agents reusable guidance and workflows.",
        "/docs/ai/integrations/skills/",
    ),
)

_ENTERPRISE_DEVELOPER_ITEMS = (
    (
        "Auto MCP",
        "Turn your application's workflows into tools for AI agents.",
        "/docs/enterprise/mcp/",
    ),
    (
        "Authentication",
        "Add secure OIDC authentication and authorization.",
        "/docs/enterprise/auth/overview/",
    ),
    (
        "End-to-End Testing",
        "Run browser tests against a live Reflex app.",
        "/docs/enterprise/testing/",
    ),
)

_PLATFORM_ITEMS = (
    (
        "Platform Overview",
        "See how the Reflex platform fits together.",
        "/platform/",
    ),
    (
        "AI Builder",
        "Build and test production software with AI.",
        "/ai-builder/",
    ),
    (
        "Integrations",
        "Connect your data, APIs, models, and services.",
        "/integrations/",
    ),
    (
        "App Management",
        "Deploy, Monitor and govern your apps.",
        "/hosting/",
    ),
    (
        "Workflows",
        "Automate business processes with AI agents. Join the waitlist.",
        "/workflows/",
    ),
    (
        "Implementation",
        "Enterprise controls and hands-on engineering from discovery to rollout.",
        "/enterprise/",
    ),
)

_SOLUTION_INDUSTRIES = (
    (
        "Financial Services",
        "Put trusted analysis next to every decision.",
        "/use-cases/finance/",
    ),
    (
        "Public Sector",
        "Modernize essential services without losing control.",
        "/use-cases/government/",
    ),
    (
        "Healthcare",
        "Turn complex care workflows into clear next actions.",
        "/use-cases/healthcare/",
    ),
    (
        "Technology",
        "Ship differentiated products from one Python stack.",
        "/use-cases/technology/",
    ),
    (
        "Manufacturing",
        "Connect factory operations to faster, safer decisions.",
        "/use-cases/manufacturing/",
    ),
    (
        "Consulting",
        "Turn expert analysis into client-ready software.",
        "/use-cases/consulting/",
    ),
)


# These primitives are shared by desktop menus and the mobile disclosure panel.
_LINK = "flex w-full flex-col gap-1 rounded-xl px-3 py-2.5 text-left hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring focus-visible:-outline-offset-2"
_LINK_COMPACT = "flex w-full flex-col gap-0.5 rounded-xl px-4 py-2 text-left hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring focus-visible:-outline-offset-2"
_LINK_SPACIOUS = "flex w-full flex-col gap-1 rounded-xl px-3 py-3 text-left hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring focus-visible:-outline-offset-2"
_LINK_COMPACT_SPACIOUS = "flex w-full flex-col gap-0.5 rounded-xl px-4 py-3 text-left hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring focus-visible:-outline-offset-2"
_HEADING = "mx-4 border-b border-border pb-3 text-sm font-book text-subtle-foreground"


def _link(
    title: str,
    description: str,
    href: str,
    *,
    compact: bool = False,
    spacious: bool = False,
    stars: str | None = None,
) -> rx.Component:
    """Render link.

    Returns:
        The rendered component.
    """
    if compact:
        link_class = _LINK_COMPACT_SPACIOUS if spacious else _LINK_COMPACT
    else:
        link_class = _LINK_SPACIOUS if spacious else _LINK
    content = [
        rx.el.span(title, class_name="text-sm font-medium leading-5 text-foreground")
    ]
    if title == "Workflows":
        content[0] = rx.el.span(
            content[0],
            rx.el.span(
                "Coming soon",
                class_name="inline-flex shrink-0 items-center whitespace-nowrap rounded-full border border-border-subtle bg-subtle px-2.5 py-1 text-micro font-medium leading-3 text-muted-foreground",
            ),
            class_name="flex flex-wrap items-center gap-2",
        )
    if description:
        content.append(
            rx.el.span(
                description, class_name="text-xs leading-4 text-muted-foreground"
            )
        )
    if stars:
        content = [
            rx.el.span(*content, class_name="flex min-w-0 flex-col gap-1"),
            rx.el.span(
                get_icon(
                    "github_navbar",
                    class_name="size-3.5 shrink-0 [&>svg]:block [&>svg]:size-full",
                ),
                rx.el.span(stars, class_name="leading-none"),
                aria_label=f"{stars} GitHub stars",
                class_name="inline-flex h-7 w-16 shrink-0 items-center justify-center gap-1.5 rounded-full border border-border bg-background px-2 text-xs font-book tabular-nums text-muted-foreground",
            ),
        ]
        link_class = link_class.replace(
            "flex-col", "flex-row items-center justify-between"
        ).replace("gap-1 ", "gap-3 ")
    if not href:
        return rx.el.div(
            *content,
            aria_disabled="true",
            class_name=f"{link_class.replace(' hover:bg-accent', '')} cursor-default",
        )
    anchor, href = site_anchor(href)
    return anchor(*content, href=href, class_name=link_class)


def _column(title: str, items: tuple, class_name: str = "") -> rx.Component:
    """Render column.

    Returns:
        The rendered component.
    """
    return rx.el.div(
        rx.el.div(title, class_name=_HEADING),
        rx.el.div(
            *[
                _link(*item[:3], stars=item[3] if len(item) > 3 else None)
                for item in items
            ],
            class_name="grid gap-1 pt-3",
        ),
        class_name=f"flex min-w-0 flex-col px-3 pb-3 pt-6 {class_name}",
    )


def _platform_content() -> rx.Component:
    """Render platform content.

    Returns:
        The rendered component.
    """
    return rx.el.div(
        rx.el.div(
            *[_link(*item, compact=True) for item in _PLATFORM_ITEMS],
            class_name="grid grid-flow-col grid-cols-2 grid-rows-3",
        ),
        class_name="w-[38rem] p-4",
    )


def _developers_content() -> rx.Component:
    """Render developers content.

    Returns:
        The rendered component.
    """
    return rx.el.div(
        _column(
            "Open source",
            (
                _FRAMEWORK_OVERVIEW_ITEM,
                (
                    "Reflex",
                    "Web apps in pure Python",
                    GITHUB_URL,
                    _REFLEX_GITHUB_STARS_LABEL,
                ),
                (
                    "XY",
                    "Fast and composable charts",
                    XY_GITHUB_URL,
                    _XY_GITHUB_STARS_LABEL,
                ),
            ),
        ),
        _column("Resources", _DEVELOPER_TOOL_ITEMS, "border-l border-border"),
        _column(
            "Enterprise Package",
            _ENTERPRISE_DEVELOPER_ITEMS,
            "border-l border-border",
        ),
        class_name="grid w-[60.75rem] grid-cols-3 gap-x-4",
    )


def _resources_items() -> tuple:
    """Render resources items.

    Returns:
        The rendered component.
    """
    return (
        (
            "Learn",
            (
                ("Docs", "", "/docs/"),
                ("Templates", "", "/templates/"),
                ("MCP", "", _MCP_DOCS_URL),
                ("Skills", "", "/docs/ai/integrations/skills/"),
            ),
        ),
        (
            "Company",
            (
                ("About", "", "/about/"),
                ("Careers", "", JOBS_BOARD_URL),
                ("Press", "", "/press/"),
                ("Discord", "", DISCORD_URL),
            ),
        ),
    )


def _blog_item(post: BlogPostDict) -> rx.Component:
    """Render blog item.

    Returns:
        The rendered component.
    """
    cover = rx.el.div(
        rx.el.img(
            src=rx.cond(
                post["image"] != "",
                post["image"],
                "https://reflex.dev/homepage/news/yellow-pixel-art.avif",
            ),
            alt="",
            loading="lazy",
            decoding="async",
            class_name="absolute inset-0 size-full object-cover",
        ),
        class_name="order-1 mt-2 relative w-full aspect-video overflow-hidden rounded-xl",
    )
    return rx.el.elements.a(
        cover,
        marketing_date(
            value=post["date"],
            compact=True,
            class_name="text-xs text-muted-foreground",
        ),
        rx.el.span(
            post["title"], class_name="text-sm font-medium leading-5 text-foreground"
        ),
        href=rx.cond(
            post["url"].startswith("/"), "https://reflex.dev" + post["url"], post["url"]
        ),
        class_name="flex flex-col gap-2",
    )


def _resources_content() -> rx.Component:
    """Render resources content.

    Returns:
        The rendered component.
    """
    return rx.el.div(
        rx.el.div(
            *[
                rx.el.div(
                    rx.el.div(
                        title,
                        class_name=_HEADING,
                    ),
                    rx.el.div(
                        *[_link(*item, compact=True, spacious=True) for item in items],
                        class_name="flex flex-col",
                    ),
                    class_name="flex min-w-0 flex-col gap-3",
                )
                for title, items in _resources_items()
            ],
            class_name="grid w-[31rem] grid-cols-2 gap-2 border-r border-border px-3 pb-3 pt-6",
        ),
        rx.el.div(
            rx.foreach(RecentBlogsState.posts[:1], _blog_item),
            rx.el.elements.a(
                "Read All in Blog",
                ui.icon("ArrowRight01Icon", class_name="size-4"),
                href="https://reflex.dev/blog/",
                class_name="mt-auto flex items-center gap-2 pt-3 text-xs text-muted-foreground hover:text-foreground",
            ),
            on_mount=RecentBlogsState.fetch_recent_blogs,
            class_name="flex w-[18rem] shrink-0 flex-col justify-between gap-4 bg-subtle p-6",
        ),
        class_name="flex",
    )


def _solutions_content() -> rx.Component:
    """Render solutions content.

    Returns:
        The rendered component.
    """
    return rx.el.div(
        rx.el.div(
            _link(
                "Explore solutions",
                "Find a workflow, customer example, and starting point.",
                "/use-cases/",
                compact=True,
            ),
            rx.el.div(
                *[
                    _link(*item, compact=True, spacious=True)
                    for item in _SOLUTION_INDUSTRIES
                ],
                class_name="grid grid-cols-2",
            ),
            class_name="w-[35rem] p-3",
        ),
        rx.el.div(
            rx.el.elements.a(
                rx.image(
                    src=f"{REFLEX_ASSETS_CDN}case_studies/logos/light/autodesk_top.svg",
                    alt="Autodesk",
                    loading="lazy",
                    class_name="h-4 w-auto self-start",
                ),
                rx.el.span(
                    "How Autodesk saved 25% of their development time",
                    class_name="text-xl font-medium leading-7 tracking-tight text-balance",
                ),
                href="https://reflex.dev/customers/autodesk/",
                class_name="-mx-3 flex flex-col gap-4 rounded-xl p-3 hover:bg-accent",
            ),
            button_link(
                "Case studies",
                ui.icon("ArrowRight01Icon", class_name="size-4", aria_hidden=True),
                href="/customers/",
                variant="outline",
                size="md",
                class_name="w-full justify-center text-center",
            ),
            class_name="flex w-[18rem] shrink-0 flex-col justify-between gap-5 border-l border-border bg-accent p-6 text-foreground",
        ),
        class_name="flex",
    )


_IGNORE_CLICK_WHEN_HOVER_OPEN = rx.Var(
    "(event) => { if (event.detail > 0 && event.pointerType !== 'touch' "
    "&& event.currentTarget.getAttribute('aria-expanded') === 'true') "
    "{ event.preventBaseUIHandler(); } }"
)


def _menu_trigger(title: str, content: rx.Component) -> rx.Component:
    """Render menu trigger.

    Returns:
        The rendered component.
    """
    return ui.navigation_menu.item(
        ui.navigation_menu.trigger(
            title,
            unstyled=True,
            class_name="cursor-pointer rounded-full px-3 py-2 text-sm font-book text-muted-foreground hover:text-foreground data-[popup-open]:text-foreground focus-visible:outline-2 focus-visible:outline-ring",
            aria_label=f"{title} menu",
            # A mouse click on an already hover-opened trigger would switch Base UI
            # into click mode, where the menu ignores hover-out and looks stuck.
            # Keyboard clicks (detail 0) and touch still go through.
            custom_attrs={"onClick": _IGNORE_CLICK_WHEN_HOVER_OPEN},
        ),
        ui.navigation_menu.content(
            content,
            unstyled=True,
            keep_mounted=True,
            class_name=(
                "flex w-max overflow-hidden rounded-[inherit] bg-background font-sans text-foreground "
                # Base UI absolutely positions the outgoing panel while it exits;
                # fade and slide it so it does not snap over the incoming one.
                "transition-[opacity,translate] duration-150 ease-out motion-reduce:transition-none "
                "data-[starting-style]:opacity-0 data-[ending-style]:opacity-0 "
                "data-[activation-direction=left]:data-[starting-style]:-translate-x-1/4 "
                "data-[activation-direction=left]:data-[ending-style]:translate-x-1/4 "
                "data-[activation-direction=right]:data-[starting-style]:translate-x-1/4 "
                "data-[activation-direction=right]:data-[ending-style]:-translate-x-1/4"
            ),
        ),
        value=title,
        unstyled=True,
        class_name="hidden h-full items-center xl:flex",
    )


def marketing_mobile_drawer() -> rx.Component:
    """Render marketing mobile drawer.

    Returns:
        The rendered component.
    """
    sections = (
        ("Platform", _PLATFORM_ITEMS),
        *_resources_items(),
        (
            "Solutions",
            (
                (
                    "Explore solutions",
                    "Find a workflow and starting point.",
                    "/use-cases/",
                ),
                *_SOLUTION_INDUSTRIES,
            ),
        ),
        (
            "Developers",
            (
                _FRAMEWORK_OVERVIEW_ITEM,
                ("Reflex", "Web apps in pure Python", GITHUB_URL),
                ("XY", "Fast and composable charts", XY_GITHUB_URL),
                *_DEVELOPER_TOOL_ITEMS,
                *_ENTERPRISE_DEVELOPER_ITEMS,
            ),
        ),
    )
    return rx.el.details(
        rx.el.summary(
            ui.icon("Menu01Icon", class_name="size-5 group-open/mobile:hidden"),
            ui.icon("Cancel01Icon", class_name="hidden size-5 group-open/mobile:block"),
            aria_label="Toggle navigation menu",
            class_name=f"flex size-9 cursor-pointer list-none items-center justify-center rounded-full text-foreground hover:bg-accent {FOCUS_RING} [&::-webkit-details-marker]:hidden",
        ),
        rx.el.div(
            *[
                rx.el.details(
                    rx.el.summary(
                        title,
                        ui.icon(
                            "ArrowDown01Icon",
                            aria_hidden=True,
                            class_name="size-5 shrink-0 text-muted-foreground transition-transform duration-200 group-open/nav-section:rotate-180 motion-reduce:transition-none",
                        ),
                        class_name="flex cursor-pointer list-none items-center justify-between gap-3 border-b border-border px-4 py-4 text-base font-medium [&::-webkit-details-marker]:hidden",
                    ),
                    rx.el.div(
                        *[_link(*item) for item in items], class_name="px-2 py-3"
                    ),
                    class_name="group/nav-section",
                )
                for title, items in sections
            ],
            _link("Pricing", "", "/pricing/"),
            _link("Sign In", "", REFLEX_BUILD_LOGIN_URL),
            rx.el.div(
                demo_link(
                    "Book a Demo", variant="primary", size="lg", class_name="w-full"
                ),
                class_name="px-4 pt-2",
            ),
            class_name="absolute inset-x-0 top-full max-h-[calc(100dvh-6rem)] overflow-y-auto border-b border-border bg-background pb-4 text-foreground shadow-medium",
        ),
        class_name="group/mobile xl:hidden",
        custom_attrs={"data-navbar-mobile-menu": ""},
    )


def _search_item() -> rx.Component:
    """Restore the shared search dialog with an icon-only desktop trigger.

    Returns:
        The rendered component.
    """
    from reflex_site_shared.components.algolia import algolia_search

    return ui.navigation_menu.item(
        rx.el.div(
            Button.create(
                ui.icon(
                    "Search01Icon",
                    class_name="size-4",
                    stroke_width=1.5,
                    aria_hidden=True,
                ),
                variant="ghost",
                size="icon-sm",
                type="button",
                aria_label="Search (loading)",
                aria_disabled=True,
                aria_busy=True,
                tab_index=-1,
                class_name="ReflexSearch-button group-has-[.ReflexSearch-root]/search:!hidden",
            ),
            algolia_search(),
            class_name=(
                "group/search flex size-9 items-center justify-center "
                "[&_.ReflexSearch-root]:!w-auto "
                "[&_.ReflexSearch-button]:!size-9 [&_.ReflexSearch-button]:!min-w-0 "
                "[&_.ReflexSearch-button]:!justify-center [&_.ReflexSearch-button]:!p-0 "
                "[&_.ReflexSearch-button]:!rounded-full [&_.ReflexSearch-button]:!border-0 "
                "[&_.ReflexSearch-button]:!bg-transparent [&_.ReflexSearch-button]:!shadow-none "
                "[&_.ReflexSearch-button]:!text-[var(--navbar-search-color,var(--muted-foreground))] "
                "[&_.ReflexSearch-button:hover]:!bg-[var(--navbar-search-hover,var(--accent))] "
                "[&_.ReflexSearch-button:focus-visible]:!outline-2 "
                "[&_.ReflexSearch-button:focus-visible]:!outline-offset-2 "
                "[&_.ReflexSearch-button:focus-visible]:!outline-ring "
                "[&_.ReflexSearch-button>svg]:!size-4 [&_.ReflexSearch-button>svg]:!m-0 "
                "[&_.ReflexSearch-buttonText]:!hidden [&_.ReflexSearch-shortcut]:!hidden"
            ),
        ),
        unstyled=True,
        class_name="hidden items-center justify-center xl:flex",
    )


def _navigation_menu() -> rx.Component:
    """Render navigation menu.

    Returns:
        The rendered component.
    """
    nav_link = "inline-flex items-center justify-center gap-2 rounded-full px-3 py-2 text-sm font-book text-foreground hover:text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring"
    action_link = "inline-flex items-center justify-center gap-2 rounded-full h-10 px-0 text-sm font-book text-foreground hover:text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring"
    return ui.navigation_menu.root(
        ui.navigation_menu.list(
            _menu_trigger("Platform", _platform_content()),
            _menu_trigger("Resources", _resources_content()),
            _menu_trigger("Solutions", _solutions_content()),
            _menu_trigger("Developers", _developers_content()),
            ui.navigation_menu.item(
                rx.el.elements.a(
                    "Pricing",
                    href="https://reflex.dev/pricing/",
                    class_name=nav_link.replace(
                        "text-foreground hover:text-muted-foreground",
                        "text-muted-foreground hover:text-foreground",
                    ),
                ),
                unstyled=True,
                class_name="hidden xl:flex",
            ),
            _search_item(),
            unstyled=True,
            class_name="m-0 flex h-full list-none items-center",
            custom_attrs={"data-navbar-links": ""},
        ),
        ui.navigation_menu.list(
            ui.navigation_menu.item(
                rx.el.elements.a(
                    get_icon("github_navbar", class_name="size-4"),
                    _TOTAL_GITHUB_STARS_LABEL,
                    # The count spans Reflex and XY, so it points at the org.
                    href=GITHUB_ORG_URL,
                    aria_label=(
                        f"{_TOTAL_GITHUB_STARS_LABEL} GitHub stars — {_TOTAL_GITHUB_STARS:,} combined across Reflex and XY"
                    ),
                    title=f"Reflex + XY: {_TOTAL_GITHUB_STARS:,} stars (rounded up)",
                    class_name=action_link,
                ),
                unstyled=True,
            ),
            ui.navigation_menu.item(
                rx.el.elements.a(
                    "Sign In",
                    href=REFLEX_BUILD_LOGIN_URL,
                    target="_blank",
                    rel="noopener noreferrer",
                    class_name=action_link,
                ),
                unstyled=True,
                class_name="hidden min-[480px]:flex",
            ),
            ui.navigation_menu.item(
                demo_link(
                    "Book a Demo", variant="primary", size="sm", class_name="text-sm"
                ),
                unstyled=True,
                class_name="hidden xl:flex",
            ),
            ui.navigation_menu.item(
                marketing_mobile_drawer(), unstyled=True, class_name="flex xl:hidden"
            ),
            unstyled=True,
            class_name="m-0 flex h-full list-none items-center gap-4 sm:gap-6",
            custom_attrs={"data-navbar-actions": ""},
        ),
        ui.navigation_menu.portal(
            ui.navigation_menu.positioner(
                ui.navigation_menu.popup(
                    ui.navigation_menu.viewport(
                        unstyled=True,
                        class_name="relative h-full w-full overflow-hidden rounded-[inherit]",
                    ),
                    unstyled=True,
                    class_name="relative h-[var(--popup-height)] w-[var(--popup-width)] origin-[var(--transform-origin)] overflow-hidden rounded-panel border border-border bg-background shadow-medium transition-[opacity,translate,width,height] duration-150 data-[starting-style]:-translate-y-1 data-[starting-style]:opacity-0 data-[ending-style]:-translate-y-1 data-[ending-style]:opacity-0 motion-reduce:transition-none",
                ),
                unstyled=True,
                side_offset=2,
                align="start",
                align_offset=-109,
                position_method="fixed",
                class_name="z-[10000] box-border h-[var(--positioner-height)] w-[var(--positioner-width)] max-w-[var(--available-width)] transition-[top,left,right,bottom] duration-150 ease-out data-[instant]:transition-none motion-reduce:transition-none",
            ),
        ),
        delay=0,
        close_delay=150,
        unstyled=True,
        class_name="flex h-full w-full items-center justify-between gap-2",
    )


def _marketing_navbar(
    expanded_banner: bool,
    *,
    include_announcement: bool = True,
    split_demo: bool = False,
    banner: rx.Component | None = None,
) -> rx.Component:
    """Render marketing navbar.

    Returns:
        The rendered component.
    """
    return rx.el.div(
        (banner if banner is not None else announcement_banner())
        if include_announcement
        else rx.fragment(),
        rx.el.header(
            rx.el.div(
                rx.el.elements.a(
                    rx.image(
                        src=f"{REFLEX_ASSETS_CDN}logos/light/reflex.svg",
                        alt="Reflex",
                        class_name="h-auto w-[5.5rem] brightness-0 dark:invert",
                    ),
                    href="https://reflex.dev/",
                    class_name="mr-4 shrink-0 lg:mr-9",
                    custom_attrs={"data-navbar-logo": ""},
                ),
                _navigation_menu(),
                class_name="mx-auto flex h-full w-full max-w-[90rem] items-center px-4 min-[55rem]:px-8 lg:px-12",
                custom_attrs={"data-navbar-inner": ""},
            ),
            class_name="relative [&_nav]:!static [&_ul]:!static h-16 w-full border-b border-transparent transition-[border-color,background-color,backdrop-filter] duration-200 group-data-[scrolled=true]/navbar:border-border-subtle bg-transparent group-data-[scrolled=true]/navbar:bg-background/95 group-data-[scrolled=true]/navbar:backdrop-blur-sm"
            if expanded_banner
            else "relative [&_nav]:!static [&_ul]:!static h-16 w-full border-b border-transparent bg-background transition-[border-color] duration-200 group-data-[scrolled=true]/navbar:border-border-subtle motion-reduce:transition-none",
        ),
        class_name="group/navbar fixed top-0 z-[9999] flex w-full flex-col self-center",
        custom_attrs={
            "data-navbar": "demo"
            if split_demo
            else "landing"
            if expanded_banner
            else "standard",
            "data-scrolled": "false",
        },
    )


def marketing_navbar(
    banner: rx.Component | None = None, *, show_banner: bool = True
) -> rx.Component:
    """Render shared marketing navigation with an optional announcement.

    Args:
        banner: Optional replacement announcement component.
        show_banner: Whether to include an announcement.

    Returns:
        Fixed navbar with desktop menus and mobile navigation.
    """
    return _marketing_navbar(
        expanded_banner=False, include_announcement=show_banner, banner=banner
    )


@rx.memo
def landing_marketing_navbar() -> rx.Component:
    """Render landing marketing navbar.

    Returns:
        The rendered component.
    """
    return _marketing_navbar(expanded_banner=True)


@rx.memo
def marketing_navbar_without_announcement() -> rx.Component:
    """Standard navigation for pages that omit the announcement.

    Returns:
        The rendered component.
    """
    return _marketing_navbar(expanded_banner=False, include_announcement=False)


@rx.memo
def demo_marketing_navbar() -> rx.Component:
    """Navigation that continues the booking page photo and form split.

    Returns:
        The rendered component.
    """
    return _marketing_navbar(
        expanded_banner=False, include_announcement=False, split_demo=True
    )
