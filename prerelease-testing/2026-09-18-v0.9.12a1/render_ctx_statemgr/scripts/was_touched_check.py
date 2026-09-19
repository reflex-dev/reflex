"""#7132 / #7136: can a State still declare a var named `_get_was_touched`?"""
import reflex as rx

assert "/envs/shared/" in rx.__file__, rx.__file__
print("reflex", rx.constants.Reflex.VERSION, "from", rx.__file__)

results = {}
try:
    class VarState(rx.State):
        _get_was_touched: bool = False
    results["plain_var"] = "ALLOWED (class created)"
except Exception as e:
    results["plain_var"] = f"{type(e).__name__}: {e}"

try:
    class CvState(rx.State):
        @rx.var
        def _get_was_touched(self) -> bool:
            return False
    results["computed_var"] = "ALLOWED (class created)"
except Exception as e:
    results["computed_var"] = f"{type(e).__name__}: {e}"

for k, v in results.items():
    print(f"{k}: {v}")
