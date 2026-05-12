"""Site footer layout and sections for marketing pages."""

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
    TWITTER_URL,
)


def logo() -> rx.Component:
    """Homepage logo link for the footer.

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
    """Single color-mode toggle tab (system, light, or dark).

    Returns:
        The component.
    """
    active_cn = " shadow-[0_-1px_0_0_rgba(0,0,0,0.08)_inset,0_0_0_1px_rgba(0,0,0,0.08)_inset,0_1px_2px_0_rgba(0,0,0,0.02),0_1px_4px_0_rgba(0,0,0,0.02)] dark:shadow-[0_1px_0_0_rgba(255,255,255,0.16)_inset] bg-white-1 hover:bg-secondary-2 text-secondary-12"
    unactive_cn = " hover:text-secondary-12 text-secondary-11"
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
    """Footer control group for switching color mode.

    Returns:
        The component.
    """
    return rx.box(
        tab_item("system", "computer_footer"),
        tab_item("light", "sun_footer"),
        tab_item("dark", "moon_footer"),
        class_name="flex flex-row gap-0.5 items-center p-0.5 [box-shadow:0_1px_0_0_rgba(0,_0,_0,_0.08),_0_0_0_1px_rgba(0,_0,_0,_0.08),_0_1px_2px_0_rgba(0,_0,_0,_0.02),_0_1px_4px_0_rgba(0,_0,_0,_0.02)] w-fit mt-auto bg-secondary-1 rounded-[0.625rem] dark:border dark:border-secondary-4 border border-transparent",
    )


def footer_link(text: str, href: str) -> rx.Component:
    """Link styled for footer link columns.

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
        target="_blank" if not href.startswith("/") else "",
        class_name="font-[525] text-secondary-11 hover:text-secondary-12 text-sm transition-color w-full lg:w-fit flex flex-row justify-between items-center min-h-[24px]",
    )


def footer_link_flex(
    heading: str, links: list[rx.Component], class_name: str = ""
) -> rx.Component:
    """Column with a heading and stacked footer links.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.h3(
            heading,
            class_name="text-xs text-secondary-12 font-[525] w-fit mb-2",
        ),
        *links,
        class_name=ui.cn("flex flex-col gap-2", class_name),
    )


def social_menu_item(
    icon: str, url: str, name: str, class_name: str = ""
) -> rx.Component:
    """Icon link to a social profile or community.

    Returns:
        The component.
    """
    return rx.el.elements.a(
        get_icon(icon, class_name="size-5 shrink-0"),
        href=url,
        custom_attrs={"aria-label": "Social link for " + name},
        target="_blank",
        class_name=ui.cn(
            "text-secondary-11 hover:text-secondary-12 transition-colors flex items-center justify-center size-7 rounded-md",
            "lg:size-auto lg:h-full lg:w-full lg:rounded-none",
            class_name,
        ),
    )


def menu_socials() -> rx.Component:
    """Row of major social and community links.

    Returns:
        The component.
    """
    return rx.el.div(
        social_menu_item("twitter_footer", TWITTER_URL, "Twitter"),
        social_menu_item("github_navbar", GITHUB_URL, "Github"),
        social_menu_item("discord_navbar", DISCORD_URL, "Discord"),
        social_menu_item("linkedin_footer", LINKEDIN_URL, "LinkedIn"),
        social_menu_item("forum_footer", FORUM_URL, "Forum"),
        class_name="flex flex-row items-center gap-2 lg:gap-0 lg:grid lg:grid-cols-5 lg:border-y lg:border-secondary-4 lg:divide-x lg:divide-secondary-4 lg:w-full lg:h-16",
    )


def newsletter_input() -> rx.Component:
    """Email signup form or post-subscribe confirmation.

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
                        class_name="!text-primary-9",
                    ),
                    rx.text(
                        "Thanks for subscribing!",
                        class_name="text-xs font-[525] text-secondary-12",
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
                ui.input(
                    placeholder="Email",
                    name="input_email",
                    type="email",
                    required=True,
                    size="sm",
                    class_name="w-[195px]",
                ),
                ui.button(
                    "Subscribe",
                    type="submit",
                    variant="outline-shadow",
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
    """Newsletter call-to-action block with heading.

    Returns:
        The component.
    """
    return rx.el.div(
        newsletter_input(),
        class_name="flex flex-col items-start gap-4 self-stretch mt-6",
    )


@rx.memo
def footer_index(class_name: str = "", grid_class_name: str = "") -> rx.Component:
    """Full marketing footer: logo, newsletter, links, and legal.

    Returns:
        The component.
    """
    return rx.el.footer(
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.el.div(
                        rx.el.div(
                            class_name="absolute -right-px -top-24 h-24 w-px bg-linear-to-b from-transparent to-current text-secondary-4 max-lg:hidden"
                        ),
                        logo(),
                        newsletter(),
                        rx.el.div(
                            menu_socials(),
                            class_name="mt-6 w-full lg:-mx-8 lg:w-[calc(100%+4rem)]",
                        ),
                        rx.el.div(
                            dark_mode_toggle(),
                            rx.el.span(
                                f"Copyright © {datetime.now().year} Pynecone, Inc.",
                                class_name="text-xs font-[525] text-secondary-11",
                            ),
                            rx.el.div(
                                server_status(StatusState.status), class_name="-ml-2.5"
                            ),
                            class_name="mt-auto justify-start flex flex-col items-start gap-6 pt-8",
                        ),
                        class_name="flex flex-col lg:pr-8 lg:pl-8 lg:pb-8 min-w-[337px] lg:border-r border-secondary-4 shrink-0 relative pt-16",
                    ),
                    rx.el.div(
                        footer_link_flex(
                            "Product",
                            [
                                footer_link("AI Builder", REFLEX_BUILD_URL),
                                footer_link(
                                    "Agent Toolkit",
                                    "/docs/ai/integrations/overview/",
                                ),
                                footer_link(
                                    "Enterprise",
                                    "/docs/enterprise/overview/",
                                ),
                                footer_link("App Management", "/hosting"),
                                footer_link("Pricing", "/pricing"),
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
                                footer_link("Blog", "/blog"),
                                footer_link("Templates", "/templates"),
                                footer_link(
                                    "Integrations",
                                    "/docs/ai/integrations/overview/",
                                ),
                            ],
                        ),
                        footer_link_flex(
                            "Migration",
                            [
                                footer_link("From No-Code", "/migration/no-code/"),
                                footer_link("From Low-Code", "/migration/low-code/"),
                                footer_link(
                                    "From Other Frameworks",
                                    "/migration/other-frameworks/",
                                ),
                                footer_link(
                                    "From Other AI Tools",
                                    "/migration/other-ai-tools/",
                                ),
                            ],
                        ),
                        footer_link_flex(
                            "Developers",
                            [
                                footer_link("Documentation", "/docs"),
                                footer_link("Changelog", CHANGELOG_URL),
                                footer_link("Common Errors", "/errors"),
                            ],
                        ),
                        footer_link_flex(
                            "Company",
                            [
                                footer_link("About", "/about"),
                                footer_link(
                                    "Careers",
                                    "https://www.ycombinator.com/companies/reflex/jobs",
                                ),
                                footer_link(
                                    "Privacy Policy",
                                    "https://build.reflex.dev/privacy-policy",
                                ),
                                footer_link(
                                    "Terms of Service",
                                    "https://build.reflex.dev/terms-of-use",
                                ),
                            ],
                        ),
                        class_name=ui.cn(
                            "grid grid-cols-1 lg:grid-cols-3 gap-x-12 gap-y-12 w-full relative lg:px-8 pb-8 pt-16",
                            grid_class_name,
                        ),
                    ),
                    class_name="flex lg:flex-row flex-col max-lg:gap-6 w-full",
                ),
                rx.el.div(
                    class_name="absolute -top-px -right-24 w-24 h-px bg-linear-to-l from-transparent to-current text-secondary-4 max-lg:hidden"
                ),
                rx.el.div(
                    class_name="absolute -top-px -left-24 w-24 h-px bg-linear-to-r from-transparent to-current text-secondary-4 max-lg:hidden"
                ),
                class_name="relative flex flex-col w-full lg:border-x border-secondary-4 border-t",
            ),
            class_name="w-full min-w-0 lg:px-2",
        ),
        class_name=ui.cn(
            "flex flex-col w-full min-w-0 max-w-(--landing-layout-max-width) items-stretch mx-auto max-lg:px-4 lg:border-x border-secondary-4 relative",
            class_name,
        ),
    )
