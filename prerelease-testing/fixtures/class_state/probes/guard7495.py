"""Adversarial probes for the #7495 dev-mode SetUndefinedStateVarError guard (N-008 follow-up).

Run: REFLEX_ENV_MODE=dev|prod REFLEX_TELEMETRY_ENABLED=false EXPECT_VENV=<venv> <venv>/bin/python -I guard7495.py
Each row: the write, and 'accepted' or the exception. In dev, a3 should raise only for names that are neither declared
nor dunder nor mangled by the state's own class / a base / a mixin.
"""

import os
import sys

import reflex as rx

EXPECT = os.environ["EXPECT_VENV"]
assert f"/envs/{EXPECT}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

print(f"reflex {version('reflex')} REFLEX_ENV_MODE={os.environ.get('REFLEX_ENV_MODE', '<unset>')}")


def inst(cls):
    try:
        return cls(_reflex_internal_init=True)
    except TypeError:
        return cls()


def row(label, fn):
    try:
        r = fn()
        out = "accepted" if r is None else f"accepted -> {r!r}"
    except Exception as e:  # noqa: BLE001
        out = f"{type(e).__name__}: {str(e)[:110]}"
    print(f"{label:<78} -> {out}")


class GMixin(rx.State, mixin=True):
    def mx_write(self):
        self.__mxv = 1  # mangled to _GMixin__mxv
        return self.__mxv


class GBase(rx.State):
    def base_write(self):
        self.__bv = 2  # _GBase__bv
        return self.__bv


class GChild(GMixin, GBase):
    def own_write(self):
        self.__own = 3  # _GChild__own
        return self.__own


class _GUnder(rx.State):
    def under_write(self):
        self.__u = 4  # _GUnder__u
        return self.__u


class __GDunderName(rx.State):  # noqa: N801
    def w(self):
        self.__d = 5  # _GDunderName__d
        return self.__d


class Helper:
    """A non-state helper class whose methods mangle with its own name."""

    def poke(self, st):
        st.__h = 6  # _Helper__h

    @staticmethod
    def poke_static(st):
        st.__hs = 7  # _Helper__hs


class GTmpl(rx.ComponentState):
    n: int = 0

    def tmpl_write(self):
        self.__t = 8  # _GTmpl__t
        return self.__t

    @classmethod
    def get_component(cls, *children, **props):
        return rx.text(cls.n)


def make_local():
    class GLocal(rx.State):
        def w(self):
            self.__loc = 9  # _GLocal__loc
            return self.__loc

    class GLocalSub(GLocal):
        def w2(self):
            self.__locsub = 10  # _GLocalSub__locsub
            return self.__locsub

    return GLocal, GLocalSub


c = inst(GChild)
row("own class mangled self.__own (GChild)", c.own_write)
row("mixin mangled self.__mxv (GMixin)", c.mx_write)
row("base mangled self.__bv (GBase)", c.base_write)
row("underscore class _GUnder self.__u", inst(_GUnder).under_write)
row("double-underscore class __GDunderName self.__d", inst(__GDunderName).w)
row("non-state Helper().poke(state) -> _Helper__h", lambda: Helper().poke(inst(GChild)))
row("non-state Helper.poke_static(state) -> _Helper__hs", lambda: Helper.poke_static(inst(GChild)))
row("_sneaky__name = 1 (single _, '__' inside, undeclared)", lambda: setattr(inst(GChild), "_sneaky__name", 1))
row("_GChild__typo = 1 (own-prefix, undeclared; by design plain)", lambda: setattr(inst(GChild), "_GChild__typo", 1))
row("_GBase__x via setattr (base prefix)", lambda: setattr(inst(GChild), "_GBase__x", 1))
row("_State__x via setattr (rx.State in MRO)", lambda: setattr(inst(GChild), "_State__x", 1))
row("_BaseState__x via setattr (framework class in MRO)", lambda: setattr(inst(GChild), "_BaseState__x", 1))
row("_object__x via setattr", lambda: setattr(inst(GChild), "_object__x", 1))
row("_OtherState__x via setattr (unrelated state name)", lambda: setattr(inst(GChild), "_OtherState__x", 1))
row("__x via setattr (dunder-prefixed string)", lambda: setattr(inst(GChild), "__x", 1))
row("__x__ via setattr (dunder)", lambda: setattr(inst(GChild), "__x__", 1))
row("_typo_x (control, no __)", lambda: setattr(inst(GChild), "_typo_x", 1))
row("typo (control, public)", lambda: setattr(inst(GChild), "typo", 1))
row("_x__ (trailing __ only)", lambda: setattr(inst(GChild), "_x__", 1))
try:
    comp = GTmpl.create()
    row(f"ComponentState generated class {comp.State.__name__} tmpl self.__t", inst(comp.State).tmpl_write)
except Exception as e:  # noqa: BLE001
    print(f"ComponentState setup failed: {type(e).__name__}: {e}")
try:
    L, LS = make_local()
    print(f"   local classes renamed to {L.__name__}/{LS.__name__}, __original_name__={L.__dict__.get('__original_name__')!r}/{LS.__dict__.get('__original_name__')!r}")
    row("locally defined state self.__loc", inst(L).w)
    row("locally defined substate self.__locsub", inst(LS).w2)
    row("locally defined substate inherited self.__loc", inst(LS).w)
except Exception as e:  # noqa: BLE001
    print(f"local setup failed: {type(e).__name__}: {e}")
# a state renamed after creation by the user
class GRenamed(rx.State):  # noqa: E305
    def w(self):
        self.__r = 11  # _GRenamed__r
        return self.__r


GRenamed.__name__ = "GRenamedLater"
row("state whose __name__ was changed after creation, self.__r", inst(GRenamed).w)
