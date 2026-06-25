"""Automatic purity validation — prove native work is real, not a Python wrapper.

Guards the failure mode where a "ported" path passes golden tests by quietly
keeping construction in Python and matching output. With native registry
construction, the native-vs-not decision happens at BUILD time (a non-native
child becomes a pre-rendered `RawDict`), so the enforcement is:

  1. STRUCTURAL (strongest): `render_to_js_pure` runs with the GIL released, so
     it cannot touch Python. It succeeds only for a fully build-native tree; a
     RawDict subtree makes it error. This is the binary "is this build-native?"
  2. RENDER PROFILER: `sys.setprofile` shows codegen runs 0 Python functions in
     BOTH cases (Stage A: codegen is always native) — so output equality alone
     can never tell native from not. That is exactly why layer 1 is needed.
  3. BUILD-TIME LEDGER + STRICT: `py_fallback_count()` counts non-native
     subtrees encountered during construction; `set_strict(True)` turns any
     such subtree into a hard error at build.

Run:  uv run python experimental/reflex-compiler-core/validate.py
"""

import sys

import reflex as rx
import reflex_compiler_core as rcc

import fastnodes as fast

el = fast.el


def python_calls_during(fn, *args):
    counter = [0]

    def prof(_frame, event, _arg):
        if event == "call":
            counter[0] += 1

    sys.setprofile(prof)
    try:
        fn(*args)
    finally:
        sys.setprofile(None)
    return counter[0]


def audit(name, build):
    """Build (ledger reset first), then run all layers; return verdict dict."""
    rcc.reset_fallback_count()
    tree = build()
    fallbacks = rcc.py_fallback_count()  # counted during build

    try:
        rcc.render_to_js_pure(tree)
        structural_native = True
    except RuntimeError:
        structural_native = False

    render_py_calls = python_calls_during(rcc.render_to_js, tree)
    return {
        "name": name,
        "structural_native": structural_native,
        "render_py_calls": render_py_calls,
        "fallbacks": fallbacks,
        "build_native": structural_native and fallbacks == 0,
    }


def main():
    # Native: only registry elements.
    pure = lambda: el.div(el.h1("T", class_name="hd"), el.span("hi"), class_name="root")
    # "Cheat": a Python component child (here a cond) — construction stays Python.
    cheat = lambda: el.div(rx.cond(rx.Var.create(True), rx.el.span("y"), rx.el.span("n")), class_name="root")

    rows = [audit("pure (all native)", pure), audit("cheat (python subtree)", cheat)]

    print(f"{'tree':<26}{'GIL-pure':>10}{'render_py':>11}{'fallbacks':>11}{'verdict':>14}")
    print("-" * 72)
    for r in rows:
        verdict = "BUILD-NATIVE" if r["build_native"] else "NOT NATIVE"
        print(
            f"{r['name']:<26}{('yes' if r['structural_native'] else 'no'):>10}"
            f"{r['render_py_calls']:>11}{r['fallbacks']:>11}{verdict:>14}"
        )
    print("\nNote: render_py_calls is 0 for BOTH — codegen is always native, so")
    print("output equality cannot distinguish native from not. Layer 1 (GIL-pure)")
    print("and the build-time ledger are what actually prove construction is native.")

    # Strict mode rejects a non-native subtree at BUILD time.
    rcc.set_strict(True)
    try:
        cheat()
        strict_caught = False
    except RuntimeError:
        strict_caught = True
    finally:
        rcc.set_strict(False)
    print("\nstrict mode rejects non-native construction:", strict_caught)

    assert rows[0]["build_native"], "pure tree must prove build-native"
    assert not rows[1]["build_native"], "cheat tree must be detected"
    assert strict_caught, "strict mode must reject non-native construction"
    print("\nGATE OK: build-native work is verifiable; non-native construction is auto-detected.")


if __name__ == "__main__":
    main()
