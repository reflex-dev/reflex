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
        rx.el.span(
            icon,
            class_name="mt-0.5 inline-flex size-4 shrink-0 items-center justify-center text-muted-foreground",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    title, class_name="text-sm font-medium leading-5 text-foreground"
                ),
                ui.icon(
                    "ArrowUpRight01Icon",
                    size=12,
                    class_name="shrink-0 text-subtle-foreground",
                )
                if href
                else rx.fragment(),
                class_name="flex items-center justify-between gap-3",
            ),
            rx.el.span(
                description, class_name="text-xs leading-5 text-muted-foreground"
            ),
            class_name="flex min-w-0 flex-1 flex-col items-stretch",
        ),
        class_name="flex w-full items-start gap-2.5",
    )
    action_class = (
        "block w-full cursor-pointer rounded-md px-2.5 py-2 text-left no-underline "
        "transition-colors hover:bg-accent focus-visible:bg-accent "
        "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
    )
    if href:
        return rx.el.a(
            row,
            href=href,
            target="_blank",
            rel="noopener noreferrer",
            class_name=action_class,
        )
    return rx.el.button(
        row,
        type="button",
        on_click=on_click,
        class_name=action_class,
    )


def _reflex_build_menu_item(markdown_url: str) -> rx.Component:
    """Render the Reflex Build action using the shared menu treatment.

    Args:
        markdown_url: Absolute public URL for the current page's Markdown.

    Returns:
        The external Reflex Build action row.
    """
    return _menu_item(
        icon=ui.icon("AiMagicIcon", size=16),
        title="Build this with AI",
        description="Open in Reflex Build",
        href=_prefill_url(
            "https://build.reflex.dev/?prompt=",
            markdown_url,
            "and help me build an app based on it.",
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
                "border border-border border-r-0 rounded-l-md text-muted-foreground "
                "hover:text-foreground hover:bg-accent active:scale-[0.96] "
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
                        "border border-border rounded-r-md text-muted-foreground "
                        "hover:text-foreground hover:bg-accent active:scale-[0.96] "
                        "transition-all cursor-pointer"
                    ),
                )
            ),
            ui.popover.portal(
                ui.popover.positioner(
                    ui.popover.popup(
                        rx.el.div(
                            _reflex_build_menu_item(markdown_url),
                            rx.el.div(class_name="mx-2.5 my-1 h-px bg-border-subtle"),
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
                            rx.el.div(class_name="mx-2.5 my-1 h-px bg-border-subtle"),
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
                            class_name="flex w-full flex-col",
                        ),
                        class_name=(
                            "docs-page-actions-menu w-[304px] max-w-[calc(100vw-2rem)] "
                            "gap-0 rounded-lg border border-border bg-background p-1.5 "
                            "shadow-[0_8px_24px_rgb(0_0_0/0.08)]"
                        ),
                    ),
                    align="end",
                    align_offset=0,
                    side_offset=8,
                )
            ),
        ),
        class_name="hidden lg:flex flex-row items-center shrink-0",
    )


__all__ = ["docs_page_actions"]
