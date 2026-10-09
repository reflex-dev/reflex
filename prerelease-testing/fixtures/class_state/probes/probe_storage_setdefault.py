"""N-005 / A3-02 with Field.set_default (#7519): storage-var defaults set through the FIELD (`S.get_fields()[name]`, which is
`S.__fields__[name]` on 0.10). Prints, per var and per new default: compiled client-storage entry (kind, options),
_is_client_storage, and what a fresh instance holds. Also checks base_vars.md's statements.

Run: EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_storage_setdefault.py
"""
import os
from typing import Optional

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

from reflex.compiler.utils import _compile_client_storage_recursive  # noqa: E402

print(f"reflex {version('reflex')} venv {os.environ['EXPECT_VENV']}")
N = [0]


def entry(cls, name):
    for kind, d in zip(("cookie", "local", "session"), _compile_client_storage_recursive(cls)):
        for k, v in d.items():
            if k.rsplit(".", 1)[-1].split("_rx_state_")[0] == name:
                return (kind, v)
    return None


def mk(ann, decl):
    N[0] += 1
    return type(f"S{N[0]}", (rx.State,), {"__module__": __name__, "__annotations__": {"v": ann}, "v": decl})


DECLS = {
    "str LS(name,sync)": (str, lambda: rx.LocalStorage("d", name="k_ls", sync=True)),
    "str Cookie(opts)": (str, lambda: rx.Cookie("d", name="k_ck", max_age=3600, same_site="strict", path="/")),
    "str SS(name)": (str, lambda: rx.SessionStorage("d", name="k_ss")),
    "LS-annot LS(name)": (rx.LocalStorage, lambda: rx.LocalStorage("d", name="k_lsa")),
    "Cookie-annot Cookie": (rx.Cookie, lambda: rx.Cookie("d", name="k_cka", max_age=60)),
    "Optional[str] LS": (Optional[str], lambda: rx.LocalStorage("d", name="k_opt")),
    "str plain": (str, lambda: "d"),
}
NEW = {
    "storage value (same type, new name)": lambda decl: type(decl)("n", name="k_new") if isinstance(decl, rx.LocalStorage) or isinstance(decl, rx.SessionStorage) else (rx.Cookie("n", name="k_new", max_age=10) if isinstance(decl, rx.Cookie) else rx.LocalStorage("n", name="k_new")),
    "plain str": lambda decl: "n",
    "None": lambda decl: None,
    "int 5": lambda decl: 5,
}

for dname, (ann, mkdecl) in DECLS.items():
    S0 = mk(ann, mkdecl())
    print(f"\n== {dname}: declared -> entry={entry(S0, 'v')} is_cs={S0._is_client_storage('v')}")
    for nname, mknew in NEW.items():
        S = mk(ann, mkdecl())
        decl = S.get_fields()["v"].default
        new = mknew(decl)
        S.get_fields()["v"].set_default(new)
        try:
            inst = repr(getattr(S(_reflex_internal_init=True), "v"))
        except Exception as e:  # noqa: BLE001
            inst = f"<{type(e).__name__}: {e}>"
        print(f"   default={nname:38s} entry={entry(S, 'v')!s:75s} is_cs={S._is_client_storage('v')!s:5s} instance={inst}")

# default_factory returning storage (docs: honored for a storage-ANNOTATED var)
for ann_name, ann in (("LS-annot", rx.LocalStorage), ("str", str)):
    S = mk(ann, rx.LocalStorage("d", name="k_f0"))
    f = S.get_fields()["v"]
    f.set_default(default_factory=lambda: rx.LocalStorage("f", name="k_fac", sync=True))
    print(f"\n== {ann_name}-annotated var, default MISSING + factory returning LocalStorage(name=k_fac,sync): entry={entry(S, 'v')} "
          f"is_cs={S._is_client_storage('v')} instance={getattr(S(_reflex_internal_init=True), 'v')!r}")
