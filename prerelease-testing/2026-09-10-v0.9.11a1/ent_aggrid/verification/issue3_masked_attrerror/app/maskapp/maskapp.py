"""Minimal pure-reflex app: a buggy user serializer under an rx.foreach."""

import reflex as rx


class Point:
    """A user domain object."""

    def __init__(self, x: int):
        self.x = x


@rx.serializer
def serialize_point(p: Point) -> str:
    """Buggy on purpose: Point has no `.label`."""
    return p.label  # noqa


POINTS = [Point(1), Point(2)]


def index() -> rx.Component:
    """The index page."""
    return rx.vstack(
        rx.heading("mask repro"),
        rx.foreach(POINTS, lambda p: rx.text(p.to_string())),
    )


app = rx.App()
app.add_page(index)
