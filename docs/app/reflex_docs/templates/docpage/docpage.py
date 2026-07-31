"""Template for documentation pages."""

import functools
from collections.abc import Callable, Collection

import reflex as rx
import reflex_components_internal as ui
from reflex.components.radix.themes.base import LiteralAccentColor
from reflex.experimental.client_state import ClientStateVar
from reflex.utils.format import to_snake_case, to_title_case
from reflex_site_shared.components.blocks.code import *
from reflex_site_shared.components.blocks.demo import *
from reflex_site_shared.components.blocks.headings import *
from reflex_site_shared.components.blocks.typography import *
from reflex_site_shared.components.docs_page_actions import docs_page_actions
from reflex_site_shared.components.docs_shell import (
    docs_feedback_button_toc,
    docs_left_sidebar,
    docs_page_footer,
    docs_right_sidebar,
)
from reflex_site_shared.components.icons import get_icon
from reflex_site_shared.components.marketing_button import button as marketing_button
from reflex_site_shared.route import Route, get_path
from reflex_site_shared.templates.docs import docs_layout_shell
from reflex_site_shared.utils.docpage import right_sidebar_item_highlight

_REGISTERED_DOC_ROUTES: set[str] = set()

# Title-cased breadcrumb labels that should be displayed as acronyms.
_BREADCRUMB_LABEL_OVERRIDES: dict[str, str] = {
    "Ai": "AI",
    "Api": "API",
    "Sdk": "SDK",
    "Cli": "CLI",
    "Css": "CSS",
}


def _normalize_doc_route(path: str) -> str:
    """Normalize a docs route to use leading and trailing slashes."""
    route = f"/{path.strip('/')}"
    return "/" if route == "/" else f"{route}/"


def _register_doc_route(path: str) -> None:
    """Track a route registered through the docpage template."""
    _REGISTERED_DOC_ROUTES.add(_normalize_doc_route(path))


def _resolve_breadcrumb_href(
    href: str, registered_routes: Collection[str] | None = None
) -> str | None:
    """Resolve a generated breadcrumb href to a registered docs route.

    Breadcrumbs are built from path segments, but intermediate segments (e.g.
    ``/ai`` or ``/hosting``) are often just categories with no page of their
    own. This returns the matching route, preferring an ``overview`` child when
    the bare path is not itself a page, or ``None`` when no registered route
    exists so the caller can render the segment as non-clickable text instead of
    a broken link.

    Args:
        href: The generated, app-relative breadcrumb href (no ``/docs`` prefix).
        registered_routes: Routes to match against. Defaults to the routes
            registered through the docpage template.

    Returns:
        The resolved route, or ``None`` if no registered route matches.
    """
    routes = _REGISTERED_DOC_ROUTES if registered_routes is None else registered_routes
    route = _normalize_doc_route(href)
    if route in routes:
        return route

    overview_route = _normalize_doc_route(f"{route}overview")
    if overview_route in routes:
        return overview_route

    return None


def feedback_button_toc() -> rx.Component:
    return docs_feedback_button_toc()


@rx.memo
def copy_to_markdown(text: rx.Var[str]) -> rx.Component:
    copied = ClientStateVar.create("is_copied", default=False, global_ref=False)
    return marketing_button(
        rx.cond(
            copied.value,
            ui.icon(
                "CheckmarkCircle02Icon",
            ),
            get_icon("markdown", class_name="[&_svg]:h-4 [&_svg]:w-auto"),
        ),
        "Copy to markdown",
        type="button",
        size="sm",
        variant="ghost",
        class_name="justify-start pl-0 text-secondary-11",
        on_click=[
            rx.call_function(copied.set_value(True)),
            rx.set_clipboard(text),
        ],
        on_mouse_down=rx.call_function(copied.set_value(False)).debounce(1500),
    )


def ask_ai_chat() -> rx.Component:
    return rx.el.a(
        marketing_button(
            ui.icon("AiChat02Icon"),
            "Ask AI about this page",
            size="sm",
            variant="ghost",
            class_name="justify-start pl-0 text-secondary-11",
            native_button=False,
        ),
        to="/ai/integrations/mcp-overview/",
    )


@rx.memo
def docpage_footer(path: rx.Var[str]) -> rx.Component:
    """Render the shared official footer for a Reflex docs route."""
    return docs_page_footer(
        issue_href=(
            "https://github.com/reflex-dev/reflex/issues/new"
            "?template=documentation.md"
            "&labels=documentation"
            f"&title=Issue with reflex.dev{path}"
            f"&body=Path: {path}%0A%0A"
        ),
        edit_href=f"https://github.com/reflex-dev/reflex/blob/main/docs{path}.md",
    )


DOCS_PROD_BASE = "https://reflex.dev/docs"
LLMS_FULL_TXT_PATH = "/llms-full.txt"


def breadcrumb(path: str, nav_sidebar: rx.Component, doc_content: str | None = None):
    from reflex_docs.components.docpage.navbar.buttons.sidebar import (
        docs_sidebar_drawer,
    )

    # Split the path into segments, removing 'docs'.
    segments = [segment for segment in path.split("/") if segment and segment != "docs"]

    # Initialize an empty list to store the breadcrumbs and their separators
    breadcrumbs = []

    # Iteratively build the href for each segment (paths are app-relative, no /docs prefix)
    current_path = ""
    for i, segment in enumerate(segments):
        current_path += f"/{segment}"

        label = to_title_case(to_snake_case(segment), sep=" ")
        label = _BREADCRUMB_LABEL_OVERRIDES.get(label, label)
        base_class = ui.cn(
            "min-h-8 flex items-center text-sm font-[525] text-secondary-12 last:text-secondary-11",
            "truncate" if i == len(segments) - 1 else "",
        )

        # Category segments (e.g. /ai, /hosting) often have no page of their own.
        # Render those as plain text so the breadcrumb doesn't link to a 404.
        href = _resolve_breadcrumb_href(current_path)
        if href is None:
            breadcrumbs.append(rx.el.span(label, class_name=base_class))
        else:
            breadcrumbs.append(
                rx.el.a(
                    label,
                    class_name=ui.cn(
                        base_class,
                        "hover:text-primary-10 dark:hover:text-primary-9",
                    ),
                    underline="none",
                    href=href,
                )
            )

        # If it's not the last segment, add a separator
        if i < len(segments) - 1:
            breadcrumbs.append(
                ui.icon(
                    "ArrowRight01Icon",
                    class_name="lg:flex hidden text-secondary-11 size-4",
                ),
            )
            breadcrumbs.append(
                rx.text(
                    "/",
                    class_name="font-sm text-secondary-11 lg:hidden flex",
                )
            )
    from reflex_site_shared.views.hosting_banner import HostingBannerState

    # Return the list of breadcrumb items with separators
    return rx.box(
        docs_sidebar_drawer(
            nav_sidebar,
            trigger=rx.box(
                class_name="absolute inset-0 bg-transparent z-[1] lg:hidden flex",
            ),
        ),
        rx.box(
            *breadcrumbs,
            class_name="flex flex-row items-center gap-[5px] lg:gap-4 overflow-hidden",
        ),
        rx.box(
            docs_page_actions(
                markdown_url=f"{DOCS_PROD_BASE}{path.rstrip('/')}.md",
                llms_full_txt_url=LLMS_FULL_TXT_PATH,
            )
            if doc_content
            else rx.fragment(),
            ui.icon(
                "ArrowDown01Icon",
                size=14,
                class_name="!text-secondary-9 lg:hidden flex",
            ),
            class_name="flex flex-row items-center gap-2 lg:p-0 p-[0.563rem]",
        ),
        class_name=ui.cn(
            "relative z-10 flex flex-row justify-between items-center gap-4 lg:gap-0 border-secondary-4 mt-[139px] lg:p-0 border-b lg:border-none w-full max-lg:py-2",
            rx.cond(
                HostingBannerState.is_banner_visible,
                "lg:mt-[139px]",
                "lg:mt-[145px] mt-[77px]",
            ),
        ),
    )


def docpage(
    set_path: str | None = None,
    t: str | None = None,
    right_sidebar: bool = True,
    page_title: str | None = None,
    pseudo_right_bar: bool = False,
    description: str | None = None,
):
    """A template that most pages on the reflex.dev site should use.

    This template wraps the webpage with the navbar and footer.

    Args:
        set_path: The path to set for the sidebar.
        t: The title to set for the page.
        right_sidebar: Whether to show the right sidebar.
        page_title: The full title to set for the page. If None, defaults to `{title} · Reflex Docs`.
        pseudo_right_bar: Whether to show a pseudo right sidebar (empty space).
        description: The meta description for the page. If None, a descriptive
            fallback derived from the page title is used so the page always has
            a non-empty, page-specific meta description.

    Returns:
        A wrapper function that returns the full webpage.
    """

    def docpage(contents: Callable[[], Route]) -> Route:
        """Wrap a component in a docpage template.

        Args:
            contents: A function that returns a page route.

        Returns:
            The final route with the template applied.
        """
        path = get_path(contents, "reflex-docs/pages") if set_path is None else set_path
        _register_doc_route(path)

        title = contents.__name__.replace("_", " ").title() if t is None else t

        @functools.wraps(contents)
        def wrapper(*args, **kwargs) -> rx.Component:
            """The actual function wrapper.

            Args:
                *args: Args to pass to the contents function.
                **kwargs: Kwargs to pass to the contents function.

            Returns:
                The page with the template applied.
            """
            from reflex_site_shared.views.hosting_banner import HostingBannerState

            from reflex_docs.templates.docpage.sidebar import get_prev_next
            from reflex_docs.templates.docpage.sidebar import sidebar as sb
            from reflex_docs.views.docs_navbar import docs_navbar

            sidebar = sb(url=path, width="300px")

            nav_sidebar = sb(url=path, width="100%")

            prev, next = get_prev_next(path)
            links = []

            if prev:
                next_prev_name = prev.alt_name_for_next_prev or prev.names
                links.append(
                    rx.box(
                        rx.link(
                            rx.box(
                                get_icon(
                                    icon="arrow_right", transform="rotate(180deg)"
                                ),
                                "Back",
                                class_name="flex flex-row justify-center lg:justify-start items-center gap-2 rounded-lg w-full",
                            ),
                            underline="none",
                            href=prev.link,
                            class_name="py-0.5 lg:py-0 rounded-lg lg:w-auto font-small text-secondary-9 hover:!text-secondary-11 transition-color",
                        ),
                        rx.text(
                            next_prev_name, class_name="font-smbold text-secondary-12"
                        ),
                        class_name="flex flex-col justify-start gap-1",
                    )
                )
            else:
                links.append(rx.fragment())
            links.append(rx.spacer())

            if next:
                next_prev_name = next.alt_name_for_next_prev or next.names
                links.append(
                    rx.box(
                        rx.link(
                            rx.box(
                                "Next",
                                get_icon(icon="arrow_right"),
                                class_name="flex flex-row lg:justify-start items-center gap-2 rounded-lg w-full self-end",
                            ),
                            underline="none",
                            href=next.link,
                            class_name="py-0.5 lg:py-0 rounded-lg lg:w-auto font-small text-secondary-9 hover:!text-secondary-11 transition-color",
                        ),
                        rx.text(
                            next_prev_name, class_name="font-smbold text-secondary-12"
                        ),
                        class_name="flex flex-col justify-start gap-1 items-end",
                    )
                )
            else:
                links.append(rx.fragment())

            toc = []
            doc_content = None
            if not isinstance(contents, rx.Component):
                comp = contents(*args, **kwargs)
            else:
                comp = contents

            if isinstance(comp, tuple) and len(comp) == 2:
                first, second = comp
                # Check if first is (toc, doc_content) from get_toc
                if isinstance(first, tuple) and len(first) == 2:
                    toc, doc_content = first
                    comp = second
                else:
                    # Legacy format: (toc, comp)
                    toc, comp = first, second

            show_right_sidebar = right_sidebar and len(toc) >= 2
            return docs_layout_shell(
                docs_navbar(),
                rx.el.main(
                    docs_left_sidebar(sidebar),
                    rx.box(
                        rx.box(
                            breadcrumb(
                                path=path,
                                nav_sidebar=nav_sidebar,
                                doc_content=doc_content,
                            ),
                            class_name=(
                                "px-0 pt-0 mb-[2rem]"
                                + rx.cond(
                                    HostingBannerState.is_banner_visible,
                                    " mt-[90px]",
                                    "",
                                )
                            ),
                        ),
                        rx.box(
                            rx.el.article(comp, class_name="[&>div]:!p-0"),
                            rx.el.nav(
                                *links,
                                class_name="flex flex-row gap-2 mt-8 lg:mt-10 mb-6 lg:mb-12",
                            ),
                            docpage_footer(path=path.rstrip("/")),
                            class_name="lg:mt-0 h-auto",
                        ),
                        class_name=ui.cn(
                            "flex-1 h-auto mx-auto lg:max-w-[52rem] px-4 overflow-y-auto",
                            "lg:max-w-[64rem]" if not show_right_sidebar else "",
                        ),
                    ),
                    docs_right_sidebar(
                        toc,
                        path=path,
                        feedback=feedback_button_toc(),
                    )
                    if show_right_sidebar and not pseudo_right_bar
                    else rx.box(
                        class_name="w-[180px] h-screen sticky top-0 shrink-0 hidden xl:block"
                    ),
                    class_name="flex justify-center mx-auto mt-0 max-w-[108rem] h-full min-h-screen w-full",
                ),
                on_mount=rx.call_script(right_sidebar_item_highlight()),
            )

        # Section is the first path segment (these routes are mounted under
        # /docs at runtime, so the path itself has no "docs" prefix).
        segments = [c for c in path.split("/") if c]
        section = segments[0] if len(segments) > 1 else None
        category = (
            " ".join(word.capitalize() for word in section.replace("-", " ").split())
            if section
            else None
        )
        # Drop the section if it just repeats the page title (avoids titles like
        # "Introduction · Introduction · Reflex Docs").
        if category and category.lower() == title.lower():
            category = None

        # Build a descriptive, length-appropriate <title>. Nested docs pages
        # previously used the bare title (e.g. "Styling"), which is too short
        # for search engines; suffix the section and site so every doc title is
        # unique and substantial, dropping the section if it would push the
        # title past the ~60 char SERP truncation point.
        if page_title:
            seo_title = page_title
        else:
            with_category = (
                f"{title} · {category} · Reflex Docs"
                if category
                else f"{title} · Reflex Docs"
            )
            fallback = f"{title} · Reflex Docs"
            seo_title = (
                with_category
                if len(with_category) <= 60
                else (fallback if len(fallback) <= 60 else title)
            )

        # Always provide a non-empty, page-specific meta description. Real
        # descriptions come from the doc (see make_docpage); otherwise fall back
        # to a concise, title-derived sentence so the page is never description-less.
        from reflex_docs.pages.docs.metadata import truncate_meta_description

        seo_description = truncate_meta_description(
            description
            or (
                f"{title} — Reflex docs. Reflex is the open-source Python framework "
                "for building full-stack web apps and internal tools."
            )
        )

        return Route(
            path=path,
            title=seo_title,
            description=seo_description,
            component=wrapper,
        )

    return docpage


class RadixDocState(rx.State):
    """The app state."""

    color: str = "tomato"

    @rx.event
    def set_color(self, color: str):
        self.color = color


def hover_item(component: rx.Component, component_str: str) -> rx.Component:
    return rx.hover_card.root(
        rx.hover_card.trigger(rx.flex(component)),
        rx.hover_card.content(
            rx.el.button(
                get_icon(icon="copy", class_name="p-[5px]"),
                rx.text(
                    component_str,
                    class_name="flex-1 font-small truncate",
                ),
                on_click=rx.set_clipboard(component_str),
                class_name="flex flex-row items-center gap-1.5 border-secondary-5 bg-secondary-1 hover:bg-secondary-3 shadow-small pr-1.5 border rounded-md w-full max-w-[300px] text-secondary-11 transition-bg cursor-pointer",
            ),
        ),
    )


def dict_to_formatted_string(input_dict):
    # List to hold formatted string parts
    formatted_parts = []

    # Iterate over dictionary items
    for key, value in input_dict.items():
        # Format each key-value pair
        if isinstance(value, str):
            formatted_part = f'{key}="{value}"'  # Enclose string values in quotes
        else:
            formatted_part = f"{key}={value}"  # Non-string values as is

        # Append the formatted part to the list
        formatted_parts.append(formatted_part)

    # Join all parts with a comma and a space
    return ", ".join(formatted_parts)


def used_component(
    component_used: rx.Component,
    components_passed: rx.Component | str | None,
    color_scheme: str,
    variant: str,
    high_contrast: bool,
    disabled: bool = False,
    **kwargs,
) -> rx.Component:
    if components_passed is None and disabled is False:
        return component_used(
            color_scheme=color_scheme,
            variant=variant,
            high_contrast=high_contrast,
            **kwargs,
        )

    elif components_passed is not None and disabled is False:
        return component_used(
            components_passed,
            color_scheme=color_scheme,
            variant=variant,
            high_contrast=high_contrast,
            **kwargs,
        )

    elif components_passed is None and disabled is True:
        return component_used(
            color_scheme=color_scheme,
            variant=variant,
            high_contrast=high_contrast,
            disabled=True,
            **kwargs,
        )

    else:
        return component_used(
            components_passed,
            color_scheme=color_scheme,
            variant=variant,
            high_contrast=high_contrast,
            disabled=True,
            **kwargs,
        )


def style_grid(
    component_used: rx.Component,
    component_used_str: str,
    variants: list,
    components_passed: rx.Component | str | None = None,
    disabled: bool = False,
    **kwargs,
) -> rx.Component:
    text_cn = "text-nowrap font-md flex items-center"
    return rx.box(
        rx.grid(
            rx.text("", size="5"),
            *[
                rx.text(variant, class_name=text_cn + " text-secondary-11")
                for variant in variants
            ],
            rx.text(
                "Accent",
                color=f"var(--{RadixDocState.color}-10)",
                class_name=text_cn,
            ),
            *[
                hover_item(
                    component=used_component(
                        component_used=component_used,
                        components_passed=components_passed,
                        color_scheme=RadixDocState.color,
                        variant=variant,
                        high_contrast=False,
                        **kwargs,
                    ),
                    component_str=f"{component_used_str}(color_scheme={RadixDocState.color}, variant={variant}, high_contrast=False, {dict_to_formatted_string(kwargs)})",
                )
                for variant in variants
            ],
            rx.text("", size="5"),
            *[
                hover_item(
                    component=used_component(
                        component_used=component_used,
                        components_passed=components_passed,
                        color_scheme=RadixDocState.color,
                        variant=variant,
                        high_contrast=True,
                        **kwargs,
                    ),
                    component_str=f"{component_used_str}(color_scheme={RadixDocState.color}, variant={variant}, high_contrast=True, {dict_to_formatted_string(kwargs)})",
                )
                for variant in variants
            ],
            rx.text("Gray", class_name=text_cn + " text-secondary-11"),
            *[
                hover_item(
                    component=used_component(
                        component_used=component_used,
                        components_passed=components_passed,
                        color_scheme="gray",
                        variant=variant,
                        high_contrast=False,
                        **kwargs,
                    ),
                    component_str=f"{component_used_str}(color_scheme={RadixDocState.color}, variant={variant}, high_contrast=False, {dict_to_formatted_string(kwargs)})",
                )
                for variant in variants
            ],
            rx.text("", size="5"),
            *[
                hover_item(
                    component=used_component(
                        component_used=component_used,
                        components_passed=components_passed,
                        color_scheme="gray",
                        variant=variant,
                        high_contrast=True,
                        **kwargs,
                    ),
                    component_str=f"{component_used_str}(color_scheme={RadixDocState.color}, variant={variant}, high_contrast=True, {dict_to_formatted_string(kwargs)})",
                )
                for variant in variants
            ],
            (
                rx.fragment(
                    rx.text("Disabled", class_name=text_cn + " text-secondary-11"),
                    *[
                        hover_item(
                            component=used_component(
                                component_used=component_used,
                                components_passed=components_passed,
                                color_scheme="gray",
                                variant=variant,
                                high_contrast=True,
                                disabled=disabled,
                                **kwargs,
                            ),
                            component_str=f"{component_used_str}(color_scheme={RadixDocState.color}, variant={variant}, disabled=True, {dict_to_formatted_string(kwargs)})",
                        )
                        for variant in variants
                    ],
                )
                if disabled
                else ""
            ),
            flow="column",
            columns="5",
            rows=str(len(variants) + 1),
            spacing="3",
        ),
        rx.popover.root(
            rx.popover.trigger(
                rx.box(
                    rx.button(
                        rx.text(RadixDocState.color, class_name="font-small"),
                        # Match the select.trigger svg icon
                        rx.html(
                            """<svg width="9" height="9" viewBox="0 0 9 9" fill="currentcolor" xmlns="http://www.w3.org/2000/svg" class="rt-SelectIcon" aria-hidden="true"><path d="M0.135232 3.15803C0.324102 2.95657 0.640521 2.94637 0.841971 3.13523L4.5 6.56464L8.158 3.13523C8.3595 2.94637 8.6759 2.95657 8.8648 3.15803C9.0536 3.35949 9.0434 3.67591 8.842 3.86477L4.84197 7.6148C4.64964 7.7951 4.35036 7.7951 4.15803 7.6148L0.158031 3.86477C-0.0434285 3.67591 -0.0536285 3.35949 0.135232 3.15803Z"></path></svg>"""
                        ),
                        color_scheme=RadixDocState.color,
                        variant="surface",
                        class_name="justify-between w-32",
                    ),
                ),
            ),
            rx.popover.content(
                rx.grid(
                    *[
                        rx.box(
                            rx.icon(
                                "check",
                                size=15,
                                class_name="top-1/2 left-1/2 absolute text-secondary-12 transform -translate-x-1/2 -translate-y-1/2"
                                + rx.cond(
                                    RadixDocState.color == color,
                                    " block",
                                    " hidden",
                                ),
                            ),
                            on_click=RadixDocState.set_color(color),
                            background_color=f"var(--{color}-9)",
                            class_name="relative rounded-md cursor-pointer shrink-0 size-[30px]"
                            + rx.cond(
                                RadixDocState.color == color,
                                " border-2 border-secondary-12",
                                "",
                            ),
                        )
                        for color in list(map(str, LiteralAccentColor.__args__))
                    ],
                    columns="6",
                    spacing="3",
                ),
            ),
        ),
        class_name="flex flex-col justify-center items-center gap-6 border-secondary-4 bg-secondary-2 mb-4 p-6 border rounded-xl",
    )
