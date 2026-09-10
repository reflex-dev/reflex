"""Does a state var annotated with a class defined LATER in the module import? (both versions)"""
from __future__ import annotations
import sys, reflex
print(sys.version.split()[0], reflex.__file__)
import dataclasses
import reflex as rx
try:
    class S(rx.State):
        items: list[Later] = []  # noqa: F821
    @dataclasses.dataclass
    class Later:
        name: str
    print("RESULT: class creation OK")
except Exception as e:
    print("RESULT:", type(e).__name__, str(e)[:120])
