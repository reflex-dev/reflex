"""Enterprise-shaped declaration: a mixin state with a metaclass and a get_delta override, then a concrete state using it."""
import reflex as rx
print("reflex", rx.constants.Reflex.VERSION)
Meta = type(rx.State)  # forward-compatible spelling on both versions
class CookieMeta(Meta):
    def __new__(mcs, name, bases, attrs, **kw):
        return super().__new__(mcs, name, bases, attrs, **kw)
try:
    class OIDCLike(rx.State, mixin=True, metaclass=CookieMeta):
        token: str = ""
        def get_delta(self):
            d = super().get_delta()
            return d
    print("mixin with get_delta override: OK")
    class Concrete(OIDCLike, rx.State):
        x: int = 0
    print("concrete state from the mixin: OK; get_delta is", type(Concrete.__dict__.get("get_delta", OIDCLike.__dict__.get("get_delta"))).__name__)
    s = Concrete(_reflex_internal_init=True) if "_reflex_internal_init" in Concrete.__init__.__code__.co_varnames else None
    print("event_handlers named get_delta:", [n for n in Concrete.event_handlers if n == "get_delta"])
except Exception as e:
    print("FAIL:", type(e).__name__, str(e)[:200])
