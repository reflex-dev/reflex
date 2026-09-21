import reflex as rx
from reflex.state import _override_base_method
print("reflex from:", rx.__file__)

# 1. decorated override, declared in the class body
try:
    class D1(rx.State):
        n: int = 0
        @_override_base_method
        def get_delta(self):
            d = super().get_delta()
            d["__probe__"] = True
            return d
    print("decorated class-body override: ALLOWED; is EventHandler?",
          type(D1.__dict__["get_delta"]).__name__,
          "| in event_handlers:", "get_delta" in D1.event_handlers)
except Exception as e:
    print("decorated class-body override:", type(e).__name__, e)

# 2. decorated override on a plain mixin base
try:
    class Mix2:
        @_override_base_method
        def get_delta(self):
            return super().get_delta()
    class D2(Mix2, rx.State):
        n: int = 0
    print("decorated mixin base: ALLOWED")
except Exception as e:
    print("decorated mixin base:", type(e).__name__, e)

# 3. other public builtin methods -- is get_delta special?
for meth in ("get_value", "get_delta", "reset", "setvar", "update_vars_internal"):
    try:
        ns = {"__annotations__": {"n": int}, "n": 0,
              meth: (lambda self, *a, **k: None)}
        type(f"X_{meth}", (rx.State,), ns)
        print(f"plain override of `{meth}`: ALLOWED")
    except Exception as e:
        print(f"plain override of `{meth}`:", type(e).__name__, str(e)[:90])

# 4. does a declared-and-decorated override actually get CALLED?
try:
    class D3(rx.State):
        n: int = 0
        @_override_base_method
        def get_delta(self):
            d = super().get_delta()
            d.setdefault("__called__", 1)
            return d
    inst = D3(_reflex_internal_init=True)
    inst.n = 1
    out = inst.get_delta()
    print("decorated override invoked:", "__called__" in out, "| delta:", dict(out))
except Exception as e:
    print("decorated override invoked:", type(e).__name__, e)

# 5. post-hoc assignment actually invoked?
try:
    class D4(rx.State):
        n: int = 0
    _orig = rx.State.get_delta
    def patched(self):
        d = _orig(self)
        d.setdefault("__posthoc__", 1)
        return d
    D4.get_delta = patched
    i4 = D4(_reflex_internal_init=True)
    i4.n = 2
    o4 = i4.get_delta()
    print("post-hoc override invoked:", "__posthoc__" in o4, "| delta:", dict(o4))
except Exception as e:
    print("post-hoc override invoked:", type(e).__name__, e)
