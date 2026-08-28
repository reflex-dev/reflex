"""Organic repro of the masking on reflex 0.9.9a1 + reflex-enterprise 0.9.4.

No instrumentation in phase 1: a dict prop containing a python lambda (exactly what
rxe.ag_grid column_defs produce) becomes a LiteralObjectVar; its
_cached_get_all_var_data computation lazily converts the lambda via
LiteralLambdaVar.create, which on 0.9.9a1 raises
AttributeError: module 'reflex.components.dynamic' has no attribute 'bundled_libraries'.
That AttributeError escapes reflex-base's cached_property.__get__ and is masked as
VarAttributeError('Attribute _cached_get_all_var_data not found.') with no
__cause__/__context__.

Phase 2 instruments reflex_base.vars.base.cached_property.__get__ to prove the
swallowed exception is exactly the bundled_libraries AttributeError.

Run: <venv_a1>/bin/python probe_masking_rxe.py
"""

import importlib.metadata
import sys
import traceback

import reflex as rx
import reflex_enterprise  # noqa: F401  (registers LiteralLambdaVar for FunctionType)
from reflex.vars import LiteralVar
from reflex_base.utils.exceptions import VarAttributeError
from reflex_base.vars import base as rb_base

print(
    "reflex", importlib.metadata.version("reflex"),
    "reflex-enterprise", importlib.metadata.version("reflex-enterprise"),
    "python", sys.version.split()[0],
)

failures = []


def check(name, cond, detail=""):
    print(f"  [{'ok' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not cond:
        failures.append(name)


COLDEF = {"field": "x", "cellRenderer": lambda params: rx.text(params.value, color="tomato")}


def make_var(value):
    """Build a prop var the way rxe.ag_grid column defs do.

    Args:
        value: The raw python prop value (dict or list of dicts with a lambda).

    Returns:
        The lazily-converting Literal*Var holding the lambda cell renderer.
    """
    return LiteralVar.create(value)


print("\nphase 1a: organic access on the column_defs LIST var (the ag_grid shape)")
var = make_var([COLDEF])
print(f"  prop var constructed lazily as {type(var).__name__} (no error yet)")
try:
    var._get_all_var_data()
except BaseException as e:  # noqa: BLE001
    tb = traceback.format_exc()
    check("raises VarAttributeError", isinstance(e, VarAttributeError), type(e).__name__)
    check(
        "misleading message",
        str(e) == "Attribute _cached_get_all_var_data not found.",
        repr(str(e)),
    )
    check("__cause__ is None", e.__cause__ is None, repr(e.__cause__))
    check("__context__ is None", e.__context__ is None, repr(e.__context__))
    check("'bundled_libraries' absent from traceback", "bundled_libraries" not in tb)
    check("'reflex_enterprise' absent from traceback", "reflex_enterprise" not in tb)
else:
    check("raised at all", False, "no exception -- masking scenario not present")

print("\nphase 1b: same on a bare DICT var -- masking degrades to a SILENT bogus value")
dvar = make_var(COLDEF)
print(f"  prop var constructed lazily as {type(dvar).__name__} (no error yet)")
try:
    dresult = dvar._get_all_var_data()
except BaseException as e:  # noqa: BLE001
    check("dict variant did not raise", False, f"{type(e).__name__}: {e}")
else:
    from reflex.vars import Var

    check(
        "returns a Var (ObjectItemOperation) instead of VarData -- silent corruption",
        isinstance(dresult, Var),
        f"got {type(dresult).__name__}",
    )

print("\nphase 2: instrument cached_property.__get__ to reveal the swallowed error")
original_get = rb_base.cached_property.__get__
captured = []


def instrumented_get(self, instance, owner=None):
    """Wrap cached_property.__get__ to capture AttributeErrors it lets escape.

    Args:
        self: The cached_property descriptor.
        instance: The instance being accessed.
        owner: The owner class.

    Returns:
        The original descriptor result.
    """
    try:
        return original_get(self, instance, owner)
    except AttributeError as ae:
        captured.append((self._attrname, ae))
        raise


rb_base.cached_property.__get__ = instrumented_get
try:
    fresh = make_var([COLDEF])  # fresh instance: cached_property caches per-instance
    try:
        fresh._get_all_var_data()
    except BaseException as e:  # noqa: BLE001
        check("still surfaces as VarAttributeError", isinstance(e, VarAttributeError), type(e).__name__)
finally:
    rb_base.cached_property.__get__ = original_get

check("instrumentation captured swallowed AttributeError(s)", bool(captured))
for attr, ae in captured:
    print(f"    swallowed during {attr!r}: AttributeError: {ae}")
if captured:
    check(
        "swallowed error is the real root cause (bundled_libraries)",
        any("bundled_libraries" in str(ae) for _, ae in captured),
    )

print()
if failures:
    print("FAILED checks:", failures)
    sys.exit(1)
print("ALL CHECKS PASSED — organic masking + hidden root cause confirmed")
