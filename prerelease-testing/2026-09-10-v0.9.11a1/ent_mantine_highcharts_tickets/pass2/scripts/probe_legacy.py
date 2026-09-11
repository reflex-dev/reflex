"""Offline re-check of the 0.9.9a1 enterprise breakage on reflex 0.9.11a1 + rxe 0.9.5.

Covers the 2026-08-27 campaign's FINDING-001 (dynamic.bundled_libraries removed),
FINDING-023 (reflex.page.DECORATED_PAGES removed), FINDING-024 (AttributeError inside
a cached var masked) and FINDING-029/026 code paths, with no server needed.

Run from a neutral directory (never the reflex checkout):
    $SB/envs/mht_a1/bin/python probe_legacy.py
"""

import importlib.metadata as md
import traceback
import warnings

import reflex

assert "/envs/mht_" in reflex.__file__, reflex.__file__
print("reflex", md.version("reflex"), "| rxe", md.version("reflex-enterprise"))
print("module:", reflex.__file__)
print()

print("== FINDING-001: reflex.components.dynamic.bundled_libraries")
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    try:
        import reflex.components.dynamic as dyn

        value = dyn.bundled_libraries
        print("   OK ->", type(value).__name__, sorted(value)[:6])
    except Exception as exc:  # noqa: BLE001
        print("   RAISES", type(exc).__name__, exc)
    print("   warnings:", [str(w.message)[:120] for w in caught])

print("== FINDING-023: reflex.page.DECORATED_PAGES")
try:
    from reflex.page import DECORATED_PAGES

    print("   OK ->", type(DECORATED_PAGES).__name__, len(DECORATED_PAGES))
except Exception as exc:  # noqa: BLE001
    print("   RAISES", type(exc).__name__, exc)

print("== rxe compat helper (rxe #219)")
try:
    from reflex_enterprise.vars import get_bundled_libraries

    print("   get_bundled_libraries() ->", sorted(get_bundled_libraries())[:6])
except Exception as exc:  # noqa: BLE001
    print("   RAISES", type(exc).__name__, exc)

print("== FINDING-024: AttributeError inside a cached var computation")
from reflex.vars.base import CachedVarOperation, Var, cached_property_no_lock  # noqa: E402


class Boom(CachedVarOperation, Var):
    """A var whose cached computation raises AttributeError."""

    @cached_property_no_lock
    def _cached_get_all_var_data(self):
        raise AttributeError("the real error: 'Foo' object has no attribute 'bar'")


try:
    Boom(_js_expr="boom")._get_all_var_data()
except Exception:  # noqa: BLE001
    tb = traceback.format_exc()
    print("   raised:", tb.strip().splitlines()[-1])
    print("   real message present in traceback:", "the real error" in tb)

print("== FINDING-029 path: does rxe still call console.error / console.info?")
import pathlib  # noqa: E402
import re  # noqa: E402

import reflex_enterprise  # noqa: E402

root = pathlib.Path(reflex_enterprise.__file__).parent
hits = []
for path in root.rglob("*.py"):
    for i, line in enumerate(path.read_text().splitlines(), 1):
        if re.search(r"console\.(error|info)\(", line):
            hits.append(f"{path.relative_to(root)}:{i}: {line.strip()[:90]}")
print("   " + ("\n   ".join(hits) if hits else "none"))

print("== is console.error/console.info deprecated in this reflex-base?")
from reflex_base.utils import console  # noqa: E402

for name in ("error", "info", "warn", "deprecate"):
    fn = getattr(console, name, None)
    print(f"   console.{name}: {'present' if fn else 'MISSING'}")
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    console.error("probe: console.error call")
    console.info("probe: console.info call")
    print("   python warnings raised:", [str(w.message)[:100] for w in caught])

print("== FINDING-026 path: which rxe module registers /_reflex/cookies/sync?")
for path in root.rglob("*.py"):
    text = path.read_text()
    if "cookies/sync" in text:
        for i, line in enumerate(text.splitlines(), 1):
            if "cookies/sync" in line:
                print(f"   {path.relative_to(root)}:{i}: {line.strip()[:100]}")
