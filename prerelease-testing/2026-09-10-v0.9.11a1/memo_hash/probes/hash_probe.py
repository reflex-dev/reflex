"""Hash-level probes for #6947: the collision table, cache release, name stability.

Run from a neutral cwd with the venv python, e.g.
  cd $SB/apps/memo_hash && $SB/envs/smoke/bin/python probes/hash_probe.py
"""

import dataclasses
import enum
import gc
import json
import sys

import reflex  # noqa: E402

VENV = sys.argv[1] if len(sys.argv) > 1 else "smoke"
assert f"/envs/{VENV}/" in reflex.__file__, reflex.__file__
print("reflex:", reflex.__file__, reflex.constants.Reflex.VERSION)

import reflex as rx
from reflex_base.utils.deterministic_hash import deterministic_hash

results = {}


def rec(name, ok, detail=""):
    results[name] = {"ok": bool(ok), "detail": str(detail)}
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


# --- collision row: dataclasses encoded by field layout alone ------------------
@dataclasses.dataclass(frozen=True)
class Alpha:
    a: str


@dataclasses.dataclass(frozen=True)
class Beta:
    a: str


ha, hb = deterministic_hash(Alpha(a="x")), deterministic_hash(Beta(a="x"))
rec("dataclass_identity", ha != hb, f"Alpha={ha[:12]} Beta={hb[:12]}")


# --- collision row: enum members encoded as str(value) -------------------------
class Level(enum.IntEnum):
    ONE = 1
    TWO = 2


class OtherLevel(enum.IntEnum):
    ONE = 1


he, hi = deterministic_hash(Level.ONE), deterministic_hash(1)
rec("intenum_vs_int", he != hi, f"Level.ONE={he[:12]} 1={hi[:12]}")
h2 = deterministic_hash(OtherLevel.ONE)
rec("intenum_cross_enum", he != h2, f"Level.ONE={he[:12]} OtherLevel.ONE={h2[:12]}")


class Color(enum.Enum):
    RED = "red"


hc, hs = deterministic_hash(Color.RED), deterministic_hash("red")
rec("strvalue_enum_vs_str", hc != hs, f"Color.RED={hc[:12]} 'red'={hs[:12]}")


# --- collision row: caches never released (dataclass in a function body) -------
def make_dc(i):
    @dataclasses.dataclass(frozen=True)
    class Local:
        a: str

    Local.__qualname__ = f"Local{i}"
    return Local


from reflex_base.utils import deterministic_hash as dh_mod

dh_mod.clear_hash_caches()
import weakref

refs = []
for i in range(50):
    cls = make_dc(i)
    deterministic_hash(cls(a="x"))
    refs.append(weakref.ref(cls))
    del cls
gc.collect()
alive_before = sum(1 for r in refs if r() is not None)
dh_mod.clear_hash_caches()
gc.collect()
alive_after = sum(1 for r in refs if r() is not None)
rec(
    "infunction_dataclass_release",
    alive_after == 0,
    f"alive before clear={alive_before}, after clear={alive_after}",
)

# in-function dataclasses with identical layouts but distinct types
A1, A2 = make_dc(1), make_dc(2)
rec(
    "infunction_dataclass_distinct",
    deterministic_hash(A1(a="x")) != deterministic_hash(A2(a="x")),
    "two function-local dataclasses of identical shape",
)

# --- component-level: same qualname, different modules -------------------------
import types

from reflex_base.components.memo import component_hash, memo_tag

src = """
import reflex as rx

class Widget(rx.el.Div):
    pass
"""
mods = {}
for name in ("modx", "mody"):
    m = types.ModuleType(name)
    m.__file__ = f"/tmp/{name}.py"
    sys.modules[name] = m
    exec(compile(src, f"/tmp/{name}.py", "exec"), m.__dict__)
    mods[name] = m

wx = mods["modx"].Widget.create("same")
wy = mods["mody"].Widget.create("same")
tx, ty = memo_tag(wx), memo_tag(wy)
rec("same_qualname_diff_module", tx != ty, f"{tx} vs {ty}")

# --- add_custom_code in the hash ------------------------------------------------
src_cc = """
import reflex as rx

class CodeWidget(rx.el.Div):
    def add_custom_code(self) -> list[str]:
        return [{code!r}]
"""
cc_tags = []
for i, name in enumerate(("ccx", "ccy")):
    m = types.ModuleType(name)
    m.__file__ = f"/tmp/{name}.py"
    sys.modules[name] = m
    exec(
        compile(src_cc.format(code=f"window.CC_{i} = {i};"), f"/tmp/{name}.py", "exec"),
        m.__dict__,
    )
    cc_tags.append(memo_tag(m.CodeWidget.create("same")))
rec("add_custom_code_hashed", cc_tags[0] != cc_tags[1], f"{cc_tags[0]} vs {cc_tags[1]}")

# same module, same class, different add_custom_code via a subclass with the
# SAME qualname (simulates two modules) is covered above; now check that
# add_custom_code alone (identical module+qualname impossible) is in the digest
# by hashing artifacts directly.
from reflex_base.components.memo import _component_artifacts


class CCBase(rx.el.Div):
    def add_custom_code(self):
        return ["window.CC_BASE = 1;"]


class CCOther(rx.el.Div):
    def add_custom_code(self):
        return ["window.CC_OTHER = 2;"]


CCOther.__qualname__ = "CCBase"
CCOther.__module__ = CCBase.__module__
a1 = list(_component_artifacts(CCBase.create("same"), recursive=False))
a2 = list(_component_artifacts(CCOther.create("same"), recursive=False))
rec(
    "add_custom_code_only_difference",
    deterministic_hash(*a1) != deterministic_hash(*a2),
    "identical module+qualname, only add_custom_code differs",
)


# --- _get_dynamic_imports in the hash --------------------------------------------
class DynA(rx.el.Div):
    def _get_dynamic_imports(self):
        return "const DYN_A = 1;"


class DynB(rx.el.Div):
    def _get_dynamic_imports(self):
        return "const DYN_B = 2;"


DynB.__qualname__ = "DynA"
DynB.__module__ = DynA.__module__
rec(
    "dynamic_imports_hashed",
    deterministic_hash(*_component_artifacts(DynA.create("s"), recursive=False))
    != deterministic_hash(*_component_artifacts(DynB.create("s"), recursive=False)),
    "identical module+qualname, only _get_dynamic_imports differs",
)


# --- tagless ImportVar (css side-effect import) -----------------------------------
from reflex_base.utils.imports import ImportVar


class CssA(rx.el.Div):
    def add_imports(self):
        return {"$/public/memo_a.css": [ImportVar(tag=None)]}


class CssB(rx.el.Div):
    def add_imports(self):
        return {"$/public/memo_b.css": [ImportVar(tag=None)]}


CssB.__qualname__ = "CssA"
CssB.__module__ = CssA.__module__
rec(
    "tagless_importvar_hashed",
    deterministic_hash(*_component_artifacts(CssA.create("s"), recursive=False))
    != deterministic_hash(*_component_artifacts(CssB.create("s"), recursive=False)),
    "identical module+qualname, only a tagless ImportVar differs",
)


# --- app-wrap components: rx.text('a') vs rx.text('bbbbb') -------------------------
class WrapA(rx.el.Div):
    @staticmethod
    def _get_app_wrap_components():
        return {(60, "MemoWrap"): rx.text("a")}


class WrapB(rx.el.Div):
    @staticmethod
    def _get_app_wrap_components():
        return {(60, "MemoWrap"): rx.text("bbbbb")}


WrapB.__qualname__ = "WrapA"
WrapB.__module__ = WrapA.__module__
rec(
    "appwrap_markdowncomponentmap_hashed",
    deterministic_hash(*_component_artifacts(WrapA.create("s"), recursive=False))
    != deterministic_hash(*_component_artifacts(WrapB.create("s"), recursive=False)),
    "app-wrap rx.text('a') vs rx.text('bbbbb')",
)
rec(
    "rx_text_direct_hash",
    deterministic_hash(rx.text("a")) != deterministic_hash(rx.text("bbbbb")),
    "deterministic_hash(rx.text('a')) vs rx.text('bbbbb')",
)

# --- name stability across identical recomputes -----------------------------------
dh_mod.clear_hash_caches()
t1 = memo_tag(mods["modx"].Widget.create("same"))
dh_mod.clear_hash_caches()
t2 = memo_tag(mods["modx"].Widget.create("same"))
t3 = memo_tag(mods["modx"].Widget.create("same"))
rec("tag_stable_across_cache_clear", t1 == t2 == t3, f"{t1}")

print()
print(json.dumps(results, indent=2))
bad = [k for k, v in results.items() if not v["ok"]]
print("FAILED:", bad if bad else "none")
