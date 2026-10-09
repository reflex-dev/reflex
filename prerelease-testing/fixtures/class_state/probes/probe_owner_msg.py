"""#7519 error-message owner: for each assignment, print the message, the owner it names, and whether FOLLOWING the
message literally (`<Owner>.__fields__[name].set_default(NEW)`, with Owner resolved by name) gives the assigned-through
class the new default. Run: EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_owner_msg.py"""
import os
import re
from typing import ClassVar

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

print("reflex", version("reflex"))
REG = {}


def reg(*classes):
    for c in classes:
        REG[c.__name__] = c
    return classes[0]


def tree_inst(cls):
    root = rx.State(_reflex_internal_init=True)
    if cls is rx.State:
        return root
    return root.get_substate(cls.get_full_name().split(".")[1:])


def check(label, through, name, new, action="assign", inst=tree_inst):
    try:
        if action == "assign":
            setattr(through, name, new)
        else:
            delattr(through, name)
        print(f"ROW {label} | ACCEPTED (no error)")
        return
    except TypeError as e:
        msg = str(e)
    m = re.search(r"Set its default with (\w+)\.__fields__\['(\w+)'\]\.(set_default\(\.\.\.\)|default = \.\.\.)", msg)
    owner_name = m.group(1) if m else None
    owner = REG.get(owner_name) or getattr(through, "__mro__", [None])[0] if owner_name == through.__name__ else REG.get(owner_name)
    if owner_name == through.__name__:
        owner = through
    followed = "n/a"
    if owner is not None and m:
        f = owner.__fields__[m.group(2)]
        saved = (f.default, f.default_factory)
        try:
            if hasattr(f, "set_default"):
                f.set_default(new)
            else:
                f.default = new
            got = getattr(inst(through), name)
            followed = f"fix works={got == new} (instance of {through.__name__} reads {got!r})"
        except Exception as e2:  # noqa: BLE001
            followed = f"fix FAILED {type(e2).__name__}: {e2}"
        finally:
            f.default, f.default_factory = saved
    print(f"ROW {label} | names={owner_name} | {followed} | msg={msg}")


class P(rx.State):
    x: int = 1
    _b: str = "b"


class C(P):
    y: int = 0


class G(C):
    z: int = 0


class K(P):
    x: int = 5  # independent redeclaration (#7312)


class Mix(rx.State, mixin=True):
    m: int = 3


class UsesMix(Mix, rx.State):
    pass


class SubOfUsesMix(UsesMix):
    pass


class Shared(rx.SharedState):
    count: int = 0


reg(P, C, G, K, Mix, UsesMix, SubOfUsesMix, Shared)


class ET(rx.ComponentState):
    text: str = "t"

    @classmethod
    def get_component(cls, **props):
        return rx.text(cls.text)


comp = ET.create()
reg(comp.State, ET)


class ETSub(ET):  # a ComponentState subclass of a ComponentState
    extra: int = 0

    @classmethod
    def get_component(cls, **props):
        return rx.text(cls.text)


comp2 = ETSub.create()
reg(ETSub, comp2.State)

check("declaring state P.x", P, "x", 11)
check("backend P._b", P, "_b", "nb")
check("substate C.x (inherited)", C, "x", 12)
check("grandchild G.x", G, "x", 13)
check("del C.x", C, "x", 0, action="del")
check("redeclared K.x (own var)", K, "x", 14)
check("mixin class Mix.m", Mix, "m", 15, inst=lambda c: None)
check("mixin user UsesMix.m", UsesMix, "m", 16)
check("substate of mixin user SubOfUsesMix.m", SubOfUsesMix, "m", 17)
check("SharedState Shared.count", Shared, "count", 18)
check("ComponentState instance class comp.State.text", comp.State, "text", "n")
check("ComponentState template ET.text", ET, "text", "tt", inst=lambda c: None)
check("ComponentState subclass instance class comp2.State.text", comp2.State, "text", "n2")
check("framework var MyState.is_hydrated", C, "is_hydrated", True)
check("framework var C.router", C, "router", None)
