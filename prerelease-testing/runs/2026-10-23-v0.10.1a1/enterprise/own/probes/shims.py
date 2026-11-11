"""ENT-01 / ENT-02 / CLI-03: deprecated shims still work and warn.

Usage: EXPECT_VENV=<venv> <venv>/bin/python -I shims.py
"""
import os, warnings, io, contextlib
import reflex
assert f"/envs/{os.environ['EXPECT_VENV']}/" in reflex.__file__, reflex.__file__
from reflex_base.utils import console
results = {}
def run(label, fn):
    buf = io.StringIO()
    with warnings.catch_warnings(record=True) as w, contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        warnings.simplefilter("always")
        try:
            r = fn()
            ok = True
        except Exception as e:  # noqa: BLE001
            r = f"{type(e).__name__}: {e}"
            ok = False
    results[label] = (ok, repr(r)[:160], [f"{x.category.__name__}: {x.message}" for x in w], buf.getvalue().strip()[:300])
def ent01():
    from reflex.components import dynamic
    return type(dynamic.bundled_libraries).__name__, len(dynamic.bundled_libraries)
def ent01b():
    from reflex.components.dynamic import bundled_libraries
    return type(bundled_libraries).__name__
def ent02():
    from reflex.page import DECORATED_PAGES
    return type(DECORATED_PAGES).__name__
def cli03():
    from reflex.config import get_config
    c = get_config(reload=True)
    return type(c).__name__
def cli03b():
    from reflex.config import get_config
    return type(get_config()).__name__
def rxe_bundled():
    from reflex_enterprise.vars import get_bundled_libraries
    return sorted(get_bundled_libraries())[:5]
for label, fn in [("ENT-01 dynamic.bundled_libraries", ent01), ("ENT-01 from-import", ent01b), ("ENT-02 reflex.page.DECORATED_PAGES", ent02), ("CLI-03 get_config(reload=True)", cli03), ("get_config() plain", cli03b), ("rxe get_bundled_libraries", rxe_bundled)]:
    run(label, fn)
for k, (ok, r, w, printed) in results.items():
    print(f"{'ok ' if ok else 'ERR'} {k}: value={r} warnings={w} printed={printed!r}")
