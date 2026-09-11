"""Re-check the previous campaign's enterprise findings on this train.

Run with the venv whose python you want to test (reflex 0.9.11a1 or
0.9.10.post2, both with reflex-enterprise 0.9.5), from a neutral cwd.

Usage: python probe_prior_findings.py
"""

import importlib.metadata as md
import traceback

import reflex  # noqa: F401

print("python package under test:", reflex.__file__)
for pkg in ("reflex", "reflex-base", "reflex-enterprise"):
    print(f"  {pkg} == {md.version(pkg)}")

print("\n[FINDING-001/021/022] reflex.components.dynamic.bundled_libraries")
try:
    from reflex.components import dynamic

    print("  RESULT: present ->", type(dynamic.bundled_libraries).__name__)
except AttributeError as e:
    print("  RESULT: AttributeError ->", e)

print("\n[FINDING-001] does reflex-enterprise 0.9.5 still read it?")
import pathlib

vars_py = pathlib.Path(
    md.distribution("reflex-enterprise").locate_file("reflex_enterprise/vars.py")
)
hits = [
    f"{i}: {ln.strip()}"
    for i, ln in enumerate(vars_py.read_text().splitlines(), 1)
    if "bundled_libraries" in ln
]
print("  vars.py mentions:", hits or "NONE")

print("\n[FINDING-021/022] LiteralLambdaVar with an import-carrying return expr")
try:
    import reflex as rx
    import reflex_enterprise as rxe  # noqa: F401
    from reflex_enterprise.vars import LiteralLambdaVar

    v = LiteralLambdaVar.create(lambda params: rx.text("hello"))
    print("  RESULT: created ok ->", str(v)[:120])
except Exception:  # noqa: BLE001
    print("  RESULT: raised")
    traceback.print_exc()

print("\n[FINDING-023] from reflex.page import DECORATED_PAGES")
try:
    from reflex.page import DECORATED_PAGES

    print("  RESULT: importable ->", type(DECORATED_PAGES).__name__)
except ImportError as e:
    print("  RESULT: ImportError ->", e)

print("\n[FINDING-024/013] AttributeError inside a cached var computation")
try:
    from reflex_base.vars.base import CachedVarOperation, Var, cached_property_no_lock

    class _Boom(CachedVarOperation, Var):
        @cached_property_no_lock
        def _cached_get_all_var_data(self):
            raise AttributeError("the real error")

    _Boom(_js_expr="x")._var_value  # noqa: B018
except Exception as e:  # noqa: BLE001
    print(f"  RESULT: {type(e).__name__}: {e}")
