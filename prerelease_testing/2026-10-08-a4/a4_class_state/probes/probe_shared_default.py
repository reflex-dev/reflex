"""Docs claim (base_vars.md): 'A `default` is shared by every instance, so give a mutable default a default_factory'.
Run: EXPECT_VENV=a4_class_state-a4 $SB/envs/a4_class_state-a4/bin/python -I probe_shared_default.py"""
import os

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__


class W(rx.State):
    symbols: list[str] = []


shared = ["AAPL"]
W.__fields__["symbols"].default = shared
a, b = W(_reflex_internal_init=True), W(_reflex_internal_init=True)
a.symbols.append("MSFT")
print("a:", list(a.symbols), "b:", list(b.symbols), "shared obj:", shared, "| a.__dict__ value is shared:", a.__dict__.get("symbols") is shared)
c = W(_reflex_internal_init=True)
print("new instance after mutation:", list(c.symbols))
a.reset()
print("after a.reset():", list(a.symbols))
