import reflex as rx

def index():
    return rx.vstack(
        rx.data_editor(
            columns=[{"title": "name", "type": "str", "id": "name"}],
            data=[["a"], ["b"]],
            height="200px",
        ),
    )

app = rx.App()
app.add_page(index, route="/")
