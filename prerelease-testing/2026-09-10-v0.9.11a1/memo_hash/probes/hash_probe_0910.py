"""Baseline (reflex 0.9.10.post2) counterpart of hash_probe.py — the pre-#6947 API."""

import dataclasses
import enum
import gc
import json
import sys
import types
import weakref

import reflex

assert "/envs/base0910/" in reflex.__file__, reflex.__file__
print("reflex:", reflex.__file__, reflex.constants.Reflex.VERSION)

import reflex as rx
from reflex_base.components.component import _deterministic_hash

results = {}


def rec(name, ok, detail=""):
    results[name] = {"ok": bool(ok), "detail": str(detail)}
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


@dataclasses.dataclass(frozen=True)
class Alpha:
    a: str


@dataclasses.dataclass(frozen=True)
class Beta:
    a: str


ha, hb = _deterministic_hash(Alpha(a="x")), _deterministic_hash(Beta(a="x"))
rec("dataclass_identity", ha != hb, f"Alpha={ha[:12]} Beta={hb[:12]}")


class Level(enum.IntEnum):
    ONE = 1


he, hi = _deterministic_hash(Level.ONE), _deterministic_hash(1)
rec("intenum_vs_int", he != hi, f"Level.ONE={he[:12]} 1={hi[:12]}")


class Color(enum.Enum):
    RED = "red"


hc, hs = _deterministic_hash(Color.RED), _deterministic_hash("red")
rec("strvalue_enum_vs_str", hc != hs, f"Color.RED={hc[:12]} 'red'={hs[:12]}")


def make_dc(i):
    @dataclasses.dataclass(frozen=True)
    class Local:
        a: str

    Local.__qualname__ = f"Local{i}"
    return Local


refs = []
for i in range(50):
    cls = make_dc(i)
    _deterministic_hash(cls(a="x"))
    refs.append(weakref.ref(cls))
    del cls
gc.collect()
alive = sum(1 for r in refs if r() is not None)
rec("infunction_dataclass_release", alive == 0, f"alive after gc.collect()={alive}/50")

A1, A2 = make_dc(1), make_dc(2)
rec(
    "infunction_dataclass_distinct",
    _deterministic_hash(A1(a="x")) != _deterministic_hash(A2(a="x")),
    "two function-local dataclasses of identical shape",
)

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

tx = mods["modx"].Widget.create("same")._compute_memo_tag()
ty = mods["mody"].Widget.create("same")._compute_memo_tag()
rec("same_qualname_diff_module", tx != ty, f"{tx} vs {ty}")


class CCBase(rx.el.Div):
    def add_custom_code(self):
        return ["window.CC_BASE = 1;"]


class CCOther(rx.el.Div):
    def add_custom_code(self):
        return ["window.CC_OTHER = 2;"]


CCOther.__qualname__ = "CCBase"
CCOther.__module__ = CCBase.__module__
rec(
    "add_custom_code_only_difference",
    CCBase.create("same")._compute_memo_tag()
    != CCOther.create("same")._compute_memo_tag(),
    f"{CCBase.create('same')._compute_memo_tag()} vs {CCOther.create('same')._compute_memo_tag()}",
)


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
    DynA.create("s")._compute_memo_tag() != DynB.create("s")._compute_memo_tag(),
    f"{DynA.create('s')._compute_memo_tag()} vs {DynB.create('s')._compute_memo_tag()}",
)

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
    CssA.create("s")._compute_memo_tag() != CssB.create("s")._compute_memo_tag(),
    f"{CssA.create('s')._compute_memo_tag()} vs {CssB.create('s')._compute_memo_tag()}",
)


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
    WrapA.create("s")._compute_memo_tag() != WrapB.create("s")._compute_memo_tag(),
    f"{WrapA.create('s')._compute_memo_tag()} vs {WrapB.create('s')._compute_memo_tag()}",
)
rec(
    "rx_text_direct_hash",
    _deterministic_hash(rx.text("a")) != _deterministic_hash(rx.text("bbbbb")),
    f"{_deterministic_hash(rx.text('a'))[:12]} vs {_deterministic_hash(rx.text('bbbbb'))[:12]}",
)

print()
print(json.dumps(results, indent=2))
print("FAILED:", [k for k, v in results.items() if not v["ok"]] or "none")
