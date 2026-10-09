"""Finding 5: what `State.__fields__[name].default = <value>` actually did on 0.9.12 (and a4/a5 for contrast).

Distinguishes 'shared between sessions' from 'not applied at all', and what reset() restores.
Run: EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_09_trap2.py
"""
import os

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

print("reflex", version("reflex"))


class T(rx.State):
    items: list[str] = ["decl"]
    _bitems: list[str] = ["decl"]
    count: int = 0
    _bcount: int = 0


NEW, BNEW = ["new"], ["new"]
T.__fields__["items"].default = NEW
T.__fields__["_bitems"].default = BNEW
T.__fields__["count"].default = 10
T.__fields__["_bcount"].default = 10


def session():
    root = rx.State(_reflex_internal_init=True)
    return root.get_substate(T.get_full_name().split(".")[1:])


a, b = session(), session()
print("new session                 :", f"items={list(a.items)} _bitems={list(a._bitems)} count={a.count} _bcount={a._bcount}")
print("items shared across sessions:", a.items is b.items or getattr(a.items, "__wrapped__", 1) is getattr(b.items, "__wrapped__", 2))
a.items.append("leak")
a._bitems.append("bleak")
c = session()
print("after s1 appends, s3 sees   :", f"items={list(c.items)} _bitems={list(c._bitems)}; NEW={NEW} BNEW={BNEW}")
c.reset()
print("s3 after reset()            :", f"items={list(c.items)} _bitems={list(c._bitems)} count={c.count} _bcount={c._bcount}")
if hasattr(T.__fields__["items"], "set_default"):
    T.__fields__["items"].set_default(["sd"])
    d, e = session(), session()
    d.items.append("x")
    print("set_default(['sd']) (0.10)  :", f"s4={list(d.items)} s5={list(e.items)}")
