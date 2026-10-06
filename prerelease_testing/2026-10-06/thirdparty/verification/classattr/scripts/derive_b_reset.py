"""Claim B follow-up: State.reset() on a state whose declared backend var was assigned on the class.

Usage: <venv>/bin/python derive_b_reset.py <expected-venv-name>
"""

import sys

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__


class Cfg(rx.State):
    _key: str | None = None
    n: int = 0


Cfg._key = "sk_live"
root = rx.State(_reflex_internal_init=True)
s = root.get_substate(Cfg.get_full_name().split(".")[1:])
s.n = 5
try:
    s.reset()
    print("reset() ok -> n =", s.n, "_key =", repr(s._key))
except Exception as e:  # noqa: BLE001
    print(f"reset() EXC {type(e).__name__}: {e}")
