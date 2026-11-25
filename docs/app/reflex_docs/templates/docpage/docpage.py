"""Template for documentation pages."""

import functools
import os
import sys
from collections.abc import Callable, Collection, Sequence
from pathlib import Path
from urllib.parse import quote

import reflex as rx
import reflex_components_internal as ui
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
from reflex_site_shared.route import Route, get_path
from reflex_site_shared.templates.docs import docs_layout_shell
from reflex_site_shared.utils.docpage import right_sidebar_item_highlight

from reflex_docs.sections import navbar_tab
from reflex_docs.utils.acronyms import uppercase_acronyms

_REGISTERED_DOC_ROUTES: set[str] = set()

# The docs app lives at <repo>/docs/app; source files are linked relative to <repo>.
REPO_ROOT = Path(__file__).resolve().parents[5]
# Installed packages may live in a venv inside the checkout; their files are not
# editable on GitHub.
_SYS_PREFIX = Path(sys.prefix).resolve()
GITHUB_REPO_URL = "https://github.com/reflex-dev/reflex"

# Normalized route -> GitHub edit URL used by the page footer.
doc_edit_hrefs: dict[str, str] = {}


def _normalize_doc_route(path: str) -> str:
    """Normalize a docs route to use leading and trailing slashes."""
    route = f"/{path.strip('/')}"
    return "/" if route == "/" else f"{route}/"


def _register_doc_route(path: str) -> None:
    """Track a route registered through the docpage template."""
    _REGISTERED_DOC_ROUTES.add(_normalize_doc_route(path))


def github_edit_url(source_path: str | None) -> str:
    """Build the GitHub edit URL for the file a docs page is generated from.

    Args:
        source_path: Path of the markdown or Python source of the page.

    Returns:
        The edit URL of the file, or an empty string when there is no editable
        source in this checkout (e.g. docs shipped inside an installed package).
        Preview builds can select their source branch with ``DOCS_GITHUB_REF``.
    """
    if source_path is None:
        return ""
    resolved = Path(source_path).resolve()
    if not resolved.is_relative_to(REPO_ROOT) or resolved.is_relative_to(_SYS_PREFIX):
        return ""
    ref = quote(os.environ.get("DOCS_GITHUB_REF") or "main", safe="")
    relative_path = quote(resolved.relative_to(REPO_ROOT).as_posix())
    return f"{GITHUB_REPO_URL}/edit/{ref}/{relative_path}"


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


DOCS_PROD_BASE = "https://reflex.dev/docs"


@rx.memo
def docpage_footer(path: rx.Var[str], edit_href: rx.Var[str]) -> rx.Component:
    """Render the shared official footer for a Reflex docs route.

    Args:
        path: The route of the current page, without a trailing slash.
        edit_href: GitHub edit URL of the page's source file.

    Returns:
        The footer component.
    """
    return docs_page_footer(
        issue_href=(
            f"{GITHUB_REPO_URL}/issues/new"
            "?template=documentation.md"
            "&labels=documentation"
            f"&title=Issue%20with%20{DOCS_PROD_BASE}{path}"
            f"&body=Path:%20{DOCS_PROD_BASE}{path}%0A%0A"
        ),
        edit_href=edit_href,
    )


LLMS_FULL_TXT_PATH = "/llms-full.txt"


def breadcrumb_data(path: str, title: str) -> dict:
    """Build structured breadcrumbs using the visible navigation's route resolver.

    Args:
        path: The app-relative documentation path.
        title: The current page's name.

    Returns:
        A schema.org BreadcrumbList with canonical public URLs.
    """
    base = DOCS_PROD_BASE
    canonical = base + _normalize_doc_route(path)
    items = [
        {
            "@type": "ListItem",
            "position": 1,
            "name": "Documentation",
            "item": base + "/",
        }
    ]
    seen = {base + "/", canonical}
    segments = path.strip("/").split("/")
    for index, segment in enumerate(segments[:-1], 1):
        href = _resolve_breadcrumb_href("/" + "/".join(segments[:index]))
        if href is None or base + href in seen:
            continue
        items.append({
            "@type": "ListItem",
            "position": len(items) + 1,
            "name": _breadcrumb_label(segment),
            "item": base + href,
        })
        seen.add(base + href)
    if canonical != base + "/":
        items.append({
            "@type": "ListItem",
            "position": len(items) + 1,
            "name": title,
            "item": canonical,
        })
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": items,
    }


# Route segments whose section goes by another name in the navbar and sidebar.
_SECTION_LABELS = {"hosting": "Cloud", "library": "Components"}


def _breadcrumb_label(segment: str) -> str:
    """Turn a route segment into a breadcrumb label, keeping acronyms uppercase.

    Args:
        segment: A kebab- or snake-case route segment, such as ``api-reference``.

    Returns:
        The section's navigation name for a section segment, such as ``Cloud``
        for ``hosting``; otherwise the title-cased label, such as ``API Reference``.
    """
    if (label := _SECTION_LABELS.get(segment)) is not None:
        return label
    return uppercase_acronyms(to_title_case(to_snake_case(segment), sep=" "))


def _same_letters(label: str, segment: str) -> bool:
    """Whether a label spells a route segment, ignoring case and punctuation.

    Args:
        label: A display name, such as ``Upgrading to 0.11``.
        segment: A route segment, such as ``upgrading-to-0-11``.

    Returns:
        True when both have the same letters and digits in the same order.
    """
    return [c for c in label.lower() if c.isalnum()] == [
        c for c in segment.lower() if c.isalnum()
    ]


def _breadcrumb_items(
    path: str, names: Sequence[str] = ()
) -> list[tuple[str, str | None]]:
    """List the visible breadcrumb labels and their links.

    Args:
        path: The app-relative documentation path.
        names: The current page's display names, such as its title and sidebar
            label. The first one that spells the last route segment labels it, so
            "upgrading-to-0-11" reads "Upgrading to 0.11"; a name with other words
            is skipped and the segment is title-cased like its parents.

    Returns:
        A ``(label, href)`` pair per path segment. ``href`` is None for category
        segments that have no page of their own.
    """
    segments = [segment for segment in path.split("/") if segment and segment != "docs"]
    items = []
    current_path = ""
    for segment in segments:
        current_path += f"/{segment}"
        items.append((
            _breadcrumb_label(segment),
            _resolve_breadcrumb_href(current_path),
        ))
    if items:
        for name in names:
            label = uppercase_acronyms(name)
            if _same_letters(label, segments[-1]):
                items[-1] = (label, items[-1][1])
                break
    return items


def breadcrumb(
    path: str,
    nav_sidebar: rx.Component,
    doc_content: str | None = None,
    names: Sequence[str] = (),
):
    from reflex_docs.components.docpage.navbar.buttons.sidebar import (
        docs_sidebar_drawer,
    )

    # Initialize an empty list to store the breadcrumbs and their separators
    breadcrumbs = []

    items = _breadcrumb_items(path, names)
    for i, (label, href) in enumerate(items):
        base_class = ui.cn(
            "min-h-8 flex items-center text-sm font-[525] text-foreground last:text-muted-foreground",
            "truncate" if i == len(items) - 1 else "",
        )

        # Category segments (e.g. /ai, /hosting) often have no page of their own.
        # Render those as plain text so the breadcrumb doesn't link to a 404.
        if href is None:
            breadcrumbs.append(rx.el.span(label, class_name=base_class))
        else:
            breadcrumbs.append(
                rx.el.a(
                    label,
                    class_name=ui.cn(
                        base_class,
                        "hover:text-primary-hover dark:hover:text-primary",
                    ),
                    underline="none",
                    href=href,
                )
            )

        # If it's not the last segment, add a separator
        if i < len(items) - 1:
            breadcrumbs.append(
                ui.icon(
                    "ArrowRight01Icon",
                    class_name="lg:flex hidden text-muted-foreground size-4",
                ),
            )
            breadcrumbs.append(
                rx.text(
                    "/",
                    class_name="font-sm text-muted-foreground lg:hidden flex",
                )
            )

    # Return the list of breadcrumb items with separators
    return rx.box(
        docs_sidebar_drawer(
            nav_sidebar,
            trigger=rx.el.button(
                type="button",
                aria_label="Open documentation navigation",
                class_name="absolute inset-0 bg-transparent z-[1] lg:hidden flex focus-visible:outline-2 focus-visible:outline-primary",
            ),
        ),
        rx.el.nav(
            *breadcrumbs,
            aria_label="Breadcrumb",
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
                class_name="!text-subtle-foreground lg:hidden flex",
            ),
            class_name="flex flex-row items-center gap-2 lg:p-0 p-[0.563rem]",
        ),
        class_name=ui.cn(
            "relative z-10 flex flex-row justify-between items-center gap-4 lg:gap-0 border-border-subtle lg:p-0 border-b lg:border-none w-full max-lg:py-2",
            "mt-[var(--docs-header-height)] lg:mt-[calc(var(--docs-header-height)+2rem)]",
        ),
    )


def page_navigation_link(title: str, href: str, *, forward: bool) -> rx.Component:
    """Render the entire adjacent-page block as a single link.

    Args:
        title: Destination page title.
        href: Destination route.
        forward: Whether this is the next page rather than the previous page.

    Returns:
        Padded link containing the direction and destination title.
    """
    arrow = get_icon(
        icon="arrow_right", transform="none" if forward else "rotate(180deg)"
    )
    label = rx.el.span("Next" if forward else "Back")
    return rx.el.a(
        rx.el.span(
            *([label, arrow] if forward else [arrow, label]),
            class_name="flex items-center gap-2 font-small text-subtle-foreground group-hover:text-foreground",
        ),
        rx.el.span(
            title,
            class_name="text-base font-[500] leading-6 tracking-[-0.015rem] text-foreground",
        ),
        href=href,
        class_name=(
            "group flex min-w-0 flex-col gap-1 rounded-lg p-3 no-underline "
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring "
            + (
                "col-start-2 items-end text-right"
                if forward
                else "items-start text-left"
            )
        ),
    )


def docpage(
    set_path: str | None = None,
    t: str | None = None,
    right_sidebar: bool = True,
    page_title: str | None = None,
    pseudo_right_bar: bool = False,
    description: str | None = None,
    image: str | None = None,
    source_path: str | None = None,
    show_breadcrumb: bool = True,
    component_name: str | None = None,
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
        image: Social-preview image (relative path or absolute URL).
        source_path: File the page is generated from, used for the footer's
            "Edit this page" link. Defaults to the Python file defining the page.
        show_breadcrumb: Whether to display the page breadcrumb. Mobile sidebar
            access remains available when the breadcrumb is hidden.
        component_name: The public component name a library page documents,
            used to lead its search title.

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
        # Pages built in Python are edited in the module that defines them.
        edit_href = github_edit_url(
            source_path
            if source_path is not None
            else getattr(getattr(contents, "__code__", None), "co_filename", None)
        )
        doc_edit_hrefs[_normalize_doc_route(path)] = edit_href

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
            from reflex_docs.templates.docpage.sidebar import (
                get_prev_next,
                sidebar_label,
            )
            from reflex_docs.templates.docpage.sidebar import sidebar as sb
            from reflex_docs.views.docs_navbar import docs_navbar

            sidebar = sb(url=path, width="300px")

            nav_sidebar = sb(url=path, width="100%")

            prev, next = get_prev_next(path)
            links = []

            if prev:
                links.append(
                    page_navigation_link(
                        prev.alt_name_for_next_prev or prev.names,
                        prev.link,
                        forward=False,
                    )
                )
            if next:
                links.append(
                    page_navigation_link(
                        next.alt_name_for_next_prev or next.names,
                        next.link,
                        forward=True,
                    )
                )

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
                docs_navbar(active_tab=navbar_tab(path)),
                rx.el.main(
                    docs_left_sidebar(sidebar),
                    rx.box(
                        rx.box(
                            breadcrumb(
                                path=path if show_breadcrumb else "",
                                nav_sidebar=nav_sidebar,
                                doc_content=doc_content,
                                names=[
                                    name
                                    for name in (title, sidebar_label(path))
                                    if name is not None
                                ],
                            ),
                            class_name=(
                                "docs-breadcrumb px-0 pt-0 mb-4"
                                + ("" if show_breadcrumb else " lg:hidden")
                            ),
                        ),
                        rx.box(
                            rx.el.article(
                                comp,
                                class_name="docs-article [&>div]:!p-0"
                                + (
                                    " [&_.rt-TableRoot]:!border-0 [&_.rt-TableRoot]:!rounded-none"
                                    " [&_.rt-TableCell]:!shadow-none [&_.rt-TableCell]:!border-b [&_.rt-TableCell]:!border-border"
                                    " [&_.rt-TableCell]:!text-sm [&_.rt-TableCell]:!leading-6 [&_.rt-TableCell]:!text-foreground"
                                    " [&_.rt-TableCell_p]:!text-sm [&_.rt-TableCell_p]:!leading-6 [&_.rt-TableCell_p]:!my-0"
                                    if path.startswith("/api-reference/")
                                    else ""
                                ),
                            ),
                            rx.el.nav(
                                *links,
                                aria_label="Adjacent documentation pages",
                                class_name="docs-page-navigation grid grid-cols-2 gap-2 mt-8 lg:mt-10 mb-6 lg:mb-12",
                            ),
                            docpage_footer(path=path.rstrip("/"), edit_href=edit_href),
                            class_name="lg:mt-0 h-auto"
                            + (
                                ""
                                if show_breadcrumb
                                else " lg:pt-[calc(var(--docs-header-height)+2rem)]"
                            ),
                        ),
                        class_name=ui.cn(
                            "docs-reading-column flex-1 min-w-0 h-auto mx-auto lg:max-w-[56rem] px-4 lg:px-8 xl:px-12 overflow-y-auto",
                            "lg:max-w-[68rem]" if not show_right_sidebar else "",
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
                    class_name="docs-reading-layout flex justify-center mx-auto mt-0 max-w-[108rem] h-full min-h-screen w-full",
                ),
                on_mount=rx.call_script(right_sidebar_item_highlight()),
            )

        from reflex_docs.pages.docs.metadata import docs_metadata

        seo_title, seo_description = docs_metadata(
            path, title, description, component_name
        )
        if page_title:
            seo_title = page_title

        return Route(
            path=path,
            title=seo_title,
            description=seo_description,
            image=image,
            component=wrapper,
        )

    return docpage
