"""Define one state class per decorator-stacking pattern and report what happens at class creation.

usage (from a neutral cwd): EXPECT_VENV=$SB/envs/new $SB/envs/new/bin/python -I deco_matrix.py
"""
import asyncio
import functools
import io
import os
import sys
import contextlib

import reflex as rx

assert os.environ["EXPECT_VENV"] in rx.__file__, rx.__file__
from importlib.metadata import version

print("reflex", version("reflex"))


def logged(fn):
    @functools.wraps(fn)
    def wrapper(self, *a, **k):
        return fn(self, *a, **k)

    return wrapper


def alogged(fn):
    @functools.wraps(fn)
    async def wrapper(self, *a, **k):
        return await fn(self, *a, **k)

    return wrapper


def no_wraps(fn):
    def inner(self, *a, **k):
        return fn(self, *a, **k)

    return inner


PATTERNS = {
    "event": lambda f: rx.event(f),
    "event / logged": lambda f: rx.event(logged(f)),
    "logged / event": lambda f: logged(rx.event(f)),
    "no_wraps / event": lambda f: no_wraps(rx.event(f)),
    "event / event": lambda f: rx.event(rx.event(f)),
    "event / event(background=True)  [overkey]": lambda f: rx.event(rx.event(background=True)(f)),
    "event(background=True) / event": lambda f: rx.event(background=True)(rx.event(f)),
    "event / event(throttle=300)": lambda f: rx.event(rx.event(throttle=300)(f)),
    "event(throttle=300) / event": lambda f: rx.event(throttle=300)(rx.event(f)),
    "event(background=True) / alogged": lambda f: rx.event(background=True)(alogged(f)),
    "alogged / event(background=True)": lambda f: alogged(rx.event(background=True)(f)),
    "logged / event(background=True)": lambda f: logged(rx.event(background=True)(f)),
    "staticmethod / event": lambda f: staticmethod(rx.event(f)),
    "event / staticmethod": lambda f: rx.event(staticmethod(f)),
    "classmethod / event": lambda f: classmethod(rx.event(f)),
    "event / classmethod": lambda f: rx.event(classmethod(f)),
    "functools.partialmethod(event)": lambda f: functools.partialmethod(rx.event(f), 1),
    "property / event": lambda f: property(rx.event(f)),
}

for i, (label, deco) in enumerate(PATTERNS.items()):
    buf = io.StringIO()
    result = ""
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            ns = {"__module__": __name__, "__qualname__": f"S{i}"}

            async def h(self, v: int = 0):
                return None

            h.__qualname__ = f"S{i}.h"
            ns["h"] = deco(h)
            cls = type(rx.State)(f"S{i}", (rx.State,), ns)
            eh = cls.event_handlers.get("h")
            attr = cls.__dict__.get("h")
            result = (
                f"ok class-attr={type(attr).__name__} registered={'h' in cls.event_handlers}"
                + (f" fn={type(eh.fn).__name__} bg={eh.is_background} actions={eh.event_actions}" if eh else "")
            )
        except Exception as ex:
            result = f"FAILS at class creation: {type(ex).__name__}: {str(ex)[:110]}"
    warn = " ".join(buf.getvalue().split())
    print(f"- {label:44s} {result}")
    if warn:
        print(f"    warning: {warn[:230]}")
