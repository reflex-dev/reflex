"""Import every reflex_enterprise module in the running venv; record failures and warnings.

Usage: EXPECT_VENV=<venv> <venv>/bin/python -I import_sweep.py <out.json>
"""
import importlib, json, os, pkgutil, sys, warnings, time

import reflex
assert f"/envs/{os.environ['EXPECT_VENV']}/" in reflex.__file__, reflex.__file__
import reflex_enterprise as rxe

out = {"venv": os.environ["EXPECT_VENV"], "reflex": reflex.__version__ if hasattr(reflex, "__version__") else None,
       "modules": [], "failures": {}, "warnings": {}}
import importlib.metadata as m
out["versions"] = {p: m.version(p) for p in ("reflex", "reflex-base", "reflex-enterprise")}
names = [n for _, n, _ in pkgutil.walk_packages(rxe.__path__, "reflex_enterprise.")]
t0 = time.time()
for name in sorted(names):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            importlib.import_module(name)
            out["modules"].append(name)
        except Exception as e:  # noqa: BLE001
            out["failures"][name] = f"{type(e).__name__}: {e}"
        if w:
            out["warnings"][name] = sorted({f"{x.category.__name__}: {str(x.message)[:300]} ({os.path.basename(x.filename)}:{x.lineno})" for x in w})
out["elapsed"] = round(time.time() - t0, 1)
out["n_modules"] = len(names)
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(f"{out['versions']} modules={len(names)} ok={len(out['modules'])} failures={len(out['failures'])} warned_modules={len(out['warnings'])} in {out['elapsed']}s")
for k, v in out["failures"].items():
    print("FAIL", k, v[:300])
allw = sorted({x for v in out["warnings"].values() for x in v})
print("distinct warnings:", len(allw))
for x in allw:
    print("  W", x[:300])
