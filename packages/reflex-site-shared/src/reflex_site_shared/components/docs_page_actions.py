"""Actions for copying documentation pages and opening them in LLM tools."""

from __future__ import annotations

import json
from urllib.parse import quote

import reflex_components_internal as ui

import reflex as rx
from reflex.event import EventType


def _prefill_url(base_url: str, markdown_url: str, action: str) -> str:
    """Build a destination URL with a prompt about one Markdown page.

    Args:
        base_url: LLM or builder URL ending with its prompt query parameter.
        markdown_url: Absolute public URL for the current page's Markdown.
        action: Instruction appended after the page URL.

    Returns:
        URL with the encoded prompt appended.
    """
    prompt = f"Read from {markdown_url} {action}"
    return f"{base_url}{quote(prompt)}"


def _menu_item(
    icon: rx.Component,
    title: str,
    description: str,
    on_click: EventType[()] | None = None,
    href: str | None = None,
) -> rx.Component:
    """Render one action-menu row.

    Args:
        icon: Icon displayed beside the action text.
        title: Visible action title.
        description: Supporting action description.
        on_click: Optional click event for button actions.
        href: Optional external destination for link actions.

    Returns:
        A button or external link row.
    """
    row = rx.el.div(
        rx.el.div(
            icon,
            class_name="flex size-8 items-center justify-center rounded-md border border-secondary-5 bg-secondary-2 text-secondary-11 shrink-0",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.span(title, class_name="text-sm font-medium text-secondary-12"),
                ui.icon(
                    "ArrowUpRight01Icon",
                    size=12,
                    class_name="text-secondary-9",
                )
                if href
                else rx.fragment(),
                class_name="flex items-center gap-1",
            ),
            rx.el.span(description, class_name="text-xs text-secondary-10"),
            class_name="flex flex-col items-start gap-0.5",
        ),
        class_name="flex items-start gap-3 px-3 py-2 w-full hover:bg-secondary-3 transition-colors cursor-pointer",
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


def _reflex_build_menu_item(markdown_url: str) -> rx.Component:
    """Render the highlighted Reflex Build action.

    Args:
        markdown_url: Absolute public URL for the current page's Markdown.

    Returns:
        The highlighted external action row.
    """
    href = _prefill_url(
        "https://build.reflex.dev/?prompt=",
        markdown_url,
        "and help me build an app based on it.",
    )
    return rx.el.a(
        rx.el.div(
            rx.el.div(
                ui.icon("AiMagicIcon", size=16, class_name="text-primary-contrast"),
                class_name=(
                    "flex size-8 items-center justify-center rounded-md "
                    "bg-gradient-to-br from-primary-9 to-primary-11 "
                    "dark:from-primary-7 dark:to-primary-9 "
                    "shadow-[0_0_0_1px_var(--primary-7),0_2px_8px_-2px_var(--primary-a8)] shrink-0"
                ),
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.span(
                        "Build this with AI",
                        class_name="text-sm font-semibold text-secondary-12",
                    ),
                    ui.icon(
                        "ArrowUpRight01Icon",
                        size=12,
                        class_name="!text-primary-11",
                    ),
                    class_name="flex items-center gap-1",
                ),
                rx.el.span(
                    "Open in Reflex Build",
                    class_name="text-xs text-secondary-10",
                ),
                class_name="flex flex-col items-start gap-0.5",
            ),
            class_name="flex items-start gap-3 px-3 py-3 w-full",
        ),
        href=href,
        target="_blank",
        rel="noopener noreferrer",
        class_name=(
            "no-underline w-full text-left block "
            "bg-gradient-to-br from-primary-2 to-secondary-1 "
            "hover:from-primary-3 hover:to-primary-2 "
            "dark:from-primary-a3 dark:to-secondary-2 "
            "dark:hover:from-primary-a4 dark:hover:to-secondary-3 "
            "border-b border-secondary-4 transition-colors cursor-pointer"
        ),
    )


def _copy_action(copy_url: str | None):
    """Build the browser event that copies the current page as Markdown.

    Args:
        copy_url: Explicit local Markdown URL, or ``None`` to derive it from
            the browser path using the official docs' ``/low`` convention.

    Returns:
        Reflex client-side script event.
    """
    copy_url_expression = (
        json.dumps(copy_url)
        if copy_url is not None
        else """cleanPath.endsWith('/low')
    ? cleanPath.replace(/\\/low$/, '-ll.md')
    : cleanPath + '.md'"""
    )
    return rx.run_script(
        f"""
((function() {{
  const cleanPath = window.location.pathname.replace(/\\/$/, '');
  const mdUrl = {copy_url_expression};
  const animate = () => {{
    document.querySelectorAll('[data-copy-icon]').forEach((icon) => {{
      if (icon.dataset.animating === '1') return;
      icon.dataset.animating = '1';
      const original = icon.innerHTML;
      const check = '<svg xmlns=\\"http://www.w3.org/2000/svg\\" width=\\"16\\" height=\\"16\\" viewBox=\\"0 0 24 24\\" fill=\\"none\\" stroke=\\"currentColor\\" stroke-width=\\"2\\" stroke-linecap=\\"round\\" stroke-linejoin=\\"round\\"><polyline points=\\"20 6 9 17 4 12\\"></polyline></svg>';
      icon.style.transition = 'transform 140ms cubic-bezier(0.34, 1.56, 0.64, 1), opacity 140ms ease-out, color 140ms ease-out';
      icon.style.transform = 'scale(0.2)';
      icon.style.opacity = '0';
      setTimeout(() => {{
        icon.innerHTML = check;
        icon.style.color = 'var(--c-grass-11)';
        icon.style.transform = 'scale(1)';
        icon.style.opacity = '1';
      }}, 140);
      setTimeout(() => {{
        icon.style.transform = 'scale(0.2)';
        icon.style.opacity = '0';
      }}, 1500);
      setTimeout(() => {{
        icon.innerHTML = original;
        icon.style.color = '';
        icon.style.transform = 'scale(1)';
        icon.style.opacity = '1';
        icon.dataset.animating = '0';
      }}, 1640);
    }});
  }};
  animate();
  if (navigator.clipboard && typeof ClipboardItem !== 'undefined' && navigator.clipboard.write) {{
    const blobPromise = fetch(mdUrl).then((response) => {{
      if (!response.ok) throw new Error(response.status);
      const contentType = response.headers.get('content-type') || '';
      if (!contentType.includes('markdown') && !contentType.includes('text/plain')) {{
        throw new Error('not-markdown');
      }}
      return response.text().then((text) => new Blob([text], {{ type: 'text/plain' }}));
    }});
    navigator.clipboard
      .write([new ClipboardItem({{ 'text/plain': blobPromise }})])
      .catch((error) => console.error('Copy page failed:', error));
    return;
  }}
  fetch(mdUrl)
    .then((response) => {{
      if (!response.ok) return Promise.reject(response.status);
      const contentType = response.headers.get('content-type') || '';
      if (!contentType.includes('markdown') && !contentType.includes('text/plain')) {{
        return Promise.reject('not-markdown');
      }}
      return response.text();
    }})
    .then((text) => {{
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        return navigator.clipboard.writeText(text);
      }}
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      try {{ document.execCommand('copy'); }} catch (error) {{ console.error(error); }}
      document.body.removeChild(textarea);
    }})
    .catch((error) => console.error('Copy page failed:', error));
}})())
        """
    )


def docs_page_actions(
    markdown_url: str,
    llms_full_txt_url: str,
    *,
    llms_label: str = "llms-full.txt",
    copy_url: str | None = None,
) -> rx.Component:
    """Render copy and LLM actions for one documentation page.

    Args:
        markdown_url: Absolute public URL for the current page's Markdown.
        llms_full_txt_url: URL of the site's combined agent-readable docs.
        llms_label: Visible label for the linked agent-readable docs file.
        copy_url: Optional local Markdown URL fetched by the copy action. When
            omitted, the URL is derived from the current browser path.

    Returns:
        The official split copy button and actions popover.
    """
    copy_action = _copy_action(copy_url)
    return rx.el.div(
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
                "border border-secondary-5 border-r-0 rounded-l-md text-secondary-11 "
                "hover:text-secondary-12 hover:bg-secondary-3 active:scale-[0.96] "
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
                        "border border-secondary-5 rounded-r-md text-secondary-11 "
                        "hover:text-secondary-12 hover:bg-secondary-3 active:scale-[0.96] "
                        "transition-all cursor-pointer"
                    ),
                )
            ),
            ui.popover.portal(
                ui.popover.positioner(
                    ui.popover.popup(
                        rx.el.div(
                            _reflex_build_menu_item(markdown_url),
                            _menu_item(
                                icon=ui.icon("Copy01Icon", size=16),
                                title="Copy page",
                                description="Copy page as Markdown for LLMs",
                                on_click=copy_action,
                            ),
                            _menu_item(
                                icon=ui.icon("DocumentValidationIcon", size=16),
                                title=llms_label,
                                description="View all docs as Markdown for LLMs",
                                href=llms_full_txt_url,
                            ),
                            rx.el.div(class_name="h-px bg-secondary-4"),
                            _menu_item(
                                icon=ui.icon("MessageProgrammingIcon", size=16),
                                title="Open in ChatGPT",
                                description="Ask ChatGPT about this page",
                                href=_prefill_url(
                                    "https://chatgpt.com/?hints=search&q=",
                                    markdown_url,
                                    "so I can ask questions about its contents",
                                ),
                            ),
                            _menu_item(
                                icon=ui.icon("AiChat02Icon", size=16),
                                title="Open in Claude",
                                description="Ask Claude about this page",
                                href=_prefill_url(
                                    "https://claude.ai/new?q=",
                                    markdown_url,
                                    "so I can ask questions about its contents",
                                ),
                            ),
                            class_name=(
                                "flex flex-col min-w-[260px] "
                                "bg-white dark:bg-secondary-2 border border-secondary-5 rounded-lg shadow-lg "
                                "data-[state=open]:animate-in data-[state=open]:fade-in-0 "
                                "data-[state=open]:zoom-in-95 data-[state=open]:slide-in-from-top-2"
                            ),
                        ),
                        class_name="p-0 overflow-hidden",
                    ),
                    align="end",
                    align_offset=-4,
                )
            ),
        ),
        class_name="hidden lg:flex flex-row items-center shrink-0",
    )


__all__ = ["docs_page_actions"]
