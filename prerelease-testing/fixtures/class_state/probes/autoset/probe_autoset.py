"""Auto setters (state_auto_setters=True via ./rxconfig.py) + #7516 guard, and rx.Model var pickling.
Run from this dir: EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_autoset.py"""
import os
import pickle
import sys
import traceback

sys.path.insert(0, os.getcwd())
import reflex as rx  # noqa: E402

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

print(f"reflex {version('reflex')} auto_setters={rx.config.get_config().state_auto_setters}")


def fields(cls):
    return getattr(cls, "__fields__", None) or cls.get_fields()


class S(rx.State):
    v: int = 0


fields(S)["v"].default = 4
s = S(_reflex_internal_init=True)
print("auto setter set_v present:", "set_v" in S.event_handlers, "| default:", s.v)
S.event_handlers["setvar"].fn(s, "v", 9)
print("setvar ->", s.v, "| set_v ->", (S.event_handlers["set_v"].fn(s, 11), s.v)[1])


class Item(rx.Model, table=True):
    name: str = ""


class M(rx.State):
    rows: list[Item] = []


fields(M)["rows"].default_factory = lambda: [Item(name="cfg")]
m = M(_reflex_internal_init=True)
m.rows.append(Item(name="x"))
m2 = pickle.loads(pickle.dumps(m))
m.reset()
print("Model rows: reset ->", [r.name for r in m.rows], "pickled ->", [r.name for r in m2.rows])

try:
    class P(rx.State):
        set_color: str = "p"

    class C(P):
        color: str = "c"

    print("parent var 'set_color' + child var 'color' with auto setters: created; C.set_color ->", type(C.__dict__.get("set_color", P.__dict__.get("set_color"))).__name__)
except Exception as e:  # noqa: BLE001
    tb = traceback.extract_tb(e.__traceback__)
    print(f"parent var 'set_color' + child var 'color' with auto setters: {type(e).__name__}: {e} @ {[f'{os.path.basename(t.filename)}:{t.lineno}' for t in tb[-3:]]}")
