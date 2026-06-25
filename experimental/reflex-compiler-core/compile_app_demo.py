"""Compile a REAL Reflex page end-to-end, with Rust doing the JSX codegen.

Micro-benchmarks measure construction + render. But "compiling an app" is
`compile_app`: per page it aggregates imports/hooks/custom-code from the whole
tree, then `page_template(...)` wraps the JSX into a full module
(`import ...; export function Page() { ...hooks...; return (<jsx>) }`).

The Rust piece we built (`render_dict_to_js`) is exactly the one codegen call
(`_RenderUtils.render`) used inside that template. This script swaps it into the
real pipeline (`reflex.compiler.compiler._compile_page`) on a real page with
state, an event handler, and a cond — and asserts the FULL page module is
byte-identical to the stock compiler. Everything else (imports/hooks
aggregation, the template, file writing) stays Python and is unchanged.

Run:  uv run python experimental/reflex-compiler-core/compile_app_demo.py
"""

import reflex as rx
import reflex_compiler_core as rcc
from reflex.compiler import compiler
from reflex_base.compiler import templates


class S(rx.State):
    count: int = 0
    name: str = "world"

    def inc(self):
        self.count += 1


def page():
    return rx.el.div(
        rx.el.h1("Hello"),
        rx.el.p(S.name, class_name="greet"),
        rx.el.button("inc", on_click=S.inc, class_name="btn"),
        rx.cond(S.count > 0, rx.el.span("positive"), rx.el.span("zero")),
        class_name="container",
        id="root",
    )


def compile_with(render_fn):
    """Compile the page with `_RenderUtils.render` swapped to render_fn."""
    original = templates._RenderUtils.render
    templates._RenderUtils.render = staticmethod(render_fn)
    try:
        return compiler._compile_page(page())
    finally:
        templates._RenderUtils.render = original


def main():
    stock_render = templates._RenderUtils.render
    stock = compile_with(stock_render)
    rust = compile_with(lambda c: rcc.render_dict_to_js(c))

    print("=== Full compiled page module (Rust codegen) ===\n")
    print(rust)
    print("\n" + "=" * 70)
    print("full page module byte-identical (stock vs Rust codegen):", stock == rust)
    if stock != rust:
        i = next((k for k in range(min(len(stock), len(rust))) if stock[k] != rust[k]), 0)
        print(f"  first diff at {i}:\n  stock: ...{stock[max(0,i-40):i+60]!r}\n  rust:  ...{rust[max(0,i-40):i+60]!r}")
    assert stock == rust, "page module diverged"
    print("\nReal page compiled end-to-end with Rust codegen — imports, hooks, and")
    print("template are Python; the JSX expression was produced by render_dict_to_js.")


if __name__ == "__main__":
    main()
