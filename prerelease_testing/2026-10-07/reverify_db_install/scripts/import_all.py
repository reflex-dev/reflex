"""Import every module of every reflex* distribution in this venv; report failures."""
import importlib
import pkgutil
import sys
import traceback
import warnings

import reflex

EXPECT = sys.argv[1]
assert EXPECT in reflex.__file__, reflex.__file__

roots = []
for name in sorted(m.name for m in pkgutil.iter_modules()):
    if name.startswith(("reflex", "reflex_")) and name not in ("reflex_build_sdk",):
        roots.append(name)
print("roots:", roots)
failures = {}
count = 0
skipped_prefixes = (
    "reflex.testing",  # needs selenium extras
)
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    for root in roots:
        try:
            pkg = importlib.import_module(root)
        except Exception as e:  # noqa: BLE001
            failures[root] = repr(e)
            continue
        if not hasattr(pkg, "__path__"):
            count += 1
            continue
        for info in pkgutil.walk_packages(pkg.__path__, prefix=root + "."):
            mod = info.name
            if ".tests" in mod or mod.endswith("__main__"):
                continue
            try:
                importlib.import_module(mod)
                count += 1
            except Exception as e:  # noqa: BLE001
                failures[mod] = f"{type(e).__name__}: {e}"
print(f"imported {count} modules; {len(failures)} failures")
for k, v in failures.items():
    print("FAIL", k, "->", v[:300])
seen = set()
for w in caught:
    key = (str(w.category.__name__), str(w.message)[:200])
    if key in seen:
        continue
    seen.add(key)
    print("WARN", w.category.__name__, str(w.message)[:300], f"({w.filename}:{w.lineno})")
