"""#7465 re-verification: double-underscore (name-mangled / dunder) attributes on states.

Usage: REFLEX_ENV_MODE=dev|prod <venv>/bin/python derive_f_dunder.py <expected-venv-name>
"""

import os
import pickle
import sys
from typing import ClassVar

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

print(f"reflex {version('reflex')}  REFLEX_ENV_MODE={os.environ.get('REFLEX_ENV_MODE', '<unset>')}")


class Params:
    @classmethod
    def from_request(cls, x):
        return f"Params.from_request({x})"


class Params2(Params):
    @classmethod
    def from_request(cls, x):
        return f"Params2.from_request({x})"


class Mx(rx.State, mixin=True):
    __mx = 0  # mangled to _Mx__mx

    @rx.event
    def bump_mx(self):
        self.__mx += 1  # -> self._Mx__mx

    def get_mx(self):
        return self.__mx


class D(Mx, rx.State):
    __counter = 0  # mangled _D__counter, unannotated
    __ann_plain: int = 5  # annotated, no rx.field -> plain per news
    __dunder_thing__ = "dunder-value"
    __data_source_params_class__: type[Params] = Params  # enterprise-style annotated dunder
    __fielded: rx.Field[int] = rx.field(0)  # explicit -> real backend var _D__fielded
    _single__mid: int = 7  # single leading underscore, '__' in the middle: regular backend var?
    shown: str = ""

    @rx.event
    def bump(self):
        self.__counter += 1

    @rx.event
    def bump_fielded(self):
        self.__fielded += 1

    def get_counter(self):
        return self.__counter

    def get_fielded(self):
        return self.__fielded

    @rx.var
    def counter_view(self) -> int:
        return self.__counter

    @rx.var
    def fielded_view(self) -> int:
        return self.__fielded


class Sub(D):
    __data_source_params_class__ = Params2  # override in a substate


class _Under(rx.State):  # class name starting with an underscore
    __u = 1

    def set_u(self, v):
        self.__u = v

    def get_u(self):
        return self.__u


class Base2(rx.State):
    def write_private(self):
        self.__from_base = "base-wrote"  # mangled _Base2__from_base, never declared anywhere


class Child2(Base2):
    pass


def t(label, fn):
    try:
        r = fn()
        print(f"{label:62} -> {r!r}"[:260])
    except Exception as e:  # noqa: BLE001
        print(f"{label:62} -> EXC {type(e).__name__}: {str(e)[:220]}")


f = D.get_fields()
print("--- classification")
for n in ["_D__counter", "_D__ann_plain", "__dunder_thing__", "__data_source_params_class__", "_D__fielded", "_single__mid", "_Mx__mx", "shown"]:
    print(f"  {n:30} in get_fields(): {n in f!s:5} | backend: {getattr(f.get(n), '_backend', '-')!s:5} | in D.vars: {n in D.vars}")
print("--- class access")
t("D._D__counter", lambda: D._D__counter)
t("D._D__ann_plain", lambda: D._D__ann_plain)
t("D.__dunder_thing__", lambda: D.__dunder_thing__)
t("D.__data_source_params_class__.from_request(1)", lambda: D.__data_source_params_class__.from_request(1))
t("Sub.__data_source_params_class__.from_request(1)", lambda: Sub.__data_source_params_class__.from_request(1))
t("D._D__fielded (explicit field)", lambda: D._D__fielded)
t("D._single__mid", lambda: D._single__mid)
t("Mx._Mx__mx / D._Mx__mx", lambda: (Mx._Mx__mx, D._Mx__mx))
t("_Under._Under__u", lambda: _Under._Under__u)
root = rx.State(_reflex_internal_init=True)
d = root.get_substate(D.get_full_name().split(".")[1:])
sub = root.get_substate(Sub.get_full_name().split(".")[1:])
u = root.get_substate(_Under.get_full_name().split(".")[1:])
c2 = root.get_substate(Child2.get_full_name().split(".")[1:])
print("--- instance writes (dev guard)")
t("d.bump() -> d.get_counter()", lambda: (D.bump.fn(d), d.get_counter())[1])
t("   dirty_vars after bump", lambda: sorted(d.dirty_vars))
t("   D._D__counter class value unchanged", lambda: D._D__counter)
t("   counter_view (computed, should NOT react)", lambda: d.counter_view)
d._clean() if hasattr(d, "_clean") else None
t("d.bump_mx() (mixin-mangled name) -> d.get_mx()", lambda: (D.bump_mx.fn(d), d.get_mx())[1])
t("u.set_u(5) (class name starts with _) -> u.get_u()", lambda: (_Under.set_u.fn(u, 5), _Under.get_u.fn(u))[1])
t("Base2.write_private on a Child2 instance (mangled by a base)", lambda: (Base2.write_private.fn(c2), c2._Base2__from_base)[1])
t("d.__dunder_thing__ = 'x' on instance", lambda: (setattr(d, "__dunder_thing__", "inst"), d.__dunder_thing__)[1])
t("d._D__typo__x = 1 (undeclared, contains __)", lambda: (setattr(d, "_D__typo__x", 1), "accepted")[1])
t("d._typo_x = 1 (undeclared, control)", lambda: (setattr(d, "_typo_x", 1), "accepted")[1])
t("d._sneaky__name = 1 (undeclared, single _ + '__' inside)", lambda: (setattr(d, "_sneaky__name", 1), "accepted")[1])
print("--- explicit rx.field dunder is a real backend var")
d2 = rx.State(_reflex_internal_init=True).get_substate(D.get_full_name().split(".")[1:])
t("d2.bump_fielded() -> get_fielded()", lambda: (D.bump_fielded.fn(d2), d2.get_fielded())[1])
t("   dirty_vars", lambda: sorted(d2.dirty_vars))
t("   fielded_view (computed, should react)", lambda: d2.fielded_view)
t("_single__mid instance write dirty?", lambda: (setattr(d2, "_single__mid", 8), sorted(d2.dirty_vars))[1])
print("--- pickle round trip (what disk/redis managers do)")
d3 = rx.State(_reflex_internal_init=True).get_substate(D.get_full_name().split(".")[1:])
for _n, _v in (("_D__counter", 41), ("_D__fielded", 42), ("_Mx__mx", 43)):
    t(f"d3.{_n} = {_v}", lambda: (setattr(d3, _n, _v), "ok")[1])
b = pickle.loads(pickle.dumps(d3))
t("after pickle: _D__counter (plain, was 41)", lambda: b._D__counter)
t("after pickle: _D__fielded (field, was 42)", lambda: b._D__fielded)
t("after pickle: _Mx__mx (plain mixin, was 43)", lambda: b._Mx__mx)
print("--- reset()")
t("d3.reset()", lambda: (d3.reset(), "ok")[1])
t("after reset: _D__counter / _D__fielded / _Mx__mx", lambda: (d3._D__counter, d3._D__fielded, getattr(d3, "_Mx__mx", "<missing>")))
print("--- class-level assignment of dunder/mangled")
D._D__counter = 100
t("D._D__counter = 100 -> fresh instance reads", lambda: rx.State(_reflex_internal_init=True).get_substate(D.get_full_name().split(".")[1:])._D__counter)
D.__data_source_params_class__ = Params2
t("D.__data_source_params_class__ = Params2 -> class", lambda: D.__data_source_params_class__.__name__)
D._D__fielded = 9
t("D._D__fielded = 9 (explicit field) -> fresh instance reads", lambda: rx.State(_reflex_internal_init=True).get_substate(D.get_full_name().split(".")[1:])._D__fielded)
t("type(D.__dict__['_D__fielded'])", lambda: type(D.__dict__["_D__fielded"]).__name__)
print("--- ComponentState with a dunder")


class CS(rx.ComponentState):
    __clicks = 0
    n: int = 0

    @rx.event
    def click(self):
        self.__clicks += 1
        self.n = self.__clicks

    @classmethod
    def get_component(cls, **props):
        return rx.button(rx.text(cls.n), on_click=cls.click)


comp = CS.create()
cs_cls = type(comp).__name__
t("CS.create() ok", lambda: str(comp)[:60])
