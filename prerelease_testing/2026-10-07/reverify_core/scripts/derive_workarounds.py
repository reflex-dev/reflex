"""Workarounds for claims A/B: ClassVar statics and get_fields()[name].default_value().

Usage: <venv>/bin/python derive_workarounds.py <expected-venv-name>
"""

import pickle
import sys
from typing import ClassVar

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__


class W(rx.State):
    _KEY: ClassVar[str | None] = None
    _backend: str = "declared-default"


W._KEY = "configured"
root = rx.State(_reflex_internal_init=True)
inst = root.get_substate(W.get_full_name().split(".")[1:])
inst2 = pickle.loads(pickle.dumps(inst))
print("ClassVar: class", repr(W._KEY), "| fresh", repr(inst._KEY), "| pickled", repr(inst2._KEY), "| is field:", "_KEY" in W.get_fields())
print("get_fields()['_backend'].default_value():", repr(W.get_fields()["_backend"].default_value()))
print("rx.text(W._KEY):", str(rx.text(W._KEY))[-40:])
