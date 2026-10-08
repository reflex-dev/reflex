"""a4_hydration Part 2: reflex#7505 (state.js storage-echo skipping) regression hunt.

Every client-storage flavour in one app:
  Prefs     LS sync=True `h4_syn`, LS sync=False `h4_nos`, SS `h4_ses`, Cookie max_age `h4_ck`,
            LS sync=True `h4_san` + LS sync=False `h4_sanns` SANITISED by a get_delta override
            (lowercase + clamp to 12 chars), so the server-changed value must be written back.
  Sub(Prefs) substate: LS sync=True `h4_sub`, Cookie `h4_subck`.
  Box       rx.ComponentState, LS sync=True without name (one key per instance), LS sync=False.
  Stamp     /stamp on_load writes LS sync=True `h4_last` and LS sync=False `h4_visits`.
Handlers: set by input (on_blur), fixed-value buttons (back-to-back clicks), same value, "" and back
(yield chain), unicode / JSON-looking / long strings, a background task writing inside `async with self`,
a yielded chain into another handler.
"""

import asyncio
import json
import os

import reflex as rx
from reflex.constants.state import FIELD_MARKER

assert f"/scratchpad/envs/{os.environ['RVH_VENV']}/" in rx.__file__, (os.environ.get("RVH_VENV"), rx.__file__)

UNI = "ünïcödé ✓ 日本語 🎉 \"q\" 'a' \\ end"
JSONISH = '{"a": [1, 2, {"b": null}], "c": "x\\"y", "d": true}'
LONG = "L" + "0123456789abcdef" * 400 + "Z"  # 6402 chars


def trace(tag: str, **kw):
    print(f"H4TRACE {tag} {json.dumps(kw, default=str, sort_keys=True)}", flush=True)


def sanitise(v):
    return v.lower()[:12] if isinstance(v, str) else v


class Prefs(rx.State):
    syn: str = rx.LocalStorage("syn-default", name="h4_syn", sync=True)
    nos: str = rx.LocalStorage("nos-default", name="h4_nos")
    ses: str = rx.SessionStorage("ses-default", name="h4_ses")
    ck: str = rx.Cookie("ck-default", name="h4_ck", max_age=3600, path="/")
    san: str = rx.LocalStorage("san-default", name="h4_san", sync=True)
    sanns: str = rx.LocalStorage("sanns-default", name="h4_sanns")
    bg_runs: int = 0

    @rx.var
    def syn_len(self) -> int:
        return len(self.syn)

    @rx.state._override_base_method
    def get_delta(self):
        delta = super().get_delta()
        sub = delta.get(self.get_full_name())
        if sub:
            for f in ("san", "sanns"):
                k = f + FIELD_MARKER
                if k in sub and sub[k] != sanitise(sub[k]):
                    trace("SANITISE", tok=self.router.session.client_token[:8], field=f, before=sub[k], after=sanitise(sub[k]))
                    sub[k] = sanitise(sub[k])
        return delta

    @rx.event
    def set_syn(self, v: str):
        self.syn = v

    @rx.event
    def set_nos(self, v: str):
        self.nos = v

    @rx.event
    def set_ses(self, v: str):
        self.ses = v

    @rx.event
    def set_ck(self, v: str):
        self.ck = v

    @rx.event
    def set_san(self, v: str):
        self.san = v

    @rx.event
    def set_sanns(self, v: str):
        self.sanns = v

    @rx.event
    def same_all(self):
        # Assign every storage var the value it already has.
        self.syn = self.syn
        self.nos = self.nos
        self.ses = self.ses
        self.ck = self.ck
        self.san = self.san
        self.sanns = self.sanns

    @rx.event
    def click_syn(self, v: str):
        self.syn = v

    @rx.event
    def empty_and_back(self):
        old_syn, old_nos = self.syn, self.nos
        self.syn = ""
        self.nos = ""
        yield
        self.syn = old_syn + "-back"
        self.nos = old_nos + "-back"

    @rx.event
    def to_empty(self):
        self.syn = ""
        self.nos = ""

    @rx.event
    def special(self, which: str):
        val = {"uni": UNI, "json": JSONISH, "long": LONG}[which]
        self.syn = val
        self.nos = val

    @rx.event
    def chain(self):
        self.syn = "chain-1"
        yield
        self.syn = "chain-2"
        yield Prefs.chain_end

    @rx.event
    def chain_end(self):
        self.syn = "chain-3"
        self.nos = "chain-3-nos"

    @rx.event(background=True)
    async def bg_write(self):
        await asyncio.sleep(0.3)
        async with self:
            self.bg_runs += 1
            self.syn = f"bg-{self.bg_runs}"
            self.nos = f"bg-nos-{self.bg_runs}"


class Sub(Prefs):
    sub: str = rx.LocalStorage("sub-default", name="h4_sub", sync=True)
    subck: str = rx.Cookie("subck-default", name="h4_subck", max_age=7200)

    @rx.event
    def set_sub(self, v: str):
        self.sub = v
        self.subck = v


class Stamp(rx.State):
    last: str = rx.LocalStorage("last-default", name="h4_last", sync=True)
    visits: str = rx.LocalStorage("0", name="h4_visits")

    @rx.event
    def on_load_stamp(self):
        self.last = f"stamp@{self.router.page.path}"
        self.visits = str(int(self.visits or "0") + 1)


class Box(rx.ComponentState):
    bsyn: str = rx.LocalStorage("bsyn-default", sync=True)
    bnos: str = rx.LocalStorage("bnos-default")

    @rx.event
    def set_both(self, v: str):
        self.bsyn = v
        self.bnos = v

    @classmethod
    def get_component(cls, label: str, **props):
        return rx.hstack(
            rx.text(cls.bsyn, id=f"box-{label}-syn"),
            rx.text(cls.bnos, id=f"box-{label}-nos"),
            rx.input(id=f"box-{label}-in", on_blur=cls.set_both),
        )


box_a = Box.create("a")
box_b = Box.create("b")


def values():
    return rx.vstack(
        rx.text(rx.cond(rx.State.is_hydrated, "H:yes", "H:no"), id="hyd"),
        rx.text(Prefs.syn, id="v-syn"),
        rx.text(Prefs.nos, id="v-nos"),
        rx.text(Prefs.ses, id="v-ses"),
        rx.text(Prefs.ck, id="v-ck"),
        rx.text(Prefs.san, id="v-san"),
        rx.text(Prefs.sanns, id="v-sanns"),
        rx.text(Prefs.syn_len, id="v-synlen"),
        rx.text(Sub.sub, id="v-sub"),
        rx.text(Sub.subck, id="v-subck"),
        rx.text(Stamp.last, id="v-last"),
        rx.text(Stamp.visits, id="v-visits"),
        rx.text(Prefs.bg_runs, id="v-bgruns"),
    )


def controls():
    return rx.vstack(
        *[rx.input(id=f"in-{f}", on_blur=getattr(Prefs, f"set_{f}")) for f in ("syn", "nos", "ses", "ck", "san", "sanns")],
        rx.input(id="in-sub", on_blur=Sub.set_sub),
        rx.hstack(*[rx.button(f"c{i}", on_click=Prefs.click_syn(f"c{i}"), id=f"c{i}") for i in range(10)]),
        rx.button("same", on_click=Prefs.same_all, id="same"),
        rx.button("empty-and-back", on_click=Prefs.empty_and_back, id="empty-back"),
        rx.button("to-empty", on_click=Prefs.to_empty, id="to-empty"),
        rx.button("uni", on_click=Prefs.special("uni"), id="sp-uni"),
        rx.button("json", on_click=Prefs.special("json"), id="sp-json"),
        rx.button("long", on_click=Prefs.special("long"), id="sp-long"),
        rx.button("chain", on_click=Prefs.chain, id="chain"),
        rx.button("bg", on_click=Prefs.bg_write, id="bg"),
        box_a,
        box_b,
        rx.hstack(
            rx.link("home", href="/", id="nav-home"),
            rx.link("other", href="/other", id="nav-other"),
            rx.link("stamp", href="/stamp", id="nav-stamp"),
        ),
    )


def index():
    return rx.vstack(rx.heading("home"), values(), controls())


def other():
    return rx.vstack(rx.heading("other"), values(), controls())


def stamp():
    return rx.vstack(rx.heading("stamp"), values(), controls())


app = rx.App()
app.add_page(index)
app.add_page(other, route="/other")
app.add_page(stamp, route="/stamp", on_load=Stamp.on_load_stamp)
