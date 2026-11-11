"""`@rx.event` stacked on `@rx.event(...)` (as in reflex-examples overkey `tick`). Run: python -I stacked_event_probe.py <venv>"""
import sys
import traceback

import reflex as rx

assert f"/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__


def report(label, build):
    try:
        cls = build()
        print(f"[ok ] {label}: class defined; type={type(cls.tick).__name__}")
    except Exception as e:  # noqa: BLE001
        tb = traceback.extract_tb(e.__traceback__)[-1]
        print(f"[ERR] {label}: {type(e).__name__}: {e}  (raised at {tb.filename.split('site-packages/')[-1]}:{tb.lineno})")


def v1():
    class St1(rx.State):
        @rx.event
        @rx.event(background=True)
        async def tick(self):
            pass

    return St1


def v2():
    class St2(rx.State):
        @rx.event
        @rx.event
        def tick(self):
            pass

    return St2


def v3():
    class St3(rx.State):
        @rx.event(background=True)
        @rx.event
        async def tick(self):
            pass

    return St3


def v4():
    class St4(rx.State):
        @rx.event(background=True)
        async def tick(self):
            pass

    return St4


report("@rx.event over @rx.event(background=True)  [overkey]", v1)
report("@rx.event over @rx.event", v2)
report("@rx.event(background=True) over @rx.event", v3)
report("single @rx.event(background=True)", v4)
