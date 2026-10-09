"""ComponentState per-instance default of a browser-storage var set in get_component (#7461 / N-005 / A3-02).

0.10.0a4+ (#7516) rejects the old class assignment `cls.pref = value` with a TypeError naming the field API; the
supported form is `cls.__fields__["pref"].set_default(...)`. Prints, per pattern, whether the var stays browser storage,
its default and its storage name. Expected on 0.10.0 (re-validated): the `assign_*` rows raise the #7516 TypeError;
`field_plain` / `field_none` make the str-annotated var an ORDINARY var (documented: storage is kept only when the new
default is a storage value); `field_storage` keeps LocalStorage with the per-instance name `box_pref_dark`.
Run with each venv's python from a neutral dir: $SB/envs/<venv>/bin/python -I cs_storage_default_probe.py <venv-name>"""
import sys
from importlib.metadata import version

import reflex as rx

assert f"/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
print("reflex", version("reflex"))


class Box(rx.ComponentState):
    pref: str = rx.LocalStorage("light", name="box_pref")
    opt: str | None = rx.LocalStorage("x", name="box_opt")

    @classmethod
    def get_component(cls, *children, initial="light", mode="field_plain", **props):
        f = cls.__fields__
        if mode == "assign_plain":
            cls.pref = initial
        elif mode == "assign_storage":
            cls.pref = rx.LocalStorage(initial, name=f"box_pref_{initial}")
        elif mode == "field_plain":
            f["pref"].set_default(initial)
        elif mode == "field_storage":
            f["pref"].set_default(rx.LocalStorage(initial, name=f"box_pref_{initial}"))
        elif mode == "field_none":
            f["opt"].set_default(None)
        return rx.text(cls.pref)


for mode in ["assign_plain", "assign_storage", "field_plain", "field_storage", "field_none"]:
    var = "opt" if mode == "field_none" else "pref"
    try:
        st = Box.create(initial="dark", mode=mode).State
        fd = st.get_fields()[var]
        print(f"{mode:14s}: is_client_storage={st._is_client_storage(var)} default={fd.default!r} "
              f"type(default)={type(fd.default).__name__} name={getattr(fd.default, 'name', None)!r}")
    except Exception as e:  # noqa: BLE001
        print(f"{mode:14s}: EXCEPTION {type(e).__name__}: {str(e)[:160]}")
