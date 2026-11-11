"""Issue 5: @staticmethod above @rx.event (and the reverse order) on a state and on a plain class.

usage (neutral cwd): EXPECT_VENV=$SB/envs/vevt-new $SB/envs/vevt-new/bin/python -I v5_staticmethod.py
"""
import os
import warnings

import reflex as rx

assert os.environ["EXPECT_VENV"] in rx.__file__, rx.__file__
from importlib.metadata import version

warnings.simplefilter("always")
print("reflex", version("reflex"))


class S(rx.State):
    @staticmethod
    @rx.event
    def static_over(x: int) -> int:
        return x * 2

    @rx.event
    @staticmethod
    def event_over(x: int) -> int:
        return x * 3

    @rx.event
    def uses_helper(self):
        print("  inside handler self.static_over(4) ->", type(self.static_over(4)).__name__)


class Helper:
    @staticmethod
    @rx.event
    def static_over(x: int) -> int:
        return x * 2


for label, call in [
    ("S.static_over(3)", lambda: S.static_over(3)),
    ("S.event_over(3)", lambda: S.event_over(3)),
    ("Helper.static_over(3)", lambda: Helper.static_over(3)),
    ("Helper().static_over(3)", lambda: Helper().static_over(3)),
]:
    try:
        r = call()
        print(f"{label:26s} -> {type(r).__name__}: {str(r)[:90]}")
    except Exception as ex:
        print(f"{label:26s} -> raises {type(ex).__name__}: {str(ex)[:90]}")
print("'static_over' in S.event_handlers:", "static_over" in S.event_handlers)
