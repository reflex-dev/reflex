"""Verifier app: client-storage vars rewritten during hydration (computed var / on_load / event).

Identical source runs on reflex 0.9.12 and 0.10.0a1. Each variant has its own state class and its
own storage key, so setting one key to 'bad' only exercises that variant.
"""

from __future__ import annotations

import os
from importlib.metadata import version

import reflex as rx

_VENV = os.environ.get("VERIFY_VENV", "")
assert _VENV and f"/scratchpad/envs/{_VENV}/" in rx.__file__, (_VENV, rx.__file__)
RX_VERSION = version("reflex")


def chrome(*children: rx.Component) -> rx.Component:
    """Common page frame: version, hydration flag, navigation links."""
    return rx.vstack(
        rx.text(f"reflex {RX_VERSION}", id="version"),
        rx.text(rx.cond(rx.State.is_hydrated, "hydrated", "not-hydrated"), id="hyd"),
        rx.hstack(
            rx.link("home", href="/", id="nav_home"),
            *[rx.link(p, href=f"/{p}", id=f"nav_{p}") for p in PAGES],
        ),
        *children,
    )


# (a) cached computed var clears a LocalStorage var of a direct rx.State subclass
class ACachedCv(rx.State):
    ls: str = rx.LocalStorage(name="v_a")
    seen: str = ""
    noop_count: int = 0

    @rx.var(cache=True)
    def check(self) -> str:
        if self.ls == "bad":
            self.ls = ""
            return "cleared-by-cached-cv"
        return f"value={self.ls!r}"

    @rx.event
    def probe(self):
        self.seen = f"backend ls={self.ls!r}"

    @rx.event
    def noop(self):
        self.noop_count += 1


# (b) uncached computed var clears a LocalStorage var
class BUncachedCv(rx.State):
    ls: str = rx.LocalStorage(name="v_b")
    seen: str = ""
    noop_count: int = 0

    @rx.var(cache=False)
    def check(self) -> str:
        if self.ls == "bad":
            self.ls = ""
            return "cleared-by-uncached-cv"
        return f"value={self.ls!r}"

    @rx.event
    def probe(self):
        self.seen = f"backend ls={self.ls!r}"

    @rx.event
    def noop(self):
        self.noop_count += 1


# (c) on_load clears LocalStorage, Cookie and SessionStorage vars
class COnLoad(rx.State):
    ls: str = rx.LocalStorage(name="v_c_ls")
    ck: str = rx.Cookie(name="v_c_ck")
    ss: str = rx.SessionStorage(name="v_c_ss")
    seen: str = ""
    loads: int = 0

    @rx.event
    def on_load(self):
        self.loads += 1
        if self.ls == "bad":
            self.ls = ""
        if self.ck == "bad":
            self.ck = ""
        if self.ss == "bad":
            self.ss = ""

    @rx.event
    def probe(self):
        self.seen = f"backend ls={self.ls!r} ck={self.ck!r} ss={self.ss!r}"


# (d) a normal (clicked) event clears LocalStorage, Cookie and SessionStorage vars
class DEvent(rx.State):
    ls: str = rx.LocalStorage(name="v_d_ls")
    ck: str = rx.Cookie(name="v_d_ck")
    ss: str = rx.SessionStorage(name="v_d_ss")
    seen: str = ""

    @rx.event
    def fix(self):
        if self.ls == "bad":
            self.ls = ""
        if self.ck == "bad":
            self.ck = ""
        if self.ss == "bad":
            self.ss = ""

    @rx.event
    def probe(self):
        self.seen = f"backend ls={self.ls!r} ck={self.ck!r} ss={self.ss!r}"


# (e1) cached computed var clears a Cookie var
class ECookieCv(rx.State):
    ck: str = rx.Cookie(name="v_e_ck")
    seen: str = ""
    noop_count: int = 0

    @rx.var(cache=True)
    def check(self) -> str:
        if self.ck == "bad":
            self.ck = ""
            return "cleared-by-cached-cv"
        return f"value={self.ck!r}"

    @rx.event
    def probe(self):
        self.seen = f"backend ck={self.ck!r}"

    @rx.event
    def noop(self):
        self.noop_count += 1


# (e2) cached computed var clears a SessionStorage var
class ESessionCv(rx.State):
    ss: str = rx.SessionStorage(name="v_e_ss")
    seen: str = ""
    noop_count: int = 0

    @rx.var(cache=True)
    def check(self) -> str:
        if self.ss == "bad":
            self.ss = ""
            return "cleared-by-cached-cv"
        return f"value={self.ss!r}"

    @rx.event
    def probe(self):
        self.seen = f"backend ss={self.ss!r}"

    @rx.event
    def noop(self):
        self.noop_count += 1


# (f) cached computed var on a SUBSTATE clears that substate's own LocalStorage var
class FParent(rx.State):
    parent_note: str = "parent"


class FChild(FParent):
    ls: str = rx.LocalStorage(name="v_f")
    seen: str = ""
    noop_count: int = 0

    @rx.var(cache=True)
    def check(self) -> str:
        if self.ls == "bad":
            self.ls = ""
            return "cleared-by-substate-cached-cv"
        return f"value={self.ls!r}"

    @rx.event
    def probe(self):
        self.seen = f"backend ls={self.ls!r}"

    @rx.event
    def noop(self):
        self.noop_count += 1


# (g) cached computed var sets a DIFFERENT, plain var (not client storage)
class GOtherVar(rx.State):
    ls: str = rx.LocalStorage(name="v_g")
    plain: str = "initial"
    seen: str = ""
    noop_count: int = 0

    @rx.var(cache=True)
    def check(self) -> str:
        if self.ls == "bad":
            self.plain = "set-by-cv"
            return "saw-bad"
        return f"value={self.ls!r}"

    @rx.event
    def probe(self):
        self.seen = f"backend ls={self.ls!r} plain={self.plain!r}"

    @rx.event
    def noop(self):
        self.noop_count += 1


def _cv_page(S, var: str, label: str) -> rx.Component:
    return chrome(
        rx.heading(label),
        rx.text("var=", getattr(S, var), id="var"),
        rx.text("check=", S.check, id="check"),
        *([rx.text("plain=", S.plain, id="plain")] if hasattr(S, "plain") else []),
        rx.text("seen=", S.seen, id="seen"),
        rx.text("noop=", S.noop_count, id="noop_count"),
        rx.button("probe", id="probe", on_click=S.probe),
        rx.button("noop", id="noop", on_click=S.noop),
    )


@rx.page(route="/a")
def page_a() -> rx.Component:
    return _cv_page(ACachedCv, "ls", "(a) cached cv clears LocalStorage")


@rx.page(route="/b")
def page_b() -> rx.Component:
    return _cv_page(BUncachedCv, "ls", "(b) uncached cv clears LocalStorage")


@rx.page(route="/c", on_load=COnLoad.on_load)
def page_c() -> rx.Component:
    return chrome(
        rx.heading("(c) on_load clears LocalStorage/Cookie/SessionStorage"),
        rx.text("ls=", COnLoad.ls, id="ls"),
        rx.text("ck=", COnLoad.ck, id="ck"),
        rx.text("ss=", COnLoad.ss, id="ss"),
        rx.text("loads=", COnLoad.loads, id="loads"),
        rx.text("seen=", COnLoad.seen, id="seen"),
        rx.button("probe", id="probe", on_click=COnLoad.probe),
    )


@rx.page(route="/d")
def page_d() -> rx.Component:
    return chrome(
        rx.heading("(d) clicked event clears LocalStorage/Cookie/SessionStorage"),
        rx.text("ls=", DEvent.ls, id="ls"),
        rx.text("ck=", DEvent.ck, id="ck"),
        rx.text("ss=", DEvent.ss, id="ss"),
        rx.text("seen=", DEvent.seen, id="seen"),
        rx.button("fix", id="fix", on_click=DEvent.fix),
        rx.button("probe", id="probe", on_click=DEvent.probe),
    )


@rx.page(route="/e_cookie")
def page_e_cookie() -> rx.Component:
    return _cv_page(ECookieCv, "ck", "(e1) cached cv clears Cookie")


@rx.page(route="/e_session")
def page_e_session() -> rx.Component:
    return _cv_page(ESessionCv, "ss", "(e2) cached cv clears SessionStorage")


@rx.page(route="/f")
def page_f() -> rx.Component:
    return _cv_page(FChild, "ls", "(f) substate cached cv clears its own LocalStorage")


@rx.page(route="/g")
def page_g() -> rx.Component:
    return _cv_page(GOtherVar, "ls", "(g) cached cv sets a plain var")


PAGES = ["a", "b", "c", "d", "e_cookie", "e_session", "f", "g"]


class Diag(rx.State):
    """Reports, from inside the backend worker, its pid, hash seed and small-set iteration order."""

    info: str = ""

    @rx.event
    def diag(self):
        self.info = (
            f"pid={os.getpid()} seed={os.environ.get('PYTHONHASHSEED')} "
            f"order_tp={list({'ls_cv'}.union({'cv_check'}))} order_a={list({'ls'}.union({'check'}))}"
        )


@rx.page(route="/")
def index() -> rx.Component:
    return chrome(
        rx.heading("cvstore index"),
        rx.button("diag", id="diag", on_click=Diag.diag),
        rx.text(Diag.info, id="diag_info"),
    )


app = rx.App()
