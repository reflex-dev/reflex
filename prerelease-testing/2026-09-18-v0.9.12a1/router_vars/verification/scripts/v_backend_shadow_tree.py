import reflex as rx
assert "/envs/" in rx.__file__, rx.__file__
import importlib.metadata as md
print("reflex", md.version("reflex"))

class P(rx.State):
    _priv: int = 1
    def show_p(self):
        return self._priv

class C(P):
    _priv: str = "shadow"
    def show_c(self):
        return self._priv

root = rx.State(_reflex_internal_init=True)
p = root.get_substate(P.get_full_name().split(".")[1:])
c = root.get_substate(C.get_full_name().split(".")[1:])
print("P instance _priv:", repr(p._priv))
print("C instance _priv:", repr(c._priv))
c._priv = "written-by-child"
print("after c._priv = 'written-by-child':")
print("   C._priv reads:", repr(c._priv))
print("   P._priv reads:", repr(p._priv))
print("   C.dirty_vars:", c.dirty_vars, " P.dirty_vars:", p.dirty_vars)
print("   C._backend_vars:", {k: v for k, v in c._backend_vars.items() if k == '_priv'})
print("   P._backend_vars:", {k: v for k, v in p._backend_vars.items() if k == '_priv'})
