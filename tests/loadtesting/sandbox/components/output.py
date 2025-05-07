import reflex as rx

from sandbox.states.queries import QueryAPI
from sandbox.components.drawer import render_drawer


def create_table_header(title: str):
    return rx.table.column_header_cell(title)


def create_query_rows(data: dict[str, str]):
    def fill_rows_with_data(data_):
        return rx.table.cell(
            f"{data_[1]}",
            on_click=QueryAPI.display_selected_row(data),
            cursor="pointer",
        )

    return rx.table.row(
        rx.foreach(data, fill_rows_with_data),
        _hover={"bg": rx.color(color="gray", shade=4)},
    )


def create_pagination():
    return rx.hstack(
        rx.hstack(
            rx.text("Entries per page", weight="bold"),
            rx.select(
                QueryAPI.limits, default_value="10", on_change=QueryAPI.delta_limit
            ),
            align_items="center",
        ),
        rx.hstack(
            rx.text(
                f"Page {QueryAPI.current_page}/{QueryAPI.total_pages}",
                width="100px",
                weight="bold",
            ),
            rx.chakra.button_group(
                rx.icon(
                    tag="chevron-left", on_click=QueryAPI.previous, cursor="pointer"
                ),
                rx.icon(tag="chevron-right", on_click=QueryAPI.next, cursor="pointer"),
                is_attached=True,
            ),
            align_items="center",
            spacing="1",
        ),
        align_items="center",
        spacing="4",
    )


def render_output():
    return rx.center(
        rx.cond(
            QueryAPI.get_data,
            rx.vstack(
                render_drawer(),
                create_pagination(),
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.foreach(QueryAPI.get_table_headers, create_table_header)
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(QueryAPI.paginated_data, create_query_rows)
                    ),
                    width="100%",
                    variant="surface",
                    size="1",
                ),
                rx.text(
                    "* Click a row to edit its contents.",
                    weight="bold",
                    size="1",
                ),
                width="100%",
                overflow="auto",
                padding="2em 2em",
            ),
            rx.spacer(),
        ),
        flex="60%",
        bg=rx.color_mode_cond(
            "#faf9fb",
            "#1a181a",
        ),
        border_radius="10px",
        overflow="auto",
    )
