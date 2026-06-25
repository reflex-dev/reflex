"""Automatic purity validation — prove native Rust work is real, not a Python wrapper.

The failure mode this guards against: an implementation (or a future regression,
or a lazy agent) makes the golden/equivalence tests pass by quietly delegating to
Python and string-matching the output. The work looks "ported" but nothing moved.

Three independent layers. The first two do NOT trust the Rust code's self-report:

  1. STRUCTURAL (strongest): `render_to_js_pure` runs with the GIL released, so it
     physically cannot call Python. If it returns a string, zero Python executed.
     If the tree needs Python, it errors instead of silently falling back.
  2. EXTERNAL PROFILER: `sys.setprofile` counts real Python function entries during
     the render. A native render triggers 0; every Python fallback triggers many.
  3. SELF-REPORTED LEDGER: `py_fallback_count()` — graded coverage; CI fails if a
     component claimed "native" falls back even once.

Run:  uv run python experimental/reflex-compiler-core/validate.py
"""

import sys

import reflex as rx
import reflex_compiler_core as rcc

sys.path.insert(0, "experimental/reflex-compiler-core")
import fastnodes as fast


def python_calls_during(fn, *args):
    """Count Python-level function entries while `fn(*args)` runs (0 == no Python).

    `fn` must be the C function itself (not a Python wrapper), so its own
    invocation is a 'c_call' and only Python re-entry below it is counted.
    """
    counter = [0]

    def prof(_frame, event, _arg):
        if event == "call":  # a Python function was entered (C calls are 'c_call')
            counter[0] += 1

    sys.setprofile(prof)
    try:
        fn(*args)
    finally:
        sys.setprofile(None)
    return counter[0]


def audit(name, handle):
    """Run all three layers and return a verdict dict."""
    # Layer 1: structural (GIL released) — cannot touch Python by construction.
    try:
        rcc.render_to_js_pure(handle)
        structural_native = True
        structural_note = "rendered with GIL released (0 Python possible)"
    except RuntimeError as e:
        structural_native = False
        structural_note = str(e).split(" — ")[-1]

    # Layer 2: external profiler over the normal render.
    rcc.reset_fallback_count()
    py_calls = python_calls_during(rcc.render_to_js, handle)

    # Layer 3: self-reported ledger.
    fallbacks = rcc.py_fallback_count()

    native_proven = structural_native and py_calls == 0 and fallbacks == 0
    return {
        "name": name,
        "structural_native": structural_native,
        "structural_note": structural_note,
        "py_calls": py_calls,
        "fallbacks": fallbacks,
        "native_proven": native_proven,
    }


def main():
    # (a) Pure tree: only native nodes.
    pure = fast.fast_div(
        fast.fast_h1("Title", class_name="hd"),
        fast.fast_span("hello", class_name="sp"),
        class_name="root",
    )
    # (b) "Cheat" tree: embeds a real Python component leaf — exactly what a lazy
    #     port does to make string output match without doing native work.
    cheat = fast.fast_div(
        rx.el.button("click", class_name="btn"),  # real Python Component
        fast.fast_span("hello", class_name="sp"),
        class_name="root",
    )

    rows = [audit("pure (all native)", pure), audit("cheat (python leaf)", cheat)]

    print(f"{'tree':<22}{'structural':>12}{'py_calls':>10}{'fallbacks':>11}{'verdict':>12}")
    print("-" * 67)
    for r in rows:
        verdict = "NATIVE ✓" if r["native_proven"] else "FALLBACK ✗"
        print(
            f"{r['name']:<22}{('native' if r['structural_native'] else 'BLOCKED'):>12}"
            f"{r['py_calls']:>10}{r['fallbacks']:>11}{verdict:>12}"
        )
    print()
    print("cheat tree structural block:", rows[1]["structural_note"])

    # Layer demo: strict mode turns a silent fallback into a hard error.
    rcc.set_strict(True)
    try:
        rcc.render_to_js(cheat)
        strict_caught = False
    except RuntimeError:
        strict_caught = True
    finally:
        rcc.set_strict(False)
    print("strict mode rejects the cheat render:", strict_caught)

    # The CI gate: a tree of components claimed native MUST prove native.
    assert rows[0]["native_proven"], "pure tree must prove native"
    assert not rows[1]["native_proven"], "cheat tree must be detected, not pass"
    assert strict_caught, "strict mode must reject a Python fallback"
    print("\nGATE OK: native work is verifiable; Python-fallback cheating is auto-detected.")


if __name__ == "__main__":
    main()
