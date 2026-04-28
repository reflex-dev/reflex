"""Template for documentation pages."""

import functools
from datetime import datetime
from typing import Callable

import reflex as rx
import reflex_components_internal as ui
from reflex.components.radix.themes.base import LiteralAccentColor
from reflex.experimental.client_state import ClientStateVar
from reflex.utils.format import to_snake_case, to_title_case
from reflex_base.event import run_script
from reflex_site_shared.backend.status import StatusState
from reflex_site_shared.components.blocks.code import *
from reflex_site_shared.components.blocks.demo import *
from reflex_site_shared.components.blocks.headings import *
from reflex_site_shared.components.blocks.typography import *
from reflex_site_shared.components.icons import get_icon
from reflex_site_shared.components.marketing_button import button as marketing_button
from reflex_site_shared.components.server_status import server_status
from reflex_site_shared.route import Route, get_path
from reflex_site_shared.styles.colors import c_color
from reflex_site_shared.utils.docpage import right_sidebar_item_highlight
from reflex_site_shared.views.footer import dark_mode_toggle


class FeedbackState(rx.State):
    """Minimal stub for feedback buttons (full implementation removed)."""

    score: int = -1

    def set_score(self, score: int):
        self.score = score

    def handle_submit(self, form_data: dict):
        pass


def footer_link(text: str, href: str):
    return rx.link(
        text,
        class_name="font-small text-slate-9 hover:!text-slate-11 transition-color",
        href=href,
        underline="none",
    )


def footer_link_flex(heading: str, links):
    return rx.box(
        rx.el.h4(
            heading,
            class_name="font-semibold text-slate-12 text-sm tracking-[-0.01313rem]",
        ),
        *links,
        class_name="flex flex-col gap-4",
    )


def thumb_card(score: int, icon: str) -> rx.Component:
    return rx.el.button(
        ui.icon(
            icon,
            color=rx.cond(
                FeedbackState.score == score, c_color("slate", 11), c_color("slate", 9)
            ),
            size=16,
        ),
        background_color=rx.cond(
            FeedbackState.score == score, c_color("slate", 3), c_color("white", 1)
        ),
        on_click=FeedbackState.set_score(score),
        class_name="transition-bg hover:bg-slate-3 shadow-medium border border-slate-4 rounded-lg items-center justify-center cursor-pointer p-2 size-9 flex",
    )


def thumbs_cards() -> rx.Component:
    return rx.hstack(
        thumb_card(1, "ThumbsUpIcon"),
        thumb_card(0, "ThumbsDownIcon"),
        gap="8px",
    )


def feedback_content() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.form(
                rx.el.div(
                    ui.textarea(
                        name="feedback",
                        placeholder="Write a comment…",
                        type="text",
                        max_length=500,
                        enter_key_submit=True,
                        resize="vertical",
                        required=True,
                    ),
                    thumbs_cards(),
                    ui.input(
                        name="email",
                        type="email",
                        placeholder="Contact email (optional)",
                        max_length=100,
                    ),
                    ui.popover.close(
                        ui.button(
                            "Send feedback",
                            type="submit",
                            class_name="w-full",
                        )
                    ),
                    class_name="w-full gap-4 flex flex-col",
                ),
                class_name="w-full",
                reset_on_submit=True,
                on_submit=FeedbackState.handle_submit,
            ),
            class_name="flex flex-col gap-4 w-full",
        ),
        class_name="p-2",
    )


def feedback_button() -> rx.Component:
    thumb_cn = " flex flex-row items-center justify-center gap-2 text-slate-9 whitespace-nowrap border border-slate-5 bg-slate-1 shadow-large cursor-pointer transition-bg hover:bg-slate-3 font-small"
    return ui.popover.root(
        ui.popover.trigger(
            render_=rx.el.div(
                rx.el.button(
                    ui.icon("ThumbsUpIcon"),
                    "Yes",
                    type="button",
                    class_name=ui.cn(
                        "w-full gap-2 border-r-0 px-3 py-0.5 rounded-[20px_0_0_20px]",
                        thumb_cn,
                    ),
                    aria_label="Yes",
                    on_click=FeedbackState.set_score(1),
                ),
                rx.el.button(
                    ui.icon("ThumbsDownIcon"),
                    "No",
                    type="button",
                    class_name=ui.cn(
                        "w-full gap-2 border-r-0 px-3 py-0.5 rounded-[0_20px_20px_0]",
                        thumb_cn,
                    ),
                    aria_label="No",
                    on_click=FeedbackState.set_score(0),
                ),
                class_name="w-full lg:w-auto items-center flex flex-row",
            ),
        ),
        ui.popover.portal(
            ui.popover.positioner(
                ui.popover.popup(
                    render_=feedback_content(),
                ),
            ),
        ),
    )


def feedback_button_toc() -> rx.Component:
    return ui.popover(
        trigger=marketing_button(
            ui.icon("ThumbsUpIcon"),
            "Send feedback",
            variant="ghost",
            size="sm",
            type="button",
            on_click=FeedbackState.set_score(1),
            class_name="justify-start pl-0 text-m-slate-7 dark:text-m-slate-6",
        ),
        content=feedback_content(),
    )


@rx.memo
def copy_to_markdown(text: str) -> rx.Component:
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
        class_name="justify-start pl-0 text-m-slate-7 dark:text-m-slate-6",
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
            class_name="justify-start pl-0 text-m-slate-7 dark:text-m-slate-6",
            native_button=False,
        ),
        to="/ai-builder/integrations/mcp-overview/",
    )


def link_pill(text: str, href: str) -> rx.Component:
    return rx.link(
        text,
        href=href,
        underline="none",
        class_name="lg:flex hidden flex-row justify-center items-center gap-2 lg:border-slate-5 bg-slate-3 lg:bg-slate-1 hover:bg-slate-3 shadow-none lg:shadow-large px-3 py-0.5 lg:border lg:border-solid border-none rounded-lg lg:rounded-full w-auto font-small font-small text-slate-9 !hover:text-slate-11 hover:!text-slate-9 truncate whitespace-nowrap transition-bg transition-color cursor-pointer",
    )


@rx.memo
def docpage_footer(path: str):
    from reflex_site_shared.constants import FORUM_URL, ROADMAP_URL
    from reflex_site_shared.views.footer import menu_socials

    return rx.el.footer(
        rx.box(
            rx.box(
                rx.text(
                    "Did you find this useful?",
                    class_name="font-small text-slate-11 lg:text-slate-9 whitespace-nowrap",
                ),
                feedback_button(),
                class_name="flex lg:flex-row flex-col items-center gap-3 lg:gap-4 bg-slate-3 lg:bg-transparent p-4 lg:p-0 rounded-lg w-full",
            ),
            rx.box(
                link_pill(
                    "Raise an issue",
                    href=f"https://github.com/reflex-dev/reflex-web/issues/new?title=Issue with reflex.dev documentation&amp;body=Path: {path}",
                ),
                link_pill(
                    "Edit this page",
                    f"https://github.com/reflex-dev/reflex-web/tree/main{path}.md",
                ),
                class_name="lg:flex hidden flex-row items-center gap-2 w-auto",
            ),
            class_name="flex flex-row justify-center lg:justify-between items-center border-slate-4 border-y-0 lg:border-y pt-0 lg:pt-8 pb-6 lg:pb-8 w-full",
        ),
        rx.box(
            rx.box(
                footer_link_flex(
                    "Links",
                    [
                        footer_link("Home", "/"),
                        footer_link("Blog", "/blog"),
                        footer_link(
                            "Changelog", "https://github.com/reflex-dev/reflex/releases"
                        ),
                    ],
                ),
                footer_link_flex(
                    "Documentation",
                    [
                        footer_link("Introduction", "/getting-started/introduction/"),
                        footer_link("Installation", "/getting-started/installation/"),
                        footer_link("Components", "/library/"),
                        footer_link("Hosting", "/hosting/deploy-quick-start/"),
                    ],
                ),
                footer_link_flex(
                    "Resources",
                    [
                        footer_link("FAQ", "/faq/"),
                        footer_link("Roadmap", ROADMAP_URL),
                        footer_link("Forum", FORUM_URL),
                    ],
                ),
                class_name="flex flex-wrap justify-between gap-12 w-full",
            ),
            rx.box(
                rx.box(dark_mode_toggle(), class_name="[&>div]:!ml-0"),
                menu_socials(),
                class_name="flex flex-row gap-6 justify-between items-end w-full",
            ),
            rx.el.div(
                rx.text(
                    f"Copyright © {datetime.now().year} Pynecone, Inc.",
                    class_name="font-small text-slate-9",
                ),
                server_status(StatusState.status),
                class_name="flex flex-row items-center gap-4 justify-between w-full",
            ),
            class_name="flex flex-col justify-between gap-10 py-6 lg:py-8 w-full",
        ),
        class_name="flex flex-col w-full max-w-full lg:max-w-auto",
    )


def _copy_page_menu_item(
    icon: rx.Component,
    title: str,
    description: str,
    on_click=None,
    href: str | None = None,
) -> rx.Component:
    row = rx.el.div(
        rx.el.div(
            icon,
            class_name="flex size-8 items-center justify-center rounded-md border border-slate-5 bg-slate-2 text-slate-11 shrink-0",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.span(title, class_name="text-sm font-medium text-slate-12"),
                ui.icon(
                    "ArrowUpRight01Icon",
                    size=12,
                    class_name="!text-slate-9",
                )
                if href
                else rx.fragment(),
                class_name="flex items-center gap-1",
            ),
            rx.el.span(
                description,
                class_name="text-xs text-slate-10",
            ),
            class_name="flex flex-col items-start gap-0.5",
        ),
        class_name="flex items-start gap-3 px-3 py-2 w-full hover:bg-slate-3 transition-colors cursor-pointer",
    )
    if href:
        return rx.el.a(
            row,
            href=href,
            target="_blank",
            rel="noopener noreferrer",
            class_name="no-underline",
        )
    return rx.el.button(
        row,
        type="button",
        on_click=on_click,
        class_name="w-full text-left",
    )


DOCS_PROD_BASE = "https://reflex.dev/docs"


def _build_prefill_url(base_url: str, path: str, action: str) -> str:
    from urllib.parse import quote

    page_md_url = f"{DOCS_PROD_BASE}{path.rstrip('/')}.md"
    prompt = f"Read from {page_md_url} {action}"
    return f"{base_url}{quote(prompt)}"


def _build_reflex_menu_item(path: str) -> rx.Component:
    href = _build_prefill_url(
        "https://build.reflex.dev/?prompt=",
        path,
        "and help me build an app based on it.",
    )
    return rx.el.a(
        rx.el.div(
            rx.el.div(
                ui.icon(
                    "AiMagicIcon",
                    size=16,
                    class_name="!text-white",
                ),
                class_name=(
                    "flex size-8 items-center justify-center rounded-md "
                    "bg-gradient-to-br from-violet-9 to-violet-11 "
                    "shadow-[0_0_0_1px_var(--violet-7),0_2px_8px_-2px_var(--violet-a8)] shrink-0"
                ),
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.span(
                        "Build this with AI",
                        class_name="text-sm font-semibold text-slate-12",
                    ),
                    ui.icon(
                        "ArrowUpRight01Icon",
                        size=12,
                        class_name="!text-violet-11",
                    ),
                    class_name="flex items-center gap-1",
                ),
                rx.el.span(
                    "Open in Reflex Build",
                    class_name="text-xs text-slate-10",
                ),
                class_name="flex flex-col items-start gap-0.5",
            ),
            class_name="flex items-start gap-3 px-3 py-2.5 w-full",
        ),
        href=href,
        target="_blank",
        rel="noopener noreferrer",
        class_name=(
            "no-underline w-full text-left block "
            "bg-gradient-to-br from-violet-2 to-slate-1 "
            "hover:from-violet-3 hover:to-violet-2 "
            "border-b border-slate-4 transition-colors cursor-pointer"
        ),
    )


def _llm_menu_item_href(base_url: str, path: str) -> str:
    return _build_prefill_url(
        base_url, path, "so I can ask questions about its contents"
    )


def _copy_page_button(doc_content: str, path: str = "") -> rx.Component:
    copy_action = run_script(
        """
((function() {
  const mdUrl = window.location.pathname.replace(/\\/$/, '') + '.md';
  const animate = () => {
    document.querySelectorAll('[data-copy-icon]').forEach((icon) => {
      if (icon.dataset.animating === '1') return;
      icon.dataset.animating = '1';
      const original = icon.innerHTML;
      const check = '<svg xmlns=\\"http://www.w3.org/2000/svg\\" width=\\"16\\" height=\\"16\\" viewBox=\\"0 0 24 24\\" fill=\\"none\\" stroke=\\"currentColor\\" stroke-width=\\"2\\" stroke-linecap=\\"round\\" stroke-linejoin=\\"round\\"><polyline points=\\"20 6 9 17 4 12\\"></polyline></svg>';
      icon.style.transition = 'transform 140ms cubic-bezier(0.34, 1.56, 0.64, 1), opacity 140ms ease-out, color 140ms ease-out';
      icon.style.transform = 'scale(0.2)';
      icon.style.opacity = '0';
      setTimeout(() => {
        icon.innerHTML = check;
        icon.style.color = 'var(--c-grass-11)';
        icon.style.transform = 'scale(1)';
        icon.style.opacity = '1';
      }, 140);
      setTimeout(() => {
        icon.style.transform = 'scale(0.2)';
        icon.style.opacity = '0';
      }, 1500);
      setTimeout(() => {
        icon.innerHTML = original;
        icon.style.color = '';
        icon.style.transform = 'scale(1)';
        icon.style.opacity = '1';
        icon.dataset.animating = '0';
      }, 1640);
    });
  };
  animate();
  if (navigator.clipboard && typeof ClipboardItem !== 'undefined' && navigator.clipboard.write) {
    const blobPromise = fetch(mdUrl).then((r) => {
      if (!r.ok) throw new Error(r.status);
      return r.text().then((t) => new Blob([t], { type: 'text/plain' }));
    });
    navigator.clipboard
      .write([new ClipboardItem({ 'text/plain': blobPromise })])
      .catch((err) => console.error('Copy page failed:', err));
    return;
  }
  fetch(mdUrl)
    .then((r) => (r.ok ? r.text() : Promise.reject(r.status)))
    .then((text) => {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(text);
      }
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); } catch (e) {}
      document.body.removeChild(ta);
    })
    .catch((err) => console.error('Copy page failed:', err));
})())
        """
    )
    trigger = rx.el.div(
        rx.el.button(
            rx.el.span(
                ui.icon("Copy01Icon", size=16),
                custom_attrs={"data-copy-icon": "main"},
                class_name="inline-flex items-center justify-center transition-transform",
            ),
            type="button",
            aria_label="Copy page as Markdown",
            on_click=copy_action,
            class_name=(
                "flex items-center justify-center px-2.5 h-8 "
                "border border-slate-5 border-r-0 rounded-l-md text-slate-11 "
                "hover:text-slate-12 hover:bg-slate-3 active:scale-[0.96] "
                "transition-all cursor-pointer"
            ),
        ),
        ui.popover.root(
            ui.popover.trigger(
                render_=rx.el.button(
                    ui.icon("ArrowDown01Icon", size=14),
                    type="button",
                    aria_label="Copy page options",
                    class_name=(
                        "flex items-center justify-center px-1.5 h-8 "
                        "border border-slate-5 rounded-r-md text-slate-11 "
                        "hover:text-slate-12 hover:bg-slate-3 active:scale-[0.96] "
                        "transition-all cursor-pointer"
                    ),
                ),
            ),
            ui.popover.portal(
                ui.popover.positioner(
                    ui.popover.popup(
                        render_=rx.el.div(
                            _build_reflex_menu_item(path=path),
                            _copy_page_menu_item(
                                icon=ui.icon("Copy01Icon", size=16),
                                title="Copy page",
                                description="Copy page as Markdown for LLMs",
                                on_click=copy_action,
                            ),
                            rx.el.div(class_name="h-px bg-slate-4 my-1 mx-2"),
                            _copy_page_menu_item(
                                icon=ui.icon("MessageProgrammingIcon", size=16),
                                title="Open in ChatGPT",
                                description="Ask ChatGPT about this page",
                                href=_llm_menu_item_href(
                                    "https://chatgpt.com/?hints=search&q=", path
                                ),
                            ),
                            _copy_page_menu_item(
                                icon=ui.icon("AiChat02Icon", size=16),
                                title="Open in Claude",
                                description="Ask Claude about this page",
                                href=_llm_menu_item_href(
                                    "https://claude.ai/new?q=", path
                                ),
                            ),
                            class_name=(
                                "flex flex-col min-w-[260px] py-1 "
                                "bg-slate-1 border border-slate-5 rounded-lg shadow-lg "
                                "data-[state=open]:animate-in data-[state=open]:fade-in-0 "
                                "data-[state=open]:zoom-in-95 data-[state=open]:slide-in-from-top-2"
                            ),
                        ),
                    ),
                    side="bottom",
                    align="end",
                    side_offset=6,
                ),
            ),
        ),
        class_name="hidden lg:flex flex-row items-center shrink-0",
    )
    return trigger


def breadcrumb(path: str, nav_sidebar: rx.Component, doc_content: str | None = None):
    from reflex_docs.components.docpage.navbar.buttons.sidebar import (
        docs_sidebar_drawer,
    )

    # Split the path into segments, removing 'docs' and capitalizing each segment
    segments = [
        segment.capitalize()
        for segment in path.split("/")
        if segment and segment != "docs"
    ]

    # Initialize an empty list to store the breadcrumbs and their separators
    breadcrumbs = []

    # Iteratively build the href for each segment (paths are app-relative, no /docs prefix)
    current_path = ""
    for i, segment in enumerate(segments):
        current_path += f"/{segment.lower()}"

        # Add the breadcrumb item to the list
        breadcrumbs.append(
            rx.el.a(
                to_title_case(to_snake_case(segment), sep=" "),
                class_name="min-h-8 flex items-center text-sm font-[525] text-m-slate-12 dark:text-m-slate-3 last:text-m-slate-7 dark:last:text-m-slate-6 hover:text-primary-10 dark:hover:text-primary-9"
                + (" truncate" if i == len(segments) - 1 else ""),
                underline="none",
                href=current_path,
            )
        )

        # If it's not the last segment, add a separator
        if i < len(segments) - 1:
            breadcrumbs.append(
                ui.icon(
                    "ArrowRight01Icon",
                    class_name="lg:flex hidden dark:text-m-slate-6 text-m-slate-7 size-4",
                ),
            )
            breadcrumbs.append(
                rx.text(
                    "/",
                    class_name="font-sm dark:text-m-slate-6 text-m-slate-7 lg:hidden flex",
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
            _copy_page_button(doc_content, path=path) if doc_content else rx.fragment(),
            ui.icon(
                "ArrowDown01Icon",
                size=14,
                class_name="!text-slate-9 lg:hidden flex",
            ),
            class_name="flex flex-row items-center gap-2 lg:p-0 p-[0.563rem]",
        ),
        class_name=ui.cn(
            "relative z-10 flex flex-row justify-between items-center gap-4 lg:gap-0 border-slate-4 bg-slate-1 mt-[139px] lg:p-0 border-b lg:border-none w-full max-lg:py-2",
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
):
    """A template that most pages on the reflex.dev site should use.

    This template wraps the webpage with the navbar and footer.

    Args:
        set_path: The path to set for the sidebar.
        t: The title to set for the page.
        right_sidebar: Whether to show the right sidebar.
        page_title: The full title to set for the page. If None, defaults to `{title} · Reflex Docs`.
        pseudo_right_bar: Whether to show a pseudo right sidebar (empty space).

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
                            class_name="py-0.5 lg:py-0 rounded-lg lg:w-auto font-small text-slate-9 hover:!text-slate-11 transition-color",
                        ),
                        rx.text(next_prev_name, class_name="font-smbold text-slate-12"),
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
                            class_name="py-0.5 lg:py-0 rounded-lg lg:w-auto font-small text-slate-9 hover:!text-slate-11 transition-color",
                        ),
                        rx.text(next_prev_name, class_name="font-smbold text-slate-12"),
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
            return rx.box(
                docs_navbar(),
                rx.el.main(
                    rx.box(
                        sidebar,
                        class_name=(
                            "w-[19.5rem] shrink-0 hidden lg:block z-10 border-r border-m-slate-4 dark:border-m-slate-10 sticky left-0 "
                            "before:content-[''] before:absolute before:top-0 before:bottom-0 before:right-0 before:w-[100vw] before:bg-white-1 dark:before:bg-m-slate-11 before:-z-10 "
                            + rx.cond(
                                HostingBannerState.is_banner_visible,
                                " top-[113px] h-[calc(100vh-113px)]",
                                " top-[77px] h-[calc(100vh-77px)]",
                            )
                        ),
                    ),
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
                    rx.box(
                        rx.el.nav(
                            rx.box(
                                rx.el.p(
                                    rx.icon(
                                        "align-left",
                                        size=14,
                                        class_name="dark:text-m-slate-3 text-m-slate-12",
                                    ),
                                    "On This Page",
                                    class_name="text-sm h-8 flex items-center gap-1.5 justify-start font-[525] dark:text-m-slate-3 text-m-slate-12",
                                ),
                                rx.el.ul(
                                    *[
                                        (
                                            rx.el.li(
                                                rx.el.a(
                                                    text,
                                                    class_name="text-sm font-[525] text-m-slate-7 dark:text-m-slate-6 pl-4 py-1 block hover:text-m-slate-9 dark:hover:text-m-slate-5 transition-colors truncate",
                                                    href=path
                                                    + "#"
                                                    + text.lower().replace(" ", "-"),
                                                ),
                                            )
                                            if level == 1
                                            else (
                                                rx.el.li(
                                                    rx.el.a(
                                                        text,
                                                        class_name="text-sm font-[525] text-m-slate-7 dark:text-m-slate-6 pl-4 py-1 block hover:text-m-slate-9 dark:hover:text-m-slate-5 transition-colors truncate",
                                                        href=path
                                                        + "#"
                                                        + text.lower().replace(
                                                            " ", "-"
                                                        ),
                                                    ),
                                                )
                                                if level == 2
                                                else rx.el.li(
                                                    rx.el.a(
                                                        text,
                                                        class_name="text-sm font-[525] text-m-slate-7 dark:text-m-slate-6 pl-8 py-1 block hover:text-m-slate-9 dark:hover:text-m-slate-5 transition-colors truncate",
                                                        href=path
                                                        + "#"
                                                        + text.lower().replace(
                                                            " ", "-"
                                                        ),
                                                    ),
                                                )
                                            )
                                        )
                                        for level, text in toc
                                    ],
                                    id="toc-navigation",
                                    class_name="flex flex-col gap-y-1 list-none shadow-[1.5px_0_0_0_var(--m-slate-4)_inset] dark:shadow-[1.5px_0_0_0_var(--m-slate-9)_inset] max-h-[80vh]",
                                ),
                                rx.el.div(
                                    feedback_button_toc(),
                                    copy_to_markdown(text=doc_content)
                                    if doc_content
                                    else None,
                                    ask_ai_chat(),
                                    class_name="flex flex-col mt-1.5 justify-start",
                                ),
                                class_name="flex flex-col justify-start gap-y-4 overflow-y-auto sticky top-4",
                            ),
                            class_name=(
                                "w-full h-full"
                                + rx.cond(
                                    HostingBannerState.is_banner_visible,
                                    " mt-[146px]",
                                    " mt-[90px]",
                                )
                            ),
                        ),
                        class_name=(
                            "w-[240px] h-screen sticky top-0 shrink-0 hidden 2xl:block"
                        ),
                    )
                    if show_right_sidebar and not pseudo_right_bar
                    else rx.box(
                        class_name="w-[180px] h-screen sticky top-0 shrink-0 hidden xl:block"
                    ),
                    class_name="flex justify-center mx-auto mt-0 max-w-[108rem] h-full min-h-screen w-full",
                ),
                class_name="flex flex-col justify-center bg-m-slate-1 dark:bg-m-slate-12 w-full relative",
                on_mount=rx.call_script(right_sidebar_item_highlight()),
            )

        components = path.split("/")
        category = (
            " ".join(
                word.capitalize() for word in components[2].replace("-", " ").split()
            )
            if len(components) > 2
            else None
        )
        if page_title:
            return Route(
                path=path,
                title=page_title,
                component=wrapper,
            )
        return Route(
            path=path,
            title=f"{title} · Reflex Docs" if category is None else title,
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
                class_name="flex flex-row items-center gap-1.5 border-slate-5 bg-slate-1 hover:bg-slate-3 shadow-small pr-1.5 border rounded-md w-full max-w-[300px] text-slate-11 transition-bg cursor-pointer",
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
                rx.text(variant, class_name=text_cn + " text-slate-11")
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
            rx.text("Gray", class_name=text_cn + " text-slate-11"),
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
                    rx.text("Disabled", class_name=text_cn + " text-slate-11"),
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
                                class_name="top-1/2 left-1/2 absolute text-gray-12 transform -translate-x-1/2 -translate-y-1/2"
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
                                " border-2 border-gray-12",
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
        class_name="flex flex-col justify-center items-center gap-6 border-slate-4 bg-slate-2 mb-4 p-6 border rounded-xl",
    )
