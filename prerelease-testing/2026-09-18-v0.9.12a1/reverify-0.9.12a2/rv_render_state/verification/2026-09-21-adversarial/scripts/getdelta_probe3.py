import traceback, reflex as rx
print("reflex from:", rx.__file__)
print("reflex version:", getattr(rx, "constants", None) and rx.constants.Reflex.VERSION)
for meth in ("get_delta", "get_value", "reset", "setvar", "_clean", "_mark_dirty"):
    ns = {"__module__": "__main__", "__qualname__": f"X_{meth}",
          "__annotations__": {"n": int}, "n": 0,
          meth: (lambda self, *a, **k: None)}
    try:
        type(f"X_{meth}", (rx.State,), ns)
        print(f"plain override of `{meth}`: ALLOWED")
    except Exception as e:
        print(f"plain override of `{meth}`: {type(e).__name__}: {str(e)[:100]}")
print("---- full traceback for the plain get_delta class-body override ----")
try:
    class S(rx.State):
        n: int = 0
        def get_delta(self):
            return super().get_delta()
except Exception:
    traceback.print_exc()
