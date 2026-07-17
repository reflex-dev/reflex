"""Reusable layout for Markdown-backed documentation pages."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

import reflex_components_internal as ui

import reflex as rx
from reflex.event import EventType
from reflex_site_shared.components.docs_shell import (
    docs_feedback_button,
    docs_feedback_button_toc,
    docs_footer_shell,
    docs_left_sidebar,
    docs_navbar_frame,
    docs_right_sidebar,
    docs_sidebar_leaf,
    docs_sidebar_section,
)
from reflex_site_shared.components.icons import get_icon
from reflex_site_shared.components.inkeep import inkeep
from reflex_site_shared.components.marketing_button import button
from reflex_site_shared.docs.markdown import get_markdown_toc, render_markdown
from reflex_site_shared.docs.models import (
    DocsLayoutConfig,
    DocsNavbarAction,
    DocsPage,
    NavigationItem,
)
from reflex_site_shared.docs.navigation import get_prev_next
from reflex_site_shared.views.footer import dark_mode_toggle
from reflex_site_shared.views.hosting_banner import HostingBannerState


def render_markdown_page(page: DocsPage) -> rx.Component:
    """Render a discovered page with the shared Markdown component map.

    Args:
        page: Discovered documentation page.

    Returns:
        Styled Markdown content.
    """
    source_path = page.source_path.resolve()
    return render_markdown(
        page.content,
        virtual_filepath=str(source_path),
        filename=str(source_path),
    )


def docs_layout_shell(
    navbar: rx.Component,
    main: rx.Component,
    *,
    on_mount: EventType[()] | None = None,
) -> rx.Component:
    """Render the shared top-level documentation layout shell.

    Args:
        navbar: Site navbar rendered above the documentation columns.
        main: Responsive documentation columns.
        on_mount: Optional event run when the shell mounts.

    Returns:
        The complete documentation shell.
    """
    return rx.box(
        navbar,
        main,
        class_name="flex flex-col justify-center bg-secondary-1 w-full relative",
        on_mount=on_mount,
    )


def _first_route(item: NavigationItem) -> str | None:
    """Return the first route reachable from a navigation item.

    Args:
        item: Navigation item to inspect.

    Returns:
        The first route, if one exists.
    """
    if item.route is not None:
        return item.route
    for child in item.children:
        if route := _first_route(child):
            return route
    return None


def _navbar_button(
    *children: rx.Component | str,
    variant: Literal["ghost", "primary"] = "ghost",
    class_name: str = "",
) -> rx.Component:
    """Render the button treatment used by the official docs navbar.

    Args:
        *children: Button contents.
        variant: Visual variant, either ``ghost`` or ``primary``.
        class_name: Additional utility classes.

    Returns:
        A navbar button surface suitable for links and dialog triggers.
    """
    return button(
        *children,
        variant=variant,
        size="sm",
        native_button=False,
        class_name=class_name,
    )


def _navbar_action(action: DocsNavbarAction | None) -> rx.Component:
    """Render a link action or consumer-provided action component.

    Args:
        action: Link tuple or component factory.

    Returns:
        Navbar action content.
    """
    if action is None:
        return rx.fragment()
    if callable(action):
        return action()
    label, href = action
    return rx.el.a(
        _navbar_button(
            label,
            variant="primary",
            class_name="whitespace-nowrap",
        ),
        href=href,
        class_name="no-underline",
    )


def _default_navbar(
    config: DocsLayoutConfig,
    navigation: tuple[NavigationItem, ...],
    current_route: str,
) -> rx.Component:
    """Render the default documentation navbar.

    Args:
        config: Shared layout configuration.
        navigation: Full nested site navigation.
        current_route: Current page route.

    Returns:
        Navbar component.
    """
    configured_links = config.nav_links or tuple(
        (item.title, route)
        for item in navigation
        if (route := _first_route(item)) is not None
    )
    navigation_menu = ui.navigation_menu.root(
        ui.navigation_menu.list(
            *(
                ui.navigation_menu.item(
                    rx.el.a(
                        _navbar_button(label),
                        href=href,
                        class_name="no-underline",
                    ),
                    class_name=ui.cn(
                        "hidden h-full items-center justify-center md:flex",
                        (
                            "shadow-[inset_0_-1px_0_0_var(--primary-10)] [&_div]:text-primary-10"
                            if href == current_route
                            else ""
                        ),
                    ),
                    custom_attrs={"role": "menuitem"},
                )
                for label, href in configured_links
            ),
            class_name="m-0 flex h-full list-none flex-row items-center gap-2",
            custom_attrs={"role": "menubar"},
        ),
        ui.navigation_menu.list(
            (
                ui.navigation_menu.item(
                    rx.el.a(
                        _navbar_button(
                            get_icon("github_navbar", class_name="size-4 shrink-0"),
                            "GitHub",
                        ),
                        href=config.github_url,
                        target="_blank",
                        rel="noopener noreferrer",
                        aria_label=f"View {config.site_title} on GitHub",
                    ),
                    unstyled=True,
                    class_name="hidden md:flex",
                    custom_attrs={"role": "menuitem"},
                )
                if config.github_url and config.show_github_navbar
                else ui.navigation_menu.item(rx.fragment(), unstyled=True)
            ),
            ui.navigation_menu.item(
                config.search() if config.search is not None else inkeep(),
                unstyled=True,
                custom_attrs={"role": "menuitem"},
            ),
            ui.navigation_menu.item(
                _navbar_action(config.call_to_action),
                unstyled=True,
                class_name=(
                    "hidden xl:flex" if config.call_to_action is not None else "hidden"
                ),
                custom_attrs={"role": "menuitem"},
            ),
            ui.navigation_menu.item(
                rx.el.details(
                    rx.el.summary(
                        "Menu",
                        class_name="cursor-pointer list-none rounded-lg border border-secondary-4 px-3 py-1.5 text-sm text-secondary-12",
                    ),
                    rx.el.nav(
                        rx.el.ul(
                            *(
                                _navigation_item(item, current_route)
                                for item in navigation
                            ),
                            class_name="flex list-none flex-col gap-1",
                        ),
                        custom_attrs={"aria-label": "Mobile documentation navigation"},
                        class_name="absolute right-0 top-11 z-50 max-h-[70vh] w-[18rem] overflow-y-auto rounded-xl border border-secondary-4 bg-secondary-1 p-3 shadow-lg",
                    ),
                    class_name="relative md:hidden",
                ),
                unstyled=True,
                class_name="flex md:hidden",
                custom_attrs={"role": "menuitem"},
            ),
            class_name="m-0 flex h-full list-none flex-row items-center gap-2 lg:gap-4",
            custom_attrs={"role": "menubar"},
        ),
        unstyled=True,
        class_name="relative mx-auto flex h-full w-full flex-row items-center justify-between gap-6",
    )
    logo = rx.el.a(
        config.logo()
        if config.logo is not None
        else rx.fragment(
            rx.el.span(
                config.site_title.upper(),
                class_name="text-xl font-black tracking-[-0.04em] text-secondary-12",
            ),
            rx.el.span(
                "DOCS",
                class_name="font-mono text-xl font-bold text-primary-10",
            ),
        ),
        href="/",
        class_name="mr-10 flex shrink-0 items-center gap-2.5 no-underline",
    )
    return docs_navbar_frame(logo, navigation_menu, show_banner=config.show_banner)


def _navigation_item(item: NavigationItem, current_route: str) -> rx.Component:
    """Render one recursive navigation item.

    Args:
        item: Navigation item to render.
        current_route: Current page route.

    Returns:
        Sidebar list item.
    """
    if item.children:
        return docs_sidebar_section(
            item.title,
            _first_route(item) or "#",
            *(_navigation_item(child, current_route) for child in item.children),
        )
    return docs_sidebar_leaf(
        title=item.title,
        href=item.route or "#",
        active=item.route == current_route,
        guide_margin_class="ml-[2.5rem]",
    )


def _pager_link(
    item: NavigationItem | None, label: str, *, align_right: bool = False
) -> rx.Component:
    """Render a previous or next page link.

    Args:
        item: Adjacent navigation item, when present.
        label: Direction label.
        align_right: Whether to align the link to the right.

    Returns:
        Pager link or an empty fragment.
    """
    if item is None or item.route is None:
        return rx.fragment()
    return rx.el.a(
        rx.el.span(label, class_name="text-xs text-secondary-9"),
        rx.el.span(item.title, class_name="font-[525] text-secondary-12"),
        href=item.route,
        class_name=ui.cn(
            "flex flex-col gap-1 rounded-lg p-3 no-underline hover:bg-secondary-2",
            "items-end text-right" if align_right else "items-start",
        ),
    )


def _breadcrumb(page: DocsPage) -> rx.Component:
    """Render route breadcrumbs matching the official docs hierarchy.

    Args:
        page: Current documentation page.

    Returns:
        Breadcrumb navigation.
    """
    segments = [part for part in page.route.strip("/").split("/") if part]
    labels = [segment.replace("-", " ").title() for segment in segments]
    if not labels:
        labels = [page.title]
    elif labels[-1].lower() != page.title.lower():
        labels.append(page.title)
    children: list[rx.Component] = []
    for index, label in enumerate(labels):
        if index:
            children.append(
                ui.icon(
                    "ArrowRight01Icon",
                    class_name="size-4 text-secondary-11",
                )
            )
        children.append(
            rx.el.span(
                label,
                class_name=ui.cn(
                    "text-sm font-[525]",
                    (
                        "text-secondary-11"
                        if index == len(labels) - 1
                        else "text-secondary-12"
                    ),
                ),
            )
        )
    return rx.el.nav(
        *children,
        custom_attrs={"aria-label": "Breadcrumb"},
        class_name="mb-10 flex min-h-8 items-center gap-4 overflow-hidden",
    )


def _right_sidebar(
    page: DocsPage,
    toc: list[tuple[int, str]],
    *,
    show_banner: bool,
) -> rx.Component:
    """Render the official-style on-page table of contents.

    Args:
        page: Current documentation page.
        toc: Parsed page headings.
        show_banner: Whether the shared announcement banner is rendered.

    Returns:
        Sticky table-of-contents navigation.
    """
    del page
    return docs_right_sidebar(
        toc,
        feedback=docs_feedback_button_toc(),
        show_banner=show_banner,
    )


def _default_footer(config: DocsLayoutConfig, page: DocsPage) -> rx.Component:
    """Render the shared documentation feedback and footer area.

    Args:
        config: Shared layout configuration.
        page: Current documentation page.

    Returns:
        Documentation footer.
    """
    feedback = rx.box(
        rx.text(
            "Did you find this useful?",
            class_name="whitespace-nowrap font-small text-secondary-11 lg:text-secondary-9",
        ),
        docs_feedback_button(),
        class_name="flex w-full flex-col items-center gap-3 rounded-lg bg-secondary-3 p-4 lg:w-auto lg:flex-row lg:gap-4 lg:bg-transparent lg:p-0",
    )
    actions = (
        rx.box(
            rx.el.a(
                "Edit this page",
                href=f"{config.github_url.rstrip('/')}/blob/main/docs/{page.relative_path.as_posix()}",
                target="_blank",
                class_name="hidden rounded-full border border-secondary-5 bg-secondary-1 px-3 py-0.5 font-small text-secondary-9 no-underline shadow-large hover:bg-secondary-3 lg:flex",
            ),
            class_name="hidden flex-row items-center gap-2 lg:flex",
        )
        if config.github_url
        else rx.fragment()
    )
    footer_links = config.nav_links or (("Overview", "/"),)
    link_columns = rx.box(
        rx.box(
            rx.el.h4(
                config.site_title,
                class_name="text-sm font-semibold text-secondary-12",
            ),
            *(
                rx.el.a(
                    label,
                    href=href,
                    class_name="font-small text-secondary-9 no-underline hover:text-secondary-11",
                )
                for label, href in footer_links
            ),
            class_name="flex flex-col gap-4",
        ),
        class_name="flex w-full flex-wrap justify-between gap-12",
    )
    controls = rx.box(
        rx.box(dark_mode_toggle(), class_name="[&>div]:!ml-0"),
        class_name="flex w-full flex-row items-end justify-between gap-6",
    )
    copyright_status = rx.el.div(
        rx.text(
            f"Copyright © {datetime.now().year} {config.site_title}",
            class_name="font-small text-secondary-9",
        ),
        class_name="flex w-full flex-row items-center justify-between gap-4",
    )
    return docs_footer_shell(
        feedback,
        actions,
        link_columns,
        controls,
        copyright_status,
    )


def docs_layout(
    page: DocsPage,
    content: rx.Component,
    navigation: tuple[NavigationItem, ...],
    *,
    config: DocsLayoutConfig | None = None,
) -> rx.Component:
    """Wrap page content in the shared responsive documentation shell.

    Args:
        page: Current documentation page.
        content: Rendered page body.
        navigation: Full nested site navigation.
        config: Optional visual configuration.

    Returns:
        Complete documentation page component.
    """
    layout_config = config or DocsLayoutConfig()
    previous, next_ = get_prev_next(navigation, page.route)
    navbar = (
        layout_config.navbar()
        if layout_config.navbar is not None
        else _default_navbar(layout_config, navigation, page.route)
    )
    toc = get_markdown_toc(page.content)
    sidebar = (
        layout_config.sidebar(page.route)
        if layout_config.sidebar is not None
        else rx.el.nav(
            rx.el.ul(
                *(_navigation_item(item, page.route) for item in navigation),
                class_name="m-0 flex list-none flex-col gap-1 p-0",
            ),
            custom_attrs={"aria-label": "Documentation navigation"},
            class_name="flex h-full w-full flex-col items-start gap-8 overflow-x-hidden overflow-y-scroll pb-24 pl-6 pr-4 pt-8 3xl:pl-0",
        )
    )
    return docs_layout_shell(
        navbar,
        rx.el.main(
            docs_left_sidebar(
                sidebar,
                show_banner=layout_config.show_banner,
            ),
            rx.el.div(
                (
                    layout_config.breadcrumb(page, sidebar)
                    if layout_config.breadcrumb is not None
                    else _breadcrumb(page)
                ),
                rx.el.article(content, class_name="[&>div]:!p-0"),
                rx.el.nav(
                    _pager_link(previous, "Back"),
                    rx.spacer(),
                    _pager_link(next_, "Next", align_right=True),
                    custom_attrs={"aria-label": "Previous and next pages"},
                    class_name="mt-10 flex border-t border-secondary-4 pt-6",
                ),
                (
                    layout_config.page_footer(page)
                    if layout_config.page_footer is not None
                    else (
                        layout_config.footer()
                        if layout_config.footer is not None
                        else _default_footer(layout_config, page)
                    )
                ),
                class_name=ui.cn(
                    "mx-auto min-w-0 max-w-[64rem] flex-1 px-4 pb-10 lg:px-12",
                    (
                        rx.cond(
                            HostingBannerState.is_banner_visible,
                            "pt-[9.5rem]",
                            "pt-[7.25rem]",
                        )
                        if layout_config.show_banner
                        else "pt-[7.25rem]"
                    ),
                ),
            ),
            _right_sidebar(
                page,
                toc,
                show_banner=layout_config.show_banner,
            ),
            class_name="mx-auto flex min-h-screen w-full max-w-[108rem] justify-center",
        ),
    )


__all__ = [
    "DocsLayoutConfig",
    "docs_layout",
    "docs_layout_shell",
    "render_markdown_page",
]
