"""Independent re-derivation of claim B: class-level assignment to a declared backend var.

Usage: <venv>/bin/python derive_b.py <expected-venv-name>
"""

import os
import pickle
import sys

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

print(f"reflex {version('reflex')}  REFLEX_ENV_MODE={os.environ.get('REFLEX_ENV_MODE', '<unset>')}")


class Cfg(rx.State):
    _key: str | None = None  # declared backend var, reassigned on the class below
    _undeclared_ok = None  # placeholder so the class has a second backend var
    hits: int = 0

    @classmethod
    def configure(cls, key):
        cls._key = key


print("before: type(Cfg.__dict__['_key']) =", type(Cfg.__dict__["_key"]).__name__)
Cfg.configure("sk_live")
print("after : type(Cfg.__dict__['_key']) =", type(Cfg.__dict__["_key"]).__name__, "| Cfg._key =", repr(Cfg._key))
print("get_fields()['_key'] still:", Cfg.get_fields()["_key"])

Cfg._brand_new = "plain"  # never declared: just a class attribute on any version


def fresh():
    root = rx.State(_reflex_internal_init=True)
    return root.get_substate(Cfg.get_full_name().split(".")[1:])


a = fresh()
print("fresh instance a._key                  :", repr(a._key), "| a._brand_new:", repr(a._brand_new))
blob = pickle.dumps(a)  # what the disk/redis managers do on save
print("SAME instance a._key after pickle.dumps:", repr(a._key), "| '_key' in vars(a):", "_key" in vars(a))
b = pickle.loads(blob)
print("unpickled b._key                       :", repr(b._key))
c = fresh()
c._key = "set-on-instance"
print("instance write c._key='set-on-instance': dirty_vars=", sorted(getattr(c, "dirty_vars", set())),
      "| touched=", c._get_was_touched() if hasattr(c, "_get_was_touched") else getattr(c, "_was_touched", "?"))
d = fresh()
d.hits += 1
print("control write d.hits+=1                : dirty_vars=", sorted(getattr(d, "dirty_vars", set())),
      "| touched=", d._get_was_touched() if hasattr(d, "_get_was_touched") else getattr(d, "_was_touched", "?"))
e = fresh()
e._undeclared_ok = "x"
print("control backend write (descriptor kept): dirty_vars=", sorted(getattr(e, "dirty_vars", set())),
      "| touched=", e._get_was_touched() if hasattr(e, "_get_was_touched") else getattr(e, "_was_touched", "?"))
