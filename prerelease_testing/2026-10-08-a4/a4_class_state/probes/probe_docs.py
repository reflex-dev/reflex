"""Docs samples / statements of v0.10.0a4 (base_vars.md "Changing Defaults" + backend vars + ClassVar, component_state.md,
upgrading-to-0-10.md "Assigning a state var through its class", CHANGELOG #7461/#7516), run as written where possible.
Run: EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_docs.py   (0.9.12 rows that use __fields__ use get_fields())"""
import os
import random  # noqa: F401  (the BackendVarState demo uses it from the docs page context)
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
        r = f"EXC {type(e).__name__}: {str(e)[:160]}"
    print(f"ROW {name} | {r}")


def inst(cls):
    return cls(_reflex_internal_init=True)


def entry(cls, name):
    for kind, d in zip(("cookie", "local", "session"), _compile_client_storage_recursive(cls)):
        for k, v in d.items():
            if k.rsplit(".", 1)[-1].split("_rx_state_")[0] == name:
                return (kind, v)
    return None


# base_vars.md "Changing Defaults" sample, as written
class WatchlistState(rx.State):
    ticker: str = "AAPL"
    symbols: list[str] = []


def watchlist():
    WatchlistState.__fields__["ticker"].default = "MSFT"
    WatchlistState.__fields__["symbols"].default_factory = lambda: ["AAPL", "MSFT"]
    a, b = inst(WatchlistState), inst(WatchlistState)
    a.symbols.append("X")
    a.ticker = "Z"
    a.reset()
    return f"new={b.ticker},{list(b.symbols)} reset={a.ticker},{list(a.symbols)} independent={list(b.symbols) == ['AAPL', 'MSFT']}"


row("base_vars: WatchlistState sample", watchlist)


def watch_patch():
    with mock.patch.object(WatchlistState.__fields__["ticker"], "default", "MSFT"):
        during = inst(WatchlistState).ticker
    return f"during={during} after={inst(WatchlistState).ticker}"


row("base_vars: mock.patch.object(field, 'default') sample", watch_patch)


def factory_ignored_when_default():
    class Q(rx.State):
        t: str = "A"

    Q.__fields__["t"].default_factory = lambda: "F"
    return f"str var with default + factory -> {inst(Q).t!r} (docs: default wins)"


row("base_vars: 'uses its default when one is set'", factory_ignored_when_default)


def no_annotation_check():
    class Q(rx.State):
        n: int = 0

    Q.__fields__["n"].default = "not-an-int"
    return f"int var given str default -> instance {inst(Q).n!r} (docs: field does not check)"


row("base_vars: 'does not check the value against the annotation'", no_annotation_check)


def inherited_field_shared():
    class P(rx.State):
        x: int = 1

    class C(P):
        pass

    P.__fields__["x"].default = 5
    return f"C.__fields__['x'] is P's={C.__fields__['x'] is P.__fields__['x']} inst(C).x={inst(C).x}"


row("base_vars: inherited var default changes for every inheriting state", inherited_field_shared)


# backend vars section
class MyState(rx.State):
    _endpoint: ClassVar[str] = "https://example.com/api"
    _token: str = ""
    _options: list[str] = ["a", "b"]


def backend_rows():
    out = [f"MyState._token is {type(MyState._token).__name__}"]
    try:
        MyState._token = "x"
        out.append("MyState._token='x' accepted")
    except TypeError:
        out.append("MyState._token='x' TypeError")
    MyState._endpoint = "https://example.com/v2"
    out.append(f"ClassVar set -> {MyState._endpoint} instance sees {inst(MyState)._endpoint}")
    fe = rx.foreach(MyState._options.default_value(), rx.text)
    d1, d2 = MyState._options.default_value(), MyState._options.default_value()
    out.append(f"foreach(default_value()) ok={type(fe).__name__}; default_value fresh copy={d1 is not d2}")
    return "; ".join(out)


row("base_vars: backend vars + ClassVar sample", backend_rows)


def backend_demo():
    import numpy as np

    class BackendVarState(rx.State):
        _backend: np.ndarray = np.array([random.randint(0, 100) for _ in range(100)])
        offset: int = 0
        limit: int = 10

        @rx.var(cache=True)
        def page(self) -> list[int]:
            return [int(x) for x in self._backend[self.offset : self.offset + self.limit]]

    a, b = inst(BackendVarState), inst(BackendVarState)
    a._backend[0] = -1
    return f"demo state ok; page len={len(a.page)}; instances share array={b._backend[0] == -1}"


row("base_vars: BackendVarState demo (numpy)", backend_demo)


# component_state.md: unnamed storage var gets a per-component key
class Unnamed(rx.ComponentState):
    theme: str = rx.LocalStorage("light")

    @classmethod
    def get_component(cls, **props):
        return rx.text(cls.theme)


def unnamed_keys():
    a, b = Unnamed.create(), Unnamed.create()
    return f"keys a={entry(a.State, 'theme')} b={entry(b.State, 'theme')}"


row("component_state: unnamed storage var -> own key per component", unnamed_keys)


# upgrading-to-0-10.md sample, as written (class named State)
def upgrade_sample():
    import httpx

    class State(rx.State):
        count: int = 0
        _client: ClassVar[httpx.AsyncClient | None] = None

    State.__fields__["count"].default = 10
    State._client = httpx.AsyncClient()  # a ClassVar stays an ordinary class attribute

    with mock.patch.object(State.__fields__["count"], "default", 99):
        during = inst(State).count
    return f"count default={inst(State).count} during patch={during} client={type(State._client).__name__} instance client is class client={inst(State)._client is State._client}"


row("upgrade guide: 'Assigning a state var through its class' sample", upgrade_sample)


# CHANGELOG #7461 (a4 wording): storage-annotated var declared with a default_factory
class FacSt(rx.State):
    v: rx.Field[rx.LocalStorage] = rx.field(default_factory=lambda: rx.LocalStorage("fx", name="k_fac", sync=True))


def changelog_7461():
    s = inst(FacSt)
    s.v = "changed"
    s.reset()
    return f"compiled={entry(FacSt, 'v')} reset->{s.v!r}"


row("CHANGELOG #7461: rx.Field[rx.LocalStorage] + default_factory", changelog_7461)
