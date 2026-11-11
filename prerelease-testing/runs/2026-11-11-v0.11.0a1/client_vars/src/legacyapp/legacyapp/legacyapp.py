"""An app written against the 0.10.1 `rx._x.client_state` API, run unchanged on 0.10.1 and 0.11.0a1."""
import os

import reflex as rx
from reflex.experimental.client_state import ClientStateVar

if os.environ.get("EXPECT_VENV"):
    assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__

g = rx._x.client_state("g_named", default="g0")
g_dict = ClientStateVar.create("g_dict", default={"n": 1, "tags": ["a"]})
local = rx._x.client_state("loc", default=0, global_ref=False)
anon = rx._x.client_state(default="anon0")
nodefault = ClientStateVar.create("nodef")
not_included = ClientStateVar.create("not_included", default="ni0")
local_two_pages = ClientStateVar.create("ltp", default=0, global_ref=False)


class S(rx.State):
    got: str = ""
    rows: list[str] = ["a", "b"]

    @rx.event
    def push(self):
        return g.push("pushed")

    @rx.event
    def push_dict(self):
        return g_dict.push({"n": 2, "tags": ["a", "b"]})

    @rx.event
    def retrieve(self):
        return g.retrieve(S.on_got)

    @rx.event
    def retrieve_dict(self):
        return g_dict.retrieve(S.on_got_any)

    @rx.event
    def retrieve_ni(self):
        return not_included.retrieve(S.on_got_any)

    @rx.event
    def on_got(self, v: str):
        self.got = repr(v)

    @rx.event
    def on_got_any(self, v: dict | str | None):
        self.got = repr(v)


def nav() -> rx.Component:
    return rx.hstack(
        rx.link("home", href="/", id="nav-home"),
        rx.link("two", href="/two", id="nav-two"),
        rx.text(rx.cond(S.is_hydrated, "hydrated", "no"), id="hyd"),
    )


def index() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("home"),
        g, g_dict, local, anon, nodefault, local_two_pages,
        rx.el.span(g.value, id="g"),
        rx.el.span(g_dict.value.to_string(), id="gd"),
        rx.el.span(local.value, id="loc"),
        rx.el.span(anon.value, id="anon"),
        rx.el.span(nodefault.value.to_string(), id="nodef"),
        rx.el.span(not_included.value, id="ni"),
        rx.el.span(local_two_pages.value, id="ltp"),
        rx.el.span(S.got, id="got"),
        rx.input(value=g.value, on_change=g.set, id="g-input"),
        rx.button("g-set", id="g-set", on_click=g.set_value("g1")),
        rx.button("loc-inc", id="loc-inc", on_click=local.set_value(local.value + 1)),
        rx.button("anon-set", id="anon-set", on_click=anon.set_value("anon1")),
        rx.button("nodef-set", id="nodef-set", on_click=nodefault.set_value("nd1")),
        rx.button("ni-set", id="ni-set", on_click=not_included.set_value("ni1")),
        rx.button("ltp-inc", id="ltp-inc", on_click=local_two_pages.set_value(local_two_pages.value + 1)),
        rx.button("push", id="push", on_click=S.push),
        rx.button("push-dict", id="push-dict", on_click=S.push_dict),
        rx.button("retrieve", id="retrieve", on_click=S.retrieve),
        rx.button("retrieve-dict", id="retrieve-dict", on_click=S.retrieve_dict),
        rx.button("retrieve-ni", id="retrieve-ni", on_click=S.retrieve_ni),
        rx.box(rx.foreach(S.rows, lambda r: rx.el.span(r, "=", g.value, class_name="row")), id="rows"),
    )


def two() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("two"),
        g, local_two_pages,
        rx.el.span(g.value, id="g"),
        rx.el.span(local_two_pages.value, id="ltp"),
        rx.el.span(S.got, id="got"),
        rx.button("ltp-inc", id="ltp-inc", on_click=local_two_pages.set_value(local_two_pages.value + 1)),
        rx.button("retrieve", id="retrieve", on_click=S.retrieve),
        rx.button("retrieve-dict", id="retrieve-dict", on_click=S.retrieve_dict),
    )


app = rx.App()
app.add_page(index, route="/")
app.add_page(two, route="/two")
