"""Python 3.14 (PEP 649/749 lazy annotations) + state_auto_setters=True: is `set_<var>` generated for a substate's own vars?

Usage: <venv>/bin/python probe.py   (run from this directory; rxconfig.py enables state_auto_setters)
"""
from __future__ import annotations

import sys
import warnings

warnings.simplefilter("ignore")
import reflex as rx
from pkgmod import PkgBaseState


class UserState(PkgBaseState):
    extra: str = ""


class PlainState(rx.State):
    plain: str = ""


for cls, names in ((PkgBaseState, ["items", "note"]), (UserState, ["extra", "note"]), (PlainState, ["plain"])):
    print(cls.__name__, {n: (f"set_{n}" in cls.event_handlers) for n in names}, "hasattr:", {n: hasattr(cls, f"set_{n}") for n in names})
import importlib.metadata as md

print("python", sys.version.split()[0], "reflex", md.version("reflex"))
