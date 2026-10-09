"""A3-04 adapted to #7516: 8 threads x 1500 set/restore the FIELD default (no class assignment, no undo stack).
(1) set + restore-to-declared on the field (the original's shape): must end on the declared default, 0 errors.
(2) the same through mock.patch.object(field, 'default', v) (save/restore per thread) vs the same on a plain object:
    concurrent non-LIFO save/restore is plain-Python semantics; reflex must behave exactly like a plain attribute.
Run: EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_thread_fields.py
"""
import contextvars
import dataclasses
import os
import sys
import threading
from unittest import mock

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
print(f"python {sys.version.split()[0]} venv {os.environ['EXPECT_VENV']}")
MISSING = dataclasses.MISSING


class S(rx.State):
    count: int = 0
    _f: str = "d"


def run(worker, n=8):
    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    errs = []

    def wrap(i):
        try:
            worker(i)
        except Exception as e:  # noqa: BLE001
            errs.append(f"{type(e).__name__}: {e}")

    # each thread runs in a copy of the main context (RegistrationContext is a ContextVar; a bare thread has none)
    ts = [threading.Thread(target=contextvars.copy_context().run, args=(wrap, i)) for i in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    sys.setswitchinterval(old)
    return errs


fc, ff = S.__fields__["count"], S.__fields__["_f"]
seen_errors = []


def w1(i):
    for j in range(1500):
        fc.default = i * 10000 + j
        fc.default = 0
        ff.default, ff.default_factory = MISSING, (lambda v=f"{i}-{j}": v)
        ff.default_factory, ff.default = None, "d"
        try:
            S(_reflex_internal_init=True)  # concurrent instance creation may see a half-written pair
        except Exception as e:  # noqa: BLE001
            seen_errors.append(type(e).__name__)


errs = run(w1)
s = S(_reflex_internal_init=True)
print(f"(1) set/restore field default: errors={len(errs)} final count={s.count} _f={s._f!r} "
      f"field=({fc.default!r}, {ff.default!r}, {ff.default_factory}) want (0, 'd', None) | "
      f"instance creations that raised mid-update: {len(seen_errors)} {sorted(set(seen_errors))}")


class Plain:
    default = 0


def w2(target):
    def w(i):
        for j in range(1500):
            with mock.patch.object(target, "default", i * 10000 + j):
                pass
    return w


fc.default = 0
errs = run(w2(fc))
print(f"(2) mock.patch.object(field,'default') x8 threads: errors={len(errs)} final field default={fc.default!r} "
      f"fresh instance={S(_reflex_internal_init=True).count}")
p = Plain()
p.default = 0
errs = run(w2(p))
print(f"(2') same on a plain Python object attribute: errors={len(errs)} final={p.default!r}")
