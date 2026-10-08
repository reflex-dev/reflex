"""a3_hydration: reflex#7493 (client-storage vars applied at boot are re-marked dirty -> echoed through get_delta).

Pages:
  /         no on_load. Every storage flavour (LS, SS, Cookie plain + path/max_age/same_site, sync=True LS),
            a substate, two ComponentState instances, computed vars over storage vars, get_delta overrides
            that log what they see (BOOTTRACE GD ...) and one that sanitises a value ("bad*" -> "").
  /onload   on_load sets Srv.srv_ls to a server value -> must win over the browser's value.
  /plainload  on_load that changes nothing (frame counting with an on_load page).
Every get_delta call is logged with the client token so a driver can count calls per page load.
"""

import json
import os
import time

import reflex as rx
from reflex.constants.state import FIELD_MARKER

assert f"/scratchpad/envs/{os.environ['RVH_VENV']}/" in rx.__file__, (os.environ.get("RVH_VENV"), rx.__file__)

ROOT = "reflex___state____state"


def trace(tag: str, **kw):
    print(f"BOOTTRACE {tag} {json.dumps(kw, default=str, sort_keys=True)}", flush=True)


def _seen(state, delta, watch):
    sub = delta.get(state.get_full_name()) or {}
    out = {}
    for k, v in sub.items():
        name = k[: -len(FIELD_MARKER)] if k.endswith(FIELD_MARKER) else k
        if name in watch:
            out[name] = v
    return out


class Prefs(rx.State):
    """Root-level storage vars + computed vars over them + a logging get_delta override."""

    theme: str = rx.LocalStorage("light", name="be_theme", sync=True)
    note: str = rx.LocalStorage("note-default", name="be_note")
    sess: str = rx.SessionStorage("sess-default", name="be_sess")
    ck: str = rx.Cookie("ck-default", name="be_ck")
    ckopt: str = rx.Cookie("ckopt-default", name="be_ckopt", path="/", max_age=3600, same_site="strict")
    clicks: int = 0

    @rx.var
    def theme_upper(self) -> str:
        return f"T:{self.theme.upper()}"

    @rx.var(cache=False)
    def note_len(self) -> str:
        return f"N:{len(self.note)}:{self.note}"

    @rx.var
    def ck_combo(self) -> str:
        return f"{self.ck}|{self.ckopt}"

    @rx.state._override_base_method
    def get_delta(self):
        delta = super().get_delta()
        root = delta.get(ROOT, {})
        trace(
            "GD",
            st="Prefs",
            tok=self.router.session.client_token[:8],
            path=self.router.url.path if hasattr(self.router, "url") else self.router.page.path,
            root_is_h=root.get("is_hydrated" + FIELD_MARKER, "-"),
            seen=_seen(self, delta, {"theme", "note", "sess", "ck", "ckopt", "theme_upper", "note_len", "ck_combo"}),
        )
        return delta

    @rx.event
    def set_user(self):
        self.theme = "user-dark"
        self.note = "user-note"
        self.sess = "user-sess"
        self.ck = "user-ck"
        self.ckopt = "user-ckopt"
        self.clicks += 1

    @rx.event
    def set_theme(self, v: str):
        self.theme = v

    @rx.event
    def probe(self):
        trace("PROBE", tok=self.router.session.client_token[:8], theme=self.theme, note=self.note, sess=self.sess,
              ck=self.ck, ckopt=self.ckopt, theme_upper=self.theme_upper, note_len=self.note_len)


class SubPrefs(Prefs):
    """Substate with storage, cookie options and its own override."""

    sub_ls: str = rx.LocalStorage("sub-default", name="be_sub_ls")
    sub_ck: str = rx.Cookie("subck-default", name="be_sub_ck", max_age=7200, same_site="lax")

    @rx.var
    def sub_combo(self) -> str:
        return f"{self.sub_ls}+{self.theme}"

    @rx.state._override_base_method
    def get_delta(self):
        delta = super().get_delta()
        trace("GD", st="SubPrefs", tok=self.router.session.client_token[:8],
              seen=_seen(self, delta, {"sub_ls", "sub_ck", "sub_combo"}))
        return delta

    @rx.event
    def set_user_sub(self):
        self.sub_ls = "user-sub"
        self.sub_ck = "user-subck"


class Guard(rx.State):
    """An auth-like filter: a value starting with 'bad' is sanitised in the delta (the browser must store '')."""

    tok: str = rx.LocalStorage("", name="be_tok")

    @rx.var
    def tok_ok(self) -> bool:
        return self.tok.startswith("good")

    @rx.state._override_base_method
    def get_delta(self):
        delta = super().get_delta()
        sub = delta.get(self.get_full_name())
        seen = _seen(self, delta, {"tok", "tok_ok"})
        if sub is not None and str(sub.get("tok" + FIELD_MARKER, "")).startswith("bad"):
            sub["tok" + FIELD_MARKER] = ""
            seen["SANITISED"] = True
        trace("GD", st="Guard", tok=self.router.session.client_token[:8], seen=seen)
        return delta

    @rx.event
    def set_good(self):
        self.tok = "good-123"


class Srv(rx.State):
    """on_load overrides a storage var; the server value must win over the browser's."""

    srv_ls: str = rx.LocalStorage("srv-default", name="be_srv")
    srv_ck: str = rx.Cookie("srvck-default", name="be_srv_ck")
    loads: int = 0

    @rx.event
    def on_load_set(self):
        self.loads += 1
        trace("ONLOAD", tok=self.router.session.client_token[:8], before_ls=self.srv_ls, before_ck=self.srv_ck)
        self.srv_ls = f"srv-onload-{self.loads}"
        self.srv_ck = f"srvck-onload-{self.loads}"

    @rx.event
    def on_load_noop(self):
        trace("ONLOAD_NOOP", tok=self.router.session.client_token[:8], srv_ls=self.srv_ls)


class Box(rx.ComponentState):
    """ComponentState with storage (no name -> one key per instance)."""

    pref: str = rx.LocalStorage("box-default")
    bck: str = rx.Cookie("boxck-default", max_age=600)

    @rx.event
    def choose(self):
        self.pref = "box-user"
        self.bck = "boxck-user"

    @classmethod
    def get_component(cls, label: str, **props):
        return rx.hstack(
            rx.text(label),
            rx.text(cls.pref, id=f"box-{label}-pref"),
            rx.text(cls.bck, id=f"box-{label}-bck"),
            rx.button("choose", on_click=cls.choose, id=f"box-{label}-choose"),
        )


box_a = Box.create("a")
box_b = Box.create("b")


def common():
    return rx.vstack(
        rx.text(rx.cond(rx.State.is_hydrated, "H:yes", "H:no"), id="hyd-flag"),
        rx.text(Prefs.theme, id="theme"),
        rx.text(Prefs.note, id="note"),
        rx.text(Prefs.sess, id="sess"),
        rx.text(Prefs.ck, id="ck"),
        rx.text(Prefs.ckopt, id="ckopt"),
        rx.text(Prefs.theme_upper, id="theme-upper"),
        rx.text(Prefs.note_len, id="note-len"),
        rx.text(Prefs.ck_combo, id="ck-combo"),
        rx.text(SubPrefs.sub_ls, id="sub-ls"),
        rx.text(SubPrefs.sub_ck, id="sub-ck"),
        rx.text(SubPrefs.sub_combo, id="sub-combo"),
        rx.text(Guard.tok, id="tok"),
        rx.text(rx.cond(Guard.tok_ok, "TOK:ok", "TOK:no"), id="tok-ok"),
        rx.text(Srv.srv_ls, id="srv-ls"),
        rx.text(Srv.srv_ck, id="srv-ck"),
        rx.text(Prefs.clicks, id="clicks"),
        rx.button("set user", on_click=Prefs.set_user, id="set-user"),
        rx.button("set user sub", on_click=SubPrefs.set_user_sub, id="set-user-sub"),
        rx.button("good tok", on_click=Guard.set_good, id="good-tok"),
        rx.button("probe", on_click=Prefs.probe, id="probe"),
        rx.input(id="theme-in", on_blur=Prefs.set_theme),
        box_a,
        box_b,
        rx.hstack(
            rx.link("home", href="/", id="nav-home"),
            rx.link("onload", href="/onload", id="nav-onload"),
            rx.link("plainload", href="/plainload", id="nav-plainload"),
        ),
    )


def index():
    return common()


def onload():
    return rx.vstack(rx.heading("onload page"), common())


def plainload():
    return rx.vstack(rx.heading("plainload page"), common())


app = rx.App()
app.add_page(index)
app.add_page(onload, route="/onload", on_load=Srv.on_load_set)
app.add_page(plainload, route="/plainload", on_load=Srv.on_load_noop)
