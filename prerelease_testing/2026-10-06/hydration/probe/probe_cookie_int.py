import sys
import reflex as rx
assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__

class S(rx.State):
    ck_int: int = rx.Cookie("5", name="hyd_int")
    ls_int: int = rx.LocalStorage(7)

print("fields ok", S.get_fields()["ck_int"], repr(S.get_fields()["ls_int"].default), type(S.get_fields()["ls_int"].default))
s = S(_reflex_internal_init=True)
d = s.dict(initial=True)
print(d)
