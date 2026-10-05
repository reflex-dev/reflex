"""Framework-only repro: a user/downstream metaclass derived from reflex.vars.BaseStateMeta
(the metaclass State had through 0.9.11.post1) can no longer be used on a State subclass."""
import sys
import reflex as rx
from reflex.vars import BaseStateMeta

print("reflex", rx.constants.Reflex.VERSION, "| type(rx.State) =", type(rx.State).__module__ + "." + type(rx.State).__qualname__,
      "| BaseStateMeta is type(rx.State):", BaseStateMeta is type(rx.State))

class CookieMeta(BaseStateMeta):
    """Pattern used by reflex-enterprise 0.9.5 (auth/oidc/state.py:347): add descriptors at class creation."""
    def __new__(mcs, name, bases, attrs, **kwargs):
        attrs.setdefault("added_by_meta", "yes")
        return super().__new__(mcs, name, bases, attrs, **kwargs)

try:
    class WithBaseStateMeta(rx.State, metaclass=CookieMeta):
        x: int = 0
    print("OK   metaclass derived from BaseStateMeta:", WithBaseStateMeta.added_by_meta)
except TypeError as e:
    print("FAIL metaclass derived from BaseStateMeta ->", e)

class ForwardCompatMeta(type(rx.State)):
    def __new__(mcs, name, bases, attrs, **kwargs):
        attrs.setdefault("added_by_meta", "yes")
        return super().__new__(mcs, name, bases, attrs, **kwargs)

try:
    class WithCurrentMeta(rx.State, metaclass=ForwardCompatMeta):
        y: int = 0
    print("OK   metaclass derived from type(rx.State):", WithCurrentMeta.added_by_meta)
except Exception as e:
    print("FAIL metaclass derived from type(rx.State) ->", type(e).__name__, e)

# mixin=True variant exactly like the enterprise declaration
try:
    class Mixin(rx.State, mixin=True, metaclass=CookieMeta):
        z: int = 0
    print("OK   mixin=True with BaseStateMeta-derived metaclass")
except TypeError as e:
    print("FAIL mixin=True with BaseStateMeta-derived metaclass ->", e)
