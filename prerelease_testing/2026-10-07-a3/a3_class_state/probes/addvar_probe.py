"""Dynamic vars (State.add_var -> add_field -> setattr(cls, name, new_field)) next to #7495 class assignment/restore."""
import os, sys
import reflex as rx
assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
from importlib.metadata import version
print("reflex", version("reflex"))


class Dyn(rx.State):
    base: int = 0


def t(label, fn):
    try:
        print(f"{label:<48} -> {fn()!r}")
    except Exception as e:  # noqa: BLE001
        print(f"{label:<48} -> EXC {type(e).__name__}: {str(e)[:100]}")


t("add_var('dyn', int, 3)", lambda: Dyn.add_var("dyn", int, 3))
t("fresh .dyn", lambda: Dyn(_reflex_internal_init=True).dyn)
t("Dyn.dyn is a Var", lambda: isinstance(Dyn.dyn, rx.Var))
t("Dyn.dyn = 7 -> fresh", lambda: (setattr(Dyn, "dyn", 7), Dyn(_reflex_internal_init=True).dyn)[1])
t("del Dyn.dyn -> fresh", lambda: (delattr(Dyn, "dyn"), Dyn(_reflex_internal_init=True).dyn)[1])
t("add_var('dyn2', str, 'x') then Dyn.dyn2 = 'y'", lambda: (Dyn.add_var("dyn2", str, "x"), setattr(Dyn, "dyn2", "y"), Dyn(_reflex_internal_init=True).dyn2)[2])
t("instance write dyn2", lambda: (lambda s: (setattr(s, "dyn2", "z"), s.dyn2)[1])(Dyn(_reflex_internal_init=True)))
