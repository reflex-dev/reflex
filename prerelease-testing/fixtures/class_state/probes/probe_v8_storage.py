"""Verifier probe for a3_class_state-8: non-str defaults assigned to browser-storage vars.

Declares storage vars with str / Optional[str] / Union[str, int] annotations, assigns
class defaults, and reports whether each var is still browser storage (field default
type, compiled client-storage map, _is_client_storage) and what a fresh instance holds.

Run: EXPECT_VENV=<venv-dir-name> <venv>/bin/python -I probe_v8_storage.py
"""

import os
from typing import Optional, Union

import reflex

assert f"/envs/{os.environ['EXPECT_VENV']}/" in reflex.__file__, reflex.__file__

import reflex as rx  # noqa: E402
from reflex.compiler import utils as cutils  # noqa: E402

VERSION = reflex.__file__.split("/envs/")[1].split("/")[0]


class St(rx.State):
    plain: str = rx.LocalStorage("d", name="k_plain")
    opt: Optional[str] = rx.LocalStorage("d", name="k_opt")
    opt_cached: Optional[str] = rx.LocalStorage("d", name="k_opt_cached")
    uni: Union[str, int] = rx.LocalStorage("d", name="k_uni")
    ck: Optional[str] = rx.Cookie("d", name="k_ck", max_age=60)


def compiled_keys(cls):
    fn = getattr(cutils, "_compile_client_storage_recursive", None)
    if fn is None:
        return "n/a"
    out = fn(cls)
    keys = {}
    for kind, entries in zip(("cookies", "local", "session"), out):
        for full_name, opts in entries.items():
            keys[full_name.rsplit(".", 1)[-1].removesuffix("_rx_state_")] = (kind, opts.get("name"))
    return keys


def report(stage):
    fields = St.get_fields()
    inst = St(_reflex_internal_init=True)
    print(f"[{VERSION}] {stage}")
    print(f"    compiled storage: {compiled_keys(St)}")
    for name in ("plain", "opt", "opt_cached", "uni", "ck"):
        f = fields[name]
        print(
            f"    {name:10s} default_type={type(f.default).__name__:13s} default={f.default!r:8} "
            f"instance={getattr(inst, name)!r}"
        )


# Warm the lru_cache for one var before assigning (a backend that classified it first).
print(f"[{VERSION}] _is_client_storage('opt_cached') before assignment = {St._is_client_storage('opt_cached')}")
report("declared")

for name, value in (("plain", "x"), ("opt", None), ("opt_cached", None), ("uni", 5), ("ck", None)):
    try:
        setattr(St, name, value)
        print(f"[{VERSION}] St.{name} = {value!r}: accepted")
    except Exception as err:  # noqa: BLE001
        print(f"[{VERSION}] St.{name} = {value!r}: {type(err).__name__}: {err}")

report("after non-str assignments")
for name in ("opt", "opt_cached", "uni", "ck"):
    print(f"    _is_client_storage({name!r}) = {St._is_client_storage(name)}")

# Does a later plain-string assignment bring storage back?
St.opt = "y"
report("after St.opt = 'y'")

# Undo both assignments to opt.
del St.opt
del St.opt
report("after two `del St.opt`")
