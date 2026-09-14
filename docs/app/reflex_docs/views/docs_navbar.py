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
    REFLEX_URL,
)
from reflex_site_shared.views.hosting_banner import (
    AGENT_TOOLKIT_EARLY_ACCESS_URL,
    HostingBannerState,
)

from reflex_docs.pages.docs import ai_builder, getting_started, hosting
from reflex_docs.views.search import search_bar


def github_button() -> rx.Component:
    label = f"View Reflex on GitHub - {GITHUB_STARS // 1000}K stars"
    return rx.el.elements.a(
        button(
            get_icon(icon="github_navbar", class_name="shrink-0"),
            f"{GITHUB_STARS // 1000}K",
            custom_attrs={"aria-label": label},
            size="sm",
            variant="ghost",
            native_button=False,
        ),
        href=GITHUB_URL,
        target="_blank",
        rel="noopener noreferrer",
        custom_attrs={"aria-label": label},
    )


def logo() -> rx.Component:
    return rx.el.elements.a(
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
        href=REFLEX_URL,
        class_name="flex flex-row gap-2.5 items-center shrink-0 lg:mr-4 rounded-sm focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
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
    active_cn = "shadow-[inset_0_-1px_0_0_var(--primary-10)] [&_button]:text-primary-10 [&_div]:text-primary-10"

    if active_str.startswith("/"):
        active = is_overview if active_str == "/" else router_path == active_str
    elif active_str == "framework":
        is_ai_builder = router_path.startswith("/ai/")
        is_hosting = router_path.startswith("/hosting/")
        is_xy = router_path.startswith("/xy/")
        active = ~is_overview & ~is_ai_builder & ~is_hosting & ~is_xy
    else:
        active = router_path.startswith(f"/{active_str}/")

    anchor = rx.el.elements.a if external else rx.el.a

    return ui.navigation_menu.item(
        anchor(
            button(
                text,
                size="sm",
                class_name="px-2 lg:px-3",
                variant="ghost",
                native_button=False,
            ),
            href=href,
            aria_current=rx.cond(active, "page", "false"),
        ),
        class_name=ui.cn(
            "lg:flex hidden h-full items-center justify-center",
            rx.cond(active, active_cn, ""),
        ),
        custom_attrs={"role": "menuitem"},
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
                variant="outline",
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
                            (
                                "Build with AI",
                                ai_builder.overview.best_practices.path,
                                False,
                            ),
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
    return ui.navigation_menu.root(
        ui.navigation_menu.list(
            menu_item("Overview", "/", "/"),
            menu_item("Build with AI", ai_builder.overview.best_practices.path, "ai"),
            menu_item("Framework", getting_started.introduction.path, "framework"),
            menu_item("Cloud", hosting.deploy_quick_start.path, "hosting"),
            menu_item("XY", "/docs/xy/", "xy", external=True),
            class_name="flex flex-row items-center gap-2 m-0 h-full list-none",
            custom_attrs={"role": "menubar"},
        ),
        ui.navigation_menu.list(
            ui.navigation_menu.item(
                github_button(),
                unstyled=True,
                class_name="xl:flex hidden",
                custom_attrs={"role": "menuitem"},
            ),
            ui.navigation_menu.item(
                search_bar(),
                unstyled=True,
                custom_attrs={"role": "menuitem"},
            ),
            ui.navigation_menu.item(
                demo_form_dialog(
                    id_prefix="docs-booking",
                    trigger=button(
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
                mobile_navigation(),
                class_name="lg:hidden flex",
                unstyled=True,
                custom_attrs={"role": "menuitem"},
            ),
            class_name="flex flex-row lg:gap-4 gap-2 m-0 h-full list-none items-center",
            custom_attrs={"role": "menubar"},
        ),
        ui.navigation_menu.portal(
            ui.navigation_menu.positioner(
                ui.navigation_menu.popup(
                    ui.navigation_menu.viewport(),
                    unstyled=True,
                    class_name="relative h-[var(--popup-height)] w-max origin-[var(--transform-origin)] transition-[opacity,transform,width,height,scale,translate] duration-[0.35s] ease-[cubic-bezier(0.22,1,0.36,1)] data-[ending-style]:scale-90 data-[ending-style]:opacity-0 data-[ending-style]:duration-150 data-[starting-style]:scale-90 data-[starting-style]:opacity-0 min-[500px]:w-[var(--popup-width)] xs:w-[var(--popup-width)] rounded-panel bg-background overflow-hidden",
                    style={
                        "box-shadow": "0 0 0 1px rgba(0, 0, 0, 0.03), 0 -1px 1px 0 rgba(0, 0, 0, 0.04), 0 16px 32px 0 rgba(0, 0, 0, 0.08), 0 1px 1px 0 rgba(0, 0, 0, 0.08), 0 4px 8px 0 rgba(0, 0, 0, 0.03);",
                    },
                ),
                side_offset=30,
                align="start",
                align_offset=-20,
            ),
        ),
        unstyled=True,
        class_name="relative flex w-full items-center h-full justify-between gap-2 mx-auto flex-row",
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
