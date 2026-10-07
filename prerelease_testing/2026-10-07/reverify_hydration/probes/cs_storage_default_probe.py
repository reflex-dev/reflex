"""reverify_hydration probe: does assigning a per-instance default to a client-storage var in
ComponentState.get_component (the #7461 pattern `cls.x = value`) keep it a browser-storage var?
Run with each venv's python from a neutral dir: <venv>/bin/python cs_storage_default_probe.py <venv-name>"""
import sys

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
from importlib.metadata import version

print("reflex", version("reflex"))


class Box(rx.ComponentState):
    pref: str = rx.LocalStorage("light", name="box_pref")
    ck: str = rx.Cookie("c0", name="box_ck")

    @classmethod
    def get_component(cls, *children, initial="light", mode="plain", **props):
        if mode == "plain":
            cls.pref = initial
        elif mode == "storage":
            cls.pref = rx.LocalStorage(initial, name=f"box_pref_{initial}")
        elif mode == "factory":
            cls.pref = lambda: rx.LocalStorage(initial, name=f"box_pref_f_{initial}")
        return rx.text(cls.pref)


for mode in ["plain", "storage", "factory"]:
    try:
        comp = Box.create(initial="dark", mode=mode)
        st = comp.State
        f = st.get_fields()["pref"]
        inst_default = f.default if f.default is not None else None
        print(f"{mode:8s}: is_client_storage={st._is_client_storage('pref')} default={f.default!r} "
              f"type(default)={type(f.default).__name__} factory={f.default_factory} "
              f"name={getattr(f.default, 'name', None)!r}")
    except Exception as e:  # noqa: BLE001
        print(f"{mode:8s}: EXCEPTION {type(e).__name__}: {e}")
