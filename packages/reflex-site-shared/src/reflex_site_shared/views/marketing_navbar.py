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
    REFLEX_BUILD_URL,
)
from reflex_site_shared.views.sidebar import navbar_sidebar_button
from reflex_site_shared.views.workflow_stage import (
    workflow_stage_image,
    workflow_stage_row,
)


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
            "data-[motion^=from-]:animate-in data-[motion^=to-]:animate-out data-[motion^=from-]:fade-in data-[motion^=to-]:fade-out data-[motion=from-end]:slide-in-from-right-52 data-[motion=from-start]:slide-in-from-left-52 data-[motion=to-end]:slide-out-to-right-52 data-[motion=to-start]:slide-out-to-left-52 ease-[cubic-bezier(0.22,1,0.36,1)] group-data-[viewport=false]/navigation-menu:data-open:zoom-in-95 group-data-[viewport=false]/navigation-menu:data-closed:zoom-out-95 group-data-[viewport=false]/navigation-menu:data-open:fade-in-0 group-data-[viewport=false]/navigation-menu:data-closed:fade-out-0 group-data-[viewport=false]/navigation-menu:duration-300 data-[ending-style]:data-[activation-direction=left]:translate-x-[50%] data-[ending-style]:data-[activation-direction=right]:translate-x-[-50%] data-[starting-style]:data-[activation-direction=left]:translate-x-[-50%] data-[starting-style]:data-[activation-direction=right]:translate-x-[50%] w-max transition-[opacity,transform,translate] duration-[0.35s] data-[ending-style]:opacity-0 data-[starting-style]:opacity-0 **:data-[slot=navigation-menu-link]:focus:ring-0 **:data-[slot=navigation-menu-link]:focus:outline-none",
            "flex flex-row rounded-xl font-sans p-0",
            class_name,
        ),
        keep_mounted=True,
    )


def products_column_gutter() -> rx.Component:
    """Vertical separator between product mega-menu columns.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.div(
            class_name="pointer-events-none absolute top-0 left-0 h-12 w-full border-b border-secondary-4",
        ),
        role="presentation",
        class_name="w-8 shrink-0 bg-secondary-1 border-secondary-4 border-x relative",
    )


def products_iterate_column_body() -> rx.Component:
    """Iterate stage column: framework pitch and GitHub link.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.elements.a(
            rx.el.div(
                rx.el.span(
                    "Framework",
                    class_name="text-base font-[525] text-secondary-12 group-hover:text-primary-10 dark:group-hover:text-primary-9 transition-colors",
                ),
                badge("Open source"),
                class_name="flex flex-row items-center gap-2.5",
            ),
            rx.el.p(
                "The full-stack Python framework, optimized to build with AI agents—apps that can be used by humans and agents alike.",
                class_name="text-secondary-11 text-sm font-[475]",
            ),
            href="/open-source/",
            class_name="group flex flex-col gap-2 items-center text-center",
        ),
        rx.el.elements.a(
            get_icon(
                "github_navbar",
                class_name="size-[18px] shrink-0 text-secondary-12 group-hover:text-primary-10 dark:group-hover:text-primary-9",
            ),
            "View on GitHub",
            ui.icon("ArrowUpRight03Icon", class_name="size-3 shrink-0 -ml-1.75"),
            href=GITHUB_URL,
            target="_blank",
            class_name="flex flex-row items-center gap-2 text-sm font-medium text-secondary-12 hover:text-primary-10 dark:hover:text-primary-9 group mt-auto",
        ),
        class_name="flex flex-col p-6 text-center justify-center items-center min-h-[252px] h-full",
    )


def products_ship_column_body() -> rx.Component:
    """Ship stage column: deploy messaging and illustration.

    Returns:
        The component.
    """
    return rx.el.elements.a(
        rx.el.div(
            rx.el.span(
                "Deploy, monitor & scale",
                class_name="text-base font-[525] text-secondary-12 group-hover:text-primary-10 dark:group-hover:text-primary-9 transition-colors",
            ),
            class_name="flex flex-row items-center gap-2.5 px-6 pt-6",
        ),
        rx.el.p(
            "One click to enterprise-grade infrastructure. Track, version, and grow across teams.",
            class_name="text-secondary-11 text-sm font-[475] px-6",
        ),
        rx.el.div(
            rx.image(
                src=f"{REFLEX_ASSETS_CDN}landing/features/{rx.color_mode_cond('light', 'dark')}/ship_navbar_3.svg",
                alt="Deploy, monitor & scale",
                loading="lazy",
                class_name="h-auto w-full max-w-full object-cover",
            ),
            class_name="flex w-full mt-auto",
        ),
        href="/hosting/",
        class_name="group flex flex-col gap-2 text-center justify-center items-center min-h-[252px]",
    )


def products_build_column_body() -> rx.Component:
    """Build stage column: AI builder and agent toolkit teaser.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.elements.a(
            rx.el.div(
                rx.el.span(
                    "AI app builder",
                    class_name="text-base font-[525] text-secondary-12 group-hover:text-primary-10 dark:group-hover:text-primary-9 transition-colors",
                ),
                badge("New"),
                class_name="flex flex-row items-center gap-2.5 px-6 pt-6",
            ),
            rx.el.p(
                "Describe it, Reflex builds it.",
                class_name="text-secondary-11 text-sm font-[475] px-6 pb-6",
            ),
            href=REFLEX_BUILD_URL,
            target="_blank",
            class_name="group flex flex-col gap-2 items-center text-center",
        ),
        rx.el.div(
            get_icon(
                "arrow_turn", class_name="shrink-0 text-secondary-10 -translate-y-0.75"
            ),
            rx.el.span(
                "OR",
                class_name="px-2 font-mono text-xs font-[415] uppercase text-secondary-12",
            ),
            get_icon(
                "arrow_turn",
                class_name="shrink-0 text-secondary-10 rotate-180 translate-y-0.75",
            ),
            class_name="flex w-full shrink-0 items-center justify-center py-3 border-y border-secondary-4 px-6 bg-secondary-1",
        ),
        rx.el.elements.a(
            rx.el.div(
                rx.el.span(
                    "Agent Toolkit",
                    class_name="text-base font-[525] text-secondary-12 group-hover:text-primary-10 dark:group-hover:text-primary-9 transition-colors",
                ),
                class_name="flex flex-row items-center gap-2.5 px-6 pt-6",
            ),
            rx.el.p(
                "Get started with our MCP and Skills.",
                class_name="text-secondary-11 text-sm font-[475] px-6 pb-6",
            ),
            href="/docs/ai/integrations/ai-onboarding/",
            class_name="group flex flex-col gap-2 items-center text-center",
        ),
        class_name="flex flex-col text-center justify-center items-center min-h-[252px]",
    )


def products_content() -> rx.Component:
    """Mega-menu body for Products: build, iterate, ship columns.

    Returns:
        The component.
    """
    return menu_content(
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    workflow_stage_row(
                        "Build", right=workflow_stage_image(sweep_index=0)
                    ),
                    products_build_column_body(),
                    class_name="flex min-w-0 flex-1 shrink-0 flex-col",
                ),
                products_column_gutter(),
                rx.el.div(
                    workflow_stage_row(
                        "Iterate",
                        left=workflow_stage_image(size="small", sweep_index=1),
                        right=workflow_stage_image(size="small", sweep_index=2),
                    ),
                    products_iterate_column_body(),
                    class_name="flex min-w-0 flex-1 shrink-0 flex-col",
                ),
                products_column_gutter(),
                rx.el.div(
                    workflow_stage_row(
                        "Ship", left=workflow_stage_image(sweep_index=3)
                    ),
                    products_ship_column_body(),
                    class_name="flex min-w-0 flex-1 shrink-0 flex-col",
                ),
                class_name="flex min-h-0 w-full flex-row bg-white-1",
            ),
            products_menu_footer(),
            class_name="flex max-w-[min(100vw-2rem,1240px)] w-[1240px] flex-col overflow-hidden rounded-xl bg-secondary-1 dark:shadow-card-dark",
        ),
        class_name="p-0",
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
        rx.el.div(
            rx.el.span(
                title,
                class_name="font-mono font-[415] text-[0.75rem] leading-4 uppercase pb-4 border-b border-dashed border-secondary-6 text-secondary-11",
            ),
            class_name="px-4 pt-4 flex flex-col",
        ),
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
                class_name="text-secondary-11 text-xs font-[415] font-mono uppercase text-nowrap",
            ),
            rx.image(
                src=f"{REFLEX_ASSETS_CDN}common/{rx.color_mode_cond('light', 'dark')}/squares_blog.svg",
                class_name="pointer-events-none",
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
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    "Case Studies",
                    class_name="font-mono font-[415] text-[0.75rem] leading-4 uppercase pb-4 border-b border-dashed border-secondary-6 text-secondary-11",
                ),
                class_name="px-4 pt-4 flex flex-col",
            ),
            rx.el.div(
                rx.el.elements.a(
                    "How Autodesk saved 25% of their development time",
                    href="/customers/autodesk/",
                    class_name="text-secondary-12 text-lg font-[525] hover:text-primary-10 dark:hover:text-primary-9 mt-auto",
                ),
                rx.el.div(
                    badge("Enterprise"),
                    badge("AI"),
                    class_name="flex flex-row gap-2",
                ),
                class_name="flex flex-col gap-2 px-4 pb-4",
            ),
            rx.el.div(
                class_name="h-px w-[calc(100%+2rem)] -mx-4 shrink-0 bg-secondary-4",
            ),
            rx.el.div(
                demo_form_dialog(
                    trigger=rx.el.div(
                        rx.el.div(
                            "Book a Demo",
                            ui.icon(
                                "ArrowRight01Icon",
                                class_name="size-5",
                                stroke_width=1.5,
                            ),
                            class_name="flex flex-row items-center justify-between text-sm font-[525] text-secondary-12",
                        ),
                        rx.el.span(
                            "Reflex in action with your team.",
                            class_name="text-secondary-11 text-sm font-[475]",
                        ),
                        class_name="flex flex-col px-4 py-2 rounded-sm hover-card-shadow cursor-pointer ",
                    ),
                ),
            ),
            class_name="flex flex-col relative h-full justify-between",
        ),
        class_name="p-4 block z-[1] bg-secondary-1 dark:border-x dark:border-secondary-4 w-[296px]",
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
                class_name="p-4 flex flex-col bg-white-1 h-full w-[28rem] shadow-card dark:shadow-card-dark border-r border-secondary-4",
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
        rx.el.div(
            rx.el.span(
                "Agent onboarding",
                class_name="font-mono font-[415] text-[0.75rem] leading-4 uppercase pb-4 border-b border-dashed border-secondary-6 text-secondary-11",
            ),
            class_name="px-4 pt-4 flex flex-col",
        ),
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
            href="/blog",
            class_name="text-secondary-12 text-sm font-[525] flex items-center gap-1.5 hover:text-primary-10 dark:hover:text-primary-9 mt-auto pt-3",
        ),
        on_mount=RecentBlogsState.fetch_recent_blogs,
        class_name="flex flex-col gap-4 p-8 h-full justify-between border-l border-secondary-4",
    )


def products_menu_footer() -> rx.Component:
    """Footer links inside the Products mega-menu.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.div(
            rx.el.elements.a(
                get_icon(
                    "docs",
                    class_name="size-[18px] shrink-0 text-secondary-12 group-hover:text-primary-10 dark:group-hover:text-primary-9",
                ),
                "View All Docs",
                ui.icon("ArrowUpRight03Icon", class_name="size-3 shrink-0 -ml-1.75"),
                href="/docs/",
                target="_blank",
                class_name="flex flex-row items-center gap-2 text-sm font-medium text-secondary-12 hover:text-primary-10 dark:hover:text-primary-9 group",
            ),
            rx.el.elements.a(
                get_icon(
                    "reflex_small",
                    class_name="size-[18px] shrink-0 text-secondary-12 group-hover:text-primary-10 dark:group-hover:text-primary-9",
                ),
                "Get started for free",
                ui.icon("ArrowUpRight03Icon", class_name="size-3 shrink-0 -ml-1.75"),
                href=REFLEX_BUILD_URL,
                target="_blank",
                class_name="flex flex-row items-center gap-2 text-sm font-medium text-secondary-12 hover:text-primary-10 dark:hover:text-primary-9 group",
            ),
            class_name="flex flex-row items-center gap-8 px-6 py-3",
        ),
        class_name="flex flex-col w-full shrink-0 bg-white-1 border-t border-secondary-4",
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
                        rx.el.div(
                            solutions_column(
                                "Learn",
                                [
                                    ("Documentation", "File02Icon", "/docs"),
                                    ("Templates", "Layout02Icon", "/templates"),
                                    ("Changelog", "Clock02Icon", CHANGELOG_URL),
                                ],
                            ),
                            resources_agent_column(),
                            class_name="grid grid-cols-2 gap-8 min-w-0 p-5 bg-white-1 flex-1",
                        ),
                        resources_menu_footer(),
                        class_name="flex flex-col min-w-0 h-full",
                    ),
                    resources_blog_column(),
                    class_name="grid grid-cols-1 min-[480px]:grid-cols-[minmax(0,1fr)_min(17.5rem,40%)] h-full",
                ),
                class_name="flex flex-col w-[728px] max-w-full overflow-hidden rounded-xl bg-secondary-1 dark:shadow-card-dark",
            ),
            class_name="p-0",
        ),
    )


def navigation_menu() -> rx.Component:
    """Desktop navigation: mega-menus, CTAs, and GitHub.

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
                        "Enterprise",
                        size="sm",
                        variant="ghost",
                    ),
                    href="/docs/enterprise/overview/",
                ),
                class_name="xl:flex hidden px-1",
                custom_attrs={"role": "menuitem"},
            ),
            ui.navigation_menu.item(
                rx.el.elements.a(
                    marketing_button(
                        "Pricing",
                        size="sm",
                        variant="ghost",
                        native_button=False,
                    ),
                    href="/pricing",
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
                    href="/docs",
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
                    href=REFLEX_BUILD_URL,
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
                        class_name=" whitespace-nowrap max-xl:hidden",
                        native_button=False,
                    ),
                ),
                unstyled=True,
                class_name="xl:flex hidden",
                custom_attrs={"role": "menuitem"},
            ),
            ui.navigation_menu.item(
                navbar_sidebar_button(),
                class_name="xl:hidden flex",
                unstyled=True,
                custom_attrs={"role": "menuitem"},
            ),
            class_name="flex flex-row lg:gap-4 gap-2 m-0 h-full list-none items-center",
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
        unstyled=True,
        class_name="group/navigation-menu relative flex w-full items-center h-full justify-between gap-6 mx-auto flex-row",
    )


@rx.memo
def marketing_navbar() -> rx.Component:
    """Fixed header: hosting banner plus logo and full navigation.

    Returns:
        The component.
    """
    from reflex_site_shared.views.hosting_banner import hosting_banner

    return rx.el.div(
        hosting_banner(),
        rx.el.header(
            logo(),
            navigation_menu(),
            class_name="w-full max-w-[81rem] h-[4.5rem] mx-auto flex flex-row items-center p-5 rounded-b-xl backdrop-blur-[16px] shadow-[0_-2px_2px_1px_rgba(0,0,0,0.02),0_1px_1px_0_rgba(0,0,0,0.08),0_4px_8px_0_rgba(0,0,0,0.03),0_0_0_1px_#FFF_inset] dark:shadow-none dark:border-x dark:border-b dark:border-m-slate-10 bg-gradient-to-b from-white to-m-slate-1 dark:from-m-slate-11 dark:to-m-slate-12",
        ),
        class_name="flex flex-col w-full top-0 z-[9999] fixed self-center",
    )
