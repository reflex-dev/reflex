"""Scoping checks for FINDING-001 verification.

Confirms which LambdaVar-prop variants crash vs work, on the installed
reflex version. Prints one CHECK line per case.
"""

import importlib.metadata as md

import reflex as rx
import reflex_enterprise as rxe
from reflex.components.dynamic import bundle_library
from reflex.utils.imports import ImportVar
from reflex_base.vars.base import Var, VarData

print("reflex", md.version("reflex"), "| ent", md.version("reflex-enterprise"))

bundle_library("d3-format")

fmt_ok = Var(
    "(format(',')(item.id).length > 0)",
    _var_data=VarData(imports={"d3-format": [ImportVar(tag="format")]}),
).to(bool)


def check(name, fn):
    try:
        fn()
        print(f"CHECK {name}: OK")
    except Exception as e:
        print(f"CHECK {name}: {type(e).__name__}: {str(e)[:120]}")


# 1. plain lambda, no VarData at all -> validator runs but vd is None
check(
    "plain_lambda_no_vardata",
    lambda: rxe.dnd.drop_target(
        rx.text("t"),
        accept=["Card"],
        can_drop=lambda item, monitor: Var("true").to(bool),
        on_drop=rx.toast("d"),
    ),
)

# 2. same bundled-library var but @rxe.static -> validator skipped
static_fn = rxe.static(lambda item, monitor: fmt_ok)
check(
    "static_with_imports",
    lambda: rxe.dnd.drop_target(
        rx.text("t"), accept=["Card"], can_drop=static_fn, on_drop=rx.toast("d")
    ),
)


# 3. state-var lambda -> hooks guard (line ~138) fires first on both versions
class S(rx.State):
    allowed: bool = True


check(
    "state_var_lambda",
    lambda: rxe.dnd.drop_target(
        rx.text("t"),
        accept=["Card"],
        can_drop=lambda item, monitor: S.allowed,
        on_drop=rx.toast("d"),
    ),
)

# 4. non-static with imports (the FINDING-001 trigger)
check(
    "plain_lambda_with_imports",
    lambda: rxe.dnd.drop_target(
        rx.text("t"),
        accept=["Card"],
        can_drop=lambda item, monitor: fmt_ok,
        on_drop=rx.toast("d"),
    ),
)
