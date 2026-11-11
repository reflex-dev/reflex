import sys
import reflex
assert sys.argv[1] in reflex.__file__
import reflex as rx
import sqlmodel
class Thing(rx.Model, table=True):
    name: str = ""
for label, fn in [("rx.AdminDash(models=[Thing])", lambda: rx.AdminDash(models=[Thing])),
                  ("rx.App(admin_dash=...)", lambda: rx.App(admin_dash=rx.AdminDash(models=[Thing]))),
                  ("rx.AdminDash()", lambda: rx.AdminDash()),
                  ("rx.App(admin_dash=None)", lambda: rx.App(admin_dash=None))]:
    try:
        r = fn(); print(label, "-> OK", type(r).__name__, getattr(r, "admin_dash", None))
    except BaseException as e:
        print(label, "-> ERR", type(e).__module__ + "." + type(e).__name__, ":", e)
import importlib
print("hasattr rx.AdminDash:", hasattr(rx, "AdminDash"))
