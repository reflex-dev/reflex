"""Issue 1: each double-@rx.event stacking pattern written as normal class syntax, one class per pattern.

usage (neutral cwd): EXPECT_VENV=$SB/envs/vevt-new $SB/envs/vevt-new/bin/python -I v1_double_event.py
"""
import os
import sys
import traceback
import warnings

import reflex as rx

assert os.environ["EXPECT_VENV"] in rx.__file__, rx.__file__
from importlib.metadata import version

print("reflex", version("reflex"), sys.version.split()[0])
warnings.simplefilter("always")


def make(label):
    ns = {}
    src = {
        "event/event": "class A(rx.State):\n    v: int = 0\n    @rx.event\n    @rx.event\n    def h(self, x: int):\n        self.v += x\n",
        "event/event(background=True)": "class B(rx.State):\n    v: int = 0\n    @rx.event\n    @rx.event(background=True)\n    async def h(self):\n        async with self:\n            self.v += 1\n",
        "event/event(throttle=300)": "class C(rx.State):\n    v: int = 0\n    @rx.event\n    @rx.event(throttle=300)\n    def h(self):\n        self.v += 1\n",
        "event(background=True)/event": "class D(rx.State):\n    v: int = 0\n    @rx.event(background=True)\n    @rx.event\n    async def h(self):\n        async with self:\n            self.v += 1\n",
        "event(throttle=300)/event": "class E(rx.State):\n    v: int = 0\n    @rx.event(throttle=300)\n    @rx.event\n    def h(self):\n        self.v += 1\n",
        "event()/event": "class F(rx.State):\n    v: int = 0\n    @rx.event()\n    @rx.event\n    def h(self):\n        self.v += 1\n",
    }[label]
    try:
        exec(src, {"rx": rx, "__name__": "m_" + label.replace("/", "_").replace("(", "").replace(")", "").replace("=", "").replace(",", "")}, ns)
        cls = next(iter(ns.values()))
        eh = cls.event_handlers.get("h")
        return f"OK registered={eh is not None} bg={getattr(eh, 'is_background', None)} actions={getattr(eh, 'event_actions', None)}"
    except Exception as ex:
        tb = traceback.extract_tb(ex.__traceback__)[-1]
        return f"FAIL {type(ex).__name__}: {str(ex)[:100]}  @ {os.path.relpath(tb.filename, os.path.dirname(os.path.dirname(rx.__file__)))}:{tb.lineno}"


for label in ["event/event", "event/event(background=True)", "event/event(throttle=300)",
              "event(background=True)/event", "event(throttle=300)/event", "event()/event"]:
    print(f"{label:32s} {make(label)}")
