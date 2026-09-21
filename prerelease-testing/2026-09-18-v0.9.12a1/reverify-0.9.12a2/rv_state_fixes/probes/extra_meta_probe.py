import reflex as rx
import reflex.state
from reflex.vars import BaseStateMeta
print("reflex", rx.constants.Reflex.VERSION, reflex.__file__ if False else "")
print("type(rx.State) =", type(rx.State).__module__ + "." + type(rx.State).__qualname__)
print("_reflex_state_root:", getattr(rx.State, "_reflex_state_root", "<absent>"), "| is reflex.state.BaseState:", getattr(rx.State, "_reflex_state_root", None) is reflex.state.BaseState)

class CookieMeta(BaseStateMeta):
    pass

# reserved-name validation must still fire through a derived metaclass
try:
    class Reserved(rx.State, metaclass=CookieMeta):
        _get_was_touched: bool = False
    print("FAIL reserved name accepted through BaseStateMeta-derived metaclass")
except Exception as e:
    print("OK   reserved name rejected through derived metaclass ->", type(e).__name__, ":", str(e)[:160])

# and through the plain path
try:
    class Reserved2(rx.State):
        _get_was_touched: bool = False
    print("FAIL reserved name accepted on plain rx.State subclass")
except Exception as e:
    print("OK   reserved name rejected plain ->", type(e).__name__, ":", str(e)[:160])

# reserved handler / var names from FINDING-002 list
for nm, ann in [("router", "int"), ("substates", "int"), ("dirty_vars", "int")]:
    try:
        cls = type(f"R_{nm}", (rx.State,), {"__annotations__": {nm: int}, nm: 0, "__module__": "__main__"})
        print(f"FAIL reserved var {nm} accepted")
    except Exception as e:
        print(f"OK   reserved var {nm} rejected -> {type(e).__name__}: {str(e)[:100]}")

# mixin through derived metaclass then real subclass
class Mixin(rx.State, mixin=True, metaclass=CookieMeta):
    z: int = 0
class Real(Mixin, rx.State):
    pass
print("OK   mixin through derived metaclass usable; Real.z =", Real.z)
import reflex_base.vars as rbv
print("BaseStateMeta in reflex_base.vars.__all__:", "BaseStateMeta" in rbv.__all__)
