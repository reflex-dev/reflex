"""Docs samples and statements of v0.10.0a5 (#7519): base_vars.md "Changing Defaults" + backend vars + rx.field,
component_state.md (EditableText, ThemeToggle), upgrading-to-0-10.md, CHANGELOG/news. Samples are copied verbatim
where they are Python code; each statement row says what it checks.
Run: EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_docs.py
"""
import os
import random  # noqa: F401  (docs page context of the BackendVarState demo)
import time
from typing import ClassVar
from unittest import mock

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

from reflex.compiler.utils import _compile_client_storage_recursive  # noqa: E402

V = version("reflex")
print(f"reflex {V}")


def row(name, fn):
    try:
        r = fn()
    except Exception as e:  # noqa: BLE001
        r = f"EXC {type(e).__name__}: {str(e)[:220]}"
    print(f"ROW {name} | {r}", flush=True)


def inst(cls):
    return cls(_reflex_internal_init=True)


def entry(cls, name):
    for kind, d in zip(("cookie", "local", "session"), _compile_client_storage_recursive(cls)):
        for k, v in d.items():
            if k.rsplit(".", 1)[-1].split("_rx_state_")[0] == name:
                return (kind, v)
    return None


# ---- base_vars.md "Changing Defaults", verbatim
class WatchlistState(rx.State):
    ticker: str = "AAPL"
    symbols: list[str] = []
    opened_at: float = 0.0


def watchlist():
    before = inst(WatchlistState)
    before.ticker = "STORED"  # a value already stored on an instance
    untouched = inst(WatchlistState)  # instance exists, var never stored
    WatchlistState.__fields__["ticker"].set_default("MSFT")
    WatchlistState.__fields__["symbols"].set_default(["AAPL", "MSFT"])
    WatchlistState.__fields__["opened_at"].set_default(default_factory=time.time)
    a = inst(WatchlistState)
    time.sleep(0.01)
    b = inst(WatchlistState)
    a.symbols.append("X")
    a.ticker = "Z"
    ta = a.opened_at
    a.reset()
    return (f"new={b.ticker},{list(b.symbols)} opened_at per-instance(a!=b)={ta != b.opened_at} now-ish={abs(b.opened_at - time.time()) < 5} "
            f"| reset={a.ticker},{list(a.symbols)} reset re-calls factory={a.opened_at != ta} | stored stays={before.ticker} "
            f"| existing-instance-unstored reads={untouched.ticker} | b independent of a={list(b.symbols) == ['AAPL', 'MSFT']}")


row("base_vars: WatchlistState sample + 'applies to values not yet stored / new session / reset(); stored stay'", watchlist)


def exactly_one():
    f = WatchlistState.__fields__["ticker"]
    out = []
    for label, call in [("neither", lambda: f.set_default()), ("default_factory=None", lambda: f.set_default(default_factory=None)),
                        ("both", lambda: f.set_default("x", default_factory=lambda: "y")),
                        ("None + factory", lambda: f.set_default(None, default_factory=lambda: "y")),
                        ("default= kw", lambda: f.set_default(default="KW")), ("None", lambda: f.set_default(None))]:
        try:
            call()
            out.append(f"{label}: ok -> {inst(WatchlistState).ticker!r}")
        except TypeError as e:
            out.append(f"{label}: TypeError '{e}'")
    f.set_default("MSFT")
    return "; ".join(out)


row("base_vars: 'Pass exactly one of default and default_factory'", exactly_one)


def factory_called_each():
    calls = []

    class FC(rx.State):
        n: int = 0

    FC.__fields__["n"].set_default(default_factory=lambda: calls.append(1) or len(calls))
    vals = [inst(FC).n for _ in range(3)]
    s = inst(FC)
    _ = s.n
    s.n = 99
    s.reset()
    return f"instances={vals} after reset={s.n} calls={len(calls)}"


row("base_vars: 'a default_factory is called for each new instance'", factory_called_each)


def copies_mutable():
    class CM(rx.State):
        items: list[str] = []
        _cfg: dict = {}

    val = ["a"]
    cfg = {"k": [1]}
    CM.__fields__["items"].set_default(val)
    CM.__fields__["_cfg"].set_default(cfg)
    val.append("later")
    cfg["k"].append(2)
    a, b = inst(CM), inst(CM)
    a.items.append("a-only")
    a._cfg["k"].append(3)
    return (f"b.items={list(b.items)} b._cfg={dict(b._cfg)} a.items={list(a.items)} "
            f"field default={CM.__fields__['items'].default!r} factory={type(CM.__fields__['items'].default_factory).__name__}")


row("base_vars: 'set_default copies a mutable default when set + per instance; later changes do not reach it'", copies_mutable)


def no_check():
    class NC(rx.State):
        n: int = 0

    NC.__fields__["n"].set_default("not-an-int")
    return f"int var given str -> instance {inst(NC).n!r}"


row("base_vars: 'does not check the value against the var's annotation'", no_check)


def storage_statements():
    class SS1(rx.State):
        theme: str = rx.LocalStorage("light", name="theme", sync=True)
        plain: str = rx.LocalStorage("light", name="plain_k")
        ann: rx.LocalStorage = rx.LocalStorage("light", name="ann_k")

    SS1.__fields__["theme"].set_default(rx.LocalStorage("dark", name="theme", sync=True))
    SS1.__fields__["plain"].set_default("dark")
    SS1.__fields__["ann"].set_default("dark")
    return (f"storage value keeps name/options={entry(SS1, 'theme')} | str-annotated + plain str -> {entry(SS1, 'plain')} (ordinary var) "
            f"| storage-annotated + plain str -> {entry(SS1, 'ann')} (default key) ; instances theme={inst(SS1).theme!r} ann={inst(SS1).ann!r}")


row("base_vars: storage statements", storage_statements)


def inherited():
    class P(rx.State):
        x: int = 1

    class C(P):
        y: int = 0

    C.__fields__["x"].set_default(7)  # through the substate's mapping: it is P's field
    a = (C.__fields__["x"] is P.__fields__["x"], inst(P).x, inst(C).x)
    P.__fields__["x"].set_default(5)
    return f"C.__fields__['x'] is P's={a[0]}; via C: P={a[1]} C={a[2]}; via P: C={inst(C).x}"


row("base_vars: 'inherited var ... changing its field also changes the default for every state that inherits it'", inherited)


def patch_sample():
    with mock.patch.object(WatchlistState.__fields__["ticker"], "default", "MSFT"):
        during = inst(WatchlistState).ticker
    with mock.patch.object(WatchlistState.__fields__["symbols"], "default", ["P"]):
        d2 = list(inst(WatchlistState).symbols)
    return f"ticker during={during}; symbols(default patched over set_default factory) during={d2} after={list(inst(WatchlistState).symbols)}"


row("base_vars: 'In tests, patch the field' sample", patch_sample)


class MyState(rx.State):
    _endpoint: ClassVar[str] = "https://example.com/api"
    _token: str = ""
    _options: list[str] = ["a", "b"]


MyState._endpoint = "https://example.com/v2"


def backend_rows():
    out = [f"MyState._token is {type(MyState._token).__name__}"]
    try:
        MyState._token = "x"
        out.append("MyState._token='x' accepted")
    except TypeError as e:
        out.append(f"MyState._token='x' TypeError: {e}")
    out.append(f"ClassVar -> {MyState._endpoint} instance sees {inst(MyState)._endpoint}")
    fe = rx.foreach(MyState._options.default_value(), rx.text)
    d1, d2 = MyState._options.default_value(), MyState._options.default_value()
    out.append(f"foreach(default_value()) {type(fe).__name__}; fresh copy each call={d1 is not d2}")
    return "; ".join(out)


row("base_vars: backend vars + ClassVar sample (verbatim)", backend_rows)


def classvar_lock_shared():
    import threading

    class CL(rx.State):
        _lock: ClassVar[threading.Lock] = threading.Lock()

    return f"ClassVar lock: class read is plain={type(CL._lock).__name__} instances share={inst(CL)._lock is inst(CL)._lock is CL._lock}"


row("base_vars: 'ClassVar ... object that cannot be copied ... is shared'", classvar_lock_shared)


def backend_demo():
    import numpy as np

    class BackendVarState(rx.State):
        _backend: np.ndarray = np.array([random.randint(0, 100) for _ in range(100)])
        offset: int = 0
        limit: int = 10

        @rx.var(cache=True)
        def page(self) -> list[int]:
            return [int(x) for x in self._backend[self.offset : self.offset + self.limit]]

        @rx.event
        def generate_more(self):
            self._backend = np.append(self._backend, [random.randint(0, 100) for _ in range(random.randint(0, 100))])

    a, b = inst(BackendVarState), inst(BackendVarState)
    a._backend[0] = -1
    a.generate_more()
    return f"page len={len(a.page)}; instances share array={b._backend[0] == -1}; a len={len(a._backend)}"


row("base_vars: BackendVarState demo (numpy)", backend_demo)


def rx_field_samples():
    class FState(rx.State):
        x: rx.Field[bool] = rx.field(False)

        def flip(self):
            self.x = not self.x

    class DState(rx.State):
        x: rx.Field[dict[str, list[int]]] = rx.field(default_factory=dict)

    c = rx.vstack(rx.button("Click me", on_click=FState.flip), rx.text(FState.x), rx.text(~FState.x), rx.text(DState.x.values()[0][0]))
    s = inst(FState)
    s.flip()
    return f"components ok ({type(c).__name__}); flip -> {s.x}; dict default={inst(DState).x!r}"


row("base_vars: rx.field / rx.Field samples", rx_field_samples)


# ---- component_state.md, verbatim
class EditableText(rx.ComponentState):
    text: str = "Click to edit"
    original_text: str
    editing: bool = False

    @rx.event
    def set_text(self, value: str):
        self.text = value

    @rx.event
    def start_editing(self, original_text: str):
        self.original_text = original_text
        self.editing = True

    @rx.event
    def stop_editing(self):
        self.editing = False
        self.original_text = ""

    @classmethod
    def get_component(cls, **props):
        value = props.pop("value", cls.text)
        on_change = props.pop("on_change", cls.set_text)
        cursor = props.pop("cursor", "pointer")
        initial_value = props.pop("initial_value", None)
        if initial_value is not None:
            cls.__fields__["text"].set_default(initial_value)
        edit_controls = rx.hstack(
            rx.input(value=value, on_change=on_change, **props),
            rx.icon_button(rx.icon("x"), on_click=[on_change(cls.original_text), cls.stop_editing], type="button", color_scheme="red"),
            rx.icon_button(rx.icon("check")),
            align="center",
            width="100%",
        )
        return rx.cond(
            cls.editing,
            rx.form(edit_controls, on_submit=lambda _: cls.stop_editing()),
            rx.text(value, on_click=cls.start_editing(value), cursor=cursor, **props),
        )


editable_text = EditableText.create


def editable():
    comps = [editable_text(), editable_text(initial_value="Edit me!", color="blue"),
             editable_text(initial_value="Reflex is fun", font_family="monospace", width="100%")]
    vals = [inst(c.State).text for c in comps]
    s = inst(comps[1].State)
    s.set_text("changed")
    s.reset()
    try:
        comps[1].State.text = "x"
        assign = "accepted"
    except TypeError as e:
        assign = f"TypeError: {e}"
    return f"defaults={vals} template={EditableText.__fields__['text'].default!r} reset->{s.text!r} | cls.text=... -> {assign}"


row("component_state: EditableText sample + statements", editable)


class ThemeToggle(rx.ComponentState):
    theme: str = rx.LocalStorage("light", name="theme")

    @classmethod
    def get_component(cls, key: str, initial: str = "light", **props):
        cls.__fields__["theme"].set_default(
            rx.LocalStorage(initial, name=f"theme_{key}")
        )
        return rx.text(cls.theme, **props)


class NamedShared(rx.ComponentState):
    theme: str = rx.LocalStorage("light", name="shared_theme")

    @classmethod
    def get_component(cls, **props):
        return rx.text(cls.theme)


class Unnamed(rx.ComponentState):
    theme: str = rx.LocalStorage("light")

    @classmethod
    def get_component(cls, **props):
        return rx.text(cls.theme)


def theme_toggle():
    a, b, c = ThemeToggle.create(key="a"), ThemeToggle.create(key="b", initial="dark"), ThemeToggle.create(key="a")
    n1, n2 = NamedShared.create(), NamedShared.create()
    u1, u2 = Unnamed.create(), Unnamed.create()
    return (f"ThemeToggle a={entry(a.State, 'theme')} b={entry(b.State, 'theme')} (b default {inst(b.State).theme!r}) a-again={entry(c.State, 'theme')} "
            f"| named shared={entry(n1.State, 'theme')}/{entry(n2.State, 'theme')} | unnamed={entry(u1.State, 'theme')} vs {entry(u2.State, 'theme')}")


row("component_state: ThemeToggle sample + storage key statements", theme_toggle)


# ---- upgrading-to-0-10.md, verbatim
def upgrade_sample():
    import httpx

    class State(rx.State):
        count: int = 0
        _client: ClassVar[httpx.AsyncClient | None] = None

    State.__fields__["count"].set_default(10)
    State._client = httpx.AsyncClient()  # a ClassVar stays an ordinary class attribute

    with mock.patch.object(State.__fields__["count"], "default", 99):
        during = inst(State).count
    return f"count default={inst(State).count} during patch={during} client={type(State._client).__name__}"


row("upgrade guide: 'Assigning a state var through its class' sample", upgrade_sample)


def upgrade_items_trap():
    class TrapState(rx.State):
        items: list[str] = []

    fields = TrapState.__fields__ if hasattr(TrapState, "__fields__") else TrapState.get_fields()
    fields["items"].default = []  # the 0.9 idiom
    a, b = inst(TrapState), inst(TrapState)
    a.items.append("leak")
    shared = list(b.items) == ["leak"]
    c = inst(TrapState)
    out = f".default = [] -> instances share (leak to new instance)={shared}, new instance={list(c.items)}"
    if hasattr(fields["items"], "set_default"):
        fields["items"].set_default(default=[])
        a, b = inst(TrapState), inst(TrapState)
        a.items.append("x")
        out += f" | set_default(default=[]) -> b={list(b.items)}"
    return out


row("upgrade guide: 'On 0.9 .default = [] was safe / 0.10 shares / set_default copies'", upgrade_items_trap)


def upgrade_foreach_sample():
    class State2(rx.State):
        _items: list[str] = ["a", "b"]
        _endpoint: ClassVar[str] = "https://example.com/api"

    page = rx.vstack(rx.foreach(State2._items.default_value(), rx.text), rx.text(State2._endpoint))
    return f"ok {type(page).__name__}; get_fields form={State2.get_fields()['_items'].default_value()}"


row("upgrade guide: backend var default_value() sample", upgrade_foreach_sample)


def news_example():
    class NState(rx.State):
        items: list[str] = []
        count: int = 0

    NState.__fields__["items"].set_default(["a"])
    NState.__fields__["count"].set_default(10)
    a, b = inst(NState), inst(NState)
    a.items.append("z")
    return f"items={list(b.items)} count={b.count}"


row("news/CHANGELOG: State.__fields__['items'].set_default(['a']) / ['count'].set_default(10)", news_example)
