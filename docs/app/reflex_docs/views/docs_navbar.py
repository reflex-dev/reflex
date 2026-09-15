import reflex as rx
import reflex_components_internal as ui
from reflex_components_internal.blocks.demo_form import (
    demo_form_dialog,
    demo_form_open_cs,
)
from reflex_site_shared.components.docs_shell import docs_navbar_frame
from reflex_site_shared.components.icons import get_icon
from reflex_site_shared.components.marketing_button import button
from reflex_site_shared.constants import (
    GITHUB_STARS,
    GITHUB_URL,
    REFLEX_ASSETS_CDN,
    XY_GITHUB_STARS,
)
from reflex_site_shared.views.hosting_banner import (
    AGENT_TOOLKIT_EARLY_ACCESS_URL,
    HostingBannerState,
)

from reflex_docs.pages.docs import getting_started, hosting
from reflex_docs.views.search import search_bar


def github_button() -> rx.Component:
    stars = f"{(GITHUB_STARS + XY_GITHUB_STARS) / 1000:.0f}K"
    label = f"View Reflex on GitHub - {stars} combined stars for Reflex and Reflex XY"
    return rx.el.elements.a(
        get_icon(icon="github_navbar", class_name="size-4 shrink-0"),
        stars,
        href=GITHUB_URL,
        target="_blank",
        rel="noopener noreferrer",
        aria_label=label,
        title=f"Reflex + Reflex XY: {stars} combined GitHub stars",
        class_name="inline-flex h-9 items-center gap-2 rounded-full text-sm font-book text-foreground transition-colors hover:text-muted-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
    )


def logo() -> rx.Component:
    return rx.el.a(
        rx.el.div(
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
        ),
        rx.el.div(
            rx.image(
                src=f"{REFLEX_ASSETS_CDN}logos/light/docs.svg",
                alt="Docs Logo",
                class_name="shrink-0 block dark:hidden",
            ),
            rx.image(
                src=f"{REFLEX_ASSETS_CDN}logos/dark/docs.svg",
                alt="Docs Logo",
                class_name="shrink-0 hidden dark:block",
            ),
        ),
        href="/",
        aria_label="Docs overview",
        class_name="flex flex-row gap-2.5 items-center shrink-0 rounded-compact focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
    )


def menu_item(
    text: str, href: str, active_str: str = "", external: bool = False
) -> rx.Component:
    router_path = rx.State.router.page.path
    # Router paths include the deployment prefix; navigation describes docs routes.
    router_path = rx.cond(
        (router_path == "/docs") | router_path.startswith("/docs/"),
        router_path[5:],
        router_path,
    )
    is_overview = (router_path == "") | (router_path == "/") | (router_path == "/index")

    if active_str.startswith("/"):
        active = is_overview if active_str == "/" else router_path == active_str
    elif active_str == "framework":
        is_ai_builder = (router_path == "/ai") | router_path.startswith("/ai/")
        is_hosting = router_path.startswith("/hosting/")
        is_xy = router_path.startswith("/xy/")
        active = ~is_overview & ~is_ai_builder & ~is_hosting & ~is_xy
    else:
        active = (router_path == f"/{active_str}") | router_path.startswith(
            f"/{active_str}/"
        )

    anchor = rx.el.elements.a if external else rx.el.a

    return rx.el.li(
        anchor(
            text,
            href=href,
            aria_current=rx.cond(active, "page", "false"),
            class_name="docs-navbar-link inline-flex h-9 items-center justify-center rounded-full px-3 text-sm font-book text-muted-foreground transition-colors hover:text-foreground aria-[current=page]:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
        ),
        class_name="flex items-center",
    )


def mobile_navigation() -> rx.Component:
    """Show the same docs destinations as the desktop header.

    Returns:
        Mobile navigation drawer with native links and the shared booking action.
    """
    return rx.drawer.root(
        rx.drawer.trigger(
            button(
                rx.icon("menu", size=18),
                variant="ghost",
                size="icon-sm",
                aria_label="Open sidebar",
            ),
            as_child=True,
        ),
        rx.drawer.portal(
            rx.drawer.content(
                rx.el.div(
                    rx.drawer.title(
                        "Documentation",
                        class_name="text-xs font-book text-muted-foreground",
                        font_size="0.75rem",
                        font_weight="450",
                        line_height="1.5",
                        letter_spacing="normal",
                    ),
                    rx.drawer.close(
                        button(
                            rx.icon("x", size=18),
                            variant="ghost",
                            size="icon-sm",
                            aria_label="Close navigation",
                        ),
                        as_child=True,
                    ),
                    class_name="flex items-center justify-between gap-4",
                ),
                rx.el.nav(
                    *[
                        rx.drawer.close(
                            (rx.el.elements.a if external else rx.el.a)(
                                label,
                                rx.icon(
                                    "arrow-up-right" if external else "arrow-right",
                                    size=16,
                                    aria_hidden=True,
                                ),
                                href=href,
                                class_name="flex min-h-14 items-center justify-between gap-4 border-b border-border-subtle text-base font-book text-foreground focus-visible:outline-2 focus-visible:outline-ring",
                            ),
                            as_child=True,
                        )
                        for label, href, external in (
                            ("Overview", "/", False),
                            ("Build with AI", "/ai/", False),
                            ("Framework", getting_started.introduction.path, False),
                            ("Cloud", hosting.deploy_quick_start.path, False),
                            ("XY", "/docs/xy/", True),
                        )
                    ],
                    aria_label="Documentation navigation",
                    class_name="flex flex-col",
                ),
                rx.drawer.close(
                    button(
                        "Book a Demo",
                        variant="primary",
                        size="md",
                        on_click=rx.call_function(demo_form_open_cs.set_value(True)),
                        class_name="w-full mt-6",
                    ),
                    as_child=True,
                ),
                class_name="docs-mobile-menu fixed inset-x-0 bottom-0 top-(--docs-header-height) flex flex-col gap-4 overflow-y-auto border-t border-border-subtle bg-background p-6 outline-none",
                top="var(--docs-header-height)",
                z_index=10000,
            ),
        ),
        direction="bottom",
    )


def navigation_menu() -> rx.Component:
    """Pair quiet documentation links with compact marketing-style actions."""
    return rx.el.div(
        rx.el.nav(
            rx.el.ul(
                menu_item("Overview", "/", "/"),
                menu_item("Build with AI", "/ai/", "ai"),
                menu_item("Framework", getting_started.introduction.path, "framework"),
                menu_item("Cloud", hosting.deploy_quick_start.path, "hosting"),
                menu_item("XY", "/docs/xy/", "xy", external=True),
                class_name="m-0 flex h-full list-none items-center p-0",
            ),
            aria_label="Documentation navigation",
            class_name="hidden h-full lg:flex",
        ),
        rx.el.div(
            rx.el.div(
                button(
                    ui.icon("Search01Icon", size=16, aria_hidden=True),
                    variant="ghost",
                    size="icon-sm",
                    aria_label="Search (loading)",
                    aria_disabled=True,
                    aria_busy=True,
                    tab_index=-1,
                    class_name="group-has-[.ReflexSearch-root]/docs-search:hidden",
                ),
                search_bar(),
                class_name="group/docs-search docs-navbar-search flex h-9 w-9 lg:w-40 shrink-0 items-center justify-center",
            ),
            rx.el.div(github_button(), class_name="hidden xl:flex"),
            rx.el.div(
                demo_form_dialog(
                    id_prefix="docs-booking",
                    trigger=button(
                        "Book a Demo",
                        size="sm",
                        variant="primary",
                        class_name="whitespace-nowrap text-sm",
                        native_button=False,
                    ),
                ),
                class_name="hidden xl:flex",
            ),
            rx.el.div(mobile_navigation(), class_name="flex lg:hidden"),
            class_name="ml-auto flex items-center gap-2 sm:gap-6",
        ),
        class_name="flex h-full min-w-0 flex-1 items-center justify-between gap-2",
    )


@rx.memo
def docs_navbar() -> rx.Component:
    """Render the editorial header with a dismissible announcement."""
    return rx.fragment(
        rx.cond(
            HostingBannerState.is_banner_visible,
            rx.el.aside(
                rx.el.elements.a(
                    "Reflex Agent Toolkit is launching. Get early access",
                    href=AGENT_TOOLKIT_EARLY_ACCESS_URL,
                    class_name="text-center text-xs sm:text-sm font-medium rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#ffffff]",
                ),
                rx.el.button(
                    ui.icon("MultiplicationSignIcon", size=16),
                    type="button",
                    aria_label="Close banner",
                    on_click=HostingBannerState.hide_banner,
                    class_name="absolute right-2 top-1/2 -translate-y-1/2 flex size-8 items-center justify-center rounded-full hover:bg-white/15 focus-visible:outline-2 focus-visible:outline-[#ffffff]",
                ),
                custom_attrs={"data-docs-announcement": ""},
                class_name="fixed top-0 z-[10000] flex h-14 sm:h-10 w-full items-center justify-center bg-[#181818] text-[#ffffff] px-12",
            ),
        ),
        rx.el.div(
            docs_navbar_frame(logo(), navigation_menu(), show_banner=False),
            class_name="[&_.docs-navbar]:top-[calc(var(--docs-header-height)-4rem)]",
        ),
    )
