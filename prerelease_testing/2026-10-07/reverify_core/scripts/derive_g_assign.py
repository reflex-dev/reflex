"""#7461 re-verification: assigning through a state class updates a declared field's default.

Usage: REFLEX_ENV_MODE=dev|prod <venv>/bin/python derive_g_assign.py <expected-venv-name>
"""

import dataclasses
import datetime
import os
import pickle
import sys
from typing import Any, Callable, Literal

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

print(f"reflex {version('reflex')}  REFLEX_ENV_MODE={os.environ.get('REFLEX_ENV_MODE', '<unset>')}")


def t(label, fn):
    try:
        r = fn()
        s = r if isinstance(r, str) else repr(r)
        print(f"{label:66} -> {s}"[:300])
    except Exception as e:  # noqa: BLE001
        print(f"{label:66} -> EXC {type(e).__name__}: {str(e)[:230]}")


def fresh(cls):
    return rx.State(_reflex_internal_init=True).get_substate(cls.get_full_name().split(".")[1:])


@dataclasses.dataclass
class Pt:
    x: int = 0


class Other(rx.State):
    o: int = 3


CALLS = {"n": 0}


def items_factory():
    CALLS["n"] += 1
    return ["from-factory"]


class A(rx.State):
    count: int = 0
    ratio: float = 0.5
    items: list[str] = []
    nums: list[int] = []
    mapping: dict[str, int] = {}
    mode: Literal["a", "b"] = "a"
    when: datetime.datetime | None = None
    pt: Pt = Pt()
    opt: str | None = None
    _k: str | None = None
    _fn: Any = None
    _cb: Callable[[], int] | None = None
    text: str = ""

    @rx.var
    def doubled(self) -> int:
        return self.count * 2


print("--- frontend var default")
A.count = 10
t("A.count = 10 -> type(A.count) (still a Var for the UI?)", lambda: type(A.count).__name__)
t("   fresh(A).count", lambda: fresh(A).count)
t("   fresh(A).doubled", lambda: fresh(A).doubled)
t("   A.dict(initial=True) count", lambda: next(v for k, v in fresh(A).dict(initial=True)[A.get_full_name()].items() if k.startswith("count")))
t("   rx.text(A.count) renders a var", lambda: str(rx.text(A.count))[:80])
print("--- type validation")
t('A.count = "ten"', lambda: setattr(A, "count", "ten"))
t("   default after rejected assignment", lambda: fresh(A).count)
t("A.count = True (bool is an int subclass)", lambda: (setattr(A, "count", True), fresh(A).count)[1])
A.count = 10
t("A.ratio = 1 (int to float var)", lambda: (setattr(A, "ratio", 1), fresh(A).ratio)[1])
t('A.nums = ["x"] (wrong element type)', lambda: (setattr(A, "nums", ["x"]), fresh(A).nums)[1])
t('A.mapping = {"a": "b"} (wrong value type)', lambda: (setattr(A, "mapping", {"a": "b"}), fresh(A).mapping)[1])
t('A.mode = "c" (outside Literal)', lambda: (setattr(A, "mode", "c"), fresh(A).mode)[1])
t('A.mode = "b"', lambda: (setattr(A, "mode", "b"), fresh(A).mode)[1])
t("A.when = datetime(2026,1,1)", lambda: (setattr(A, "when", datetime.datetime(2026, 1, 1)), fresh(A).when)[1])
t("A.pt = Pt(5) (dataclass)", lambda: (setattr(A, "pt", Pt(5)), fresh(A).pt)[1])
t("A.opt = None", lambda: (setattr(A, "opt", None), fresh(A).opt)[1])
t('A._k = "sk" (backend)', lambda: (setattr(A, "_k", "sk"), fresh(A)._k)[1])
t("A._k = 5 (backend wrong type)", lambda: setattr(A, "_k", 5))
print("--- Field / Var rejection")
t("A.count = rx.field(5)", lambda: setattr(A, "count", rx.field(5)))
t("A.count = rx.Var.create(5)", lambda: setattr(A, "count", rx.Var.create(5)))
t("A.count = Other.o (another state's var)", lambda: setattr(A, "count", Other.o))
t("A._k = A._k (its own Field read on the class)", lambda: setattr(A, "_k", A._k))
t("   A still works: fresh(A).count / _k", lambda: (fresh(A).count, fresh(A)._k))
print("--- factories")
CALLS["n"] = 0
t("A.items = items_factory", lambda: (setattr(A, "items", items_factory), CALLS["n"])[1])
t("   calls after assignment (validated once)", lambda: CALLS["n"])
t("   get_fields()['items'] default / factory", lambda: (A.get_fields()["items"].default, A.get_fields()["items"].default_factory))
i1, i2 = fresh(A), fresh(A)
t("   two fresh instances", lambda: (i1.items, i2.items, CALLS["n"]))
i1.items.append("mut")
t("   mutation on one does not leak", lambda: (i1.items, i2.items, fresh(A).items))
i1.reset()
t("   reset() calls the factory again", lambda: (i1.items, CALLS["n"]))
t("A.items = lambda: 1/0 (raising factory)", lambda: setattr(A, "items", lambda: 1 / 0))
t("   previous factory kept", lambda: fresh(A).items)
t("A.items = lambda: 5 (factory with wrong type)", lambda: setattr(A, "items", lambda: 5))
t("   previous factory kept", lambda: fresh(A).items)
t("A.count = lambda x: 1 (one-arg callable)", lambda: setattr(A, "count", lambda x: 1))
t("A._fn = len (Any accepts callables: stored as-is)", lambda: (setattr(A, "_fn", len), fresh(A)._fn)[1])
t("A._cb = lambda: 7 (Callable annotation accepts it)", lambda: (setattr(A, "_cb", lambda: 7), fresh(A)._cb())[1])
t("A.text = str.upper (unbound 1-arg builtin)", lambda: setattr(A, "text", str.upper))
t("A.text = dict (a type: zero-arg callable)", lambda: setattr(A, "text", dict))
t("A.text = str (type str: zero-arg callable -> '')", lambda: (setattr(A, "text", str), repr(fresh(A).text), A.get_fields()["text"].default_factory)[1:])
print("--- mutable default copy and proxy unwrap")
A.items = ["x", "y"]
j1, j2 = fresh(A), fresh(A)
j1.items.append("z")
t("A.items = [x,y]; j1 mutates -> j2 / fresh / class default", lambda: (j2.items, fresh(A).items, A.get_fields()["items"].default_value()))
A.items = j1.items  # a MutableProxy from an instance
t("A.items = j1.items (MutableProxy) -> stored type", lambda: type(A.get_fields()["items"].default_factory.args[0] if A.get_fields()["items"].default_factory else A.get_fields()["items"].default).__name__)
print("--- pickle / reset keep the configured default")


class PK(rx.State):
    count: int = 0
    _k: str | None = None
    items: list[str] = []


PK.count = 10
PK._k = "sk"
PK.items = items_factory
k = fresh(PK)
t("pickle round trip of fresh(PK) (count/_k/items configured on class)", lambda: (lambda b: (b.count, b._k, b.items))(pickle.loads(pickle.dumps(k))))
t("state._serialize/_deserialize round trip", lambda: (lambda b: (b.count, b._k, b.items))(type(k)._deserialize(k._serialize())))
k = fresh(A)
k.count = 99
k.reset()
t("reset() -> count back to configured 10", lambda: k.count)
print("--- inheritance / mixins")


class P(rx.State):
    pv: int = 1


class C1(P):
    pass


class C2(P):
    pass


C1.pv = 5
t("C1.pv = 5 -> fresh(P).pv / fresh(C2).pv (documented: declaring state changes)", lambda: (fresh(P).pv, fresh(C2).pv))


class Mx(rx.State, mixin=True):
    mv: int = 1
    _mbe: int = 1


class U1(Mx, rx.State):
    pass


class U2(Mx, rx.State):
    pass


U1.mv = 5
U1._mbe = 6
t("U1.mv=5, U1._mbe=6 -> U1 / U2 fresh", lambda: ((fresh(U1).mv, fresh(U1)._mbe), (fresh(U2).mv, fresh(U2)._mbe)))
t("Mx.mv = 7 (on the mixin itself)", lambda: setattr(Mx, "mv", 7))


class U3(Mx, rx.State):
    pass


t("   U1 / U2 / U3 (created after) fresh mv", lambda: (fresh(U1).mv, fresh(U2).mv, fresh(U3).mv))
print("--- computed var / event handler (not fields)")


class Q(rx.State):
    n: int = 1

    @rx.var
    def cv(self) -> int:
        return self.n + 1

    @rx.event
    def h(self):
        pass


t("Q.cv = 5 (computed var: not a field)", lambda: (setattr(Q, "cv", 5), type(Q.__dict__["cv"]).__name__)[1])
t("   fresh(Q).cv afterwards", lambda: fresh(Q).cv)
print("--- client storage classification after assignment")


class St(rx.State):
    ls_plain: str = rx.LocalStorage("ls-default", name="ls_plain_key")
    ls_fac_assigned: str = rx.LocalStorage("x", name="ls_fac_key")
    ls_fac_plain: str = rx.LocalStorage("y", name="ls_facplain_key")
    ls_inst: str = rx.LocalStorage("z", name="ls_inst_key")
    ck: str = rx.Cookie("ck-default", name="ck_key", max_age=3600)
    ls_declared_fac: rx.LocalStorage = rx.field(default_factory=lambda: rx.LocalStorage("decl-fac", name="decl_fac_key", sync=True))


St.ls_plain = "assigned-plain-str"
St.ls_fac_assigned = lambda: rx.LocalStorage("from-factory", name="ls_fac_key2", sync=True)
St.ls_fac_plain = lambda: "factory-plain-str"
St.ls_inst = rx.LocalStorage("inst-new", name="ls_inst_key2")
St.ck = "assigned-cookie-plain"
for n in ["ls_plain", "ls_fac_assigned", "ls_fac_plain", "ls_inst", "ck", "ls_declared_fac"]:
    fld = St.get_fields()[n]
    t(f"St.{n}: is_client_storage / default", lambda: (St._is_client_storage(n), fld.default if fld.default is not dataclasses.MISSING else "factory:" + repr(fld.default_value())))
try:
    from reflex.compiler.utils import _compile_client_storage_recursive

    ck_, ls_, ss_ = _compile_client_storage_recursive(St)
    print("   compiled cookies:", ck_)
    print("   compiled local_storage:", ls_)
except Exception as e:  # noqa: BLE001
    print("   compile storage EXC", type(e).__name__, e)
