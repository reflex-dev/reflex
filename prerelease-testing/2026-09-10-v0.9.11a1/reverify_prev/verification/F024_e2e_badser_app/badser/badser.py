import reflex as rx


class Point:
    """A plain user object rendered into a page."""

    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


@rx.serializer
def serialize_point(p: Point) -> str:
    # realistic bug: attribute renamed / typo'd
    return f"{p.x},{p.why}"


def index() -> rx.Component:
    return rx.box(
        rx.text("hello"),
        custom_attrs={"data-points": rx.Var.create([Point(1, 2)])},
    )


app = rx.App()
app.add_page(index)
