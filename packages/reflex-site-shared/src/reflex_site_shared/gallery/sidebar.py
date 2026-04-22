"""Sidebar module."""

import reflex_ui as ui

import reflex as rx
from reflex_ui_shared.gallery.apps import gallery_apps_data

TAGS = {
    "Category": [
        "AI/ML",
        "Dashboard",
        "Chat",
        "Data Visualization",
        "Image Generation",
        "API Tools",
        "Sports",
        "DevOps",
    ],
}

ITEMS_PER_PAGE = 12
TEMPLATES_FOLDER = "templates/"


TEMPLATE_SUMMARIES = [
    {
        "title": (m := doc.metadata or {}).get("title", ""),
        "description": m.get("description", ""),
        "tags": m.get("tags", []),
    }
    for (_, folder), doc in gallery_apps_data.items()
    if folder == TEMPLATES_FOLDER
]


class TemplatesState(rx.State):
    """TemplatesState."""

    query: rx.Field[str] = rx.field(default="")
    checked_tags: rx.Field[set[str]] = rx.field(default_factory=set)
    page: rx.Field[int] = rx.field(default=1)

    @rx.event
    def clear_filters(self):
        """Clear filters."""
        self.checked_tags = set()
        self.page = 1

    @rx.var
    def all_filtered_templates(self) -> list[str]:
        """All filtered templates.

        Returns:
            The component.
        """
        query = self.query.strip().lower()
        return [
            t["title"]
            for t in TEMPLATE_SUMMARIES
            if (
                not query
                or query in t["title"].lower()
                or query in t["description"].lower()
            )
            and (not self.checked_tags or set(t["tags"]) & self.checked_tags)
        ]

    @rx.var
    def total_pages(self) -> int:
        """Total pages.

        Returns:
            The component.
        """
        return max(1, -(-len(self.all_filtered_templates) // ITEMS_PER_PAGE))

    @rx.var
    def filtered_templates(self) -> list[str]:
        """Filtered templates.

        Returns:
            The component.
        """
        start = (self.page - 1) * ITEMS_PER_PAGE
        return self.all_filtered_templates[start : start + ITEMS_PER_PAGE]

    @rx.event
    def set_query(self, value: str):
        """Set query."""
        self.query = value
        self.page = 1

    @rx.event
    def toggle_template(self, value: str):
        """Toggle template."""
        if value in self.checked_tags:
            self.checked_tags.remove(value)
        else:
            self.checked_tags.add(value)
        self.page = 1

    @rx.event
    def prev_page(self):
        """Prev page."""
        if self.page > 1:
            self.page -= 1

    @rx.event
    def next_page(self):
        """Next page."""
        if self.page < self.total_pages:
            self.page += 1


def pagination() -> rx.Component:
    """Pagination.

    Returns:
        The component.
    """
    return rx.box(
        rx.box(
            ui.button(
                ui.icon("ArrowLeft01Icon"),
                disabled=TemplatesState.page == 1,
                variant="secondary",
                size="icon-sm",
                on_click=TemplatesState.prev_page,
            ),
            ui.button(
                ui.icon("ArrowRight01Icon"),
                disabled=TemplatesState.page == TemplatesState.total_pages,
                variant="secondary",
                size="icon-sm",
                on_click=TemplatesState.next_page,
            ),
            class_name="flex flex-row items-center gap-2",
        ),
        rx.text(
            f"{TemplatesState.page} of {TemplatesState.total_pages}",
            class_name="text-sm text-slate-12 font-medium",
        ),
        class_name="flex flex-row items-center gap-6 mt-10",
    )


def checkbox_item(text: str, value: str):
    """Checkbox item.

    Returns:
        The component.
    """
    return rx.box(
        rx.checkbox(
            checked=TemplatesState.checked_tags.contains(value),
            color_scheme="violet",
            key=value,
            class_name="cursor-pointer",
        ),
        rx.text(
            text,
            class_name="text-sm font-medium text-slate-12 font-sans cursor-pointer",
        ),
        on_click=TemplatesState.toggle_template(value),
        class_name="flex items-center gap-2 px-3 py-2 rounded-md bg-slate-3 hover:bg-slate-4 transition-colors cursor-pointer",
    )


def filter_section(title: str, content: list[str]):
    """Filter section.

    Returns:
        The component.
    """
    return rx.accordion.item(
        rx.accordion.trigger(
            rx.el.h3(
                title, class_name="font-semibold text-base text-slate-12 text-start"
            ),
            rx.icon(
                tag="chevron-down",
                size=19,
                class_name="!text-slate-11 group-data-[state=open]:rotate-180 transition-transform",
            ),
            class_name="hover:!bg-transparent !p-[0.5rem_0rem] !justify-between gap-4 group !mb-2",
        ),
        rx.accordion.content(
            rx.box(
                *[checkbox_item(item, item) for item in content],
                class_name="flex flex-row gap-2 flex-wrap",
            ),
            class_name="before:!h-0 after:!h-0 radix-state-open:animate-accordion-down radix-state-closed:animate-accordion-up transition-all !px-0",
        ),
        value=title,
        class_name="!p-0 w-full !bg-transparent !rounded-none !shadow-none",
    )


def sidebar() -> rx.Component:
    """Sidebar.

    Returns:
        The component.
    """
    return rx.box(
        rx.box(
            rx.box(
                rx.el.h4(
                    "Filter Templates",
                    class_name="text-base font-semibold text-slate-12",
                ),
                rx.cond(
                    TemplatesState.checked_tags,
                    rx.el.p(
                        f"Clear filters ({TemplatesState.checked_tags.length()})",
                        on_click=TemplatesState.clear_filters,
                        class_name="text-sm text-slate-9 underline hover:text-slate-11 transition-colors cursor-pointer",
                    ),
                ),
                class_name="flex flex-row items-center gap-2 justify-between",
            ),
            ui.input(
                icon="Search01Icon",
                placeholder="Search...",
                class_name="w-full",
                on_change=TemplatesState.set_query.debounce(300),
                clear_button_event=TemplatesState.set_query(""),
            ),
            class_name="flex flex-col gap-2",
        ),
        rx.accordion.root(
            *[filter_section(title, content) for title, content in TAGS.items()],
            default_value=next(iter(TAGS.keys())),
            collapsible=True,
            class_name="!p-0 w-full !bg-transparent !rounded-none !shadow-none flex flex-col gap-4",
        ),
        class_name="flex flex-col gap-4",
    )
