import reflex as rx
import reflex_components_internal as ui
from reflex_components_internal.blocks.demo_form import demo_form_dialog
from reflex_site_shared.components.icons import get_icon
from reflex_site_shared.components.marketing_button import button
from reflex_site_shared.constants import (
    GITHUB_STARS,
    GITHUB_URL,
    REFLEX_ASSETS_CDN,
    REFLEX_URL,
)

from reflex_docs.components.docpage.navbar.buttons.sidebar import navbar_sidebar_button
from reflex_docs.pages.docs import ai_builder, getting_started, hosting
from reflex_docs.views.search import search_bar


def github_button() -> rx.Component:
    label = f"View Reflex on GitHub - {GITHUB_STARS // 1000}K stars"
    return rx.el.a(
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
        class_name="flex flex-row gap-2.5 items-center shrink-0 mr-10",
    )


def menu_item(text: str, href: str, active_str: str = "") -> rx.Component:
    router_path = rx.State.router.page.path
    active_cn = "shadow-[inset_0_-1px_0_0_var(--primary-10)] [&_button]:text-primary-10 [&_div]:text-primary-10"

    # For paths starting with "/" (like Start), use exact match
    # For "framework", it's the default - active when in /docs but not matching other sections
    # For other segments (like "ai"), use contains
    if active_str.startswith("/"):
        if active_str == "/":
            active = (router_path == "/") | (router_path == "/index")
        else:
            active = router_path == active_str
    elif active_str == "framework":
        is_overview = (router_path == "/") | (router_path == "/index")
        is_ai_builder = router_path.startswith("/ai/") | router_path.startswith(
            "/docs/ai/"
        )
        is_hosting = router_path.contains("hosting")
        active = ~is_overview & ~is_ai_builder & ~is_hosting
    elif active_str == "ai":
        active = router_path.startswith("/ai/") | router_path.startswith("/docs/ai/")
    else:
        active = router_path.contains(active_str)

    return ui.navigation_menu.item(
        rx.el.a(
            button(
                text,
                size="sm",
                variant="ghost",
                native_button=False,
            ),
            href=href,
        ),
        class_name=ui.cn(
            "md:flex hidden h-full items-center justify-center",
            rx.cond(active, active_cn, ""),
        ),
        custom_attrs={"role": "menuitem"},
    )


def navigation_menu() -> rx.Component:
    return ui.navigation_menu.root(
        ui.navigation_menu.list(
            menu_item("Overview", "/", "/"),
            menu_item("Build with AI", ai_builder.overview.best_practices.path, "ai"),
            menu_item("Framework", getting_started.introduction.path, "framework"),
            menu_item("Cloud", hosting.deploy_quick_start.path, "hosting"),
            class_name="flex flex-row items-center gap-2 m-0 h-full list-none",
            custom_attrs={"role": "menubar"},
        ),
        ui.navigation_menu.list(
            ui.navigation_menu.item(
                github_button(),
                unstyled=True,
                class_name="md:flex hidden",
                custom_attrs={"role": "menuitem"},
            ),
            ui.navigation_menu.item(
                search_bar(),
                unstyled=True,
                custom_attrs={"role": "menuitem"},
            ),
            ui.navigation_menu.item(
                demo_form_dialog(
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
                navbar_sidebar_button(),
                class_name="md:hidden flex",
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
                    class_name="relative h-[var(--popup-height)] w-max origin-[var(--transform-origin)] transition-[opacity,transform,width,height,scale,translate] duration-[0.35s] ease-[cubic-bezier(0.22,1,0.36,1)] data-[ending-style]:scale-90 data-[ending-style]:opacity-0 data-[ending-style]:duration-150 data-[starting-style]:scale-90 data-[starting-style]:opacity-0 min-[500px]:w-[var(--popup-width)] xs:w-[var(--popup-width)] rounded-xl bg-secondary-1 overflow-hidden",
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
        class_name="relative flex w-full items-center h-full justify-between gap-6 mx-auto flex-row",
    )


@rx.memo
def docs_navbar() -> rx.Component:
    from reflex_site_shared.views.hosting_banner import hosting_banner

    return rx.el.div(
        hosting_banner(),
        rx.el.header(
            rx.el.div(
                logo(),
                navigation_menu(),
                class_name="relative flex w-full items-center h-full justify-between gap-6 mx-auto flex-row max-w-[108rem]",
            ),
            class_name="w-full max-full h-[4.5rem] mx-auto flex flex-row items-center 3xl:px-16 px-6 backdrop-blur-[16px] shadow-[0_-2px_2px_1px_rgba(0,0,0,0.02),0_1px_1px_0_rgba(0,0,0,0.08),0_4px_8px_0_rgba(0,0,0,0.03),0_0_0_1px_#FFF_inset] dark:shadow-none dark:border-b dark:border-m-slate-10 bg-gradient-to-b from-white to-m-slate-1 dark:from-m-slate-11 dark:to-m-slate-12",
        ),
        class_name="flex flex-col w-full top-0 z-[9999] fixed self-center",
    )
