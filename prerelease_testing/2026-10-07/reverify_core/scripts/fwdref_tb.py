"""Traceback for a state annotation naming a not-yet-defined class (lazy on 3.14 / postponed via __future__)."""
import sys
import traceback

import reflex as rx

assert sys.argv[1] in rx.__file__, rx.__file__
mode = sys.argv[2]
src_lazy = '''
import reflex as rx
class LazyState(rx.State):
    item: Later | None = None
'''
src_future = '''
from __future__ import annotations
import reflex as rx
class FutState(rx.State):
    item: Later | None = None
'''
try:
    exec(compile(src_lazy if mode == "lazy" else src_future, f"<user_module_{mode}>", "exec"), {"__name__": f"user_{mode}"})
    print(mode, "OK (no error)")
except Exception as e:  # noqa: BLE001
    tb = traceback.extract_tb(e.__traceback__)
    print(mode, "->", f"{type(e).__name__}: {e}")
    for fr in tb[-4:]:
        print("    at", fr.filename.split("site-packages/")[-1], fr.lineno, fr.name)
