"""Which downstream-style declarations does the #7136 validation reject, and with what message?"""
import reflex as rx, traceback
print("reflex", rx.constants.Reflex.VERSION)
cases = {}
def case(name, fn):
    try:
        fn(); cases[name] = "OK"
    except Exception as e:
        cases[name] = f"{type(e).__name__}: {str(e)[:150]}"
def c1():
    class S1(rx.State):
        def get_delta(self):  # enterprise OIDCAuthState overrides this to filter the delta
            return super().get_delta()
def c1b():
    class S1b(rx.State):
        def get_delta(self):
            return super().get_delta()
        get_delta.__override_base_method__ = True
def c2():
    class S2(rx.State):
        _get_was_touched: bool = False   # #7132 says persistence keeps working with this var
def c3():
    class S3(rx.State):
        def process(self): pass         # plain method named after a framework method
def c4():
    class S4(rx.State):
        dirty_vars: list[str] = []      # var named after bookkeeping
def c5():
    class S5(rx.State):
        def get_value(self): return 1
def c6():
    class S6(rx.State):
        router: str = "x"               # base var named router
def c7():
    class S7(rx.State):
        @rx.var
        def router(self) -> str: return "x"
def c8():
    class S8(rx.State):
        def add_field(self): pass       # #7136 renamed a docs example for this
def c9():
    class S9(rx.State):
        substates: int = 0
def c10():
    class S10(rx.State):
        def set(self): pass
def c11():
    class S11(rx.State):
        def dict(self): return {}
for n, f in [("get_delta override", c1), ("get_delta override marked __override_base_method__", c1b), ("_get_was_touched var", c2), ("process() method", c3), ("dirty_vars var", c4), ("get_value() method", c5), ("router base var", c6), ("router computed var", c7), ("add_field() method", c8), ("substates var", c9), ("set() method", c10), ("dict() method", c11)]:
    case(n, f)
for n, r in cases.items(): print(f"  {n:50s} -> {r}")
