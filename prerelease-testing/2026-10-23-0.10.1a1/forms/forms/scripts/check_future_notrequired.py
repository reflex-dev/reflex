"""Compile-time check: NotRequired fields (plain and inside Annotated) under
``from __future__ import annotations`` need no matching control (reflex-base #7386).

Run from a neutral dir with each venv's python; prints OK or the compile error.
"""
from __future__ import annotations

import sys
from typing import Annotated, NotRequired, TypedDict

import reflex
import reflex as rx

assert "/scratchpad/prt/envs/" in reflex.__file__, reflex.__file__


class Total(TypedDict):
    title: str
    nick: NotRequired[str]
    tags: Annotated[NotRequired[list[str]], "meta"]


class S(rx.State):
    @rx.event
    def h(self, form_data: Total):
        pass


try:
    rx.form(rx.input(name="title"), on_submit=S.h)
    print(sys.executable.split("/envs/")[1].split("/")[0], "OK: form with only 'title' compiles")
except Exception as e:
    print(sys.executable.split("/envs/")[1].split("/")[0], "ERROR:", str(e).replace("\n", " ")[:400])
