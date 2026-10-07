"""Independent re-derivation of claim A: class-level reads of State attributes, per declaration pattern.

Usage: <venv>/bin/python derive_a.py <expected-venv-name>
Run from a neutral directory (not a checkout). Prints one line per (pattern, probe).
"""

import os
import sys
from typing import ClassVar

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

print(f"reflex {version('reflex')}  REFLEX_ENV_MODE={os.environ.get('REFLEX_ENV_MODE', '<unset>')}")


class Mix(rx.State, mixin=True):
    _m_key = "mixin-label"
    _m_ann: str = "mixin-ann"


class Base(rx.State):
    _inh = "inherited"


class S(Mix, rx.State):
    _u_str = "label"  # unannotated backend
    _u_int = 16
    _u_dict = {"a": 1}
    KEY = "public-unannotated"  # unannotated public
    _cv_key: ClassVar[str] = "classvar-backend"
    CV_KEY: ClassVar[str] = "classvar-public"
    _ann: str = "annotated-backend"
    _fld: str = rx.field("field-backend")
    _fld_unann = rx.field("field-unannotated-backend")
    pub: str = "annotated-public"

    @classmethod
    def via_cls(cls, name):
        return getattr(cls, name)

    def via_type(self, name):
        return getattr(type(self), name)


class Child(Base):
    pass


def kind(v):
    n = type(v).__name__
    return "Field" if n == "Field" else ("Var:" + n if isinstance(v, rx.Var) else n)


def short(v):
    r = repr(v)
    return r if len(r) < 70 else r[:67] + "..."


def try_(fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        return f"EXC {type(e).__name__}: {str(e)[:90]}"


root = rx.State(_reflex_internal_init=True)
inst = root.get_substate(S.get_full_name().split(".")[1:])
cinst = root.get_substate(Child.get_full_name().split(".")[1:])
fields = S.get_fields()
frontend = set(S.vars)
names = ["_u_str", "_u_int", "_u_dict", "KEY", "_cv_key", "CV_KEY", "_ann", "_fld", "_fld_unann", "pub", "_m_key", "_m_ann"]
print(f"{'name':10} | {'S.<name> (class)':48} | {'cls.<name> in classmethod':22} | {'inst.<name>':28} | field? | frontend var?")
for n in names:
    c = try_(lambda: getattr(S, n))
    cm = try_(lambda: S.via_cls(n))
    i = try_(lambda: getattr(inst, n))
    print(f"{n:10} | {kind(c) + ' ' + short(c):48.48} | {kind(cm):22} | {short(i):28.28} | {str(n in fields):6} | {n in frontend}")
print(f"{'Mix._m_key':10} | {short(try_(lambda: Mix._m_key)):48.48}")
print(f"{'Child._inh':10} | {short(try_(lambda: Child._inh)):48.48} | Base._inh={short(try_(lambda: Base._inh))} | inst={short(try_(lambda: cinst._inh))}")
print(f"type(self)._u_str via instance method: {short(try_(lambda: inst.via_type('_u_str')))}")
print(f"inst.__class__._u_str: {short(try_(lambda: inst.__class__._u_str))}")
print("--- Python-level use of the class attribute")
print("S._u_str == 'label'      :", try_(lambda: S._u_str == "label"))
print("f'{S._u_str}'            :", short(try_(lambda: f"{S._u_str}")))
print("S._u_int + 1             :", try_(lambda: S._u_int + 1))
print("S._u_dict['a']           :", try_(lambda: S._u_dict["a"]))
print("bool(S._fld) [default ''] :", try_(lambda: bool(S._fld)))
print("--- Component use")
print("rx.text(S._u_str)        :", short(try_(lambda: str(rx.text(S._u_str)))))
print("rx.icon('x', size=S._u_int):", short(try_(lambda: str(rx.icon("x", size=S._u_int)))))
print("rx.text(S.KEY)           :", short(try_(lambda: str(rx.text(S.KEY)))))
print("rx.text(S._cv_key)       :", short(try_(lambda: str(rx.text(S._cv_key)))))
print("--- frontend dict sent to client contains KEY?")
d = inst.dict()
sub = next(iter(d.values())) if d else {}
print("keys of S.dict():", sorted(k for k in sub if not k.startswith("rx_router") and k not in ("is_hydrated", "router")))
