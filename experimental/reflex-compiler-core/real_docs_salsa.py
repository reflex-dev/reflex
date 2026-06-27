"""Salsa-style page cache measured on the REAL Reflex docs app.

The docs app (docs/app) depends on five packages outside the root `reflex`
install. Three are in this repo and just need installing; two are not in the
repo and are stubbed (they're used minimally at compile time):

    uv pip install -e packages/reflex-site-shared -e packages/reflex-components-internal \
                   -e packages/integrations-docs
    uv pip install python-frontmatter email-validator fastapi openai orjson pandas \
                   plotly-express "psycopg[binary]" alembic requests ruff-format sqlalchemy sqlmodel

Stubbed (not in repo): reflex-enterprise (used only as `rxe.App` here) and
reflex-pyplot (one plotting doc). With the real `reflex-enterprise`, the 26
`enterprise/*` doc pages (rxe.ag_grid/ag_chart/dnd/mantine) also compile; the
other 391 content pages compile with the stubs.

Run from the docs app dir so rx.asset / rxconfig resolve:
    cd docs/app && PYTHONPATH=$PWD uv run --no-sync --project /home/user/reflex \
        python ../../experimental/reflex-compiler-core/real_docs_salsa.py

Measured (this sandbox): 417 routes, 391 compile; cold build 35.6 s
(~104 ms/page); no-op rebuild ~0.7 ms (48000x); edit-1-page ~65 ms (549x).
The cache invalidation here is route+version (synthetic); a real cache must
fingerprint each page's actual dependency set (doc file + page module +
shared templates/sidebar) — adding/removing a page changes the nav on every
page and must invalidate them all.
"""

import gc
import hashlib
import sys
import time
import types

import reflex as rx

_rxe = types.ModuleType("reflex_enterprise")
_rxe.App = rx.App
sys.modules["reflex_enterprise"] = _rxe
_pp = types.ModuleType("reflex_pyplot")


class _PyplotStub(rx.Component):
    library = "@stub/pyplot"
    tag = "Pyplot"


_pp.pyplot = _PyplotStub.create
sys.modules["reflex_pyplot"] = _pp

from reflex.compiler import compiler  # noqa: E402

app = __import__("reflex_docs.reflex_docs", fromlist=["app"]).app
app = getattr(app, "_app", app)
routes = list(app._unevaluated_pages)


def compile_route(route):
    ev = app._unevaluated_pages[route]
    comp = ev.component
    return compiler._compile_page(comp() if callable(comp) else comp)


edited: set[str] = set()


def fingerprint(route):
    return hashlib.sha256(f"{route}:v{2 if route in edited else 1}".encode()).hexdigest()


cache: dict[str, tuple[str, str]] = {}


def cached_build(only):
    hits = misses = 0
    for r in only:
        if cache.get(r, (None,))[0] == fingerprint(r):
            hits += 1
        else:
            cache[r] = (fingerprint(r), compile_route(r))
            misses += 1
    return hits, misses


def main():
    gc.collect()
    t0 = time.perf_counter()
    ok = []
    for r in routes:
        try:
            cache[r] = (fingerprint(r), compile_route(r))
            ok.append(r)
        except Exception:
            pass
    t_cold = time.perf_counter() - t0
    print(f"routes={len(routes)}  compiled={len(ok)}")
    print(f"cold build (all)      : {t_cold:6.2f} s  ({t_cold/max(len(ok),1)*1e3:.1f} ms/page)")

    gc.collect(); t = time.perf_counter(); h, m = cached_build(ok); dt = time.perf_counter() - t
    print(f"rebuild (no change)   : {dt*1e3:6.1f} ms  hits={h} miss={m}  ({t_cold/max(dt,1e-6):.0f}x)")

    global edited
    edited = {ok[len(ok) // 2]}
    gc.collect(); t = time.perf_counter(); h, m = cached_build(ok); dt = time.perf_counter() - t
    print(f"rebuild (edit 1 page) : {dt*1e3:6.1f} ms  hits={h} miss={m}  ({t_cold/max(dt,1e-6):.0f}x)")


if __name__ == "__main__":
    main()
