"""`@rx.event` stacked on `@rx.event(background=True)` (as in reflex-examples overkey). Run: python -I stacked_event_probe.py <venv>"""
import sys, traceback
import reflex as rx
assert f"/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
try:
    class St(rx.State):
        @rx.event
        @rx.event(background=True)
        async def tick(self):
            pass
    print("OK: class defined;", type(St.tick).__name__, "background =", getattr(St.tick, "is_background", None))
except Exception as e:
    traceback.print_exc(limit=1)
    print("FAILED:", type(e).__name__, e)
