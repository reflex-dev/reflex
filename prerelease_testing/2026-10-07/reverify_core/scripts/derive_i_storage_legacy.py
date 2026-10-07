"""Is a LocalStorage var still browser storage after configuring its default the 0.9.12-documented way
(`cls.__fields__[name].default = value`) vs the 0.10.0a2 way (`cls.name = value`)?

Usage: <venv>/bin/python derive_i_storage_legacy.py <expected-venv-name>
"""
import sys

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
from reflex.compiler.utils import _compile_client_storage_recursive  # noqa: E402


class A(rx.State):
    legacy: str = rx.LocalStorage("d", name="legacy_key")
    newstyle: str = rx.LocalStorage("d", name="new_key")
    newstyle_ls: str = rx.LocalStorage("d", name="new_ls_key")


A.__fields__["legacy"].default = "configured"  # 0.9.12 docs (component_state.md, EditableText)
A.newstyle = "configured"  # 0.10.0a2 docs
A.newstyle_ls = rx.LocalStorage("configured", name="new_ls_key")  # workaround: assign a storage value
for n in ("legacy", "newstyle", "newstyle_ls"):
    print(f"{n:12} is_client_storage={A._is_client_storage(n)} default={A.get_fields()[n].default!r}")
print("compiled local_storage keys:", sorted(k.rsplit('.', 1)[-1] for k in _compile_client_storage_recursive(A)[1]))
