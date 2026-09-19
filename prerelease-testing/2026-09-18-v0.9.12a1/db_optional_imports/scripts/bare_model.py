import sys, traceback
import reflex as rx, reflex
assert "/envs/" in reflex.__file__, reflex.__file__
print("VERSION:", reflex.constants.Reflex.VERSION)
print("rx.Model is:", rx.Model)

def case(name, fn):
    print("\n--- CASE:", name, "---")
    try:
        r = fn()
        print("NO_ERROR ->", r)
    except BaseException as e:
        print("RAISED:", type(e).__name__)
        print("MSG:", str(e))

def c1():
    class Item(rx.Model, table=True):
        id: int
    return Item
case("subclass table=True", c1)

def c2():
    class Item2(rx.Model):
        id: int
    return Item2
case("plain subclass (no kwargs)", c2)

def c3():
    def f(x: "rx.Model") -> "rx.Model": return x
    ann = f.__annotations__
    return ann
case("annotation only (string)", c3)

def c4():
    def f(x: rx.Model): return x
    return f.__annotations__
case("annotation only (runtime expr)", c4)

def c5():
    return rx.Model()
case("rx.Model() instantiation", c5)

def c6():
    with rx.session() as s:
        return s
case("rx.session()", c6)

import asyncio
async def _a():
    async with rx.asession() as s:
        return s
def c7():
    return asyncio.run(_a())
case("rx.asession()", c7)

def c8():
    return rx.Model.__fields__
case("rx.Model.__fields__", c8)

def c9():
    class S(rx.State):
        m: rx.Model = None
    return S
case("State var annotated rx.Model", c9)
