"""Welcome to Reflex! This file outlines the steps to create a basic app."""

from sqlmodel import select
import reflex as rx

from data_visualisation.models import Customer, Cereals, Covid, Countries  # noqa: F401
from data_visualisation.data_loading import loading_data


MODEL = Covid
data_file_path = "data_sources/covid_data.xlsx"


class State(rx.State):
    """The app state."""

    items: list[MODEL] = []
    sort_value: str = ""
    num_items: int
    current_item: MODEL = MODEL()

    def handle_add_submit(self, form_data: dict):
        """Handle the form submit."""
        self.current_item = form_data

    def handle_update_submit(self, form_data: dict):
        """Handle the form submit."""
        self.current_item.update(form_data)

    def load_entries(self) -> list[MODEL]:
        """Get all items from the database."""
        with rx.session() as session:
            self.items = session.exec(select(MODEL)).all()
            self.num_items = len(self.items)

            if self.sort_value:
                self.items = sorted(
                    self.items,
                    key=lambda item: getattr(item, self.sort_value),
                )

    def sort_values(self, sort_value: str):
        self.sort_value = sort_value
        self.load_entries()

    def get_item(self, item: MODEL):
        self.current_item = item

    def add_item(self):
        """Add an item to the database."""
        with rx.session() as session:
            ## If need unique items on a certain column type add in a check to see if a item has already been added
            # if session.exec(
            #     select(MODEL).where(MODEL.email == self.current_item["email"])
            # ).first():
            #     return rx.window_alert("Item already exists!!!")
            session.add(MODEL(**self.current_item))
            session.commit()
        self.load_entries()
        return rx.window_alert("Item has been added.")

    def update_item(self):
        """Update an item in the database."""
        with rx.session() as session:
            item = session.exec(
                select(MODEL).where(MODEL.id == self.current_item["id"])
            ).first()

            for field in MODEL.__fields__:
                if field != "id":
                    setattr(item, field, self.current_item[field])
            session.add(item)
            session.commit()
        self.load_entries()

    def delete_item(self, id: int):
        """Delete an item from the database."""
        with rx.session() as session:
            item = session.exec(select(MODEL).where(MODEL.id == id)).first()
            session.delete(item)
            session.commit()
        self.load_entries()

    def on_load(self):
        # Check if the database is empty
        with rx.session() as session:
            # Attempt to retrieve the first entry in the MODEL table
            first_entry = session.exec(select(MODEL)).first()
            # If nothing was returned load data from the csv file
            if first_entry is None and data_file_path != "":
                loading_data(data_file_path, MODEL)

        self.load_entries()


def add_fields(field):
    return rx.flex(
        rx.text(
            field,
            as_="div",
            size="2",
            mb="1",
            weight="bold",
        ),
        rx.input(
            placeholder=field,
            name=field,
        ),
        direction="column",
        spacing="2",
    )


def update_fields_and_attrs(field, attr):
    return rx.flex(
        rx.text(
            field,
            as_="div",
            size="2",
            mb="1",
            weight="bold",
        ),
        rx.input(
            placeholder=attr,
            name=field,
            default_value=attr,
        ),
        direction="column",
        spacing="2",
    )


def add_item_ui():
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.flex(
                    "Add New Item",
                    rx.icon(tag="plus", width=24, height=24),
                    spacing="3",
                ),
                size="4",
                radius="full",
            ),
        ),
        rx.dialog.content(
            rx.dialog.title(
                "Item Details",
                font_family="Inter",
            ),
            rx.dialog.description(
                "Add your item details.",
                size="2",
                mb="4",
                padding_bottom="1em",
            ),
            rx.form(
                rx.flex(
                    *[add_fields(field) for field in MODEL.__fields__ if field != "id"],
                    rx.box(
                        rx.button(
                            "Submit",
                            type="submit",
                        ),
                    ),
                    direction="column",
                    spacing="3",
                ),
                on_submit=State.handle_add_submit,
                reset_on_submit=True,
            ),
            rx.flex(
                rx.dialog.close(
                    rx.button(
                        "Cancel",
                        variant="soft",
                        color_scheme="gray",
                    ),
                ),
                rx.dialog.close(
                    rx.button(
                        "Submit Item",
                        on_click=State.add_item,
                        variant="solid",
                    ),
                ),
                padding_top="1em",
                spacing="3",
                mt="4",
                justify="end",
            ),
            style={"max_width": 450},
            box_shadow="lg",
            padding="1em",
            border_radius="25px",
            font_family="Inter",
        ),
    )


def update_item_ui(item):
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("square_pen", width=24, height=24),
                color="white",
                on_click=lambda: State.get_item(item),
            ),
        ),
        rx.dialog.content(
            rx.dialog.title("Item Details"),
            rx.dialog.description(
                "Update your item details.",
                size="2",
                mb="4",
                padding_bottom="1em",
            ),
            rx.form(
                rx.flex(
                    *[
                        update_fields_and_attrs(
                            field, getattr(State.current_item, field)
                        )
                        for field in MODEL.__fields__
                        if field != "id"
                    ],
                    rx.box(
                        rx.button(
                            "Submit",
                            type="submit",
                        ),
                    ),
                    direction="column",
                    spacing="3",
                ),
                on_submit=State.handle_update_submit,
                reset_on_submit=True,
            ),
            rx.flex(
                rx.dialog.close(
                    rx.button(
                        "Cancel",
                        variant="soft",
                        color_scheme="gray",
                    ),
                ),
                rx.dialog.close(
                    rx.button(
                        "Submit Item",
                        on_click=State.update_item,
                        variant="solid",
                    ),
                ),
                padding_top="1em",
                spacing="3",
                mt="4",
                justify="end",
            ),
            style={"max_width": 450},
            box_shadow="lg",
            padding="1em",
            border_radius="25px",
        ),
    )


def navbar():
    return rx.hstack(
        rx.vstack(
            rx.heading("Data App", size="7", font_family="Inter"),
        ),
        rx.spacer(),
        add_item_ui(),
        rx.avatar(fallback="TG", size="4"),
        rx.color_mode.button(),
        position="fixed",
        width="100%",
        top="0px",
        z_index="1000",
        padding_x="4em",
        padding_top="2em",
        padding_bottom="1em",
        backdrop_filter="blur(10px)",
    )


def show_item(item: MODEL):
    """Show an item in a table row."""
    return rx.table.row(
        rx.table.cell(rx.avatar(fallback="DA")),
        *[
            rx.table.cell(getattr(item, field))
            for field in MODEL.__fields__
            if field != "id"
        ],
        rx.table.cell(
            update_item_ui(item),
        ),
        rx.table.cell(
            rx.button(
                "Delete",
                on_click=lambda: State.delete_item(getattr(item, "id")),
                background=rx.color("red", 9),
                color="white",
            ),
        ),
    )


def content():
    return rx.fragment(
        rx.vstack(
            rx.divider(),
            rx.hstack(
                rx.heading(
                    f"Total: {State.num_items} Items",
                    size="5",
                    font_family="Inter",
                ),
                rx.spacer(),
                rx.select(
                    [*[field for field in MODEL.__fields__ if field != "id"]],
                    placeholder="Sort By: Name",
                    size="3",
                    on_change=lambda sort_value: State.sort_values(sort_value),
                    font_family="Inter",
                ),
                width="100%",
                padding_x="2em",
                padding_top="2em",
                padding_bottom="1em",
            ),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Icon"),
                        *[
                            rx.table.column_header_cell(field)
                            for field in MODEL.__fields__
                            if field != "id"
                        ],
                        rx.table.column_header_cell("Edit"),
                        rx.table.column_header_cell("Delete"),
                    ),
                ),
                rx.table.body(rx.foreach(State.items, show_item)),
                size="3",
                width="100%",
            ),
        ),
    )


def index() -> rx.Component:
    return rx.box(
        navbar(),
        rx.box(
            content(),
            margin_top="calc(50px + 2em)",
            padding="4em",
        ),
        font_family="Inter",
    )


# Create app instance and add index page.
app = rx.App(
    theme=rx.theme(
        appearance="light", has_background=True, radius="large", accent_color="grass"
    ),
    stylesheets=["https://fonts.googleapis.com/css?family=Inter"],
)
app.add_page(
    index,
    on_load=State.on_load,
    title="Data App",
    description="A simple app to manage data.",
)
