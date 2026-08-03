"""Sidebar module."""

import reflex_components_internal as ui
from reflex_components_internal import button
from reflex_components_internal.blocks.demo_form import demo_form_dialog

import reflex as rx
from reflex_site_shared.components.icons import get_icon
from reflex_site_shared.components.marketing_button import button as marketing_button
from reflex_site_shared.constants import (
    CHANGELOG_URL,
    DISCORD_URL,
    GITHUB_URL,
    REFLEX_BUILD_LOGIN_URL,
    REFLEX_BUILD_URL,
)
from reflex_site_shared.views.hosting_banner import HostingBannerState


def drawer_badge(text: str) -> rx.Component:
    """Small pill label shown next to a drawer item (e.g. New, Open source).

    Returns:
        The component.
    """
    return rx.el.div(
        text,
        class_name="text-secondary-11 text-xs font-[475] bg-secondary-1 px-1.5 h-5 rounded-md flex items-center justify-center border border-secondary-4 shrink-0",
    )


def drawer_category_label(text: str) -> rx.Component:
    """Uppercase category divider inside a drawer panel (e.g. BUILD, ITERATE).

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.span(
            text,
            class_name="font-mono font-[415] text-[0.75rem] leading-4 uppercase pb-4 border-b border-dashed border-secondary-6 text-secondary-11 block",
        ),
        class_name="px-4 pt-4",
    )


DRAWER_ROW_CLASS = "flex flex-row items-center justify-between gap-3 w-full px-4 h-12 shrink-0 border-b border-secondary-4 hover-card-shadow"


def drawer_row_content(
    icon: rx.Component,
    title: str,
    *,
    launch: bool = False,
    badge_text: str | None = None,
) -> list[rx.Component]:
    """Inner children of a menu row: icon, label, optional badge and trailing arrow.

    Set ``launch`` to show the inline up-right arrow used by the navbar footer
    links.

    Returns:
        The icon/label group followed by the trailing right arrow.
    """
    label_children: list[rx.Component] = [
        icon,
        rx.el.span(
            title,
            class_name="text-sm font-[525] text-secondary-12 text-nowrap",
        ),
    ]
    if launch:
        label_children.append(
            ui.icon(
                "ArrowUpRight03Icon",
                class_name="size-3 shrink-0 -ml-1.75 text-secondary-12",
            )
        )
    if badge_text:
        label_children.append(drawer_badge(badge_text))
    return [
        rx.el.div(
            *label_children,
            class_name="flex flex-row items-center gap-3 min-w-0",
        ),
        ui.icon(
            "ArrowRight01Icon",
            stroke_width=1.5,
            class_name="size-4 shrink-0 text-secondary-12",
        ),
    ]


def drawer_panel_item(
    icon: rx.Component,
    title: str,
    href: str,
    *,
    external: bool = False,
    launch: bool = False,
    badge_text: str | None = None,
) -> rx.Component:
    """A single menu row inside a panel: icon, label, optional badge and arrow.

    Set ``external`` to open the link in a new tab and ``launch`` to show the
    inline up-right arrow used by the navbar footer links.

    Returns:
        The component.
    """
    return rx.el.elements.a(
        *drawer_row_content(icon, title, launch=launch, badge_text=badge_text),
        href=href,
        target="_blank" if external else None,
        class_name=DRAWER_ROW_CLASS,
    )


def drawer_card(*children: rx.Component) -> rx.Component:
    """Rounded, bordered container grouping panel items.

    Returns:
        The component.
    """
    return rx.el.div(
        *children,
        class_name="flex flex-col rounded-xl border border-secondary-4 bg-white-1 overflow-hidden",
    )


def drawer_category(label: str, *items: rx.Component) -> rx.Component:
    """Category label followed by its menu rows (each row carries its own divider).

    Returns:
        The component.
    """
    return rx.el.div(
        drawer_category_label(label),
        *items,
        class_name="flex flex-col",
    )


def drawer_panel(*cards: rx.Component) -> rx.Component:
    """Inset, vertically-stacked container holding a section's cards.

    Returns:
        The component.
    """
    return rx.el.div(
        *cards,
        class_name="flex flex-col gap-3 px-2 pb-3",
    )


def nav_icon(name: str) -> rx.Component:
    """HugeIcon styled to match the navbar menu item icons.

    Returns:
        The component.
    """
    return ui.icon(
        name,
        stroke_width=1.5,
        class_name="size-5 shrink-0 text-secondary-11",
    )


def custom_nav_icon(name: str) -> rx.Component:
    """Inline SVG icon (from the shared icon set) sized for menu rows.

    Returns:
        The component.
    """
    return get_icon(icon=name, class_name="size-[18px] shrink-0 text-secondary-12")


def products_panel() -> rx.Component:
    """Expanded contents of the Products section.

    Returns:
        The component.
    """
    return drawer_panel(
        drawer_card(
            drawer_category(
                "Build",
                drawer_panel_item(
                    nav_icon("AiChat02Icon"),
                    "AI app builder",
                    REFLEX_BUILD_URL,
                    external=True,
                    badge_text="New",
                ),
                drawer_panel_item(
                    nav_icon("RoboticIcon"),
                    "Agent Toolkit",
                    "/docs/ai/integrations/ai-onboarding/",
                ),
            ),
            drawer_category(
                "Iterate",
                drawer_panel_item(
                    nav_icon("ThirdBracketIcon"),
                    "Framework",
                    "/open-source/",
                    badge_text="Open source",
                ),
            ),
            drawer_category(
                "Ship",
                drawer_panel_item(
                    nav_icon("CloudIcon"),
                    "Deploy, monitor & scale",
                    "/hosting/",
                ),
            ),
        ),
        drawer_card(
            drawer_panel_item(
                custom_nav_icon("docs"),
                "View all docs",
                "/docs/",
                external=True,
                launch=True,
            ),
            drawer_panel_item(
                custom_nav_icon("github_navbar"),
                "View on GitHub",
                GITHUB_URL,
                external=True,
                launch=True,
            ),
            drawer_panel_item(
                custom_nav_icon("reflex_small"),
                "Get started for free",
                REFLEX_BUILD_URL,
                external=True,
                launch=True,
            ),
        ),
    )


def resources_panel() -> rx.Component:
    """Expanded contents of the Resources section.

    Returns:
        The component.
    """
    return drawer_panel(
        drawer_card(
            drawer_category(
                "Learn",
                drawer_panel_item(nav_icon("File02Icon"), "Documentation", "/docs/"),
                drawer_panel_item(nav_icon("Layout02Icon"), "Templates", "/templates/"),
                drawer_panel_item(nav_icon("Clock02Icon"), "Changelog", CHANGELOG_URL),
                drawer_panel_item(nav_icon("News01Icon"), "Blog", "/blog/"),
            ),
            drawer_category(
                "Agent onboarding",
                drawer_panel_item(
                    nav_icon("RoboticIcon"),
                    "Agents",
                    "/docs/ai/integrations/mcp-installation/",
                    badge_text="Overview",
                ),
                drawer_panel_item(
                    nav_icon("McpServerIcon"),
                    "MCP",
                    "/docs/ai/integrations/mcp-overview/",
                ),
                drawer_panel_item(
                    nav_icon("ToolsIcon"), "Skills", "/docs/ai/integrations/skills/"
                ),
            ),
        ),
        drawer_card(
            drawer_panel_item(
                custom_nav_icon("github_navbar"),
                "GitHub",
                GITHUB_URL,
                external=True,
            ),
            drawer_panel_item(
                custom_nav_icon("discord_navbar"),
                "Discord",
                DISCORD_URL,
                external=True,
            ),
        ),
    )


def solutions_panel() -> rx.Component:
    """Expanded contents of the Solutions section.

    Returns:
        The component.
    """
    return drawer_panel(
        drawer_card(
            drawer_category(
                "Industries",
                drawer_panel_item(nav_icon("OfficeIcon"), "AI", "/use-cases/"),
                drawer_panel_item(
                    nav_icon("Wallet05Icon"), "Finance", "/use-cases/finance/"
                ),
                drawer_panel_item(
                    nav_icon("HealthIcon"), "Healthcare", "/use-cases/healthcare/"
                ),
                drawer_panel_item(
                    nav_icon("SourceCodeCircleIcon"),
                    "Tech / SaaS",
                    "/use-cases/consulting/",
                ),
                drawer_panel_item(
                    nav_icon("BankIcon"), "Government", "/use-cases/government/"
                ),
            ),
            drawer_category(
                "Features",
                drawer_panel_item(
                    nav_icon("ShieldKeyIcon"), "Security", "/docs/enterprise/overview/"
                ),
                drawer_panel_item(
                    nav_icon("LoginMethodIcon"),
                    "Auth",
                    "/docs/authentication/authentication-overview/",
                ),
                drawer_panel_item(
                    nav_icon("UserUnlock01Icon"),
                    "Role-based access",
                    "/docs/hosting/adding-members/",
                ),
                drawer_panel_item(
                    nav_icon("ServerStack01Icon"),
                    "On-prem & VPC Deploy",
                    "/blog/on-premises-deployment/",
                ),
                drawer_panel_item(
                    nav_icon("PlugSocketIcon"),
                    "Integrations",
                    "/docs/ai/integrations/overview/",
                ),
            ),
        ),
        drawer_card(
            drawer_panel_item(
                custom_nav_icon("feather_pen"),
                "Read customer stories",
                "/customers/",
            ),
            demo_form_dialog(
                trigger=rx.el.div(
                    *drawer_row_content(custom_nav_icon("reflex_small"), "Book a demo"),
                    class_name=ui.cn(DRAWER_ROW_CLASS, "cursor-pointer"),
                ),
            ),
        ),
    )


DRAWER_SECTION_CLASS = (
    "flex flex-row items-center justify-between w-full px-4 h-16 shrink-0"
)
DRAWER_SECTION_TITLE_CLASS = "text-base font-[550] text-secondary-12"


def drawer_collapsible(
    title: str, content: rx.Component, *, default_open: bool = False
) -> rx.Component:
    """Collapsible drawer section with a chevron trigger.

    Returns:
        The component.
    """
    return ui.collapsible.root(
        ui.collapsible.trigger(
            rx.el.span(title, class_name=DRAWER_SECTION_TITLE_CLASS),
            ui.icon(
                "ArrowDown01Icon",
                stroke_width=1.5,
                class_name="size-5 shrink-0 text-secondary-11 transition-transform ease-out group-data-[panel-open]:rotate-180",
            ),
            class_name=ui.cn("group cursor-pointer", DRAWER_SECTION_CLASS),
        ),
        ui.collapsible.panel(content),
        default_open=default_open,
        class_name="flex flex-col border-b border-secondary-4 w-full shrink-0",
    )


def drawer_link(title: str, href: str, *, external: bool = False) -> rx.Component:
    """Non-collapsible drawer section that links directly to a page.

    Returns:
        The component.
    """
    return rx.el.elements.a(
        rx.el.span(title, class_name=DRAWER_SECTION_TITLE_CLASS),
        ui.icon(
            "ArrowRight01Icon",
            stroke_width=1.5,
            class_name="size-5 shrink-0 text-secondary-12",
        ),
        href=href,
        target="_blank" if external else None,
        class_name=ui.cn(DRAWER_SECTION_CLASS, "border-b border-secondary-4"),
    )


def drawer_footer() -> rx.Component:
    """Drawer footer with the Sign In call to action.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.elements.a(
            marketing_button(
                "Sign In",
                ui.icon("Login01Icon", class_name="scale-x-[-1]"),
                size="sm",
                variant="outline",
                native_button=False,
                class_name="w-full",
            ),
            href=REFLEX_BUILD_LOGIN_URL,
            target="_blank",
            class_name="block w-full",
        ),
        class_name="flex flex-col w-full px-4 py-4 shrink-0 border-t border-secondary-4",
    )


def drawer_top_offset(top_px: int | float) -> str:
    """Class that anchors the drawer below the navbar and fills the rest of the viewport.

    Returns:
        The Tailwind class string for the given top offset.
    """
    return f"!top-[{top_px}px] !h-[calc(100dvh-{top_px}px)]"


def navbar_sidebar_drawer(trigger: rx.Component) -> rx.Component:
    """Navbar sidebar drawer.

    Returns:
        The component.
    """
    return rx.drawer.root(
        rx.drawer.trigger(
            trigger,
        ),
        rx.drawer.portal(
            rx.drawer.content(
                rx.el.div(
                    rx.el.div(
                        drawer_collapsible(
                            "Products", products_panel(), default_open=True
                        ),
                        drawer_collapsible("Resources", resources_panel()),
                        drawer_collapsible("Solutions", solutions_panel()),
                        drawer_link("Enterprise", "/docs/enterprise/overview/"),
                        drawer_link("Pricing", "/pricing/"),
                        drawer_link("Docs", "/docs/"),
                        class_name="flex flex-col flex-1 w-full overflow-y-auto min-h-0",
                    ),
                    drawer_footer(),
                    class_name="flex flex-col w-full h-full bg-secondary-1",
                ),
                class_name=ui.cn(
                    "!bg-secondary-1 w-full !outline-none",
                    rx.cond(
                        HostingBannerState.is_banner_visible,
                        drawer_top_offset(136.5),
                        drawer_top_offset(77),
                    ),
                ),
            )
        ),
        direction="bottom",
    )


def docs_sidebar_drawer(sidebar: rx.Component, trigger: rx.Component) -> rx.Component:
    """Docs sidebar drawer.

    Returns:
        The component.
    """
    return rx.drawer.root(
        rx.drawer.trigger(trigger, as_child=True),
        rx.drawer.portal(
            rx.drawer.overlay(
                class_name="!bg-[rgba(0,0,0,0.1)] backdrop-blur-[4px]",
            ),
            rx.drawer.content(
                rx.el.div(
                    rx.drawer.close(
                        rx.el.div(
                            class_name="absolute left-1/2 transform -translate-x-1/2 top-[-12px] flex-shrink-0 bg-secondary-9 rounded-full w-[96px] h-[5px]",
                        ),
                        as_child=True,
                    ),
                    sidebar,
                    class_name="relative flex flex-col w-full flex-1 min-h-0",
                ),
                class_name="!top-[4rem] flex-col !bg-secondary-1 rounded-[24px_24px_0px_0px] w-full h-[calc(100dvh-4rem)] min-h-0 !outline-none",
            ),
        ),
    )


def navbar_sidebar_button() -> rx.Component:
    """Navbar sidebar button.

    Returns:
        The component.
    """
    return rx.el.div(
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
                variant="outline-shadow",
                custom_attrs={"aria-label": "Open sidebar"},
                native_button=False,
            ),
        ),
        class_name="flex justify-center items-center size-8",
    )
