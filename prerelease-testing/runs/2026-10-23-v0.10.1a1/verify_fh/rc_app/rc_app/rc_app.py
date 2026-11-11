"""React Compiler coverage probe: which generated page shapes get compiled (verify_fh / FS-2)."""

import os

import reflex as rx

assert f"/envs/{os.environ.get('EXPECT_VENV', 'new')}/" in rx.__file__, rx.__file__


class S(rx.State):
    count: int = 0
    items: list[str] = ["a", "b"]
    flag: bool = True

    @rx.event
    def inc(self):
        self.count += 1

    @rx.event
    def mounted(self):
        self.flag = not self.flag


@rx.memo
def memo_plain(n: int) -> rx.Component:
    return rx.text("memo plain ", n)


@rx.memo
def memo_id(n: int) -> rx.Component:
    return rx.text("memo id ", n, id="memo_id_el")


class CS(rx.ComponentState):
    v: int = 0

    @rx.event
    def bump(self):
        self.v += 1

    @classmethod
    def get_component(cls, **props):
        return rx.button(cls.v, on_click=cls.bump, **props)


def static_page():
    """No state, no events, no ids."""
    return rx.vstack(rx.heading("static"), rx.text("hello"))


def noid_page():
    """State read + event trigger + cond + foreach + on_mount, no id anywhere."""
    return rx.vstack(
        rx.heading("noid"),
        rx.text(S.count),
        rx.button("inc", on_click=S.inc),
        rx.cond(S.flag, rx.text("flag on"), rx.text("flag off")),
        rx.foreach(S.items, lambda it: rx.text(it)),
        rx.text("mounted"),
        on_mount=S.mounted,
    )


def withid_page():
    """Same as noid but one element carries an id."""
    return rx.vstack(
        rx.heading("withid"),
        rx.text(S.count, id="count"),
        rx.button("inc", on_click=S.inc),
    )


def memo_page():
    return rx.vstack(rx.heading("memo"), memo_plain(n=S.count), memo_id(n=S.count))


def cs_page():
    return rx.vstack(rx.heading("cs"), CS.create(), CS.create())


def form_page():
    """Form with a named field, no ids."""
    return rx.form(rx.input(name="x"), rx.button("go"), on_submit=S.inc)


def input_page():
    """Controlled input with on_change (debounce) and a client-state var, no ids."""
    return rx.vstack(rx.heading("input"), rx.input(value=S.count.to_string(), on_change=S.inc))


def upload_page():
    """rx.upload requires an id (refs)."""
    return rx.upload(rx.text("drop"), id="upl")


app = rx.App()
app.add_page(static_page, route="/")
app.add_page(noid_page, route="/noid")
app.add_page(withid_page, route="/withid")
app.add_page(memo_page, route="/memo")
app.add_page(cs_page, route="/cs")
app.add_page(form_page, route="/form")
app.add_page(input_page, route="/input")
app.add_page(upload_page, route="/upload")
