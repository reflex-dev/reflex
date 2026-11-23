import reflex as rx
import reflex_components_internal as ui
from reflex_site_shared.components.icons import get_icon
from reflex_site_shared.components.marketing_button import button
from reflex_site_shared.constants import (
    GITHUB_STARS,
    GITHUB_URL,
    REFLEX_ASSETS_CDN,
    REFLEX_URL,
    XY_GITHUB_STARS,
)

from reflex_docs import sections
from reflex_docs.components.docpage.navbar.buttons.sidebar import navbar_sidebar_button
from reflex_docs.pages.docs import cloud, getting_started
from reflex_docs.views.docs_announcement_banner import docs_announcement_banner
from reflex_docs.views.search import search_bar


def github_button() -> rx.Component:
    """Render the compact GitHub link with its combined star count.

    Returns:
        A link to the Reflex GitHub repository showing the combined star count.
    """
    total = GITHUB_STARS + XY_GITHUB_STARS
    stars = f"{(total + 999) // 1000}K"
    label = f"View Reflex on GitHub — {total:,} combined stars across Reflex and XY"
    return rx.el.elements.a(
        button(
            get_icon(
                icon="github_navbar",
                class_name="size-4 shrink-0 [&>svg]:block [&>svg]:size-full",
            ),
            rx.el.span(stars, class_name="tabular-nums"),
            custom_attrs={"aria-label": label},
            size="sm",
            variant="ghost",
            native_button=False,
            class_name="gap-2 rounded-[8px] px-3 text-sm font-normal text-muted-foreground hover:text-foreground",
        ),
        href=GITHUB_URL,
        target="_blank",
        rel="noopener noreferrer",
        custom_attrs={"aria-label": label},
        class_name="docs-navbar-github rounded-[8px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
    )


def logo() -> rx.Component:
    """Link each wordmark to its respective site overview.

    Returns:
        The Reflex and Docs wordmarks, each linking to its overview.
    """
    focus_class = "rounded-sm focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
    return rx.el.div(
        rx.el.elements.a(
            rx.image(
                src=f"{REFLEX_ASSETS_CDN}logos/light/reflex.svg",
                alt="Reflex Logo",
                class_name="docs-navbar-wordmark block w-auto shrink-0 dark:hidden",
            ),
            rx.image(
                src=f"{REFLEX_ASSETS_CDN}logos/dark/reflex.svg",
                alt="Reflex Logo",
                class_name="docs-navbar-wordmark hidden w-auto shrink-0 dark:block",
            ),
            href=REFLEX_URL,
            aria_label="Reflex home",
            class_name=focus_class,
        ),
        rx.el.a(
            rx.image(
                src=f"{REFLEX_ASSETS_CDN}logos/light/docs.svg",
                alt="Docs Logo",
                class_name="docs-navbar-docs-wordmark block w-auto shrink-0 dark:hidden",
                style={"filter": "grayscale(1)"},
            ),
            rx.image(
                src=f"{REFLEX_ASSETS_CDN}logos/dark/docs.svg",
                alt="Docs Logo",
                class_name="docs-navbar-docs-wordmark hidden w-auto shrink-0 dark:block",
                style={"filter": "grayscale(1) brightness(2)"},
            ),
            href="/",
            aria_label="Docs overview",
            class_name=focus_class,
        ),
        class_name="docs-navbar-brand flex shrink-0 flex-row items-center gap-3",
    )


def menu_item(
    text: str,
    href: str,
    active: rx.Var[bool] | bool = False,
    external: bool = False,
) -> rx.Component:
    """Render a section link using the docs router or an explicit external URL.

    Args:
        text: Visible section name.
        href: Destination relative to the docs mount, or a complete external path.
        active: Whether the current page belongs to this section.
        external: Whether the destination must bypass the docs router.

    Returns:
        A navigation item containing one focusable link.
    """
    anchor = rx.el.elements.a if external else rx.el.a

    return ui.navigation_menu.item(
        anchor(
            text,
            href=href,
            aria_current=rx.cond(active, "page", None),
            class_name=ui.cn(
                "docs-navbar-link inline-flex h-9 items-center justify-center whitespace-nowrap rounded-[8px] px-3 text-sm font-normal leading-none transition-colors duration-150 motion-reduce:transition-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                rx.cond(
                    active,
                    "bg-accent text-foreground",
                    "text-muted-foreground hover:text-foreground",
                ),
            ),
        ),
        class_name="flex h-full items-center justify-center",
        custom_attrs={"role": "menuitem"},
    )


def navigation_menu(active_tab: rx.Var[str] | str = "") -> rx.Component:
    """Render the docs section links, search, and responsive navigation actions.

    Args:
        active_tab: The navbar tab of the current page (see ``reflex_docs.sections``),
            or an empty string when no section is current.

    Returns:
        The navigation menu holding the section links and header actions.
    """
    return ui.navigation_menu.root(
        ui.navigation_menu.list(
            menu_item("Overview", "/", active_tab == sections.OVERVIEW),
            menu_item("Build with AI", "/ai/", active_tab == sections.AI),
            menu_item(
                "Framework",
                getting_started.introduction.path,
                active_tab == sections.FRAMEWORK,
            ),
            menu_item("Cloud", cloud.overview.path, active_tab == sections.CLOUD),
            menu_item("XY", "/docs/xy/", active_tab == sections.XY, external=True),
            class_name="docs-navbar-sections hidden xl:flex m-0 h-full list-none flex-row items-center gap-1",
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
                class_name="docs-navbar-search flex items-center",
                custom_attrs={"role": "menuitem"},
            ),
            ui.navigation_menu.item(
                rx.el.elements.a(
                    button(
                        "Book a Demo",
                        size="sm",
                        variant="primary",
                        class_name="rounded-[8px] whitespace-nowrap px-4 text-sm font-normal",
                        native_button=False,
                    ),
                    href="https://reflex.dev/demo/",
                    class_name="docs-navbar-cta rounded-[8px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                ),
                unstyled=True,
                class_name="xl:flex hidden",
                custom_attrs={"role": "menuitem"},
            ),
            ui.navigation_menu.item(
                navbar_sidebar_button(),
                class_name="docs-navbar-mobile xl:hidden flex",
                unstyled=True,
                custom_attrs={"role": "menuitem"},
            ),
            class_name="docs-navbar-actions m-0 flex h-full shrink-0 list-none flex-row items-center gap-2 lg:gap-3",
            custom_attrs={"role": "menubar"},
        ),
        ui.navigation_menu.portal(
            ui.navigation_menu.positioner(
                ui.navigation_menu.popup(
                    ui.navigation_menu.viewport(),
                    unstyled=True,
                    class_name="relative h-[var(--popup-height)] w-max origin-[var(--transform-origin)] transition-[opacity,transform,width,height,scale,translate] duration-[0.35s] ease-[cubic-bezier(0.22,1,0.36,1)] data-[ending-style]:scale-90 data-[ending-style]:opacity-0 data-[ending-style]:duration-150 data-[starting-style]:scale-90 data-[starting-style]:opacity-0 min-[500px]:w-[var(--popup-width)] xs:w-[var(--popup-width)] rounded-xl bg-background overflow-hidden",
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
        class_name="docs-navbar-nav relative mx-auto flex h-full min-w-0 w-full flex-row items-center justify-end gap-4 font-sans xl:justify-between",
    )


@rx.memo
def docs_navbar(active_tab: rx.vars.StringVar[str]) -> rx.Component:
    """Render the compact docs header with the marketing announcement treatment.

    The current tab is a prop computed per route at build time, so prerendered
    HTML marks it without waiting for the router to hydrate.

    Args:
        active_tab: The navbar tab of the current page (see ``reflex_docs.sections``),
            or an empty string when no section is current.

    Returns:
        The fixed header frame with the announcement banner above the navbar.
    """
    return rx.el.div(
        docs_announcement_banner(),
        rx.el.header(
            rx.el.div(
                logo(),
                navigation_menu(active_tab),
                class_name="docs-navbar-inner mx-auto flex h-full w-full min-w-0 flex-row items-center justify-between gap-6",
            ),
            class_name="docs-navbar-header relative [&_nav]:!static [&_ul]:!static flex h-16 w-full items-center",
        ),
        class_name="docs-nav-frame fixed top-0 z-[9999] flex w-full flex-col self-center",
    )
