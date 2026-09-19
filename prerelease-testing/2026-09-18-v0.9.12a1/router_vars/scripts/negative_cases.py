"""Negative/compile-time cases for #7068 / #7077 / #7136.

Run with the venv whose reflex you want to probe, from a NEUTRAL cwd:
    cd $SB/apps/router_vars && $SB/envs/shared/bin/python scripts/negative_cases.py
"""

import sys
import traceback

import reflex as rx

assert "/envs/" in rx.__file__, f"WRONG REFLEX: {rx.__file__}"
print(f"reflex from: {rx.__file__}")
try:
    import importlib.metadata as md

    print("reflex version:", md.version("reflex"))
except Exception as e:  # noqa: BLE001
    print("version unknown", e)
print("=" * 70)

RESULTS = []


def case(name):
    def deco(fn):
        print(f"\n### {name}")
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            tb = traceback.format_exc().strip().splitlines()
            print(f"  RAISED {type(e).__name__}: {e}")
            RESULTS.append((name, type(e).__name__, str(e)))
        else:
            print("  NO EXCEPTION (class created)")
            RESULTS.append((name, None, ""))
        return fn

    return deco


# ---- #7068: reserved rx_router_* names on a substate --------------------
@case("substate declares rx_router_url: str")
def _():
    class P1(rx.State):
        a: int = 0

    class C1(P1):
        rx_router_url: str = "x"

    print("   C1.rx_router_url repr:", repr(C1.rx_router_url))


@case("substate declares rx_router_session: dict")
def _():
    class P1b(rx.State):
        a: int = 0

    class C1b(P1b):
        rx_router_session: dict = {}


@case("substate declares rx_router_page / headers / route_id")
def _():
    class P1c(rx.State):
        a: int = 0

    class C1c(P1c):
        rx_router_page: str = ""
        rx_router_headers: str = ""
        rx_router_route_id: str = ""


@case("substate declares a base var named 'router'")
def _():
    class P1d(rx.State):
        a: int = 0

    class C1d(P1d):
        router: str = "nope"


@case("computed var named 'router'")
def _():
    class C2(rx.State):
        @rx.var
        def router(self) -> str:
            return "nope"


# ---- #7077: shadowing a parent's base var --------------------------------
@case("substate shadows parent base var (int -> str) [issue 7074 repro]")
def _():
    class Parent3(rx.State):
        x: int = 1

    class Child3(Parent3):
        x: str = "ninety-nine"

    print("   Child3.x repr:", repr(Child3.x), type(Child3.x).__name__)
    print("   is Var?", isinstance(Child3.x, rx.Var))


@case("substate shadows parent base var (same type/default)")
def _():
    class Parent3b(rx.State):
        count: int = 0

    class Child3b(Parent3b):
        count: int = 0

    print("   Child3b.count repr:", repr(Child3b.count), type(Child3b.count).__name__)


@case("grandchild shadows grandparent base var")
def _():
    class GP(rx.State):
        val: int = 1

    class Mid(GP):
        other: int = 2

    class GC(Mid):
        val: int = 5


@case("substate shadows inherited 'is_hydrated' from root State")
def _():
    class C3c(rx.State):
        is_hydrated: bool = False


@case("substate shadows a parent BACKEND var (_x)")
def _():
    class Parent3d(rx.State):
        _priv: int = 1

    class Child3d(Parent3d):
        _priv: str = "shadow"

    print("   Child3d backend vars:", list(Child3d.backend_vars))


# ---- #7136: reserved framework names -------------------------------------
RESERVED_VAR_NAMES = [
    "dirty_vars",
    "get_delta",
    "process",
    "router_data",
    "parent_state",
    "substates",
    "get_value",
    "dict",
    "set",
    "get_fields",
    "_get_was_touched",
    "_update_was_touched",
    "setvar",
    "reset",
    "get_name",
    "json",
]

for _n in RESERVED_VAR_NAMES:

    @case(f"state var named {_n!r}")
    def _(n=_n):
        ns = {"__annotations__": {n: int}, n: 0}
        type(f"RV_{n.strip('_')}", (rx.State,), ns)


for _n in ["dirty_vars", "process", "get_delta", "set", "dict", "reset", "setvar"]:

    @case(f"event handler named {_n!r}")
    def _(n=_n):
        def handler(self):
            self.a = 1

        handler.__name__ = n
        ns = {"__annotations__": {"a": int}, "a": 0, n: rx.event(handler)}
        type(f"EH_{n.strip('_')}", (rx.State,), ns)


# ---- dynamic route args ---------------------------------------------------
@case("dynamic route arg named 'router'")
def _():
    app = rx.App()

    def pg():
        return rx.text("x")

    app.add_page(pg, route="/dyn/[router]")


@case("dynamic route arg named 'state'")
def _():
    app = rx.App()

    def pg2():
        return rx.text("x")

    app.add_page(pg2, route="/dyn2/[state]")


@case("dynamic route arg named 'dirty_vars'")
def _():
    app = rx.App()

    def pg3():
        return rx.text("x")

    app.add_page(pg3, route="/dyn3/[dirty_vars]")


@case("dynamic route arg named 'rx_router_url'")
def _():
    app = rx.App()

    def pg4():
        return rx.text("x")

    app.add_page(pg4, route="/dyn4/[rx_router_url]")


print("\n" + "=" * 70)
print("SUMMARY")
for name, exc, msg in RESULTS:
    print(f"{'RAISE' if exc else 'ok   '} | {name} | {exc or ''} | {msg[:170]}")
