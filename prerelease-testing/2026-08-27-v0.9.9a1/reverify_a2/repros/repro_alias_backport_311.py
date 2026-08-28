"""typing_extensions.TypeAliasType backport on Python 3.11 (no PEP695 syntax).

Same two behaviors as the native alias: guess_type resolves (new in 0.9.9a1),
but runtime setattr validation crashes.
"""

from typing import Literal

import reflex as rx
from typing_extensions import TypeAliasType

Key = TypeAliasType("Key", Literal["a", "b"])


class S(rx.State):
    k: Key = "a"  # pyright: ignore[reportInvalidTypeForm]


print("compile OK:", type(S.k).__name__, S.k._var_type)
s = S(_reflex_internal_init=True)
try:
    s.k = "b"
    print("OK   : setattr works")
except Exception as e:
    print(f"CRASH: setattr -> {type(e).__name__}: {e}")
