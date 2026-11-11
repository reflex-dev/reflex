"""Probe: one substate whose __init__ fails -> does every later root State() fail in the process?

Usage: python initfail_probe.py <venv-name> <dev|prod> <undeclared|valueerror|dunder>
"""
import json
import os
import sys

venv, mode, kind = sys.argv[1], sys.argv[2], sys.argv[3]
os.environ["REFLEX_ENV_MODE"] = mode
import reflex as rx  # noqa: E402

assert f"/envs/{venv}/" in rx.__file__, rx.__file__
import importlib.metadata  # noqa: E402

from reflex.state import State  # noqa: E402

res = {"venv": venv, "mode": mode, "kind": kind, "version": importlib.metadata.version("reflex")}


def try_root(label):
    try:
        State(_reflex_internal_init=True)
        res[label] = "ok"
    except Exception as e:  # noqa: BLE001
        res[label] = f"{type(e).__name__}: {str(e)[:160]}"


class Healthy(rx.State):
    x: int = 1


try_root("root_before_bad_class")


class BadInit(rx.State):
    y: int = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if kind == "undeclared":
            self._init_ran = True          # undeclared backend name
        elif kind == "dunder":
            self.__init_ran = True         # mangled private name (#7465 makes this a plain attribute)
        else:
            raise ValueError("init boom")


try_root("root_after_bad_class_1")
try_root("root_after_bad_class_2")


class LaterHealthy(rx.State):
    z: int = 2


try_root("root_after_later_healthy")
print(json.dumps(res))
