"""Spike: how much do Python-side caches speed a large project?

Two Salsa-style caches, measured against the real Reflex compile path
(`compiler._compile_page`) on a synthetic docs-like project (shared chrome +
per-page content), with no Rust involved:

  1. Component (construction) caching — build shared chrome (navbar/footer) once
     and reuse across pages, instead of rebuilding it per page.
  2. Page-level caching for hot reload — after a cold compile, an edit to one
     page recompiles only that page; the rest are served from cache.

Run:  uv run python experimental/reflex-compiler-core/spike_caching.py
"""

import gc
import time

import reflex as rx
from reflex.compiler import compiler

N_PAGES = 100
NAV_LINKS = 12
SIDEBAR_ITEMS = 40


def navbar():
    return rx.el.nav(
        *[rx.el.a(f"Link {i}", href=f"/l{i}", class_name="nav-link") for i in range(NAV_LINKS)],
        class_name="nav",
    )


def footer():
    return rx.el.footer(rx.el.p("(c) 2026"), rx.el.a("github", href="/gh"), class_name="ft")


def sidebar(active):
    return rx.el.aside(
        *[
            rx.el.a(f"Doc {i}", href=f"/d{i}", class_name="active" if i == active else "item")
            for i in range(SIDEBAR_ITEMS)
        ],
        class_name="side",
    )


def content(i):
    return rx.el.main(
        rx.el.h1(f"Page {i}"),
        *[rx.el.p(f"Paragraph {j} of page {i}", class_name="p") for j in range(15)],
        *[
            rx.el.div(
                rx.el.h2(f"Section {j}"),
                rx.el.ul(*[rx.el.li(f"item {k}") for k in range(5)]),
            )
            for j in range(4)
        ],
        class_name="content",
    )


def page(i, *, shared_navbar=None, shared_footer=None):
    nav = shared_navbar if shared_navbar is not None else navbar()
    ft = shared_footer if shared_footer is not None else footer()
    return rx.el.div(nav, sidebar(i), content(i), ft, class_name="layout")


def _t(fn):
    gc.collect(); gc.disable()
    t0 = time.perf_counter()
    out = fn()
    dt = time.perf_counter() - t0
    gc.enable()
    return dt, out


def cold_compile_no_cache():
    out = {}
    for i in range(N_PAGES):
        out[i] = compiler._compile_page(page(i))
    return out


def cold_compile_component_cache():
    # Build the fully-shared chrome once; reuse across all pages.
    nav = navbar()
    ft = footer()
    out = {}
    for i in range(N_PAGES):
        out[i] = compiler._compile_page(page(i, shared_navbar=nav, shared_footer=ft))
    return out


def main():
    # node count per page (for context)
    nodes = 2 + NAV_LINKS + 1 + SIDEBAR_ITEMS + 1 + (1 + 15 + 4 * (1 + 1 + 5)) + 1
    print(f"project: {N_PAGES} pages, ~{nodes} nodes/page (~{N_PAGES * nodes} total)\n")

    # warm caches/imports
    compiler._compile_page(page(0))

    t_cold, baseline = _t(cold_compile_no_cache)
    print(f"1) cold compile, no cache         : {t_cold*1e3:8.1f} ms  ({t_cold/N_PAGES*1e3:.2f} ms/page)")

    t_cc, cached = _t(cold_compile_component_cache)
    # correctness: reused-chrome output must equal fresh-chrome output
    same = all(baseline[i] == cached[i] for i in range(N_PAGES))
    print(f"2) cold compile, component cache  : {t_cc*1e3:8.1f} ms  ({t_cold/t_cc:.2f}x)   output identical: {same}")

    # 3) hot reload: all pages cached from a prior compile; edit ONE page.
    t_one, _ = _t(lambda: compiler._compile_page(page(7)))
    print(f"3) hot reload (recompile 1 page)  : {t_one*1e3:8.1f} ms  ({t_cold/t_one:.1f}x vs full cold)")

    # decompose one page: construction (build) vs compile (render+aggregate+template)
    t_build, comp = _t(lambda: page(50))
    t_comp, _ = _t(lambda: compiler._compile_page(comp))
    print(f"\nper-page breakdown: build={t_build*1e3:.2f} ms  compile(render+agg+tmpl)={t_comp*1e3:.2f} ms")
    print(f"  -> construction is {100*t_build/(t_build+t_comp):.0f}% of per-page cost")


if __name__ == "__main__":
    main()
