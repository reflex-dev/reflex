"""Independent verification of FINDING-024 / ent_aggrid ISSUE 3.

Written from the claim text alone: a CachedVarOperation+Var subclass whose
_cached_get_all_var_data raises AttributeError -> what does _get_all_var_data() raise?

Also probes several neighbouring paths the claim does not cover, plus a
non-reflex control, to establish whether this is a reflex defect or plain
Python __getattr__ semantics.
"""

import dataclasses
import importlib.metadata as md
import json
import sys
import traceback

import reflex as rx

assert "/envs/" in rx.__file__, rx.__file__
print("reflex module :", rx.__file__)
print("reflex        :", md.version("reflex"))
print("reflex-base   :", md.version("reflex-base"))
print("python        :", sys.version.split()[0])
print()

from reflex_base.vars.base import (  # noqa: E402
    CachedVarOperation,
    Var,
    VarData,
    cached_property_no_lock,
)

REAL = "REAL ERROR: module 'x' has no attribute 'y'"
results = {}


def report(tag, fn):
    print(f"=== {tag} ===")
    try:
        out = fn()
        print(f"  no exception, returned {out!r}")
        results[tag] = {"raised": None, "returned": repr(out)}
    except BaseException as e:  # noqa: BLE001
        tb = traceback.format_exc()
        info = {
            "raised": f"{type(e).__module__}.{type(e).__name__}",
            "msg": str(e),
            "cause": repr(e.__cause__),
            "context": repr(e.__context__),
            "real_error_visible": REAL in tb,
            "tb_tail": tb.strip().splitlines()[-6:],
        }
        results[tag] = info
        print(f"  {info['raised']}: {info['msg']}")
        print(f"  __cause__   : {info['cause']}")
        print(f"  __context__ : {info['context']}")
        print(f"  real error text anywhere in traceback: {info['real_error_visible']}")
    print()


# --- A: the claim, verbatim from the written repro ------------------------
@dataclasses.dataclass(eq=False, frozen=True, slots=True)
class BoomVarData(CachedVarOperation, Var):
    """Cached var whose var-data computation raises AttributeError."""

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        return "boom"

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        raise AttributeError(REAL)


report("A_claim_get_all_var_data", lambda: BoomVarData(_js_expr="", _var_type=str)._get_all_var_data())


# --- B: same but the failure is in _cached_var_name (the hot path: str(var)) ---
@dataclasses.dataclass(eq=False, frozen=True, slots=True)
class BoomVarName(CachedVarOperation, Var):
    """Cached var whose name computation raises AttributeError."""

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        raise AttributeError(REAL)

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        return None


report("B_cached_var_name_str", lambda: str(BoomVarName(_js_expr="", _var_type=str)))
report("B2_cached_var_name_attr", lambda: BoomVarName(_js_expr="", _var_type=str)._js_expr)


# --- C: realistic shape of the 0.9.9a1 enterprise breakage ---------------
# a module attribute that no longer exists, touched from inside the cached computation
import types as _types  # noqa: E402

fake_mod = _types.ModuleType("fake_dynamic")
sys.modules["fake_dynamic"] = fake_mod
import fake_dynamic  # noqa: E402


@dataclasses.dataclass(eq=False, frozen=True, slots=True)
class RemovedApiVar(CachedVarOperation, Var):
    """Cached var that reads an attribute removed from another module."""

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        return "x"

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        return VarData(imports={} if fake_dynamic.bundled_libraries else {})


report("C_removed_module_attr", lambda: RemovedApiVar(_js_expr="", _var_type=str)._get_all_var_data())


# --- D: non-AttributeError control (does a ValueError propagate cleanly?) ---
@dataclasses.dataclass(eq=False, frozen=True, slots=True)
class BoomValueError(CachedVarOperation, Var):
    """Cached var whose var-data computation raises ValueError."""

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        return "v"

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        raise ValueError(REAL)


report("D_valueerror_control", lambda: BoomValueError(_js_expr="", _var_type=str)._get_all_var_data())


# --- E: plain-Python controls --------------------------------------------
class PlainNoGetattr:
    """Ordinary class with a failing property and no __getattr__."""

    @property
    def prop(self):
        raise AttributeError(REAL)


class PlainWithGetattr:
    """Ordinary class with a failing property and a __getattr__ fallback."""

    @property
    def prop(self):
        raise AttributeError(REAL)

    def __getattr__(self, name):
        msg = f"Attribute {name} not found."
        raise AttributeError(msg)


report("E1_plain_no_getattr", lambda: PlainNoGetattr().prop)
report("E2_plain_with_getattr", lambda: PlainWithGetattr().prop)

with open(sys.argv[1], "w") as f:
    json.dump(
        {
            "reflex": md.version("reflex"),
            "reflex_base": md.version("reflex-base"),
            "results": results,
        },
        f,
        indent=2,
    )
print("wrote", sys.argv[1])
