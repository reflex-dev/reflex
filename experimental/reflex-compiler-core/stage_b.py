"""Stage B: native registry-driven element construction, verified + purity-gated.

Proves, against public Reflex (no private deps), that building the docs-app's
dominant node types (rx.el.* elements) natively via the Rust registry:
  - is byte-identical to Component.create + _RenderUtils (incl. multi-prop
    sorting, id->ref, nesting, and cond/foreach subtrees), and
  - is purity-accounted: pure element trees render GIL-released with 0
    fallbacks; trees whose cond/foreach construction stays in Python are
    correctly flagged as codegen-native-but-not-build-native.

Run:  uv run python experimental/reflex-compiler-core/stage_b.py
"""

import gc
import sys
import time

import reflex as rx
import reflex_compiler_core as rcc
from reflex_base.compiler.templates import _RenderUtils

import fastnodes as fast

el = fast.el


class S(rx.State):
    flag: bool = True
    items: list[str] = ["a", "b", "c"]


def slow_js(component):
    return _RenderUtils.render(component.render())


def equivalence():
    """Byte-identical output across the shapes the docs app uses.

    Each case is (slow_fn, fast_fn). Native elements use `el`; cond/foreach are
    Python constructs and keep `rx.el` children (they cannot take NodeHandles),
    embedding as RawDict subtrees under a native parent — the real mixed tree.
    """
    cases = {
        "multi-prop sort": (
            lambda: rx.el.div(hidden=True, class_name="c", lang="en", id="z"),
            lambda: el.div(hidden=True, class_name="c", lang="en", id="z"),
        ),
        "id->ref": (
            lambda: rx.el.span("hi", id="s1", class_name="x"),
            lambda: el.span("hi", id="s1", class_name="x"),
        ),
        "nested+text": (
            lambda: rx.el.div(
                rx.el.h1("Title", class_name="hd"),
                rx.el.ul(rx.el.li("one"), rx.el.li("two")),
                class_name="root", id="main",
            ),
            lambda: el.div(
                el.h1("Title", class_name="hd"),
                el.ul(el.li("one"), el.li("two")),
                class_name="root", id="main",
            ),
        ),
        "native parent + cond child": (
            lambda: rx.el.div(rx.cond(S.flag, rx.el.span("yes"), rx.el.span("no")), class_name="w"),
            lambda: el.div(rx.cond(S.flag, rx.el.span("yes"), rx.el.span("no")), class_name="w"),
        ),
        "native parent + foreach child": (
            lambda: rx.el.div(rx.foreach(S.items, lambda x: rx.el.li(x)), class_name="list"),
            lambda: el.div(rx.foreach(S.items, lambda x: rx.el.li(x)), class_name="list"),
        ),
    }
    all_ok = True
    for name, (slow_fn, fast_fn) in cases.items():
        slow = slow_js(slow_fn())
        fastjs = rcc.render_to_js(fast_fn())
        ok = slow == fastjs
        all_ok &= ok
        print(f"  {name:30} {'OK' if ok else 'MISMATCH'}")
        if not ok:
            i = next((k for k in range(min(len(slow), len(fastjs))) if slow[k] != fastjs[k]), 0)
            print(f"    slow: ...{slow[max(0,i-30):i+50]!r}")
            print(f"    fast: ...{fastjs[max(0,i-30):i+50]!r}")
    return all_ok


def purity():
    """Pure element trees prove native; cond/foreach subtrees are flagged."""
    # The fallback ledger counts non-native subtrees at BUILD time, so reset
    # before constructing each tree.
    rcc.reset_fallback_count()
    pure_tree = el.div(el.h1("T", class_name="h"), el.span("x"), class_name="r")
    pure_fallbacks = rcc.py_fallback_count()
    pure_ok = True
    try:
        rcc.render_to_js_pure(pure_tree)
    except RuntimeError:
        pure_ok = False

    rcc.reset_fallback_count()
    mixed_tree = el.div(rx.cond(S.flag, rx.el.span("y"), rx.el.span("n")), class_name="r")
    mixed_fallbacks = rcc.py_fallback_count()
    mixed_pure = True
    try:
        rcc.render_to_js_pure(mixed_tree)
    except RuntimeError:
        mixed_pure = False

    print(f"  pure element tree : GIL-pure={pure_ok}  fallbacks={pure_fallbacks}  -> {'BUILD-NATIVE' if pure_ok and pure_fallbacks==0 else 'NOT'}")
    print(f"  tree with cond    : GIL-pure={mixed_pure}  fallbacks={mixed_fallbacks}  -> codegen-native, construction still Python")
    return pure_ok and pure_fallbacks == 0 and not mixed_pure and mixed_fallbacks > 0


def _time(fn, iters=5):
    gc.collect(); gc.disable()
    best = float("inf")
    for _ in range(iters):
        t0 = time.perf_counter(); fn(); best = min(best, time.perf_counter() - t0)
    gc.enable()
    return best


def benchmark():
    n = 2000

    def build(M):
        rows = [
            M.div(
                M.h1(f"T{i}", class_name="hd"),
                M.ul(M.li("a"), M.li("b")),
                class_name="row", id=f"r{i}",
            )
            for i in range(n)
        ]
        return M.div(*rows, class_name="root")

    t_slow = _time(lambda: build(rx.el))
    t_fast = _time(lambda: build(el))
    assert slow_js(build(rx.el)) == rcc.render_to_js(build(el)), "scale mismatch"
    nodes = n * 6
    print(f"  {n} rows (~{nodes} element nodes), best of 5")
    print(f"  construction   slow={t_slow*1e3:8.2f} ms   fast={t_fast*1e3:8.2f} ms   {t_slow/t_fast:5.1f}x")


def main():
    print("equivalence (byte-identical vs Component.create + _RenderUtils):")
    eq = equivalence()
    print("\npurity accounting:")
    pu = purity()
    print("\nbenchmark (registry make vs Component.create):")
    benchmark()
    assert eq, "equivalence failed"
    assert pu, "purity accounting failed"
    print("\nSTAGE B OK: native element construction is byte-identical and purity-verified.")


if __name__ == "__main__":
    sys.exit(main())
