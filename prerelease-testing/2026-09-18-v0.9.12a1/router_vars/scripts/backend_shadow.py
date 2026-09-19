import reflex as rx
assert "/envs/" in rx.__file__, rx.__file__
class P(rx.State):
    _priv: int = 1
class C(P):
    _priv: str = "shadow"
print("P backend_vars:", P.backend_vars)
print("C backend_vars:", C.backend_vars)
print("C inherited_backend_vars:", C.inherited_backend_vars)
