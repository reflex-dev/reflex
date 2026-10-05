import reflex as rx


class MiscState(rx.State):
    items: list[str] = ["ia", "ib", "ic"]
    rows: list[list] = [
        [["/red.png", "/green.png"], "Ruby"],
        [["/blue.png", "/amber.png"], "Sky"],
    ]


COLUMNS = [
    {"title": "pic", "type": "image", "id": "pic"},
    {"title": "name", "type": "str", "id": "name"},
]


def editor_page() -> rx.Component:
    return rx.box(
        rx.heading("editor"),
        rx.box(
            rx.data_editor(
                columns=COLUMNS,
                data=MiscState.rows,
                height="260px",
            ),
            id="editor-box",
        ),
        padding="1em",
    )


def id_row(item: str) -> rx.Component:
    ident = rx.vars.use_id()
    return rx.hstack(
        rx.el.label(item, html_for=ident, class_name="foreach-label"),
        rx.el.input(id=ident, default_value=item, class_name="foreach-input"),
    )


@rx.memo
def memo_row(item: str) -> rx.Component:
    ident = rx.vars.use_id()
    return rx.hstack(
        rx.el.label(item, html_for=ident, class_name="memo-label"),
        rx.el.input(id=ident, default_value=item, class_name="memo-input"),
    )


def ids_page() -> rx.Component:
    return rx.box(
        rx.heading("ids"),
        rx.box(rx.foreach(MiscState.items, id_row), id="ids-box"),
        rx.box(
            rx.foreach(MiscState.items, lambda i: memo_row(item=i)),
            id="memo-box",
        ),
        padding="1em",
    )


app = rx.App()
app.add_page(editor_page, route="/editor")
app.add_page(ids_page, route="/ids")
app.add_page(lambda: rx.box(rx.text("home")), route="/")
