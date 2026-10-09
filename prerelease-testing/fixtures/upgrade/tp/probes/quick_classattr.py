"""Class-level access to underscore (backend) state attributes: value on 0.9.12, Field on 0.10.0a1.

Usage: <venv>/bin/python quick_classattr.py <expected-venv-name>
"""
import sys

import reflex as rx

assert f"/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__


class S(rx.State):
    _KEY = "label"
    _N = 16
    _D = {"a": 1}
    _ann: str = "x"

    @classmethod
    def show(cls):
        return (cls._KEY, cls._N, cls._D, cls._ann)


print("class-level:", [repr(x) for x in S.show()])
try:
    print("rx.text(S._KEY):", str(rx.text(S._KEY))[:120])
except Exception as e:  # noqa: BLE001
    print(f"rx.text(S._KEY): EXC {type(e).__name__}: {str(e)[:200]}")
try:
    print("rx.icon('x', size=S._N):", str(rx.icon("x", size=S._N))[:80])
except Exception as e:  # noqa: BLE001
    print(f"rx.icon('x', size=S._N): EXC {type(e).__name__}: {str(e)[:200]}")
