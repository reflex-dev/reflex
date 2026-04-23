import json
import os

import httpx
import reflex as rx
from reflex_site_shared.components.icons import get_icon
from reflex_site_shared.styles.colors import c_color
from reflex_site_shared.styles.fonts import base
from reflex_site_shared.styles.shadows import shadows

from reflex_docs.templates.docpage import docpage, h1_comp, text_comp_2

SORTING_CRITERIA = {
    "Recent": lambda x: x["updated_at"],
    "Downloads": lambda x: x["downloads"]["last_month"],
}


class CustomComponentGalleryState(rx.State):
    tags: list[str] = []

    components_list: list[dict[str, str]] = []
    paginated_data: list[dict[str, str]] = []

    selected_filter: str = ""
    original_components_list: list[dict[str, str]] = []

    current_page: int = 1
    current_limit: int = 50  # Default number of items per page
    total_pages: int = 1
    offset: int = 0
    number_of_rows: int = 0

    # Added available limits for the number of items per page
    limits: list[str] = ["10", "20", "50", "100"]

    @rx.event(background=True)
    async def fetch_components_list(self):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{os.getenv('RCC_ENDPOINT')}/custom-components/gallery"
                )
                response.raise_for_status()
                component_list = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as ex:
            print(f"Internal error: failed to fetch components list due to: {ex}")
            return

        for c in component_list:
            c["downloads_last_month"] = c["downloads"]["last_month"]
            c["keywords"] = [
                keyword
                for keyword in c["keywords"] or []
                if "reflex" not in keyword.lower()
            ]
            c["download_url"] = package_url(c["package_name"])

        async with self:
            self.original_components_list = component_list
            self.number_of_rows = len(component_list)
            self.total_pages = (
                self.number_of_rows + self.current_limit - 1
            ) // self.current_limit
            yield CustomComponentGalleryState.paginate()

    @rx.event
    def paginate(self) -> None:
        start = self.offset
        end = start + self.current_limit
        self.paginated_data = self.original_components_list[start:end]
        self.current_page = (self.offset // self.current_limit) + 1

    @rx.event
    def delta_limit(self, limit: str) -> None:
        self.current_limit = int(limit)
        self.offset = 0
        self.total_pages = (
            self.number_of_rows + self.current_limit - 1
        ) // self.current_limit
        self.paginate()

    @rx.event
    def previous(self) -> None:
        if self.offset >= self.current_limit:
            self.offset -= self.current_limit
        else:
            self.offset = 0
        self.paginate()

    @rx.event
    def next(self) -> None:
        if self.offset + self.current_limit < self.number_of_rows:
            self.offset += self.current_limit
        self.paginate()

    @rx.event
    def sort_components(self):
        # Get the sorting function based on the selected filter
        sorting_function = SORTING_CRITERIA.get(
            self.selected_filter, lambda x: x["updated_at"]
        )

        # Both "Recent" and "Downloads" should be sorted in reverse order (newest/highest first)
        if self.selected_filter in ["Recent", "Downloads"]:
            self.original_components_list.sort(key=sorting_function, reverse=True)
        else:
            # Default sorting behavior, if no filter selected
            self.original_components_list.sort(key=sorting_function, reverse=False)

        # After sorting, paginate the data
        self.paginate()

    @rx.event
    def set_selected_filter(self, filter_text: str):
        # Reset to the first page when the filter is changed
        self.selected_filter = filter_text
        self.offset = 0  # Reset pagination
        self.total_pages = (
            self.number_of_rows + self.current_limit - 1
        ) // self.current_limit  # Recalculate total pages
        self.sort_components()  # Sort components based on selected filter
        self.paginate()  # Update paginated data


def filter_item(
    icon: str, text: str, border: bool = False, on_click=None
) -> rx.Component:
    is_selected = CustomComponentGalleryState.selected_filter == text
    return rx.box(
        get_icon(icon, class_name="py-[2px]", opacity=rx.cond(is_selected, 0.64, 1)),
        rx.text(text, opacity=rx.cond(is_selected, 0.64, 1), class_name="font-small"),
        rx.spacer(),
        rx.cond(
            is_selected,
            rx.box(
                class_name="size-2 justify-end bg-violet-9 rounded-full",
            ),
        ),
        class_name="flex flex-row gap-[14px] items-center justify-start w-full cursor-pointer hover:bg-slate-3 transition-bg text-nowrap overflow-hidden p-[8px_14px]",
        border_top=f"1px solid {c_color('slate', 5)}" if border else "none",
        border_bottom=f"1px solid {c_color('slate', 5)}" if border else "none",
        on_click=on_click,
    )


chips_box_style = {
    "width": ["100%", "100%", "auto"],
    "box-sizing": "border-box",
    "display": "flex",
    "flex-direction": "row",
    "align_items": "center",
    "padding": "6px 12px",
    "cursor": "pointer",
    "box-shadow": shadows["large"],
    "border-radius": "1000px",
    "transition": "background 0.075s ease-out, color 0.075s ease-out, border 0.075s ease-out",
}

# Sorting
sorting_box_style = {
    "gap": "12px",
    "outline": "none",
    "_focus": {
        "outline": "none",
    },
    **chips_box_style,
}

menu_item_style = {
    "box-sizing": "border-box",
    "width": "191px",
    "height": "auto",
    "overflow": "hidden",
    "padding": "0px",
    "cursor": "default",
    "background_color": c_color("slate", 2),
    "border": f"1px solid {c_color('slate', 5)}",
    "box-shadow": "0px 2px 4px rgba(0, 0, 0, 0.05)",
    "border-radius": "12px",
    "color": c_color("slate", 9),
    **base,
}


def sorting_filters() -> rx.Component:
    return rx.vstack(
        filter_item(
            "history",
            "Recent",
            on_click=lambda: CustomComponentGalleryState.set_selected_filter("Recent"),
        ),
        filter_item(
            "arrow_down_big",
            "Downloads",
            border=True,
            on_click=lambda: CustomComponentGalleryState.set_selected_filter(
                "Downloads"
            ),
        ),
        gap="0px",
        width="100%",
    )


def sorting_filters_dropdown_menu() -> rx.Component:
    condition = CustomComponentGalleryState.selected_filter != ""
    conditional_style = {
        "background": rx.cond(
            condition,
            c_color("violet", 9),
            c_color("slate", 1),
        ),
        "color": rx.cond(
            condition,
            "white",
            c_color("slate", 9),
        ),
        "border": rx.cond(
            condition,
            f"1px solid {c_color('violet', 9)}",
            f"1px solid {c_color('slate', 5)}",
        ),
        "&[data-state='open']": {
            "background": rx.cond(
                condition,
                c_color("violet", 9),
                c_color("slate", 3),
            ),
        },
        "_hover": {
            "background": rx.cond(
                condition,
                c_color("violet", 9),
                c_color("slate", 3),
            ),
        },
    }
    return rx.menu.root(
        rx.menu.trigger(
            rx.el.button(
                rx.text(
                    "Sort",
                    rx.cond(
                        condition,
                        rx.text(
                            f": {CustomComponentGalleryState.selected_filter}",
                            as_="span",
                            class_name="text-nowrap",
                        ),
                    ),
                    as_="span",
                    class_name="font-small",
                ),
                get_icon(
                    icon="select",
                ),
                justify_content="space-between",
            ),
            style=sorting_box_style | conditional_style,
        ),
        rx.menu.content(
            rx.menu.item(sorting_filters(), style=menu_item_style),
            bg="transparent",
            box_shadow="None",
            padding="0px",
            overflow="visible",
            border="none",
            align="center",
        ),
        width="100%",
    )


def package_url(package_name: str) -> str:
    return f"https://pypi.org/pypi/{package_name}/"


def download(download_url: str) -> rx.Component:
    return rx.link(
        get_icon(icon="new_tab"),
        underline="none",
        href=download_url,
        is_external=True,
        class_name="text-slate-9 hover:!text-slate-9 bg-slate-1 hover:bg-slate-3 transition-bg cursor-pointer rounded-[6px]",
        title="Documentation",
    )


def table_rows(category: dict):
    name = rx.Var(
        f"{category['package_name']!s}.split('-').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')",
    )

    updated_at = rx.Var(
        f"({category['updated_at']}).split('T')[0].split('-').map((part, index) => index === 1 ? 'JanFebMarAprMayJunJulAugSepOctNovDec'.slice(part * 3, part * 3 + 3) : part.padStart(2, '0'))"
        f".slice(1).join(' ') + ', ' + ({category['updated_at']}).split('T')[0].split('-')[0]"
    )

    return rx.table.row(
        rx.table.cell(name),
        rx.table.cell(updated_at),
        rx.table.cell(
            rx.box(
                rx.text(
                    "pip install " + category["package_name"],
                    as_="p",
                    class_name="font-small truncate flex-1 min-w-0",
                ),
                get_icon(icon="copy", class_name="p-[5px]"),
                on_click=rx.set_clipboard("pip install " + category["package_name"]),
                class_name="flex flex-row gap-1.5 text-slate-9 w-full items-center overflow-hidden border border-slate-5 bg-slate-1 hover:bg-slate-3 transition-bg cursor-pointer shadow-small rounded-[6px] px-1.5 max-w-[20rem]",
            )
        ),
        rx.table.cell(download(category["download_url"])),
        white_space="nowrap",
        align="center",
    )


def component_grid():
    table = rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.foreach(
                    ["Package Name", "Last Updated", "Install Command", "Docs"],
                    lambda column_name: rx.table.column_header_cell(
                        rx.text(column_name, size="1"),
                    ),
                ),
                white_space="nowrap",
            ),
        ),
        rx.table.body(
            rx.foreach(
                CustomComponentGalleryState.paginated_data,
                table_rows,
            )
        ),
        width="100%",
        variant="ghost",
        max_width="800px",
        size="1",
    )

    return rx.box(
        table,
        class_name="w-full h-full min-h-[60vh] flex flex-col items-start justify-start",
    )


def create_pagination():
    return rx.hstack(
        rx.hstack(
            rx.text("Rows per page", weight="bold", font_size="12px"),
            rx.select(
                CustomComponentGalleryState.limits,
                default_value="50",
                on_change=CustomComponentGalleryState.delta_limit,
                width="80px",
            ),
            align_items="center",
        ),
        rx.hstack(
            rx.text(
                f"Page {CustomComponentGalleryState.current_page} of {CustomComponentGalleryState.total_pages}",
                width="100px",
                weight="bold",
                font_size="12px",
            ),
            rx.button(
                rx.icon(
                    tag="chevron-left",
                    on_click=CustomComponentGalleryState.previous,
                    size=25,
                    cursor="pointer",
                ),
                color_scheme="gray",
                variant="surface",
                size="1",
                width="32px",
                height="32px",
            ),
            rx.button(
                rx.icon(
                    tag="chevron-right",
                    on_click=CustomComponentGalleryState.next,
                    size=25,
                    cursor="pointer",
                ),
                color_scheme="gray",
                variant="surface",
                size="1",
                width="32px",
                height="32px",
            ),
            align_items="center",
            spacing="1",
        ),
        align_items="center",
        spacing="4",
        flex_wrap="wrap",
    )


@docpage(set_path="/custom-components/", right_sidebar=False)
def custom_components() -> rx.Component:
    return rx.box(
        rx.box(
            h1_comp(text="Custom Components"),
            rx.box(
                text_comp_2(
                    text="Reflex has a growing ecosystem of custom components that you can use to build your apps. Below is a list of some of the custom components available for Reflex.",
                ),
                sorting_filters_dropdown_menu(),
                class_name="flex flex-row w-full gap-12 justify-between items-center",
            ),
            class_name="flex flex-col w-full",
        ),
        component_grid(),
        create_pagination(),
        class_name="flex flex-col h-full w-full gap-6 mb-16",
        on_mount=CustomComponentGalleryState.fetch_components_list,
    )
