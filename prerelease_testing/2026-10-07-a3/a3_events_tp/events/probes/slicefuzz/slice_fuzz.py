"""Compare reflex Var slice JS semantics against Python for many bound/step combos.

Usage: python slice_fuzz.py <venv-name>   (run from a neutral dir)
Generates JS for each slice form via the installed reflex, evaluates in node with
concrete values substituted, and reports mismatches vs Python slicing.
"""
import itertools
import json
import subprocess
import sys

import reflex as rx

venv = sys.argv[1]
assert f"/scratchpad/envs/{venv}/" in rx.__file__, rx.__file__


class S(rx.State):
    items: list[int] = []
    s: str = ""
    a: int = 0
    b: int = 0
    st: int = 1


ITEMS = [0, 1, 2, 3, 4, 5]
STR = "abcdef"
vals = [None, -8, -6, -5, -2, -1, 0, 1, 3, 5, 6, 9]
steps = [None, -3, -2, -1, 1, 2, 3]
cases = []
names = {"items": "S_items", "s": "S_s", "a": "S_a", "b": "S_b", "st": "S_st"}


def js_of(v):
    out = str(v)
    for field, nm in names.items():
        out = out.replace(f"reflex___state____state____main_____s.{field}_rx_state_", nm)
    return out


errors = {}
for target in ("items", "s"):
    base = getattr(S, target)
    pyval = ITEMS if target == "items" else STR
    for start, stop, step in itertools.product(vals, vals, steps):
        # var-bound variants: literal, var start/stop, var step
        for mode in ("lit", "varbounds", "varstep", "allvar"):
            if mode in ("varbounds", "allvar") and (start is None or stop is None):
                continue
            if mode in ("varstep", "allvar") and step is None:
                continue
            sa = S.a if mode in ("varbounds", "allvar") else start
            sb = S.b if mode in ("varbounds", "allvar") else stop
            ss = S.st if mode in ("varstep", "allvar") else step
            try:
                v = base[sa:sb:ss]
                expr = js_of(v)
            except BaseException as e:  # noqa: BLE001
                key = f"{type(e).__name__}: {str(e)[:80]}"
                errors.setdefault((target, mode, key), 0)
                errors[(target, mode, key)] += 1
                continue
            expected = pyval[start:stop:step]
            if target == "items":
                expected = list(expected)
            cases.append({"target": target, "mode": mode, "start": start, "stop": stop, "step": step,
                          "expr": expr, "expected": expected})

js_lines = ["const results = [];"]
for i, c in enumerate(cases):
    js_lines.append(
        "{ const S_items = %s; const S_s = %s; const S_a = %s; const S_b = %s; const S_st = %s;"
        " let r; try { r = (%s); } catch (e) { r = 'JSERR:' + e.message; } results.push(r); }"
        % (json.dumps(ITEMS), json.dumps(STR), json.dumps(c["start"]), json.dumps(c["stop"]),
           json.dumps(c["step"]), c["expr"]))
js_lines.append("console.log(JSON.stringify(results));")
with open("fuzz.js", "w") as f:
    f.write("\n".join(js_lines))
out = subprocess.run(["node", "fuzz.js"], capture_output=True, text=True)
if out.returncode:
    print("NODE FAILED", out.stderr[:2000])
    sys.exit(1)
results = json.loads(out.stdout)
mism = []
for c, r in zip(cases, results):
    if r != c["expected"]:
        mism.append((c, r))
print(f"venv={venv} cases={len(cases)} mismatches={len(mism)} compile_errors={sum(errors.values())}")
for (t, m, k), n in sorted(errors.items()):
    print(f"  compile-error target={t} mode={m} x{n}: {k}")
by_mode = {}
for c, r in mism:
    by_mode.setdefault((c["target"], c["mode"]), []).append((c, r))
for (t, m), lst in sorted(by_mode.items()):
    print(f"  MISMATCH target={t} mode={m}: {len(lst)}")
    for c, r in lst[:6]:
        print(f"     [{c['start']}:{c['stop']}:{c['step']}] py={c['expected']!r} js={r!r}")
