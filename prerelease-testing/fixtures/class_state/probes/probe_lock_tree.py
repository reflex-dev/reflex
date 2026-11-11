"""Does a state whose backend default cannot be deep-copied break the app on 0.9.12 / a4 / a5 when that state is
never used by the session? Run: EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_lock_tree.py"""
import os
import threading
import traceback
from typing import Any

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

print("reflex", version("reflex"))


class Used(rx.State):
    count: int = 0


try:

    class Unused(rx.State):
        _lock: Any = threading.Lock()

        @rx.event
        def go(self):
            with self._lock:
                pass

    print("STEP classdef ok")
except Exception as e:  # noqa: BLE001
    print("STEP classdef FAIL", type(e).__name__, e)
    traceback.print_exc(limit=-4)
    raise SystemExit(0)

try:
    root = rx.State(_reflex_internal_init=True)
    print("STEP root init ok; substates instantiated:", sorted(root.substates))
except Exception as e:  # noqa: BLE001
    print("STEP root init FAIL", type(e).__name__, e)
    raise SystemExit(0)
try:
    u = root.substates[Used.get_name()]
    u.count += 1
    print("STEP Used works", u.count)
except Exception as e:  # noqa: BLE001
    print("STEP Used FAIL", type(e).__name__, e)
try:
    s = root.substates.get(Unused.get_name()) or Unused(_reflex_internal_init=True)
    s._lock
    print("STEP Unused._lock access ok")
except Exception as e:  # noqa: BLE001
    print("STEP Unused._lock access FAIL", type(e).__name__, e)
