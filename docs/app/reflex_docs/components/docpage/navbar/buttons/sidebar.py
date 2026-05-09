import reflex as rx
import reflex_components_internal as ui
from reflex.style import toggle_color_mode
from reflex_site_shared.components.icons import get_icon
from reflex_site_shared.components.marketing_button import button
from reflex_site_shared.constants import DISCORD_URL, GITHUB_URL, TWITTER_URL
from reflex_site_shared.views.hosting_banner import HostingBannerState

_DRAWER_LINKS_DOCS = "/docs"
_DRAWER_LINKS_TEMPLATES = "/templates"
_DRAWER_LINKS_BLOG = "/blog"
_DRAWER_LINKS_CUSTOMERS = "/customers"
_DRAWER_LINKS_LIBRARY = "/docs/library"
_DRAWER_LINKS_OPEN_SOURCE = "/open-source"
_DRAWER_LINKS_HOSTING = "/hosting"
_DRAWER_LINKS_PRICING = "/pricing"


def social_menu_item(
    icon: str,
    url="/",
    border: bool = False,
) -> rx.Component:
    aria_labels = {
        "github": "Visit Reflex on GitHub",
        "twitter": "Follow Reflex on X",
        "discord": "Join Reflex Discord community",
    }
    return rx.link(
        get_icon(icon=icon, class_name="!text-slate-9"),
        class_name="flex justify-center items-center gap-2 hover:bg-slate-3 px-4 py-[0.875rem] w-full h-[47px] transition-bg overflow-hidden"
        + (" border-slate-4 border-x border-solid border-y-0" if border else ""),
        href=url,
        is_external=True,
        custom_attrs={"aria-label": aria_labels.get(icon, f"Visit {icon}")},
    )


def drawer_socials() -> rx.Component:
    return rx.box(
        social_menu_item("github", GITHUB_URL),
        social_menu_item(
            "twitter",
            TWITTER_URL,
            border=True,
        ),
        social_menu_item("discord", DISCORD_URL),
        class_name="flex flex-row items-center border-slate-4 border-y-0 !border-b w-full",
    )


def drawer_item(text: str, url: str, active_str: str = "") -> rx.Component:
    router_path = rx.State.router.page.path
    if not url.endswith("/"):
        url += "/"
    active = router_path.contains(active_str)
    if active_str == "docs":
        is_docs_home = (router_path == "/") | (router_path == "/index")
        active = rx.cond(
            is_docs_home,
            False,
            ~router_path.contains("hosting")
            & ~router_path.contains("library")
            & ~router_path.contains("gallery")
            & ~router_path.startswith("/ai/")
            & ~router_path.startswith("/docs/ai/"),
        )
    if active_str == "":
        active = False
    return rx.el.elements.a(
        text,
        href=url,
        underline="none",
        color=rx.cond(active, "var(--c-violet-9)", "var(--c-slate-9)"),
        class_name="flex justify-center items-center border-slate-4 px-4 py-[0.875rem] border-t-0 border-b border-solid w-full font-small hover:!text-violet-9 border-x-0",
    )


def navbar_sidebar_drawer(trigger) -> rx.Component:
    return rx.drawer.root(
        rx.drawer.trigger(
            trigger,
        ),
        rx.drawer.portal(
            rx.drawer.content(
                rx.box(
                    drawer_item("Docs", _DRAWER_LINKS_DOCS, "docs"),
                    drawer_item("Templates", _DRAWER_LINKS_TEMPLATES, "templates"),
                    drawer_item("Blog", _DRAWER_LINKS_BLOG, "blog"),
                    drawer_item("Case Studies", _DRAWER_LINKS_CUSTOMERS, "customers"),
                    drawer_item("Components", _DRAWER_LINKS_LIBRARY, "library"),
                    drawer_item(
                        "Open Source", _DRAWER_LINKS_OPEN_SOURCE, "open-source"
                    ),
                    drawer_item("Cloud", _DRAWER_LINKS_HOSTING, "hosting"),
                    drawer_item("Pricing", _DRAWER_LINKS_PRICING, "pricing"),
                    drawer_socials(),
                    rx.el.button(
                        rx.color_mode.icon(
                            light_component=rx.icon(
                                "sun", size=16, class_name="!text-slate-9"
                            ),
                            dark_component=rx.icon(
                                "moon", size=16, class_name="!text-slate-9"
                            ),
                        ),
                        on_click=toggle_color_mode,
                        class_name="flex flex-row justify-center items-center px-3 py-0.5 w-full h-[47px]",
                        custom_attrs={"aria-label": "Toggle color mode"},
                    ),
                    class_name="flex flex-col items-center dark:bg-m-slate-12 bg-m-slate-1 w-full h-full",
                ),
                class_name=ui.cn(
                    "dark:!bg-m-slate-12 !bg-m-slate-1 w-full h-full !outline-none",
                    rx.cond(
                        HostingBannerState.is_banner_visible,
                        "!top-[137px]",
                        "!top-[77px]",
                    ),
                ),
            )
        ),
        direction="bottom",
    )


def docs_sidebar_drawer(sidebar: rx.Component, trigger) -> rx.Component:
    """Drawer wrapping a sidebar (legacy doc layout; unused in blog-only builds)."""
    return rx.drawer.root(
        rx.drawer.trigger(trigger, as_child=True),
        rx.drawer.portal(
            rx.drawer.overlay(
                class_name="!bg-[rgba(0,0,0,0.1)] backdrop-blur-[4px]",
            ),
            rx.drawer.content(
                rx.box(
                    rx.drawer.close(
                        rx.box(
                            class_name="absolute left-1/2 transform -translate-x-1/2 top-[-12px] flex-shrink-0 bg-slate-9 rounded-full w-[96px] h-[5px]",
                        ),
                        as_child=True,
                    ),
                    sidebar,
                    class_name="relative flex flex-col w-full",
                ),
                class_name="!top-[4rem] flex-col !bg-secondary-1 rounded-[24px_24px_0px_0px] w-full h-full !outline-none",
            ),
        ),
    )


def navbar_sidebar_button() -> rx.Component:
    return rx.box(
        navbar_sidebar_drawer(
            button(
                ui.icon(
                    "Menu01Icon",
                    style={
                        "[data-state=open] &": {
                            "display": "none",
                        },
                        "[data-state=closed] &": {
                            "display": "flex",
                        },
                    },
                ),
                ui.icon(
                    "Cancel01Icon",
                    style={
                        "[data-state=open] &": {
                            "display": "flex",
                        },
                        "[data-state=closed] &": {
                            "display": "none",
                        },
                    },
                ),
                size="icon-sm",
                variant="outline",
                custom_attrs={"aria-label": "Open sidebar"},
                native_button=False,
            ),
        ),
        class_name="flex justify-center items-center size-8",
    )
