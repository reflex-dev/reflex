"""Probe the 0.9.12a1 state-declaration breaking changes (#7068/#7077/#7136)."""
import os
import reflex as rx
assert os.environ["EXPECT_VENV"] in rx.__file__, rx.__file__

def case(name, fn):
    try:
        fn()
        print(f"{name}: ACCEPTED")
    except Exception as e:
        print(f"{name}: {type(e).__name__}: {str(e)[:150]}")

def mk_reserved(attr, ann=str, default=""):
    def f():
        ns = {"__module__": __name__, "__qualname__": f"S_{attr}", "__annotations__": {attr: ann}, attr: default}
        type(f"S_{attr}", (rx.State,), ns)
    return f

for n in ("dict", "set", "reset", "router", "vars", "total", "response", "state", "data"):
    case(f"var named {n!r}", mk_reserved(n))

for n in ("rx_router_page", "rx_router_url", "rx_router_session"):
    case(f"var named {n!r}", mk_reserved(n))

class Parent(rx.State):
    shared: str = "p"

def shadow():
    class Child(Parent):
        shared: str = "c"
case("substate shadows parent var 'shared'", shadow)

def handler_named_reset():
    class H(rx.State):
        @rx.event
        def reset(self):
            pass
case("event handler named 'reset'", handler_named_reset)

def deps_router():
    class D(rx.State):
        @rx.var(deps=["router"], cache=True)
        def x(self) -> str:
            return self.router.url.path
case("computed var deps=['router']", deps_router)
