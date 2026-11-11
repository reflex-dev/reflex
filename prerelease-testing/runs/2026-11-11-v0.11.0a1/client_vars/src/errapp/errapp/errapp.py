"""One misuse per run, selected with ERR_CASE, to see what a user gets from `reflex compile` (cluster client_vars)."""
import dataclasses
import os

import pydantic
import reflex as rx

if os.environ.get("EXPECT_VENV"):
    assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__

CASE = os.environ.get("ERR_CASE", "none")


class Person(pydantic.BaseModel):
    first: str = "Ada"
    last: str = "Lovelace"

    @property
    def full(self) -> str:
        return f"{self.first} {self.last}"


@dataclasses.dataclass
class Item:
    name: str = "widget"

    @property
    def label(self) -> str:
        return self.name.upper()


class State(rx.State):
    person: Person = Person()
    people: list[Person] = [Person()]
    item: Item = Item()
    shown: str = "shown"
    _secret: str = "s3cr3t-default"

    if CASE == "storage_factory":
        theme: str = rx.field(default_factory=lambda: rx.LocalStorage("dark"))
    if CASE == "storage_factory_cookie":
        token: str | None = rx.field(default_factory=lambda: rx.Cookie("", max_age=3600))

    @rx.event
    def take(self, v: str):
        self.shown = v


def index() -> rx.Component:
    kids = [rx.text(State.shown, id="shown")]
    if CASE == "prop_pydantic":
        kids.append(rx.text(State.person.full))
    if CASE == "prop_dataclass":
        kids.append(rx.text(State.item.label))
    if CASE == "prop_foreach":
        kids.append(rx.foreach(State.people, lambda p: rx.text(p.full)))
    if CASE == "backend_child":
        kids.append(rx.text(State._secret))
    if CASE == "backend_fstring":
        kids.append(rx.text(f"value: {State._secret}"))
    if CASE == "backend_id":
        kids.append(rx.box(id=State._secret))
    if CASE == "backend_typed_prop":
        kids.append(rx.el.div(title=State._secret))
    if CASE == "backend_image":
        kids.append(rx.image(src=State._secret))
    if CASE == "backend_toast":
        kids.append(rx.button("t", on_click=rx.toast(State._secret)))
    if CASE == "backend_event_arg":
        kids.append(rx.button("t", on_click=State.take(State._secret)))
    if CASE == "backend_eq":
        kids.append(rx.cond(State._secret == "s3cr3t-default", rx.text("EQ", id="eq"), rx.text("NE", id="eq")))
    return rx.vstack(*kids)


app = rx.App()
if CASE == "page_title":
    app.add_page(index, route="/", title=State._secret)
elif CASE == "page_meta":
    app.add_page(index, route="/", meta=[{"name": "x-secret", "content": State._secret}])
elif CASE == "page_on_load":
    app.add_page(index, route="/", on_load=State._secret)
elif CASE == "page_decorator":
    rx.page(route="/", title=State._secret)(index)
else:
    app.add_page(index, route="/")
