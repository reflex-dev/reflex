"""The data pages: the product table, a product's edit form and the analytics, in a nested layout."""

import reflex as rx

from playground.layout import layout
from playground.models import Product
from playground.states.analytics import AnalyticsState
from playground.states.data import CATEGORIES, SORTABLE, DataState
from playground.states.editor import ProductEditState

DATA_LINKS = [
    ("Table", "/data"),
    ("New product", "/data/new"),
    ("Analytics", "/data/analytics"),
]


def data_layout(content: rx.Component) -> rx.Component:
    """Wrap a data page in the section's sidebar, inside the shared layout.

    Args:
        content: The page's content.

    Returns:
        The shared layout around the sidebar and the content.
    """
    return layout(
        rx.hstack(
            rx.vstack(
                rx.text("Data", weight="bold"),
                *[rx.link(label, href=href) for label, href in DATA_LINKS],
                class_name="w-40 shrink-0",
                id="data-sidebar",
            ),
            rx.box(content, class_name="grow min-w-0"),
            align="start",
            spacing="5",
            width="100%",
        )
    )


def sort_header(column: str) -> rx.Component:
    """Render a column header that sorts the table.

    Args:
        column: The column.

    Returns:
        The header cell, with an arrow on the sorted column.
    """
    return rx.table.column_header_cell(
        rx.hstack(
            rx.text(column.replace("_", " ")),
            rx.cond(
                DataState.sort_by == column,
                rx.cond(
                    DataState.descending,
                    rx.icon("arrow-down", size=14),
                    rx.icon("arrow-up", size=14),
                ),
            ),
            align="center",
            spacing="1",
        ),
        on_click=DataState.sort(column),
        cursor="pointer",
        id=f"data-sort-{column.replace('_', '-')}",
    )


def product_row(product: rx.vars.ObjectVar[Product]) -> rx.Component:
    """Render one product of the table.

    Args:
        product: The product.

    Returns:
        A table row linking to the product's page.
    """
    return rx.table.row(
        rx.table.cell(product.id),
        rx.table.cell(rx.link(product.name, href=f"/data/product/{product.id}")),
        rx.table.cell(rx.badge(product.category)),
        rx.table.cell(product.price_cents),
        rx.table.cell(product.stock),
        rx.table.cell(product.rating),
    )


def table_page() -> rx.Component:
    """Render the product table.

    Returns:
        The filters, the table and the pagination.
    """
    return data_layout(
        rx.vstack(
            rx.heading("Products"),
            rx.hstack(
                rx.input(
                    placeholder="Filter by name",
                    value=DataState.query,
                    on_change=DataState.set_query.debounce(300),
                    id="data-filter",
                ),
                rx.select(
                    list(CATEGORIES),
                    value=DataState.category,
                    on_change=DataState.set_category,
                    id="data-category",
                ),
                rx.button(
                    "Reset",
                    on_click=DataState.reset_filters,
                    variant="soft",
                    id="data-reset",
                ),
                spacing="2",
                wrap="wrap",
            ),
            rx.table.root(
                rx.table.header(rx.table.row(*[sort_header(c) for c in SORTABLE])),
                rx.table.body(rx.foreach(DataState.products, product_row)),
                id="data-table",
                width="100%",
            ),
            rx.hstack(
                rx.button(
                    "Previous", on_click=DataState.previous_page, id="data-previous"
                ),
                rx.text(DataState.page_label, id="data-page"),
                rx.button("Next", on_click=DataState.next_page, id="data-next"),
                align="center",
            ),
            width="100%",
        )
    )


def form_field(label: str, name: str, **props) -> rx.Component:
    """Render one field of the product form, with its error.

    Args:
        label: The field's label.
        name: The field's name, which the submitted data is keyed by.
        **props: Props of the input.

    Returns:
        The label, the input and the error.
    """
    return rx.vstack(
        rx.text(label, size="2", weight="medium"),
        rx.input(name=name, id=f"product-{name.replace('_', '-')}", **props),
        rx.cond(
            ProductEditState.errors.contains(name),
            rx.text(ProductEditState.errors[name], color_scheme="red", size="1"),
        ),
        spacing="1",
        width="100%",
    )


def product_form() -> rx.Component:
    """Render the product form; keyed by the product, so a loaded product resets it.

    Returns:
        The form.
    """
    values = ProductEditState.form_values
    return rx.form(
        rx.vstack(
            form_field("Name", "name", default_value=values["name"]),
            rx.vstack(
                rx.text("Category", size="2", weight="medium"),
                rx.select(
                    list(CATEGORIES[1:]),
                    name="category",
                    default_value=values["category"],
                    id="product-category",
                ),
                spacing="1",
            ),
            form_field(
                "Price (cents)", "price_cents", default_value=values["price_cents"]
            ),
            form_field("Stock", "stock", default_value=values["stock"]),
            form_field("Rating (10 to 50)", "rating", default_value=values["rating"]),
            rx.hstack(
                rx.button("Save", type="submit", id="product-save"),
                rx.cond(
                    ProductEditState.product,
                    rx.alert_dialog.root(
                        rx.alert_dialog.trigger(
                            rx.button(
                                "Delete",
                                color_scheme="red",
                                variant="soft",
                                type="button",
                                id="product-delete",
                            )
                        ),
                        rx.alert_dialog.content(
                            rx.alert_dialog.title("Delete this product?"),
                            rx.hstack(
                                rx.alert_dialog.cancel(rx.button("Cancel")),
                                rx.alert_dialog.action(
                                    rx.button(
                                        "Delete",
                                        color_scheme="red",
                                        on_click=ProductEditState.delete,
                                        id="product-delete-confirm",
                                    )
                                ),
                                justify="end",
                            ),
                        ),
                    ),
                ),
            ),
            width="100%",
        ),
        on_submit=ProductEditState.save,
        key=values["key"],
        id="product-form",
    )


def product_page() -> rx.Component:
    """Render the edit page of one product (a dynamic route), or of a new one.

    Returns:
        The heading and the form.
    """
    return data_layout(
        rx.vstack(
            rx.heading(ProductEditState.heading, id="product-heading"),
            rx.text("Saved ", ProductEditState.saved_count, " times this session."),
            product_form(),
            width="100%",
        )
    )


def leader_row(row: rx.vars.ObjectVar[dict[str, int | str]]) -> rx.Component:
    """Render one product of the leaderboard.

    Args:
        row: The product's id, name and value.

    Returns:
        A list item.
    """
    return rx.list_item(
        rx.link(row["name"], href=f"/data/product/{row['id']}"), ": ", row["value"]
    )


def analytics_page() -> rx.Component:
    """Render the analytics over the whole table.

    Returns:
        The rating filter, a bar chart and the leaderboard.
    """
    return data_layout(
        rx.vstack(
            rx.heading("Analytics"),
            rx.cond(
                AnalyticsState.loaded,
                rx.text(
                    AnalyticsState.rated_count,
                    " products rated ",
                    AnalyticsState.min_rating,
                    " or more",
                    id="analytics-count",
                ),
                rx.spinner(),
            ),
            rx.slider(
                default_value=[30],
                min=10,
                max=50,
                on_value_commit=AnalyticsState.set_min_rating,
                id="analytics-rating",
            ),
            rx.recharts.bar_chart(
                rx.recharts.bar(data_key="value", fill=rx.color("accent", 9)),
                rx.recharts.x_axis(data_key="category"),
                rx.recharts.y_axis(),
                rx.recharts.graphing_tooltip(),
                data=AnalyticsState.category_totals,
                width="100%",
                height=260,
            ),
            rx.ordered_list(
                rx.foreach(AnalyticsState.leaderboard, leader_row),
                id="analytics-leaderboard",
            ),
            width="100%",
        )
    )
