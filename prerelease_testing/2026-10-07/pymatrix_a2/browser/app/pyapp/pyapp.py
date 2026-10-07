"""Annotation-shape app for the supported Python matrix."""

import asyncio
import datetime
import sys
from typing import Annotated, Literal, Optional, Union

import reflex as rx

from .abc_states import WorldGreeter
from .future_states import FutureState
from .models import TD, Color, PModel, Point


class Shapes(rx.State):
    """Every annotation shape in one state."""

    l_opt: list[int] | None = None
    d_nested: dict[str, list[str]] = {"k": ["v1", "v2"]}
    o_str: Optional[str] = None
    ann: Annotated[int, "meta"] = 5
    point: Point = Point(1, 2, ["t"])
    pm: PModel = PModel(name="pm", tags=["a"])
    lit: Literal["a", "b"] = "a"
    color: Color = Color.RED
    when: datetime.datetime = datetime.datetime(2026, 10, 6, 12, 30)
    fld: rx.Field[list[str]] = rx.field(default_factory=lambda: ["f1"])
    uni: Union[int, str] = 1
    tup: tuple[int, str] = (1, "one")
    td: TD = {"a": 1, "b": "bee"}
    counter: int = 0
    bg_running: bool = False

    @rx.var
    def rows(self) -> list[dict[str, int]]:
        """Derive iterated rows from the nullable list.

        Returns:
            Integer rows with their squares.
        """
        return [{"i": i, "sq": i * i} for i in range(len(self.l_opt or []) + 1)]

    @rx.var
    def py_version(self) -> str:
        """Report the actual backend interpreter.

        Returns:
            Three-part Python version.
        """
        return ".".join(map(str, sys.version_info[:3]))

    @rx.event
    def mutate(self):
        """Mutate every state annotation shape through a public event."""
        self.l_opt = [*(self.l_opt or []), 7]
        self.d_nested["k"].append("v3")
        self.o_str = "now set"
        self.ann += 1
        self.point.x += 10
        self.point.tags.append("t2")
        self.pm.tags.append("b")
        self.pm.when = datetime.datetime(2026, 1, 1)
        self.lit = "b"
        self.color = Color.GREEN
        self.when = self.when + datetime.timedelta(days=1)
        self.fld.append("f2")
        self.uni = "two"
        self.tup = (2, "two")
        self.td = {"a": 2, "b": "bee2"}

    @rx.event
    def reset_opt(self):
        """Restore nullable fields without resetting other values."""
        self.l_opt = None
        self.o_str = None

    @rx.event(background=True)
    async def bg(self):
        """Increment state around simulated asynchronous work."""
        async with self:
            self.bg_running = True
        for _ in range(3):
            await asyncio.sleep(0.2)
            async with self:
                self.counter += 1
        async with self:
            self.bg_running = False


def show(label: str, var) -> rx.Component:
    """Render a state value as JSON text.

    Args:
        label: Field name used in the DOM identifier.
        var: Reactive value.

    Returns:
        A labeled state field.
    """
    return rx.hstack(
        rx.text(label + ":"),
        rx.text(var.to_string() if hasattr(var, "to_string") else var, id=f"v-{label}"),
    )


def index() -> rx.Component:
    """Render the shape controls and computed values.

    Returns:
        The annotation test dashboard.
    """
    return rx.vstack(
        rx.heading("shapes", id="page-shapes"),
        rx.text(Shapes.py_version, id="pyver"),
        show("l_opt", Shapes.l_opt),
        rx.cond(
            Shapes.l_opt,
            rx.text("has list", id="cond-list"),
            rx.text("no list", id="cond-list"),
        ),
        show("d_nested", Shapes.d_nested),
        rx.cond(
            Shapes.o_str, rx.text(Shapes.o_str, id="o_str"), rx.text("none", id="o_str")
        ),
        show("ann", Shapes.ann),
        show("point", Shapes.point),
        rx.text(Shapes.point.x, id="point-x"),
        show("pm", Shapes.pm),
        rx.text(Shapes.pm.name, id="pm-name"),
        show("lit", Shapes.lit),
        show("color", Shapes.color),
        show("when", Shapes.when),
        show("fld", Shapes.fld),
        rx.foreach(Shapes.fld, lambda f: rx.text(f, class_name="fld-item")),
        show("uni", Shapes.uni),
        show("tup", Shapes.tup),
        show("td", Shapes.td),
        rx.foreach(
            Shapes.rows, lambda r: rx.text(r["i"], "->", r["sq"], class_name="row")
        ),
        rx.text(Shapes.counter, id="counter"),
        rx.text(Shapes.bg_running.to_string(), id="bg_running"),
        rx.hstack(
            rx.button("mutate", on_click=Shapes.mutate, id="mutate"),
            rx.button("reset", on_click=Shapes.reset_opt, id="reset"),
            rx.button("bg", on_click=Shapes.bg, id="bg"),
            rx.button("greet", on_click=WorldGreeter.greet, id="greet"),
            rx.button("bump", on_click=FutureState.bump, id="bump"),
        ),
        rx.text(WorldGreeter.greeting, id="greeting"),
        rx.text(FutureState.f_summary, id="f_summary"),
        rx.link("other page", href="/other", id="to-other"),
    )


def other() -> rx.Component:
    """Render a second route for state persistence checks.

    Returns:
        The route's shared state values.
    """
    return rx.vstack(
        rx.heading("other", id="page-other"),
        rx.text(Shapes.counter, id="other-counter"),
        rx.text(FutureState.f_summary, id="other-f_summary"),
        rx.link("back", href="/", id="to-index"),
    )


app = rx.App()
app.add_page(index)
app.add_page(other, route="/other")
