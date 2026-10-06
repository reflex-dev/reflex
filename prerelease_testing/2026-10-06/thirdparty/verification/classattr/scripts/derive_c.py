"""Claim C: what each BaseContext subclass raises from .get() outside a context.

Usage: <venv>/bin/python derive_c.py <expected-venv-name>
"""

import sys

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
from reflex_base.event.context import EventContext  # noqa: E402
from reflex_base.plugins.compiler import CompileContext, PageContext  # noqa: E402

for ctx in (PageContext, CompileContext, EventContext):
    try:
        ctx.get()
        print(f"{ctx.__name__}.get(): no error")
    except Exception as e:  # noqa: BLE001
        print(f"{ctx.__name__}.get(): {type(e).__name__}: {e}")
