import reflex as rx, reflex.state
from reflex.state import BaseState, _override_base_method
print("reflex:", rx.constants.Reflex.VERSION)
# is `_get_delta` a real framework member at all?
print("BaseState has _get_delta?", hasattr(BaseState, "_get_delta"))
print("BaseState has _get_resolved_delta?", hasattr(BaseState, "_get_resolved_delta"))
# marker on a substate
class Parent(rx.State):
    a: int = 0
class Child(Parent):
    b: int = 0
    @_override_base_method
    def get_delta(self):
        d = super().get_delta()
        d["__child__"] = 1
        return d
c = Child(_reflex_internal_init=True)
c.b = 5
print("substate marked override works:", "__child__" in c.get_delta())
# marker on a mixin used by several states
class F:
    @_override_base_method
    def get_delta(self):
        d = super().get_delta()
        d["__mix__"] = 1
        return d
class M1(F, rx.State):
    x: int = 0
class M2(F, rx.State):
    y: int = 0
m = M1(_reflex_internal_init=True); m.x = 1
print("shared mixin marked override works:", "__mix__" in m.get_delta())
