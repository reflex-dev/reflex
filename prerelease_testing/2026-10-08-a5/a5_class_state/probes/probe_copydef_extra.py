"""Extra #7519 rows: add_var with a list populated later, module/engine defaults, ComponentState.create cost with a large
mutable class default. Run: EXPECT_VENV=<venv> python -I probe_copydef_extra.py"""
import json
import os
import time
from typing import Any

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

print("reflex", version("reflex"))


def row(name, fn):
    try:
        r = fn()
    except Exception as e:  # noqa: BLE001
        r = f"EXC {type(e).__name__}: {str(e)[:160]}"
    print(f"ROW {name} | {r}", flush=True)


def add_var_late():
    class AV(rx.State):
        a: int = 0

    LATE: list[str] = []
    AV.add_var("dyn", list[str], LATE)
    LATE.append("late")
    return f"add_var(list) then append -> instance {AV(_reflex_internal_init=True).dyn!r}"


row("add_var with a list populated afterwards", add_var_late)


def module_default():
    try:

        class MD(rx.State):
            _mod: Any = json

    except Exception as e:  # noqa: BLE001
        return f"FAIL@classdef {type(e).__name__}: {e}"
    try:
        return f"instance _mod is json={MD(_reflex_internal_init=True)._mod is json}"
    except Exception as e:  # noqa: BLE001
        return f"FAIL@instance {type(e).__name__}: {e}"


row("backend `_mod: Any = json` (module object default)", module_default)


def engine_default():
    import sqlalchemy

    try:

        class ED(rx.State):
            _engine: Any = sqlalchemy.create_engine("sqlite://")

    except Exception as e:  # noqa: BLE001
        return f"FAIL@classdef {type(e).__name__}: {e}"
    try:
        return f"instance engine ok {type(ED(_reflex_internal_init=True)._engine).__name__}"
    except Exception as e:  # noqa: BLE001
        return f"FAIL@instance {type(e).__name__}: {e}"


row("backend `_engine: Any = sqlalchemy.create_engine(...)`", engine_default)

BIG = list(range(200_000))


class BigCS(rx.ComponentState):
    rows: list[int] = BIG

    @classmethod
    def get_component(cls, **props):
        return rx.text(cls.rows.length())


def cs_cost():
    t0 = time.perf_counter()
    for _ in range(100):
        BigCS.create()
    t1 = time.perf_counter()
    return f"100 x ComponentState.create with a 200k-item list default: {1000 * (t1 - t0):.0f} ms"


row("ComponentState.create cost with large mutable class default", cs_cost)
