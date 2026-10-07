"""Verifier probe for a3_class_state-9: browser keys of ComponentState instances with storage vars.

Box declares a NAMED LocalStorage var and Free an UNNAMED one. Each is instantiated
three times: no assignment, `cls.pref = initial` (the a3 CHANGELOG pattern), and
`cls.pref = rx.LocalStorage(initial, name=f"..._{tag}")` (per-instance name).
Prints the compiled browser key of every instance's var.

Run: EXPECT_VENV=<venv-dir-name> <venv>/bin/python -I probe_v9_cs_keys.py
"""

import os

import reflex

assert f"/envs/{os.environ['EXPECT_VENV']}/" in reflex.__file__, reflex.__file__

import reflex as rx  # noqa: E402
from reflex.compiler import utils as cutils  # noqa: E402

VERSION = reflex.__file__.split("/envs/")[1].split("/")[0]


class Box(rx.ComponentState):
    pref: str = rx.LocalStorage("light", name="box_pref")

    @classmethod
    def get_component(cls, tag: str, mode: str, **props):
        if mode == "plain":
            cls.pref = f"init-{tag}"
        elif mode == "storage":
            cls.pref = rx.LocalStorage(f"init-{tag}", name=f"box_pref_{tag}")
        return rx.text(cls.pref, id=f"box-{tag}")


class Free(rx.ComponentState):
    pref: str = rx.LocalStorage("light")

    @classmethod
    def get_component(cls, tag: str, mode: str, **props):
        if mode == "plain":
            cls.pref = f"init-{tag}"
        return rx.text(cls.pref, id=f"free-{tag}")


comps = {}
for state_cls in (Box, Free):
    for mode in ("none", "plain", "storage") if state_cls is Box else ("none", "plain"):
        try:
            comps[(state_cls.__name__, mode)] = state_cls.create(tag=mode, mode=mode)
        except Exception as err:  # noqa: BLE001
            print(f"[{VERSION}] {state_cls.__name__}.create({mode}) failed: {type(err).__name__}: {err}")

cookies, local, session = cutils._compile_client_storage_recursive(rx.State)
for (cls_name, mode), comp in comps.items():
    st = comp.State
    full = f"{st.get_full_name()}.pref" + ("_rx_state_" if f"{st.get_full_name()}.pref_rx_state_" in local else "")
    entry = local.get(full)
    default = st.get_fields()["pref"].default if hasattr(st, "get_fields") else "?"
    print(
        f"[{VERSION}] {cls_name:4s} mode={mode:8s} substate={st.get_name():22s} "
        f"browser_key={(entry or {}).get('name') or ('<var name>' if entry else 'NOT STORAGE')!s:22s} "
        f"default={default!r} ({type(default).__name__})"
    )
