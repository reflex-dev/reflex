"""Offline probe: browser-storage declaration shapes (#7582). Run: cd probes && $SB/envs/<venv>/bin/python -I storage_decl_probe.py <venv>"""
import sys
from typing import Annotated, Any, Literal, Optional

import pydantic
import reflex as rx
from reflex.compiler.utils import compile_client_storage

venv = sys.argv[1]
assert f"/envs/{venv}/" in rx.__file__, rx.__file__

CALLS = {"n": 0}


def counting_factory():
    CALLS["n"] += 1
    return f"plain-{CALLS['n']}"


def raising_factory():
    msg = "only works at runtime"
    raise RuntimeError(msg)


def shape(label, body_fn):
    """Define a State with one var, compile its client storage, report."""
    try:
        cls = body_fn()
    except Exception as e:  # noqa: BLE001
        print(f"[DEFINE-ERR] {label}: {type(e).__name__}: {str(e)[:300]}")
        return
    try:
        cs = compile_client_storage(cls)
        kinds = {k: {n.split(".")[-1]: o for n, o in v.items()} for k, v in cs.items() if v}
    except Exception as e:  # noqa: BLE001
        print(f"[COMPILE-ERR] {label}: {type(e).__name__}: {str(e)[:400]}")
        return
    try:
        inst = cls(_reflex_internal_init=True)
        names = [n for n in cls.__fields__ if n in ("x", "y", "_x")]
        vals = {n: (type(getattr(inst, n)).__name__, getattr(inst, n)) for n in names}
    except Exception as e:  # noqa: BLE001
        vals = f"<instance error {type(e).__name__}: {str(e)[:120]}>"
    print(f"[ok] {label}: storage={kinds or 'NONE (ordinary var)'} value={vals}")


import itertools

_n = itertools.count(1)


def mk(ns_fn, bases=(rx.State,)):
    def build():
        return type(rx.State)(f"T{next(_n)}", bases, ns_fn())
    return build


def decl(label, annotations, **defaults):
    def ns():
        d = {"__annotations__": dict(annotations), "__module__": __name__, "__qualname__": "T"}
        d.update(defaults)
        return d
    shape(label, mk(ns))


LS, CK, SS = rx.LocalStorage, rx.Cookie, rx.SessionStorage
decl("x: str = rx.LocalStorage('a')", {"x": str}, x=LS("a"))
decl("x: rx.LocalStorage = rx.LocalStorage('a')", {"x": LS}, x=LS("a"))
decl("x: str = rx.Cookie('c', max_age=60, path='/p')", {"x": str}, x=CK("c", max_age=60, path="/p"))
decl("x: rx.Cookie = rx.Cookie()", {"x": CK}, x=CK())
decl("x: str = rx.SessionStorage('s')", {"x": str}, x=SS("s"))
decl("x: rx.LocalStorage  (annotation only)", {"x": LS})
decl("x: rx.LocalStorage = 'plain str default'", {"x": LS}, x="plain")
decl("x: str = rx.field(rx.LocalStorage('a'))", {"x": str}, x=rx.field(LS("a")))
decl("x: rx.Field[str] = rx.field(rx.LocalStorage('a'))", {"x": rx.Field[str]}, x=rx.field(LS("a")))
decl("x: Annotated[str, 'meta'] = rx.LocalStorage('a')", {"x": Annotated[str, "meta"]}, x=LS("a"))
decl("x: str | None = rx.LocalStorage('a')", {"x": Optional[str]}, x=LS("a"))
decl("x: int = rx.LocalStorage('5')", {"x": int}, x=LS("5"))
decl("x: set[str] = rx.LocalStorage('a')", {"x": set[str]}, x=LS("a"))
decl("x: list[str] = rx.LocalStorage('[]')", {"x": list[str]}, x=LS("[]"))
decl("x: str = rx.LocalStorage('a', name='k', sync=True)", {"x": str}, x=LS("a", name="k", sync=True))
print("--- default_factory shapes (0.11: storage ones must fail at compile)")
decl("x: str = rx.field(default_factory=lambda: rx.LocalStorage('a'))", {"x": str}, x=rx.field(default_factory=lambda: LS("a")))
decl("x: rx.LocalStorage = rx.field(default_factory=lambda: rx.LocalStorage('a'))", {"x": LS}, x=rx.field(default_factory=lambda: LS("a")))
decl("x: rx.LocalStorage = rx.field(default_factory=rx.LocalStorage)", {"x": LS}, x=rx.field(default_factory=LS))
decl("x: rx.LocalStorage = rx.field(default_factory=lambda: 'plain')", {"x": LS}, x=rx.field(default_factory=lambda: "plain"))
decl("x: str = rx.field(default_factory=lambda: rx.Cookie('c'))", {"x": str}, x=rx.field(default_factory=lambda: CK("c")))
decl("x: str = rx.field(default_factory=lambda: rx.SessionStorage('s'))", {"x": str}, x=rx.field(default_factory=lambda: SS("s")))
decl("x: str | None = rx.field(default_factory=lambda: rx.LocalStorage('a'))", {"x": Optional[str]}, x=rx.field(default_factory=lambda: LS("a")))
decl("x: Any = rx.field(default_factory=lambda: rx.LocalStorage('a'))", {"x": Any}, x=rx.field(default_factory=lambda: LS("a")))
decl("x: Literal['a','b'] = rx.field(default_factory=lambda: rx.LocalStorage('a'))", {"x": Literal["a", "b"]}, x=rx.field(default_factory=lambda: LS("a")))
decl("x: Annotated[str,'m'] = rx.field(default_factory=lambda: rx.LocalStorage('a'))", {"x": Annotated[str, "m"]}, x=rx.field(default_factory=lambda: LS("a")))
decl("x: int = rx.field(default_factory=lambda: rx.LocalStorage('5'))", {"x": int}, x=rx.field(default_factory=lambda: LS("5")))
decl("x: list[str] = rx.field(default_factory=lambda: rx.LocalStorage('[]'))", {"x": list[str]}, x=rx.field(default_factory=lambda: LS("[]")))
decl("_x: str = rx.field(default_factory=lambda: rx.LocalStorage('a'))  [backend var]", {"_x": str}, _x=rx.field(default_factory=lambda: LS("a")))
decl("x: str = rx.field(default_factory=<plain str factory>)", {"x": str}, x=rx.field(default_factory=counting_factory))
print("    plain factory calls so far (compile + instance):", CALLS["n"])
decl("x: str = rx.field(default_factory=<factory that raises>)", {"x": str}, x=rx.field(default_factory=raising_factory))
decl("x: str = pydantic.Field(default_factory=lambda: rx.LocalStorage('a'))", {"x": str}, x=pydantic.Field(default_factory=lambda: LS("a")))
decl("x: str = pydantic.Field(default=rx.LocalStorage('a'))", {"x": str}, x=pydantic.Field(default=LS("a")))
print("--- inheritance / mixin / ComponentState")


def inherited():
    class Base(rx.State):
        x: str = rx.field(default_factory=lambda: LS("a"))

    class Child(Base):
        y: str = LS("child")

    return Base


shape("factory storage on a parent state, storage on child", inherited)


def mixin():
    class M(rx.State, mixin=True):
        x: str = LS("mixed", name="mx")

    class UsesM(M, rx.State):
        pass

    return UsesM


shape("mixin with LocalStorage default", mixin)


def mixin_factory():
    class M2(rx.State, mixin=True):
        x: str = rx.field(default_factory=lambda: LS("mixed"))

    class UsesM2(M2, rx.State):
        pass

    return UsesM2


shape("mixin with factory storage", mixin_factory)


def cstate():
    class CS(rx.ComponentState):
        x: str = rx.field(default_factory=lambda: LS("a"))

        @classmethod
        def get_component(cls, **props):
            return rx.text(cls.x)

    CS.create()
    return CS


shape("ComponentState with factory storage (compile parent)", cstate)
