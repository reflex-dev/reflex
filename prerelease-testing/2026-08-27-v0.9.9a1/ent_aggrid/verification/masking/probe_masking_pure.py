"""Pure reflex-base probe for the AttributeError-masking claim (no reflex-enterprise).

Defines a CachedVarOperation subclass exactly in the style of reflex-base's own
ConcatVarOperation, whose _cached_get_all_var_data computation raises AttributeError
(stand-in for e.g. rxe reading the removed reflex.components.dynamic.bundled_libraries).

Checks:
  1. var._get_all_var_data() surfaces as VarAttributeError
     'Attribute _cached_get_all_var_data not found.' -- the real AttributeError is
     discarded: no __cause__, no __context__, marker text absent from the traceback.
  2. Control: a ValueError raised in the identical spot propagates unmasked, so the
     masking is specific to AttributeError (descriptor protocol + __getattr__ fallback).
  3. Same masking via the _js_expr -> _cached_var_name path.

Run with any venv that has reflex-base (0.9.8 or 0.9.9a1):
    <venv>/bin/python probe_masking_pure.py
Exits 0 and prints ALL CHECKS PASSED when the masking claim is reproduced.
"""

import dataclasses
import importlib.metadata
import sys
import traceback

from reflex_base.utils.exceptions import VarAttributeError
from reflex_base.vars.base import (
    CachedVarOperation,
    VarData,
    cached_property_no_lock,
)
from reflex_base.vars.sequence import StringVar

MARKER = "REAL_UNDERLYING_ATTRIBUTE_ERROR_marker_xyzzy"

print(
    f"reflex-base {importlib.metadata.version('reflex-base')}  "
    f"python {sys.version.split()[0]}"
)

failures = []


def check(name, cond, detail=""):
    print(f"  [{'ok' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not cond:
        failures.append(name)


@dataclasses.dataclass(eq=False, frozen=True, slots=True)
class BoomVarDataVar(CachedVarOperation, StringVar[str]):
    """Cached var op whose _cached_get_all_var_data computation raises AttributeError."""

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        return '"boom"'

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        raise AttributeError(MARKER)


@dataclasses.dataclass(eq=False, frozen=True, slots=True)
class BoomValueErrorVar(CachedVarOperation, StringVar[str]):
    """Identical, but the computation raises ValueError (control case)."""

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        return '"boom"'

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        raise ValueError(MARKER)


@dataclasses.dataclass(eq=False, frozen=True, slots=True)
class BoomNameVar(CachedVarOperation, StringVar[str]):
    """Cached var op whose _cached_var_name computation raises AttributeError."""

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        raise AttributeError(MARKER)

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        return None


print("\n1. AttributeError inside _cached_get_all_var_data computation:")
v = BoomVarDataVar(_js_expr="", _var_type=str)
try:
    v._get_all_var_data()
except BaseException as e:  # noqa: BLE001
    tb = traceback.format_exc()
    check("raises VarAttributeError", isinstance(e, VarAttributeError), type(e).__name__)
    check(
        "message is the misleading 'not found'",
        str(e) == "Attribute _cached_get_all_var_data not found.",
        repr(str(e)),
    )
    check("__cause__ is None", e.__cause__ is None, repr(e.__cause__))
    check("__context__ is None (fully discarded)", e.__context__ is None, repr(e.__context__))
    check("real error text absent from traceback", MARKER not in tb)
else:
    check("raised at all", False)

print("\n2. control: ValueError in the same spot propagates unmasked:")
v2 = BoomValueErrorVar(_js_expr="", _var_type=str)
try:
    v2._get_all_var_data()
except BaseException as e:  # noqa: BLE001
    check("raises the original ValueError", type(e) is ValueError and str(e) == MARKER, f"{type(e).__name__}: {e}")
else:
    check("raised at all", False)

print("\n3. AttributeError inside _cached_var_name computation (str(var) path):")
v3 = BoomNameVar(_js_expr="", _var_type=str)
try:
    str(v3)
except BaseException as e:  # noqa: BLE001
    tb = traceback.format_exc()
    check("raises VarAttributeError", isinstance(e, VarAttributeError), type(e).__name__)
    check(
        "misleading message (either _js_expr or _cached_var_name 'not found')",
        str(e) in ("Attribute _cached_var_name not found.", "Attribute _js_expr not found."),
        repr(str(e)),
    )
    check("no __cause__ and no __context__", e.__cause__ is None and e.__context__ is None)
    check("real error text absent from traceback", MARKER not in tb)
else:
    check("raised at all", False)

print()
if failures:
    print("FAILED checks:", failures)
    sys.exit(1)
print("ALL CHECKS PASSED — AttributeError masking reproduced on this version")
