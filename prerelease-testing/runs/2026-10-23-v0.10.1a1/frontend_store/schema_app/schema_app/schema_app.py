"""State-schema hash app (#7553, #7435).

SCHEMA_EXTRA=1 adds a substate + a var + a handler (a "new backend version").
SCHEMA_RENAME=1 renames one handler only. SCHEMA_DEFAULT=1 changes only a default
value (must NOT change the hash). ComponentState instances live on two pages so the
instance counter is exercised across compile / backend processes.
"""

import datetime
import os
from typing import Annotated, Any

import reflex as rx

assert f"/envs/{os.environ.get('EXPECT_VENV', 'new')}/" in rx.__file__, rx.__file__

EXTRA = os.environ.get("SCHEMA_EXTRA") == "1"
RENAME = os.environ.get("SCHEMA_RENAME") == "1"
DEFAULT = os.environ.get("SCHEMA_DEFAULT") == "1"


class Base(rx.State):
    count: int = 7 if DEFAULT else 0
    note: str = ""
    stamp: str = ""

    @rx.event
    def inc(self):
        self.count += 1

    @rx.event
    def set_note(self, v: str):
        self.note = v

    @rx.event
    def tick(self):
        self.stamp = datetime.datetime.now().isoformat()

    if RENAME:

        @rx.event
        def tock(self):
            self.stamp = "tock"

    else:

        @rx.event
        def tack(self):
            self.stamp = "tack"


class Sub(Base):
    items: list[dict[str, Any]] = [{"a": 1}]
    tagged: Annotated[str, "meta"] = "x"

    @rx.event
    def add(self):
        self.items.append({"a": len(self.items) + 1})


if EXTRA:

    class Extra(rx.State):
        extra: int = 0

        @rx.event
        def more(self):
            self.extra += 1

    class SubExtra(Sub):
        pass


class Tally(rx.ComponentState):
    n: int = 0

    @rx.event
    def inc(self):
        self.n += 1

    @classmethod
    def get_component(cls, **props):
        return rx.el.div(
            rx.el.span(cls.n, class_name="tally-n"),
            rx.el.button("+", on_click=cls.inc, class_name="tally-inc"),
            **props,
        )


def header():
    return rx.el.div(
        rx.el.div(rx.State.is_hydrated.to_string(), id="hydrated"),
        rx.el.span(Base.count, id="count"),
        rx.el.button("inc", id="inc", on_click=Base.inc),
        rx.el.input(id="free-input", placeholder="uncontrolled"),
        rx.el.input(id="note-input", on_change=Base.set_note, default_value=Base.note),
        rx.el.span(Base.note, id="note"),
        rx.el.span(Sub.items.to_string(), id="items"),
        rx.el.button("add", id="add", on_click=Sub.add),
        rx.el.a("second", href="/second", id="to-second"),
        rx.el.a("index", href="/", id="to-index"),
        rx.el.a("item", href="/item/5", id="to-item"),
    )


def index() -> rx.Component:
    return rx.el.div(header(), Tally.create(id="t1"), Tally.create(id="t2"))


def second() -> rx.Component:
    return rx.el.div(header(), Tally.create(id="t3"))


def item() -> rx.Component:
    return rx.el.div(header(), rx.el.span(rx.State.router.page.params["iid"], id="iid"))


app = rx.App()
app.add_page(index, route="/")
app.add_page(second, route="/second")
app.add_page(item, route="/item/[iid]")
