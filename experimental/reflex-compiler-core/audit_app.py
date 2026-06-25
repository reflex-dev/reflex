"""Audit a real Reflex app against the Rust compiler core.

This is the docs-app acceptance harness. Run it in an environment where the app
imports (the docs app needs its private deps: reflex-enterprise, reflex-site-
shared, etc.). It does two things:

  1. COMPONENT HISTOGRAM — hooks `Component.create` and tallies every component
     type the app instantiates. This is the ranked porting work-list for the
     native (make_node) path.
  2. CODEGEN DIFFERENTIAL (Stage A) — for every page, compares the Rust
     `render_dict_to_js(page.render())` against the Python
     `_RenderUtils.render(page.render())` byte-for-byte. This proves the Rust
     codegen reproduces the real app's output (cond/foreach/match/markdown
     included) without porting a single component.

Usage:
    PYTHONPATH=docs/app \
      uv run python experimental/reflex-compiler-core/audit_app.py \
        --module reflex_docs.reflex_docs

Exit code is non-zero if any page's codegen diverges.
"""

import argparse
import collections
import importlib
import sys
import traceback

import reflex_compiler_core as rcc
from reflex_base.components.component import Component
from reflex_base.compiler.templates import _RenderUtils


def install_histogram():
    """Wrap Component.create to tally instantiated types; return the counter."""
    counts = collections.Counter()
    original = Component.create.__func__

    def create(cls, *args, **kwargs):
        counts[cls.__name__] += 1
        return original(cls, *args, **kwargs)

    Component.create = classmethod(create)
    return counts


def get_app(module_path):
    mod = importlib.import_module(module_path)
    app = mod.app
    # rxe.App / wrappers expose the underlying reflex App as ._app.
    return getattr(app, "_app", app)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", required=True, help="import path exposing `app`")
    parser.add_argument("--max-mismatch", type=int, default=5)
    args = parser.parse_args()

    counts = install_histogram()
    app = get_app(args.module)
    routes = list(app._unevaluated_pages)
    print(f"routes registered: {len(routes)}\n")

    eval_ok = eval_err = 0
    pages_matched = pages_diverged = 0
    shown = 0
    for route in routes:
        try:
            unevaluated = app._unevaluated_pages[route]
            comp = unevaluated.component
            tree = comp() if callable(comp) else comp
            render_dict = tree.render()
            eval_ok += 1
        except Exception:
            eval_err += 1
            continue
        try:
            slow = _RenderUtils.render(render_dict)
            fast = rcc.render_dict_to_js(render_dict)
        except Exception:
            pages_diverged += 1
            if shown < args.max_mismatch:
                shown += 1
                print(f"[render error] {route}\n{traceback.format_exc()}")
            continue
        if slow == fast:
            pages_matched += 1
        else:
            pages_diverged += 1
            if shown < args.max_mismatch:
                shown += 1
                # Find the first differing offset for a focused diff.
                i = next((k for k in range(min(len(slow), len(fast))) if slow[k] != fast[k]), 0)
                print(f"[MISMATCH] {route} at offset {i}")
                print(f"  slow: ...{slow[max(0, i - 40):i + 60]!r}")
                print(f"  fast: ...{fast[max(0, i - 40):i + 60]!r}\n")

    print("\n=== CODEGEN DIFFERENTIAL (Stage A) ===")
    print(f"pages evaluated: ok={eval_ok} err={eval_err}")
    print(f"codegen: matched={pages_matched} diverged={pages_diverged}")

    print("\n=== COMPONENT HISTOGRAM (Stage B porting work-list) ===")
    total = sum(counts.values())
    print(f"distinct types: {len(counts)}   total instantiations: {total}")
    cumulative = 0
    for name, c in counts.most_common(40):
        cumulative += c
        print(f"{c:8d}  {100 * cumulative / total:5.1f}% cum  {name}")

    sys.exit(1 if pages_diverged else 0)


if __name__ == "__main__":
    main()
