"""Confirm the Any-ambiguity theory: same descriptor typed without Any in the _V slot."""
from typing import Any

import reflex as rx
from reflex_base.vars import Var
from reflex_base.vars.hybrid_property import HybridProperty
from typing_extensions import reveal_type


class S(rx.State):
    first: str = "a"


hp_any: HybridProperty[str, S, Var[Any] | None] = HybridProperty(lambda s: "x")
hp_str: HybridProperty[str, S, Var[str] | None] = HybridProperty(lambda s: "x")
hp_none: HybridProperty[str, S, None] = HybridProperty(lambda s: "x")
hp_int: HybridProperty[int, S, Var[int] | None] = HybridProperty(lambda s: 1)
hp_bool: HybridProperty[bool, S, Var[bool] | None] = HybridProperty(lambda s: True)
hp_list: HybridProperty[list[str], S, Var[list[str]] | None] = HybridProperty(lambda s: [])
reveal_type(hp_any.__get__(None, S))
reveal_type(hp_str.__get__(None, S))
reveal_type(hp_none.__get__(None, S))
reveal_type(hp_int.__get__(None, S))
reveal_type(hp_bool.__get__(None, S))
reveal_type(hp_list.__get__(None, S))
