"""Footer module."""

from datetime import datetime

import reflex_components_internal as ui
from reflex_components_internal import button as marketing_button

import reflex as rx
from reflex.style import color_mode, set_color_mode
from reflex_site_shared.backend.signup import IndexState
from reflex_site_shared.backend.status import StatusState
from reflex_site_shared.components.icons import get_icon
from reflex_site_shared.components.server_status import server_status
from reflex_site_shared.constants import (
    CHANGELOG_URL,
    DISCORD_URL,
    FORUM_URL,
    GITHUB_URL,
    LINKEDIN_URL,
    REFLEX_ASSETS_CDN,
    REFLEX_BUILD_URL,
    ROADMAP_URL,
    TWITTER_URL,
)


def ph_1() -> rx.Component:
    """Ph 1.

    Returns:
        The component.
    """
    return rx.fragment(
        rx.image(
            src=f"{REFLEX_ASSETS_CDN}logos/dark/ph_1.svg",
            class_name="hidden dark:block h-[36px] w-fit",
            alt="1st product of the day logo",
            loading="lazy",
        ),
        rx.image(
            src=f"{REFLEX_ASSETS_CDN}logos/light/ph_1.svg",
            class_name="dark:hidden block h-[36px] w-fit",
            alt="1st product of the day logo",
            loading="lazy",
        ),
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
        class_name="block shrink-0 mr-[7rem] md:hidden xl:block h-fit",
    )


def tab_item(mode: str, icon: str) -> rx.Component:
    """Tab item.

    Returns:
        The component.
    """
    active_cn = " shadow-[0_-1px_0_0_rgba(0,0,0,0.08)_inset,0_0_0_1px_rgba(0,0,0,0.08)_inset,0_1px_2px_0_rgba(0,0,0,0.02),0_1px_4px_0_rgba(0,0,0,0.02)] dark:shadow-[0_1px_0_0_rgba(255,255,255,0.16)_inset] bg-white dark:bg-m-slate-10 hover:bg-m-slate-2 dark:hover:bg-m-slate-9 text-m-slate-12 dark:text-m-slate-3"
    unactive_cn = " hover:text-m-slate-12 dark:hover:text-m-slate-3 text-m-slate-7 dark:text-m-slate-6"
    return rx.el.button(
        get_icon(icon, class_name="shrink-0"),
        on_click=set_color_mode(mode),  # type: ignore[reportArgumentType]
        class_name=ui.cn(
            "flex items-center cursor-pointer justify-center rounded-lg transition-colors size-7 outline-none focus:outline-none ",
            rx.cond(mode == color_mode, active_cn, unactive_cn),
        ),
        custom_attrs={"aria-label": f"Toggle {mode} color mode"},
    )


def dark_mode_toggle() -> rx.Component:
    """Dark mode toggle.

    Returns:
        The component.
    """
    return rx.box(
        tab_item("system", "computer_footer"),
        tab_item("light", "sun_footer"),
        tab_item("dark", "moon_footer"),
        class_name="flex flex-row gap-0.5 items-center p-0.5 [box-shadow:0_1px_0_0_rgba(0,_0,_0,_0.08),_0_0_0_1px_rgba(0,_0,_0,_0.08),_0_1px_2px_0_rgba(0,_0,_0,_0.02),_0_1px_4px_0_rgba(0,_0,_0,_0.02)] w-fit mt-auto bg-m-slate-1 dark:bg-m-slate-12 rounded-[0.625rem] dark:border dark:border-m-slate-9 border border-transparent lg:ml-auto mr-px",
    )


def footer_link(text: str, href: str) -> rx.Component:
    """Footer link.

    Returns:
        The component.
    """
    return rx.el.elements.a(
        text,
        rx.icon(
            tag="chevron-right",
            size=16,
            class_name="shrink-0 lg:hidden flex",
        ),
        href=href,
        target="_blank",
        class_name="font-[525] text-m-slate-7 hover:text-m-slate-8 dark:hover:text-m-slate-5 dark:text-m-slate-6 text-sm transition-color w-full lg:w-fit flex flex-row justify-between items-center",
    )


def footer_link_flex(
    heading: str, links: list[rx.Component], class_name: str = ""
) -> rx.Component:
    """Footer link flex.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.h3(
            heading,
            class_name="text-xs text-m-slate-12 dark:text-m-slate-3 font-semibold w-fit mb-3",
        ),
        *links,
        class_name=ui.cn("flex flex-col gap-2", class_name),
    )


def social_menu_item(icon: str, url: str, name: str) -> rx.Component:
    """Social menu item.

    Returns:
        The component.
    """
    return rx.el.elements.a(
        marketing_button(
            get_icon(icon, class_name="shrink-0"),
            variant="ghost",
            size="icon-sm",
            class_name="text-m-slate-7 dark:text-m-slate-6",
            native_button=False,
        ),
        href=url,
        custom_attrs={"aria-label": "Social link for " + name},
        target="_blank",
    )


def menu_socials() -> rx.Component:
    """Menu socials.

    Returns:
        The component.
    """
    return rx.box(
        social_menu_item("twitter_footer", TWITTER_URL, "Twitter"),
        social_menu_item("github_navbar", GITHUB_URL, "Github"),
        social_menu_item("discord_navbar", DISCORD_URL, "Discord"),
        social_menu_item("linkedin_footer", LINKEDIN_URL, "LinkedIn"),
        social_menu_item("forum_footer", FORUM_URL, "Forum"),
        class_name="flex flex-row items-center gap-2",
    )


def newsletter_input() -> rx.Component:
    """Newsletter input.

    Returns:
        The component.
    """
    return rx.box(
        rx.cond(
            IndexState.signed_up,
            rx.box(
                rx.box(
                    rx.icon(
                        tag="circle-check",
                        size=16,
                        class_name="!text-violet-9",
                    ),
                    rx.text(
                        "Thanks for subscribing!",
                        class_name="text-xs text-m-slate-7 dark:text-m-slate-6 font-semibold",
                    ),
                    class_name="flex flex-row items-center gap-2",
                ),
                marketing_button(
                    "Sign up for another email",
                    variant="outline",
                    size="sm",
                    on_click=IndexState.signup_for_another_user,
                ),
                class_name="flex flex-col flex-wrap gap-2",
            ),
            rx.form(
                rx.el.input(
                    placeholder="Email",
                    name="input_email",
                    type="email",
                    required=True,
                    class_name="relative [box-shadow:0_-1px_0_0_rgba(0,_0,_0,_0.08)_inset,_0_0_0_1px_rgba(0,_0,_0,_0.08)_inset,_0_1px_2px_0_rgba(0,_0,_0,_0.02),_0_1px_4px_0_rgba(0,_0,_0,_0.02)] rounded-lg h-8 px-2 py-1.5 w-[12rem] text-sm placeholder:text-m-slate-7 dark:placeholder:text-m-slate-6 font-[525] focus:outline-none outline-none dark:border dark:border-m-slate-9 dark:bg-m-slate-11",
                ),
                marketing_button(
                    "Subscribe",
                    type="submit",
                    variant="outline",
                    size="sm",
                    class_name="w-fit max-w-full",
                ),
                class_name="w-full flex flex-col lg:flex-row gap-2 lg:items-center items-start",
                on_submit=IndexState.signup,
            ),
        ),
        class_name="w-full",
    )


def newsletter() -> rx.Component:
    """Newsletter.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.text(
            "Get updates",
            class_name="text-xs text-m-slate-7 dark:text-m-slate-6 font-semibold",
        ),
        newsletter_input(),
        class_name="flex flex-col items-start gap-4 self-stretch",
    )


@rx.memo
def footer_index(class_name: str = "", grid_class_name: str = "") -> rx.Component:
    """Footer index.

    Returns:
        The component.
    """
    return rx.el.footer(
        rx.el.div(
            logo(),
            rx.el.div(
                footer_link_flex(
                    "Product",
                    [
                        footer_link("AI Builder", REFLEX_BUILD_URL),
                        footer_link("Framework", "/framework"),
                        footer_link("Cloud", "/cloud"),
                    ],
                ),
                footer_link_flex(
                    "Solutions",
                    [
                        footer_link("Enterprise", "/use-cases"),
                        footer_link("Finance", "/use-cases/finance"),
                        footer_link("Healthcare", "/use-cases/healthcare"),
                        footer_link("Consulting", "/use-cases/consulting"),
                        footer_link("Government", "/use-cases/government"),
                    ],
                ),
                footer_link_flex(
                    "Resources",
                    [
                        footer_link("Documentation", "/docs"),
                        footer_link("FAQ", "/faq"),
                        footer_link("Common Errors", "/errors"),
                        footer_link("Roadmap", ROADMAP_URL),
                        footer_link("Changelog", CHANGELOG_URL),
                    ],
                ),
                rx.el.div(
                    class_name="absolute -top-24 -right-px w-px h-24 bg-gradient-to-b from-transparent to-current text-m-slate-4 dark:text-m-slate-10 max-lg:hidden"
                ),
                class_name=ui.cn(
                    "grid grid-cols-1 lg:grid-cols-3 gap-12 w-full lg:pr-12 pb-8 lg:border-r border-m-slate-4 dark:border-m-slate-10 xl:ml-auto relative",
                    grid_class_name,
                ),
            ),
            rx.el.div(
                newsletter(),
                ph_1(),
                dark_mode_toggle(),
                class_name="flex flex-col gap-6 lg:pl-12 pb-8 max-lg:justify-start",
            ),
            class_name="flex flex-col max-lg:gap-6 lg:flex-row w-full",
        ),
        rx.el.div(
            server_status(StatusState.status),
            rx.el.div(
                rx.el.span(
                    f"Copyright © {datetime.now().year} Pynecone, Inc.",
                    class_name="text-xs text-m-slate-7 dark:text-m-slate-6 font-medium",
                ),
                menu_socials(),
                class_name="flex flex-row items-center gap-6",
            ),
            rx.el.div(
                class_name="absolute -top-px -right-24 w-24 h-px bg-gradient-to-l from-transparent to-current text-m-slate-4 dark:text-m-slate-10 max-lg:hidden"
            ),
            rx.el.div(
                class_name="absolute -top-px -left-24 w-24 h-px bg-gradient-to-r from-transparent to-current text-m-slate-4 dark:text-m-slate-10 max-lg:hidden"
            ),
            class_name="flex flex-row items-center justify-between py-6 gap-4 w-full border-t border-m-slate-4 dark:border-m-slate-10 relative",
        ),
        class_name=ui.cn(
            "flex flex-col max-w-(--docs-layout-max-width) justify-center items-center w-full mx-auto mt-24 max-lg:px-4 overflow-hidden",
            class_name,
        ),
    )
