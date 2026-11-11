"""Independent verification probe for #7519 finding 1 (real class statements, multi-module).

Run: EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_v1.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reflex as rx  # noqa: E402

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

print(f"reflex {version('reflex')} reflex-base {version('reflex-base')}")
import pkg.state as st  # noqa: E402
import pkg.plugins  # noqa: E402,F401  (registers plugin_a after the state module was imported)

S = st.VState


def new():
    return S(_reflex_internal_init=True)


def raw(v):
    return getattr(v, "__wrapped__", v)


s1 = new()
print("p1  options (list extended after class)       :", raw(s1.options))
print("p2  early (list extended before class)        :", raw(s1.early))
print("p3  rebound (name rebound after class)        :", raw(s1.rebound))
print("p4  backend rx.field(LATE) appended after      :", raw(s1._bf))
t_class = st.VState.__fields__["_stamp"].default_value() if hasattr(st.VState, "__fields__") else None
time.sleep(0.05)
s_a, s_b = new(), new()
print("p5  backend rx.field(default_factory=time.time): two instances differ =", s_a._stamp != s_b._stamp)
print("p5b frontend rx.field(default_factory=time.time): two instances differ =", s_a.stamp_front != s_b.stamp_front)
print("p6  frontend rx.field(LATE) appended after     :", raw(s1.ff))
print("p7  backend registry filled by later import    :", raw(s1._plugins))
print("p13 backend dataclass config mutated after     :", raw(s1._cfg))
print("p9  VState.__fields__['options'].default_value():", S.__fields__["options"].default_value() if hasattr(S, "__fields__") else S.get_fields()["options"].default_value())

# p8 naive global guestbook: session 1 signs, then a NEW session is created
st.GUESTBOOK.append("alice")  # what sign() does to the module list
s_new = new()
print("p8  new session after a global append          :", raw(s_new.entries))

# p10 compile-time initial state (what the first render of a page shows)
from reflex.compiler.utils import compile_state  # noqa: E402

root = rx.State
init = compile_state(root)
sub = next(v for k, v in init.items() if k.endswith("v_state"))
print("p10 compiled initial state options             :", sub.get("options_rx_state_", sub.get("options")))
print("p10 compiled initial state entries             :", sub.get("entries_rx_state_", sub.get("entries")))

# p11 reset() after late changes on an instance created early
s1.options.append("x")
s1.reset()
print("p11 reset() options                            :", raw(s1.options))

# p12 substate inherits var
print("p12 VChild instance options                    :", raw(st.VChild(_reflex_internal_init=True).options) if True else None)
