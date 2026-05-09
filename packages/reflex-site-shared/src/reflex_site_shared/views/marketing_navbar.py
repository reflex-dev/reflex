"""Marketing Navbar module."""

import reflex_components_internal as ui
from reflex_components_internal.blocks.demo_form import demo_form_dialog

import reflex as rx
from reflex_site_shared.backend.get_blogs import BlogPostDict, RecentBlogsState
from reflex_site_shared.components.icons import get_icon
from reflex_site_shared.components.marketing_button import button as marketing_button
from reflex_site_shared.components.marquee import marquee
from reflex_site_shared.constants import (
    CHANGELOG_URL,
    CONTRIBUTING_URL,
    DISCUSSIONS_URL,
    GITHUB_STARS,
    GITHUB_URL,
    JOBS_BOARD_URL,
    REFLEX_ASSETS_CDN,
    REFLEX_BUILD_URL,
)
from reflex_site_shared.views.sidebar import navbar_sidebar_button


def social_proof_card(image: str) -> rx.Component:
    """Social proof card.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.image(
            f"{REFLEX_ASSETS_CDN}companies/{rx.color_mode_cond('light', 'dark')}/{image}_small.svg",
            loading="lazy",
            alt=f"{image} logo",
            class_name="w-auto h-fit pointer-events-none",
        ),
        class_name="flex justify-center items-center px-3",
    )


def logos_carousel() -> rx.Component:
    """Logos carousel.

    Returns:
        The component.
    """
    logos = [
        "agricole",
        "man",
        "shell",
        "red_hat",
        "accenture",
        "dell",
        "microsoft",
        "world",
        "ford",
        "unicef",
        "nike",
    ]
    return marquee(
        *[social_proof_card(logo) for logo in logos],
        direction="left",
        gradient_color="light-dark(var(--c-white-1), var(--c-m-slate-11))",
        class_name="h-[1.625rem] w-full overflow-hidden mt-auto",
        gradient_width=65,
        speed=25,
        pause_on_hover=False,
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
    """Menu content.

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


def platform_item(image: str, title: str, description: str, href: str) -> rx.Component:
    """Platform item.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.image(
            src=f"{REFLEX_ASSETS_CDN}common/{rx.color_mode_cond('light', 'dark')}/{image}",
            alt=title,
            class_name="size-18",
        ),
        rx.el.div(
            rx.el.span(
                title,
                class_name="dark:text-m-slate-3 text-m-slate-12 text-sm font-[525]",
            ),
            rx.el.span(
                description,
                class_name="dark:text-m-slate-6 text-m-slate-7 text-sm font-[475]",
            ),
            class_name="flex flex-col",
        ),
        rx.el.elements.a(class_name="absolute inset-0", href=href),
        class_name="p-4 flex flex-row gap-6 relative cursor-pointer rounded-sm hover-card-shadow",
    )


def platform_content() -> rx.Component:
    """Platform content.

    Returns:
        The component.
    """
    return menu_content(
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.el.div(
                        rx.el.span(
                            "AI Builder",
                            class_name="dark:text-m-slate-3 text-m-slate-12 text-lg font-semibold mb-2",
                        ),
                        rx.el.span(
                            "Build production-ready web apps for your team in seconds with AI-powered code generation.",
                            class_name="dark:text-m-slate-6 text-m-slate-7 text-sm font-medium",
                        ),
                        class_name="p-4 flex flex-col relative hover-card-shadow rounded-md",
                    ),
                    rx.image(
                        src=f"{REFLEX_ASSETS_CDN}common/{rx.color_mode_cond('light', 'dark')}/ai_builder_pattern.svg",
                        alt="AI Builder Navbar Pattern",
                        class_name="pointer-events-none",
                    ),
                    rx.el.elements.a(
                        class_name="absolute inset-0",
                        href=REFLEX_BUILD_URL,
                        target="_blank",
                    ),
                    class_name="relative flex flex-col hover-card-shadow rounded-md",
                ),
                class_name="p-4 flex flex-col rounded-xl bg-white-1 dark:bg-m-slate-11 h-full shadow-card dark:shadow-card-dark dark:border-r dark:border-m-slate-9",
            ),
            rx.el.div(
                platform_item(
                    "framework_pixel.svg",
                    "Reflex Framework",
                    "Iterate on full-stack apps in pure Python. No JavaScript required.",
                    "/open-source/",
                ),
                platform_item(
                    "cloud_pixel.svg",
                    "Cloud Hosting",
                    "Deploy your app with a single command to Reflex Cloud.",
                    "/hosting/",
                ),
                rx.el.div(
                    rx.el.span(
                        "Reflex Is The Operating System ",
                        rx.el.br(),
                        " for Enterprise Apps",
                        class_name="dark:text-m-slate-6 text-m-slate-7 font-mono font-[415] text-[0.75rem] leading-4.5 uppercase",
                    ),
                    rx.image(
                        src=f"{REFLEX_ASSETS_CDN}common/{rx.color_mode_cond('light', 'dark')}/squares_navbar.svg",
                        alt="Squares Navbar",
                        class_name="absolute bottom-4 right-4 pointer-events-none",
                    ),
                    class_name="relative p-4",
                ),
                class_name="p-4 flex flex-col h-full",
            ),
            class_name="w-[46.5rem] grid grid-cols-2",
        ),
    )


def solutions_item(title: str, icon: str, href: str) -> rx.Component:
    """Solutions item.

    Returns:
        The component.
    """
    return rx.el.elements.a(
        ui.icon(
            icon,
            class_name="shrink-0 text-m-slate-7 dark:text-m-slate-6 size-4.5",
        ),
        title,
        href=href,
        class_name="flex flex-row px-4 py-2 rounded-sm text-sm font-[525] text-m-slate-12 dark:text-m-slate-3 gap-3 items-center justify-start cursor-pointer hover-card-shadow",
    )


def solutions_column(title: str, items: list[tuple[str, str, str]]) -> rx.Component:
    """Solutions column.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                title,
                class_name="font-mono font-[415] text-[0.75rem] leading-4 uppercase pb-4 border-b border-dashed dark:border-m-slate-8 border-m-slate-6 dark:text-m-slate-6 text-m-slate-7",
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
    """Blog item.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.div(
            rx.moment(
                post["date"],
                format="MMM DD YYYY",
                class_name="text-m-slate-7 dark:text-m-slate-6 text-xs font-[415] font-mono uppercase text-nowrap",
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
            class_name="dark:text-m-slate-3 text-m-slate-12 text-sm font-[525] group-hover:text-primary-10 dark:group-hover:text-primary-9 line-clamp-3",
        ),
        rx.el.elements.a(
            href=post["url"],
            class_name="absolute inset-0",
        ),
        class_name="relative group flex flex-col gap-2 mb-2",
    )


def blog_column() -> rx.Component:
    """Blog column.

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
            ui.icon("ArrowRight01Icon", class_name="ml-auto"),
            href="/blog",
            class_name="dark:text-m-slate-3 text-m-slate-12 text-sm font-[525] h-10 flex items-center justify-start gap-2 hover:text-primary-10 dark:hover:text-primary-9 mt-auto",
        ),
        on_mount=RecentBlogsState.fetch_recent_blogs,
        class_name="flex flex-col gap-6 p-4 h-full",
    )


def customers_column() -> rx.Component:
    """Customers column.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    "Customers",
                    class_name="font-mono font-[415] text-[0.75rem] leading-4 uppercase pb-4 border-b border-dashed dark:border-m-slate-8 border-m-slate-6 dark:text-m-slate-6 text-m-slate-7",
                ),
                class_name="px-4 pt-4 flex flex-col",
            ),
            rx.el.div(
                rx.el.span(
                    "Read Stories How Teams Use Reflex",
                    class_name="text-m-slate-12 dark:text-m-slate-3 text-lg font-[575]",
                ),
                rx.el.span(
                    "Discover how companies build internal tools, AI apps, and production dashboards in pure Python.",
                    class_name="text-m-slate-7 dark:text-m-slate-6 text-sm font-[475]",
                ),
                logos_carousel(),
                class_name="flex flex-col gap-2 px-4 pb-4 h-full",
            ),
            rx.el.elements.a(class_name="absolute inset-0", href="/customers/"),
            class_name="flex flex-col gap-6 hover-card-shadow rounded-lg relative h-full hover:[--m-slate-11:var(--m-slate-10)] hover:shadow-card dark:hover:shadow-card-dark",
        ),
        class_name="p-4 block rounded-lg shadow-card dark:shadow-card-dark z-[1] bg-white-1 dark:bg-m-slate-11 dark:border-x dark:border-m-slate-9",
    )


def solutions_content() -> rx.Component:
    """Solutions content.

    Returns:
        The component.
    """
    return menu_content(
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    solutions_column(
                        "Who's It For",
                        [
                            ("Executives", "LocationUser01Icon", "/use-cases/"),
                            ("Developers", "SourceCodeSquareIcon", "/use-cases/"),
                            ("Data Teams", "DatabaseIcon", "/use-cases/"),
                            (
                                "Non Technical",
                                "CursorCircleSelection02Icon",
                                "/use-cases/",
                            ),
                        ],
                    ),
                    solutions_column(
                        "Industries",
                        [
                            ("Enterprise", "OfficeIcon", "/use-cases/"),
                            ("Finance", "Wallet05Icon", "/use-cases/finance/"),
                            ("Healthcare", "HealthIcon", "/use-cases/healthcare/"),
                            (
                                "Consulting",
                                "DocumentValidationIcon",
                                "/use-cases/consulting/",
                            ),
                            (
                                "Government",
                                "BankIcon",
                                "/use-cases/government/",
                            ),
                        ],
                    ),
                    class_name="grid grid-cols-2",
                ),
                class_name="p-4 flex flex-col rounded-xl bg-white-1 dark:bg-m-slate-11 h-full w-[28rem] shadow-card dark:shadow-card-dark dark:border-r dark:border-m-slate-9",
            ),
            rx.el.div(
                solutions_column(
                    "Migration",
                    [
                        (
                            "Switch from No Code",
                            "WebDesign01Icon",
                            "/migration/no-code/",
                        ),
                        (
                            "Switch from Low Code",
                            "SourceCodeSquareIcon",
                            "/migration/low-code/",
                        ),
                        (
                            "Switch from Other Frameworks",
                            "CodeIcon",
                            "/migration/other-frameworks/",
                        ),
                        (
                            "Switch from Other AI tools",
                            "ArtificialIntelligence04Icon",
                            "/migration/other-ai-tools/",
                        ),
                    ],
                ),
                class_name="p-4 flex flex-col h-full",
            ),
            class_name="flex flex-row",
        ),
    )


def resources_content() -> rx.Component:
    """Resources content.

    Returns:
        The component.
    """
    return menu_content(
        rx.el.div(
            rx.el.div(
                solutions_column(
                    "Developers",
                    [
                        ("Templates", "Layout02Icon", "/templates/"),
                        (
                            "Integrations",
                            "PlugSocketIcon",
                            "/docs/ai-builder/integrations/overview/",
                        ),
                        ("Changelog", "Clock02Icon", CHANGELOG_URL),
                        ("Contributing", "GitCommitIcon", CONTRIBUTING_URL),
                        ("Discussion", "BubbleChatIcon", DISCUSSIONS_URL),
                        ("FAQ", "HelpSquareIcon", "/faq/"),
                    ],
                ),
                class_name="p-4 flex flex-col rounded-xl bg-m-slate-1 dark:bg-m-slate-12 h-full",
            ),
            customers_column(),
            rx.el.div(
                blog_column(),
                class_name="p-4 flex flex-col h-full bg-m-slate-1 dark:bg-m-slate-12",
            ),
            class_name="w-[52.5rem] grid grid-cols-3",
        ),
    )


def about_content() -> rx.Component:
    """About content.

    Returns:
        The component.
    """
    return menu_content(
        rx.el.div(
            rx.el.div(
                solutions_item("Company", "Profile02Icon", "/about/"),
                solutions_item("Careers", "WorkIcon", JOBS_BOARD_URL),
                class_name="p-4 flex flex-col rounded-xl bg-white-1 h-full dark:shadow-none dark:border dark:border-m-slate-9 dark:bg-m-slate-11 shadow-card",
            ),
            class_name="w-[12.5rem]",
        ),
    )


def navigation_menu() -> rx.Component:
    """Navigation menu.

    Returns:
        The component.
    """
    return ui.navigation_menu.root(
        ui.navigation_menu.list(
            menu_trigger("Platform", platform_content()),
            menu_trigger("Solutions", solutions_content()),
            menu_trigger("Resources", resources_content()),
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
            menu_trigger("About", about_content()),
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
                    class_name="relative h-[var(--popup-height)] w-[var(--popup-width)] origin-[var(--transform-origin)] rounded-xl bg-m-slate-1 dark:bg-m-slate-12 navbar-shadow transition-[opacity,transform,width,height,scale,translate] duration-150 ease-[cubic-bezier(0.22,1,0.36,1)] data-[ending-style]:ease-[ease] data-[ending-style]:scale-90 data-[ending-style]:opacity-0 data-[ending-style]:duration-150 data-[starting-style]:scale-90 data-[starting-style]:opacity-0",
                ),
                unstyled=True,
                class_name="safari-nav-positioner box-border h-[var(--positioner-height)] w-[var(--positioner-width)] max-w-[var(--available-width)] transition-[top,left,right,bottom] duration-[0.35s] ease-[cubic-bezier(0.22,1,0.36,1)] data-[instant]:transition-none",
                side_offset=30,
                align="start",
                align_offset=-20,
                position_method="fixed",
            ),
        ),
        unstyled=True,
        class_name="group/navigation-menu relative flex w-full items-center h-full justify-between gap-6 mx-auto flex-row",
    )


@rx.memo
def marketing_navbar() -> rx.Component:
    """Marketing navbar.

    Returns:
        The component.
    """
    from reflex_site_shared.views.hosting_banner import hosting_banner

    return rx.el.div(
        hosting_banner(),
        rx.el.header(
            logo(),
            navigation_menu(),
            class_name="w-full max-w-[71.5rem] h-[4.5rem] mx-auto flex flex-row items-center p-5 rounded-b-xl backdrop-blur-[16px] shadow-[0_-2px_2px_1px_rgba(0,0,0,0.02),0_1px_1px_0_rgba(0,0,0,0.08),0_4px_8px_0_rgba(0,0,0,0.03),0_0_0_1px_#FFF_inset] dark:shadow-none dark:border-x dark:border-b dark:border-m-slate-10 bg-gradient-to-b from-white to-m-slate-1 dark:from-m-slate-11 dark:to-m-slate-12",
        ),
        class_name="flex flex-col w-full top-0 z-[9999] fixed self-center",
    )
