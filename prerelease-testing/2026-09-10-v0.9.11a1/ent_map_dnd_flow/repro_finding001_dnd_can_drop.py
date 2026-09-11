"""Minimal FINDING-001 trigger for the dnd cluster.

reflex-enterprise 0.9.4 LiteralLambdaVar._validate_and_extend_return_expr
(vars.py:143) reads `reflex.components.dynamic.bundled_libraries`, which
reflex 0.9.9a1 removed (breaking change #6382 moved the list onto the active
RegistrationContext; `bundle_library()` itself still exists).

The validation only runs for a NON-@rxe.static callable whose compiled return
expression carries VarData WITHOUT hooks (a state-var reference trips the
hooks guard first, at vars.py:138, on both versions). The realistic way to get
there is the officially supported bundle_library() pattern: a lambda prop whose
JS uses an extra bundled library (documented for ag-grid value formatters, and
equally reachable via dnd's can_drop/can_drag LambdaVar props, exercised here).

Consequences for the shipped demos:
- map demo: no LambdaVar-typed props at all -> unaffected.
- dnd demo: kanban can_drop funcs are @rxe.static (validation skipped),
  basic/foreach pass no can_drop -> unaffected.
- a user combining dnd can_drop (or any LambdaVar prop) with bundle_library
  imports crashes at component construction on 0.9.9a1, works on 0.9.8.

Run:  <venv>/bin/python repro_finding001_dnd_can_drop.py
Prints OK (exit 0) on reflex 0.9.8; AttributeError traceback (exit 1) on 0.9.9a1.
"""

import importlib.metadata as md
import sys
import traceback

import reflex as rx
import reflex_enterprise as rxe
from reflex.components.dynamic import bundle_library
from reflex.utils.imports import ImportVar
from reflex_base.vars.base import Var, VarData

print(
    "reflex",
    md.version("reflex"),
    "| reflex-enterprise",
    md.version("reflex-enterprise"),
)

bundle_library("d3-format")

# Var whose JS depends on an import from the bundled library (no hooks).
fmt_ok = Var(
    "(format(',')(item.id).length > 0)",
    _var_data=VarData(imports={"d3-format": [ImportVar(tag="format")]}),
).to(bool)

try:
    comp = rxe.dnd.drop_target(
        rx.text("target"),
        accept=["Card"],
        # plain (non-@rxe.static) lambda -> _validate_and_extend_return_expr
        # runs -> reads dynamic.bundled_libraries at vars.py:143.
        can_drop=lambda item, monitor: fmt_ok,
        on_drop=rx.toast("dropped"),
    )
except AttributeError:
    traceback.print_exc()
    print("\nFINDING-001 REPRODUCED: AttributeError on dynamic.bundled_libraries")
    sys.exit(1)

print("OK: drop_target with bundled-library can_drop lambda created:", type(comp).__name__)
sys.exit(0)
