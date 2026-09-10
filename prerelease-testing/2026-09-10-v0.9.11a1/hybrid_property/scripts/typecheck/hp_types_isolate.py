"""Isolate why class-level access on a getter-only hybrid_property reveals Any."""
from typing import Any

import reflex as rx
from reflex.experimental import hybrid_property
from reflex.state import BaseState
from reflex_base.vars import Var
from reflex_base.vars.hybrid_property import HybridProperty
from typing_extensions import reveal_type


class S(rx.State):
    first: str = "a"
    n: int = 0

    @hybrid_property
    def full(self) -> str:
        return self.first

    @HybridProperty
    def direct(self) -> str:
        return self.first


class Plain:
    @hybrid_property
    def v(self) -> str:
        return "x"


reveal_type(S.first)  # control: Field-backed var on class access
reveal_type(S.n)
reveal_type(S.full)
reveal_type(S.direct)
reveal_type(Plain.v)  # non-state: descriptor itself expected
reveal_type(S.__dict__)
hp: HybridProperty[str, S, Var[Any] | None] = HybridProperty(lambda s: "x")
reveal_type(hp)
reveal_type(hp.__get__(None, S))
reveal_type(hp.__get__(None, BaseState))
hp2: HybridProperty[str, S] = HybridProperty(lambda s: "x")
reveal_type(hp2)
reveal_type(hp2.__get__(None, S))
reveal_type(HybridProperty(lambda s: "x"))
reveal_type(S.__dict__["full"])
