"""The "declare now, configure later" idiom: an UNANNOTATED backend attribute that defaults to None, set on the class at startup.

    class Cfg(rx.State):
        _client = None            # placeholder
    Cfg._client = make_client()   # configuration at import / app start

Usage: <venv>/bin/python none_slot_probe.py <expected-venv-name>
"""
import sys
from typing import Optional

import reflex as rx

assert f"/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__


class Client:
    pass


class Cfg(rx.State):
    _client = None  # unannotated placeholder
    _opt: Optional[Client] = None  # annotated placeholder (control)
    _n = 0  # unannotated int
    _s = ""  # unannotated str
    _lst = []  # unannotated list
    _any = None  # unannotated None again (second case)


def inst():
    root = rx.State(_reflex_internal_init=True)
    return root.get_substate(Cfg.get_full_name().split(".")[1:])


def case(label, name, value):
    try:
        setattr(Cfg, name, value)
        print(f"{label:60s} -> ok | instance reads {getattr(inst(), name)!r}"[:200])
    except BaseException as e:  # noqa: BLE001
        print(f"{label:60s} -> EXC {type(e).__name__}: {str(e)[:120]}")


case("`_client = None`  <- Client()", "_client", Client())
case("`_client = None`  <- 'a string'", "_client", "a string")
case("`_client = None`  <- 42", "_client", 42)
case("`_client = None`  <- None (control)", "_client", None)
case("`_opt: Optional[Client] = None` <- Client() (control)", "_opt", Client())
case("`_n = 0`         <- 5", "_n", 5)
case("`_n = 0`         <- 'five'", "_n", "five")
case("`_n = 0`         <- 2.5 (float into int)", "_n", 2.5)
case("`_s = ''`        <- None", "_s", None)
case("`_lst = []`      <- ['a']", "_lst", ["a"])
case("`_lst = []`      <- ('a',)  (tuple into list)", "_lst", ("a",))
print("declared types:", {k: str(v.outer_type_) for k, v in Cfg.get_fields().items() if k in ("_client", "_opt", "_n", "_s", "_lst", "_any")})
