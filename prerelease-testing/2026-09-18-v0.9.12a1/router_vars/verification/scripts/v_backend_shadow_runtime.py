import reflex as rx
assert "/envs/" in rx.__file__, rx.__file__
import importlib.metadata as md
print("reflex", md.version("reflex"))

class P(rx.State):
    _priv: int = 1

class C(P):
    _priv: str = "shadow"

print("C.backend_vars:", C.backend_vars)
c = C(_reflex_internal_init=True)
print("instance C()._priv =", repr(c._priv))
c._priv = "written"
print("after write, c._priv =", repr(c._priv), "dirty:", c.dirty_vars)
print("class-level C._priv =", repr(C._priv) if hasattr(C, "_priv") else "<absent>")

# same-name base var (not backend) for contrast
try:
    class P2(rx.State):
        pub: int = 1
    class C2(P2):
        pub: str = "shadow"
except Exception as e:
    print("base var shadow ->", type(e).__name__, e)
