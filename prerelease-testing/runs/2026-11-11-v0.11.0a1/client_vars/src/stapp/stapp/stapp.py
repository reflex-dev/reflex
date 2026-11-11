"""Browser storage declarations, shared-name sync (#7637) and cross-tab clear (#7652) (cluster client_vars)."""
import asyncio
import os

import reflex as rx

if os.environ.get("EXPECT_VENV"):
    assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__


class St(rx.State):
    plain: str = rx.LocalStorage("plain-default")
    typed: rx.LocalStorage = rx.LocalStorage("typed-default")
    ck: str = rx.Cookie("ck-default", max_age=5, name="ck")
    ck30: str = rx.Cookie("ck30-default", max_age=30, name="ck30")
    ck_path: str = rx.Cookie("ckp-default", path="/sub", name="ck_path")
    ck_typed: rx.Cookie = rx.Cookie("ckt-default")
    ss: str = rx.SessionStorage("ss-default")
    num: int = rx.LocalStorage("5")
    a: str = rx.LocalStorage("a-default", name="shared", sync=True)
    b: str = rx.LocalStorage("b-default", name="shared", sync=True)
    solo: str = rx.LocalStorage("solo-default", name="solo", sync=True)
    unnamed_sync: str = rx.LocalStorage("us-default", sync=True)
    mixed_sync: str = rx.LocalStorage("ms-default", name="mixed", sync=True)
    mixed_nosync: str = rx.LocalStorage("mn-default", name="mixed")
    n_events: int = 0

    @rx.var
    def solo_len(self) -> int:
        return len(self.solo)

    @rx.var
    def a_upper(self) -> str:
        return self.a.upper()

    @rx.var
    def types(self) -> str:
        return ",".join(f"{n}:{type(getattr(self, n)).__name__}" for n in ("plain", "typed", "ck", "num", "a", "solo"))

    def _bump(self):
        self.n_events += 1

    @rx.event
    def set_var(self, name: str, value: str):
        setattr(self, name, value)
        self._bump()

    @rx.event
    def set_num(self, value: str):
        self.num = int(value)
        self._bump()

    @rx.event
    def set_both(self):
        self.a = "both-A"
        self.b = "both-B"
        self._bump()

    @rx.event(background=True)
    async def bg_set_a(self):
        await asyncio.sleep(0.2)
        async with self:
            self.a = "bg-A"
            self._bump()

    @rx.event
    def remove_shared(self):
        self._bump()
        return rx.remove_local_storage("shared")

    @rx.event
    def remove_solo(self):
        self._bump()
        return rx.remove_local_storage("solo")

    @rx.event
    def clear_ls(self):
        self._bump()
        return rx.clear_local_storage()

    @rx.event
    def bump(self):
        self._bump()


class Sub(St):
    c: str = rx.LocalStorage("c-default", name="shared", sync=True)

    @rx.event
    def set_c(self, value: str):
        self.c = value
        self.n_events += 1


class Other(rx.State):
    d: str = rx.LocalStorage("d-default", name="shared", sync=True)

    @rx.event
    def set_d(self, value: str):
        self.d = value


NAMES = ("plain", "typed", "ck", "ck30", "ck_path", "ck_typed", "ss", "a", "b", "solo", "unnamed_sync", "mixed_sync", "mixed_nosync")


def body(title: str) -> rx.Component:
    return rx.vstack(
        rx.heading(title),
        rx.text(rx.cond(St.is_hydrated, "hydrated", "no"), id="hyd"),
        rx.el.span(St.n_events, id="n-events"),
        *[rx.el.span(getattr(St, n), id=n, class_name="v") for n in NAMES],
        rx.el.span(St.num, id="num", class_name="v"),
        rx.el.span(Sub.c, id="c", class_name="v"),
        rx.el.span(Other.d, id="d", class_name="v"),
        rx.el.span(St.solo_len, id="solo_len", class_name="v"),
        rx.el.span(St.a_upper, id="a_upper", class_name="v"),
        rx.el.span(St.types, id="types"),
        rx.input(id="val", default_value="x"),
        rx.hstack(
            *[rx.button(f"set-{n}", id=f"set-{n}", on_click=St.set_var(n, rx.Var("document.getElementById('val').value").to(str))) for n in NAMES],
            rx.button("set-c", id="set-c", on_click=Sub.set_c(rx.Var("document.getElementById('val').value").to(str))),
            rx.button("set-d", id="set-d", on_click=Other.set_d(rx.Var("document.getElementById('val').value").to(str))),
            rx.button("set-num", id="set-num", on_click=St.set_num("7")),
            rx.button("set-both", id="set-both", on_click=St.set_both),
            rx.button("bg-set-a", id="bg-set-a", on_click=St.bg_set_a),
            rx.button("remove-shared", id="remove-shared", on_click=St.remove_shared),
            rx.button("remove-solo", id="remove-solo", on_click=St.remove_solo),
            rx.button("clear-ls", id="clear-ls", on_click=St.clear_ls),
            rx.button("bump", id="bump", on_click=St.bump),
            wrap="wrap",
        ),
        rx.link("home", href="/", id="nav-home"),
        rx.link("sub", href="/sub", id="nav-sub"),
    )


def index() -> rx.Component:
    return body("home")


def sub() -> rx.Component:
    return body("sub")


app = rx.App()
app.add_page(index, route="/")
app.add_page(sub, route="/sub")
