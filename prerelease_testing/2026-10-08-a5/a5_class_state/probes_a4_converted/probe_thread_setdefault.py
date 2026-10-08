"""A3-04 converted to Field.set_default (#7519): 8 threads x 1500 set_default + restore-to-declared, with concurrent
instance creation. Must end on the declared defaults with 0 errors. Run: EXPECT_VENV=<venv> python -I probe_thread_setdefault.py"""
import contextvars
import os
import sys
import threading

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
print(f"python {sys.version.split()[0]} venv {os.environ['EXPECT_VENV']}")


class S(rx.State):
    count: int = 0
    _f: str = "d"
    items: list[str] = ["decl"]


fc, ff, fi = S.__fields__["count"], S.__fields__["_f"], S.__fields__["items"]
bad = []


def w(i):
    for j in range(1500):
        fc.set_default(i * 10000 + j)
        fc.set_default(0)
        ff.set_default(default_factory=lambda v=f"{i}-{j}": v)
        ff.set_default("d")
        fi.set_default([f"{i}-{j}"])
        fi.set_default(["decl"])
        try:
            s = S(_reflex_internal_init=True)
            _ = (s.count, s._f, list(s.items))
        except Exception as e:  # noqa: BLE001
            bad.append(f"{type(e).__name__}: {e}")


old = sys.getswitchinterval()
sys.setswitchinterval(1e-6)
errs = []


def wrap(i):
    try:
        w(i)
    except Exception as e:  # noqa: BLE001
        errs.append(f"{type(e).__name__}: {e}")


ts = [threading.Thread(target=contextvars.copy_context().run, args=(wrap, i)) for i in range(8)]
[t.start() for t in ts]
[t.join() for t in ts]
sys.setswitchinterval(old)
s = S(_reflex_internal_init=True)
print(f"set_default stress: errors={len(errs)} {errs[:2]} instance errors={len(bad)} {sorted(set(bad))[:3]} | final count={s.count} "
      f"_f={s._f!r} items={list(s.items)} | fields: count=({fc.default!r},{fc.default_factory}) _f=({ff.default!r},{ff.default_factory}) "
      f"items.default={fi.default!r} | want 0 'd' ['decl']")
