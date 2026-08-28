"""Repro: runtime assignment to PEP695-alias-annotated state vars raises TypeError.

Run (Python 3.12+): python repro_alias_setattr.py
State.__setattr__ validates via reflex_base.utils.types._isinstance, which does
not resolve TypeAliasType -> isinstance() raises. The validation was meant to
only LOG a type mismatch, but instead every event handler assignment crashes.
"""

from typing import Literal

import reflex as rx

type Name = str
type Key = Literal["a", "b"]
type Items[T] = list[T]


class S(rx.State):
    name: Name = "x"
    k: Key = "a"
    entries: Items[str] = []
    maybe: Key | None = None


s = S(_reflex_internal_init=True)
for attr, value in [("name", "y"), ("k", "b"), ("entries", ["z"]), ("maybe", "a")]:
    try:
        setattr(s, attr, value)
        print(f"OK   : s.{attr} = {value!r}")
    except Exception as e:
        print(f"CRASH: s.{attr} = {value!r} -> {type(e).__name__}: {e}")

# In-place container mutation bypasses __setattr__ validation:
type Pair[K, V] = dict[K, V]


class S2(rx.State):
    pair: Pair[str, int] = {}


s2 = S2(_reflex_internal_init=True)
try:
    s2.pair["c"] = 3
    print(f"OK   : s2.pair['c'] = 3 (in-place mutation) -> {s2.pair}")
except Exception as e:
    print(f"CRASH: s2.pair['c'] = 3 -> {type(e).__name__}: {e}")
