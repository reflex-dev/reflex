"""FINDING-024 follow-up: does reflex-base still mask AttributeError raised inside a
CachedVarOperation cached computation as 'VarAttributeError: Attribute ... not found'?

Run with a venv python from a neutral cwd.
"""

import dataclasses
import traceback

import reflex as rx
from reflex_base.vars.base import (
    CachedVarOperation,
    Var,
    VarData,
    cached_property_no_lock,
)

print("reflex module:", rx.__file__)
import importlib.metadata as md

print("reflex-base:", md.version("reflex-base"))


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class BoomVar(CachedVarOperation, Var):
    """A cached var whose var-data computation raises AttributeError."""

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        return "boom"

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        raise AttributeError("REAL ERROR: module 'x' has no attribute 'y'")


v = BoomVar(_js_expr="", _var_type=str)
try:
    v._get_all_var_data()
    print("RESULT: no exception (unexpected)")
except Exception as e:
    print(f"RESULT: {type(e).__module__}.{type(e).__name__}: {e}")
    print("  __cause__:", repr(e.__cause__))
    print("  __context__:", repr(e.__context__))
    traceback.print_exc()
