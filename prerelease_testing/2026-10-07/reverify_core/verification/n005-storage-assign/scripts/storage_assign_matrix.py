"""Which class-level assignments keep a browser-storage var's storage classification and options?

Usage: <venv>/bin/python storage_assign_matrix.py <expected-venv-name>
For each storage type (LocalStorage, SessionStorage, Cookie) x annotation (str, the storage type) x assignment kind,
print: assignment outcome, _is_client_storage, compiled storage entry (key + options), fresh-instance value.
"""

import sys
import dataclasses

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

from reflex.compiler.utils import _compile_client_storage_recursive  # noqa: E402

print("reflex", version("reflex"))
KINDS = {
    "none (control)": None,
    "plain value 'x'": lambda T: "x",
    "factory -> plain 'x'": lambda T: (lambda: "x"),
    "factory -> T('x', name='k2')": lambda T: (lambda: T("x", name="k2")),
    "T('x', name='k2') value": lambda T: T("x", name="k2"),
    "T('x') value (no name)": lambda T: T("x"),
}

n = 0
for T in (rx.LocalStorage, rx.SessionStorage, rx.Cookie):
    for ann_name, ann in (("str", str), (T.__name__, T)):
        for kind, mk in KINDS.items():
            n += 1
            cls = type(
                f"S{n}",
                (rx.State,),
                {"__annotations__": {"v": ann}, "v": T("d", name="k1"), "__module__": __name__},
            )
            outcome = "-"
            if mk is not None:
                try:
                    setattr(cls, "v", mk(T))
                    outcome = "ok"
                except Exception as e:  # noqa: BLE001
                    outcome = f"{type(e).__name__}: {str(e)[:90]}"
            fld = cls.get_fields()["v"]
            is_cs = cls._is_client_storage("v")
            ck, ls, ss = _compile_client_storage_recursive(cls)
            comp = {**ck, **ls, **ss}
            entry = next(({"kind": kk, **vv} for kk, d in (("cookie", ck), ("local", ls), ("session", ss)) for k, vv in d.items() if k.rsplit(".", 1)[-1].split("_rx_state_")[0] == "v"), None)
            try:
                inst = cls(_reflex_internal_init=True) if "_reflex_internal_init" in rx.State.__init__.__code__.co_varnames or True else None
                val = inst.v
            except Exception as e:  # noqa: BLE001
                val = f"<{type(e).__name__}>"
            print(f"{T.__name__:15}| ann={ann_name:15}| {kind:30}| assign={outcome:10}| is_client_storage={is_cs!s:5}| compiled={entry}| fresh={val!r}")
