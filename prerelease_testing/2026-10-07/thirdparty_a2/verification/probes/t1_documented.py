"""Does the documented #7461 'Changing Defaults' pattern itself still work on a2?

Checks (each printed PASS/FAIL/INFO), independent of the explorer's probes:
  D1  frontend var:   S.count = 10  -> fresh instance reads 10; S.count is still a Var usable in UI
  D2  backend var:    S._token = "abc" -> fresh instance reads "abc"
  D3  initialized instance values stay unchanged; reset() uses the last configured default
  D4  mutable defaults stay independent per instance
  D5  zero-arg callable updates the factory (one validation call, then per-instance calls)
  D6  Var / Field assignments are rejected (documented)
  D7  ClassVar keeps ordinary assignment
  D8  ComponentState: cls.text = initial_value in get_component -> per-component defaults, still a Var in UI
  D9  documented ROUND TRIP: value read from the class (Field) cannot be assigned back (documented rejection)
  D10 restoring by re-assigning the ORIGINAL value (not the Field) works
"""

import os
import sys
import types
from typing import ClassVar

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

print("reflex", version("reflex"), "(", os.environ["EXPECT_VENV"], ")")


def inst(cls):
    try:
        return cls(_reflex_internal_init=True)
    except TypeError:
        return cls()


def _try(fn):
    try:
        fn()
        return "NO ERROR"
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {str(e)[:70]}"


def check(label, fn):
    try:
        res = fn()
        print(f"  {label:<78} {res}")
    except Exception as e:  # noqa: BLE001
        print(f"  {label:<78} EXC {type(e).__name__}: {str(e)[:110]}")


class S(rx.State):
    count: int = 0
    _token: str = ""
    items: list[str] = ["a"]
    _priv_items: list[str] = ["p"]
    CV: ClassVar[str] = "cv0"


print("D1/D2/D3 plain assignment")
before_inst = inst(S)
_ = before_inst.count, before_inst._token  # initialize the values BEFORE the class assignment (lazy per-instance init)
uninit_inst = inst(S)  # never read before the assignment: the documented "not yet initialized" case
S.count = 10
S._token = "abc"
check("D1 fresh S().count == 10", lambda: inst(S).count == 10)
check("D1 S.count still a Var (UI usable)", lambda: type(S.count).__mro__[1].__name__ + " / " + type(S.count).__name__[:30])
check("D1 rx.text(S.count) renders", lambda: "ok:" + str(rx.text(S.count))[:40].replace("\n", " "))
check("D2 fresh S()._token == 'abc'", lambda: inst(S)._token == "abc")
check("D2 S._token (class read) is", lambda: type(S._token).__name__)
check("D3 already-initialized instance keeps old value (count==0)", lambda: before_inst.count == 0)
check("D3 never-initialized instance picks up new default (count==10) [documented]", lambda: uninit_inst.count == 10)
s2 = inst(S)


def _write_then_reset():
    s2.count = 55
    s2.reset()
    return s2.count == 10


check("D3 instance write then reset(): count back to configured 10", _write_then_reset)

print("D4 mutable defaults independent")
S.items = ["x", "y"]
a, b = inst(S), inst(S)
a.items.append("z")
check("D4 b.items unaffected (['x','y'])", lambda: list(b.items) == ["x", "y"])

print("D5 callable factory")
calls = {"n": 0}


def make_list():
    calls["n"] += 1
    return ["f"]


S._priv_items = make_list
check("D5 one validation call at assignment", lambda: calls["n"] == 1)
x, y = inst(S), inst(S)
check("D5 instances get factory results (['f']) and separate objects", lambda: (list(x._priv_items) == ["f"], x._priv_items is not y._priv_items, calls["n"]))

print("D6 Var/Field rejected")
check("D6 S.count = Var -> ", lambda: _try(lambda: setattr(S, "count", rx.Var.create(3))))
check("D6 S._token = rx.field(default='z') ->", lambda: _try(lambda: setattr(S, "_token", rx.field(default="z"))))

print("D7 ClassVar")
S.CV = "cv1"
check("D7 S.CV == 'cv1'", lambda: S.CV == "cv1")

print("D9/D10 round trip")
field_obj = S.__dict__["_token"]
check("D9 S._token = <Field object read from class> ->", lambda: _try(lambda: setattr(S, "_token", field_obj)))
check("D10 S._token = 'original'  -> fresh instance sees 'original'", lambda: (setattr(S, "_token", "original"), inst(S)._token)[1])

print("D8 ComponentState")


def _mk_cs():
    def body(ns):
        ns["__module__"] = __name__
        ns["__annotations__"] = {"text": str}
        ns["text"] = "default"

        @classmethod
        def get_component(cls, **props):
            initial_value = props.pop("initial_value", None)
            if initial_value is not None:
                cls.text = initial_value
            return rx.text(cls.text)

        ns["get_component"] = get_component

    return types.new_class("EditableText", (rx.ComponentState,), {}, body)


CS = _mk_cs()
c1 = CS.create(initial_value="one")
c2 = CS.create(initial_value="two")
c3 = CS.create()
check("D8 generated states have distinct defaults one/two/default", lambda: (inst(c1.State).text, inst(c2.State).text, inst(c3.State).text))
check("D8 UI references frontend var (no literal default baked in)", lambda: ("text" in str(c1).lower(), "one" in str(c1)))
s = inst(c1.State)
s.text = "edited"
check("D8 reset restores last configured default 'one'", lambda: (s.reset(), s.text)[1])
