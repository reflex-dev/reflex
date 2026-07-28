"""Marketing Navbar module."""

import reflex_components_internal as ui
from reflex_components_internal.blocks.demo_form import demo_form_dialog

import reflex as rx
from reflex_site_shared.backend.get_blogs import BlogPostDict, RecentBlogsState
from reflex_site_shared.components.icons import get_icon
from reflex_site_shared.components.marketing_button import button as marketing_button
from reflex_site_shared.constants import (
    CHANGELOG_URL,
    DISCORD_URL,
    GITHUB_STARS,
    GITHUB_URL,
    REFLEX_ASSETS_CDN,
    REFLEX_BUILD_LOGIN_URL,
    REFLEX_BUILD_URL,
)
from reflex_site_shared.views.sidebar import navbar_sidebar_button


def github() -> rx.Component:
    """Github.

    Returns:
        The component.
    """
    return rx.el.elements.a(
        marketing_button(
            get_icon(icon="github_navbar", class_name="shrink-0"),
            f"{GITHUB_STARS // 1000}K",
            custom_attrs={
                "aria-label": f"View Reflex on GitHub - {GITHUB_STARS // 1000}K stars"
            },
            size="sm",
            variant="ghost",
        ),
        href=GITHUB_URL,
        custom_attrs={
            "aria-label": f"View Reflex on GitHub - {GITHUB_STARS // 1000}K stars"
        },
    )


def logo() -> rx.Component:
    """Logo.

    Returns:
        The component.
    """
    return rx.el.elements.a(
        rx.image(
            src=f"{REFLEX_ASSETS_CDN}logos/light/reflex.svg",
            alt="Reflex Logo",
            class_name="shrink-0 block dark:hidden",
        ),
        rx.image(
            src=f"{REFLEX_ASSETS_CDN}logos/dark/reflex.svg",
            alt="Reflex Logo",
            class_name="shrink-0 hidden dark:block",
        ),
        href="/",
        class_name="block shrink-0 lg:mr-9",
    )


def menu_trigger(title: str, content: rx.Component) -> rx.Component:
    """Menu trigger.

    Returns:
        The component.
    """
    return ui.navigation_menu.item(
        ui.navigation_menu.trigger(
            marketing_button(
                title,
                ui.icon(
                    "ArrowDown01Icon", class_name="chevron transition-all ease-out"
                ),
                size="sm",
                variant="ghost",
                class_name="font-[550] menu-button",
                native_button=False,
            ),
            style={
                "&[data-popup-open] .chevron": {
                    "transform": "rotate(180deg)",
                },
                "&[data-popup-open] .menu-button": {
                    "color": "light-dark(var(--primary-10), var(--primary-9))",
                },
            },
            class_name="px-1",
            aria_label=f"{title} menu",
            unstyled=True,
        ),
        content,
        value=title,
        class_name="cursor-pointer xl:flex hidden h-full items-center justify-center",
        unstyled=True,
        custom_attrs={"role": "menuitem"},
    )


def menu_content(content: rx.Component, class_name: str = "") -> rx.Component:
    """Styled dropdown panel wrapper for navigation menu items.

    Returns:
        The component.
    """
    return ui.navigation_menu.content(
        content,
        unstyled=True,
        class_name=ui.cn(
            "w-max **:data-[slot=navigation-menu-link]:focus:ring-0 **:data-[slot=navigation-menu-link]:focus:outline-none",
            "flex flex-row rounded-xl font-sans p-0",
            class_name,
        ),
        keep_mounted=True,
    )


def nav_section_heading(title: str) -> rx.Component:
    """Render the uppercase heading shared by mega-menu sections.

    Args:
        title: The section title.

    Returns:
        The section heading.
    """
    return rx.el.div(
        rx.el.span(
            title,
            class_name="font-mono font-[415] text-caption uppercase pb-4 rule-dashed-b text-secondary-11",
        ),
        class_name="px-4 pt-4 flex flex-col",
    )


def gold_star() -> rx.Component:
    """Render the gradient star used by open-source repository counts.

    Returns:
        The star icon.
    """
    return rx.el.svg(
        rx.el.defs(
            rx.el.linear_gradient(
                rx.el.stop(offset="0", stop_color="#FFDD73"),
                rx.el.stop(offset="1", stop_color="#FFB800"),
                id="os-star-fill",
                x1="12",
                y1="2",
                x2="12",
                y2="20",
                gradient_units="userSpaceOnUse",
            ),
        ),
        rx.el.path(
            d="M12 2 14.35 8.76 21.51 8.91 15.8 13.24 17.88 20.09 12 16 6.12 20.09 8.2 13.24 2.49 8.91 9.65 8.76Z",
            fill="url(#os-star-fill)",
            stroke="rgba(0,0,0,0.08)",
            stroke_width="1",
            stroke_linejoin="round",
        ),
        view_box="0 0 24 24",
        fill="none",
        class_name="size-3 shrink-0",
        custom_attrs={"aria-hidden": "true"},
    )


def open_source_row(
    name: str,
    repo: str,
    stars: str,
    *,
    tagline: str | None = None,
) -> rx.Component:
    """Render an open-source project row in the Products menu.

    Args:
        name: The project name.
        repo: The repository URL.
        stars: The abbreviated star count.
        tagline: An optional project description.

    Returns:
        The project link row.
    """
    project_details = [
        rx.el.span(name, class_name="text-sm font-[525] text-secondary-12")
    ]
    if tagline:
        project_details.append(
            rx.el.span(
                tagline,
                class_name="text-xs font-[475] text-secondary-11",
            )
        )

    return rx.el.elements.a(
        rx.el.span(*project_details, class_name="flex flex-col text-nowrap"),
        rx.el.span(
            rx.el.span(
                gold_star(),
                stars,
                class_name="flex h-6 shrink-0 items-center gap-1 rounded-md border border-secondary-4 bg-white-1 px-1.5 text-xs font-[475] text-secondary-11",
            ),
            rx.el.span(
                get_icon(
                    "github_navbar",
                    class_name="size-3.5 shrink-0 text-secondary-11 transition-colors group-hover/gh:text-secondary-12",
                ),
                class_name="group/gh relative flex size-6 shrink-0 items-center justify-center rounded-md border border-secondary-4 bg-white-1 transition-colors after:absolute after:-inset-2 after:content-[''] hover:border-secondary-8 hover:bg-secondary-3",
            ),
            class_name="flex shrink-0 items-center gap-2",
        ),
        href=repo,
        target="_blank",
        class_name="flex flex-row px-4 py-2 rounded-sm gap-4 items-center justify-between w-full cursor-pointer hover-card-shadow",
    )


def open_source_column() -> rx.Component:
    """Render the open-source project column in the Products menu.

    Returns:
        The open-source column.
    """
    return rx.el.div(
        nav_section_heading("Open Source"),
        rx.el.div(
            open_source_row(
                "Reflex",
                GITHUB_URL,
                f"{GITHUB_STARS // 1000}K",
                tagline="Web apps in pure Python",
            ),
            open_source_row(
                "XY",
                "https://github.com/reflex-dev/xy",
                "6",
                tagline="Fast and composable charts",
            ),
            class_name="flex flex-col",
        ),
        class_name="flex flex-col gap-4",
    )


def products_content() -> rx.Component:
    """Render the Platform and Open Source Products mega-menu.

    Returns:
        The Products menu content.
    """
    return menu_content(
        rx.el.div(
            rx.el.div(
                solutions_column(
                    "Platform",
                    [
                        ("AI Builder", "RoboticIcon", REFLEX_BUILD_URL),
                        (
                            "Agent Toolkit",
                            "McpServerIcon",
                            "/docs/ai/integrations/ai-onboarding/",
                        ),
                        (
                            "Integrations",
                            "PlugSocketIcon",
                            "/docs/ai/integrations/overview/",
                        ),
                        ("Deploy", "ServerStack01Icon", "/hosting/"),
                    ],
                ),
                class_name="flex h-full w-[15rem] flex-col bg-white-1 p-4 shadow-card dark:shadow-card-dark border-r border-secondary-4",
            ),
            rx.el.div(
                open_source_column(),
                class_name="flex w-[22rem] flex-col bg-secondary-1 p-4 dark:border-x dark:border-secondary-4",
            ),
            class_name="flex flex-row",
        ),
    )


def solutions_item(title: str, icon: str, href: str) -> rx.Component:
    """Solutions submenu row with icon and title.

    Returns:
        The component.
    """
    return rx.el.elements.a(
        ui.icon(
            icon,
            stroke_width=1.5,
            class_name="shrink-0 text-secondary-11 size-5",
        ),
        title,
        href=href,
        class_name="flex flex-row px-4 py-2 rounded-sm text-sm font-[525] text-secondary-12 gap-3 items-center justify-start cursor-pointer hover-card-shadow text-nowrap",
    )


def solutions_row(
    title: str,
    icon: str,
    href: str,
    *,
    trailing_pill: str | None = None,
) -> rx.Component:
    """Full-width solutions link row with optional badge.

    Returns:
        The component.
    """
    link_children: list[rx.Component] = [
        ui.icon(
            icon,
            stroke_width=1.5,
            class_name="shrink-0 text-secondary-11 size-5",
        ),
        rx.el.span(
            title,
            class_name="text-sm font-[525] text-secondary-12 text-nowrap",
        ),
    ]
    if trailing_pill:
        link_children.append(
            badge(trailing_pill),
        )
    return rx.el.elements.a(
        *link_children,
        href=href,
        class_name="flex flex-row px-4 py-2 rounded-sm gap-3 items-center w-full cursor-pointer hover-card-shadow text-nowrap",
    )


def solutions_column(title: str, items: list[tuple[str, str, str]]) -> rx.Component:
    """Grouped solutions links under a section heading.

    Returns:
        The component.
    """
    return rx.el.div(
        nav_section_heading(title),
        rx.el.div(
            *[solutions_item(item[0], item[1], item[2]) for item in items],
            class_name="flex flex-col",
        ),
        class_name="flex flex-col gap-4",
    )


def blog_item(post: BlogPostDict) -> rx.Component:
    """Compact preview card for a recent blog post.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.div(
            rx.moment(
                post["date"],
                format="MMM DD YYYY",
                class_name="text-secondary-11 text-caption font-[415] font-mono uppercase text-nowrap",
            ),
            rx.image(
                src=f"{REFLEX_ASSETS_CDN}common/{rx.color_mode_cond('light', 'dark')}/squares_blog.svg",
                class_name="pointer-events-none dark:opacity-50",
                alt="Squares Blog",
            ),
            class_name="flex flex-row items-center justify-start gap-6",
        ),
        rx.el.span(
            post["title"],
            class_name="text-secondary-12 text-base font-[525] group-hover:text-primary-10 line-clamp-3",
        ),
        rx.el.elements.a(
            href=post["url"],
            class_name="absolute inset-0",
        ),
        class_name="relative group flex flex-col gap-2 mb-2",
    )


def badge(text: str) -> rx.Component:
    """Small pill label for nav highlights (e.g. New, Enterprise).

    Returns:
        The component.
    """
    return rx.el.div(
        text,
        class_name="text-secondary-11 text-xs font-[475] bg-secondary-1 px-1.5 h-5 rounded-md flex items-center justify-center border border-secondary-4",
    )


def case_studies_column() -> rx.Component:
    """Case study teaser and book-demo CTA for Solutions menu.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.elements.a(
            rx.el.span(
                "Case Studies",
                class_name="rule-dashed-b pb-4 font-mono font-[415] text-caption uppercase text-secondary-11",
            ),
            rx.el.div(
                rx.el.span(
                    "How Autodesk saved 25% of their development time",
                    class_name="text-lg font-[525] text-secondary-12 transition-colors group-hover:text-primary-10 dark:group-hover:text-primary-9",
                ),
                rx.el.div(
                    badge("Enterprise"),
                    badge("AI"),
                    class_name="flex flex-row gap-2",
                ),
                class_name="flex flex-col gap-2",
            ),
            href="/customers/",
            class_name="group flex flex-1 flex-col gap-4 p-8",
            custom_attrs={"aria-label": "View Autodesk case study"},
        ),
        rx.el.div(class_name="h-px shrink-0 bg-secondary-4"),
        demo_form_dialog(
            trigger=rx.el.div(
                rx.el.div(
                    "Book a Demo",
                    ui.icon(
                        "ArrowRight01Icon",
                        class_name="size-4 shrink-0",
                    ),
                    class_name="flex flex-row items-center gap-2 text-sm font-[525] text-secondary-12 transition-colors group-hover/demo:text-primary-10 dark:group-hover/demo:text-primary-9",
                ),
                rx.el.span(
                    "Reflex in action with your team.",
                    class_name="text-nowrap text-sm font-[475] text-secondary-11",
                ),
                class_name="group/demo flex cursor-pointer flex-col gap-1 p-8",
            ),
        ),
        class_name="z-[1] flex w-[296px] flex-col bg-secondary-1 dark:border-x dark:border-secondary-4",
    )


def solutions_content() -> rx.Component:
    """Mega-menu body for Solutions: industries, features, case studies.

    Returns:
        The component.
    """
    return menu_content(
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    solutions_column(
                        "Industries",
                        [
                            ("AI", "OfficeIcon", "/use-cases/"),
                            ("Finance", "Wallet05Icon", "/use-cases/finance/"),
                            ("Healthcare", "HealthIcon", "/use-cases/healthcare/"),
                            (
                                "Tech / SaaS",
                                "SourceCodeCircleIcon",
                                "/use-cases/consulting/",
                            ),
                            ("Government", "BankIcon", "/use-cases/government/"),
                        ],
                    ),
                    solutions_column(
                        "Features",
                        [
                            ("Security", "ShieldKeyIcon", "/docs/enterprise/overview/"),
                            (
                                "Auth",
                                "LoginMethodIcon",
                                "/docs/authentication/authentication-overview/",
                            ),
                            (
                                "Role-based access",
                                "UserUnlock01Icon",
                                "/docs/hosting/adding-members/",
                            ),
                            (
                                "On-prem & VPC Deploy",
                                "ServerStack01Icon",
                                "/blog/on-premises-deployment/",
                            ),
                            (
                                "Integrations",
                                "PlugSocketIcon",
                                "/docs/ai/integrations/overview/",
                            ),
                        ],
                    ),
                    class_name="grid grid-cols-2",
                ),
                class_name="p-4 flex flex-col bg-white-1 h-full w-[32rem] shadow-card dark:shadow-card-dark border-r border-secondary-4",
            ),
            case_studies_column(),
            class_name="flex flex-row",
        ),
    )


def resources_agent_column() -> rx.Component:
    """Agent onboarding links (agents, MCP, skills).

    Returns:
        The component.
    """
    return rx.el.div(
        nav_section_heading("Agent onboarding"),
        rx.el.div(
            solutions_row(
                "Agents",
                "RoboticIcon",
                "/docs/ai/integrations/mcp-installation/",
                trailing_pill="Overview",
            ),
            solutions_row(
                "MCP", "McpServerIcon", "/docs/ai/integrations/mcp-overview/"
            ),
            solutions_row("Skills", "ToolsIcon", "/docs/ai/integrations/skills/"),
            class_name="flex flex-col",
        ),
        class_name="flex flex-col gap-4",
    )


def resources_blog_column() -> rx.Component:
    """Recent posts list with link to the blog index.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.foreach(
            RecentBlogsState.posts[:2],
            blog_item,
        ),
        rx.el.elements.a(
            "Read All in Blog",
            ui.icon("ArrowRight01Icon", class_name="size-4 shrink-0"),
            href="/blog/",
            class_name="text-secondary-12 text-sm font-[525] flex items-center gap-2 hover:text-primary-10 dark:hover:text-primary-9 mt-auto pt-3",
        ),
        on_mount=RecentBlogsState.fetch_recent_blogs,
        class_name="flex flex-col gap-4 p-8 h-full justify-between border-l border-secondary-4",
    )


def resources_menu_footer() -> rx.Component:
    """Community links footer inside the Resources mega-menu.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.div(
            rx.el.elements.a(
                get_icon(
                    "github_navbar",
                    class_name="size-[18px] shrink-0 text-secondary-12 group-hover:text-primary-10 dark:group-hover:text-primary-9",
                ),
                "GitHub",
                href=GITHUB_URL,
                target="_blank",
                class_name="flex flex-row items-center gap-2 text-sm font-medium text-secondary-12 hover:text-primary-10 dark:hover:text-primary-9 group",
            ),
            rx.el.elements.a(
                get_icon(
                    "discord_navbar",
                    class_name="size-[18px] shrink-0 text-secondary-12 group-hover:text-primary-10 dark:group-hover:text-primary-9",
                ),
                "Discord",
                href=DISCORD_URL,
                target="_blank",
                class_name="flex flex-row items-center gap-2 text-sm font-medium text-secondary-12 hover:text-primary-10 dark:hover:text-primary-9 group",
            ),
            class_name="flex flex-row items-center gap-8 px-6 py-3",
        ),
        class_name="flex flex-col w-full shrink-0 bg-white-1 border-t border-secondary-4",
    )


def resources_content() -> rx.Component:
    """Mega-menu body for Resources: learn, agents, blog.

    Returns:
        The component.
    """
    return menu_content(
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.el.div(
                        solutions_column(
                            "Learn",
                            [
                                ("Documentation", "File02Icon", "/docs/"),
                                ("Templates", "Layout02Icon", "/templates/"),
                                ("Changelog", "Clock02Icon", CHANGELOG_URL),
                            ],
                        ),
                        resources_agent_column(),
                        class_name="grid grid-cols-2 min-w-0 p-4 flex-1",
                    ),
                    resources_menu_footer(),
                    class_name="flex min-w-0 flex-col bg-white-1",
                ),
                resources_blog_column(),
                class_name="grid grid-cols-1 min-[480px]:grid-cols-[minmax(0,1fr)_min(17.5rem,40%)] h-full",
            ),
            class_name="flex flex-col w-[728px] max-w-full overflow-hidden rounded-xl bg-secondary-1 dark:shadow-card-dark",
        ),
    )


def navigation_menu(*, show_banner: bool = True) -> rx.Component:
    """Desktop navigation: mega-menus, CTAs, and GitHub.

    Args:
        show_banner: Whether the navbar includes the hosting banner.

    Returns:
        The component.
    """
    return ui.navigation_menu.root(
        ui.navigation_menu.list(
            menu_trigger("Products", products_content()),
            menu_trigger("Resources", resources_content()),
            menu_trigger("Solutions", solutions_content()),
            ui.navigation_menu.item(
                rx.el.elements.a(
                    marketing_button(
                        "Pricing",
                        size="sm",
                        variant="ghost",
                        native_button=False,
                    ),
                    href="/pricing/",
                ),
                class_name="xl:flex hidden px-1",
                custom_attrs={"role": "menuitem"},
            ),
            ui.navigation_menu.item(
                rx.el.elements.a(
                    marketing_button(
                        "Docs",
                        size="sm",
                        variant="ghost",
                    ),
                    href="/docs/",
                ),
                class_name="xl:flex hidden px-1",
                custom_attrs={"role": "menuitem"},
            ),
            class_name="flex flex-row items-center m-0 h-full list-none",
            custom_attrs={"role": "menubar"},
        ),
        ui.navigation_menu.list(
            ui.navigation_menu.item(
                github(),
                custom_attrs={"role": "menuitem"},
            ),
            ui.navigation_menu.item(
                rx.el.elements.a(
                    marketing_button(
                        "Sign In",
                        ui.icon("Login01Icon", class_name="scale-x-[-1]"),
                        size="sm",
                        variant="outline",
                        native_button=False,
                    ),
                    href=REFLEX_BUILD_LOGIN_URL,
                    target="_blank",
                ),
                custom_attrs={"role": "menuitem"},
            ),
            ui.navigation_menu.item(
                demo_form_dialog(
                    trigger=marketing_button(
                        "Book a Demo",
                        size="sm",
                        variant="primary",
                        class_name="whitespace-nowrap",
                        native_button=False,
                    ),
                ),
                class_name="max-xl:hidden",
                unstyled=True,
                custom_attrs={"role": "menuitem"},
            ),
            ui.navigation_menu.item(
                navbar_sidebar_button(show_banner=show_banner),
                class_name="xl:hidden flex",
                unstyled=True,
                custom_attrs={"role": "menuitem"},
            ),
            class_name="flex flex-row gap-4 m-0 h-full list-none items-center",
            custom_attrs={"role": "menubar"},
        ),
        ui.navigation_menu.portal(
            ui.navigation_menu.positioner(
                ui.navigation_menu.popup(
                    ui.navigation_menu.viewport(
                        unstyled=True,
                        class_name="relative h-full w-full overflow-hidden rounded-[inherit]",
                    ),
                    unstyled=True,
                    class_name="relative h-[var(--popup-height)] w-[var(--popup-width)] origin-[var(--transform-origin)] rounded-xl bg-secondary-1 navbar-shadow transition-[opacity,transform,width,height,scale,translate] duration-150 ease-[cubic-bezier(0.22,1,0.36,1)] data-[ending-style]:ease-[ease] data-[ending-style]:scale-90 data-[ending-style]:opacity-0 data-[ending-style]:duration-150 data-[starting-style]:scale-90 data-[starting-style]:opacity-0",
                ),
                unstyled=True,
                class_name="safari-nav-positioner box-border h-[var(--positioner-height)] w-[var(--positioner-width)] max-w-[var(--available-width)] transition-[top,left,right,bottom] duration-[0.35s] ease-[cubic-bezier(0.22,1,0.36,1)] data-[instant]:transition-none",
                side_offset=30,
                align="start",
                align_offset=-109,
                position_method="fixed",
            ),
        ),
        delay=0,
        close_delay=150,
        unstyled=True,
        class_name="group/navigation-menu relative flex w-full items-center h-full justify-between gap-6 mx-auto flex-row",
    )


_NAVBAR_WRAPPER_CLASS = "flex flex-col w-full top-0 z-[9999] fixed self-center"


def _navbar_header_content(*, show_banner: bool) -> rx.Component:
    """Render the logo and navigation menu for a banner configuration.

    Args:
        show_banner: Whether the navbar includes the hosting banner.

    Returns:
        The component.
    """
    return rx.el.header(
        rx.el.div(
            logo(),
            navigation_menu(show_banner=show_banner),
            class_name="mx-auto flex h-full w-full max-w-[96.5rem] flex-row items-center px-gutter",
            custom_attrs={"data-navbar-inner": ""},
        ),
        class_name="w-full h-[4.5rem] backdrop-blur-[16px] border-b border-secondary-4 bg-gradient-to-b from-secondary-2 to-secondary-1",
    )


@rx.memo
def _navbar_header() -> rx.Component:
    """Render the memoized navbar header used with the hosting banner.

    Returns:
        The component.
    """
    return _navbar_header_content(show_banner=True)


@rx.memo
def _bannerless_navbar_header() -> rx.Component:
    """Render the memoized bannerless navbar header used by the 404 page.

    Returns:
        The component.
    """
    return _navbar_header_content(show_banner=False)


@rx.memo
def _default_marketing_navbar() -> rx.Component:
    """Marketing navbar with the default shared hosting banner, memoized so it
    is emitted once across the many pages that use the default banner.

    Returns:
        The component.
    """
    from reflex_site_shared.views.hosting_banner import hosting_banner

    return rx.el.div(
        hosting_banner(),
        _navbar_header(),
        class_name=_NAVBAR_WRAPPER_CLASS,
    )


def marketing_navbar(
    banner: rx.Component | None = None, *, show_banner: bool = True
) -> rx.Component:
    """Fixed header: hosting banner plus logo and full navigation.

    Args:
        banner: Banner to render above the header. Defaults to the shared
            hosting banner.
        show_banner: Whether to render a banner. Set to false for the compact
            navbar used on the 404 page.

    Returns:
        The component.
    """
    if not show_banner:
        return rx.el.div(
            _bannerless_navbar_header(),
            class_name=_NAVBAR_WRAPPER_CLASS,
        )

    if banner is None:
        return _default_marketing_navbar()

    return rx.el.div(
        banner,
        _navbar_header(),
        class_name=_NAVBAR_WRAPPER_CLASS,
    )
