"""Extended hybrid_property typing probe for FINDING-005 acceptance.

Adds inherited properties, container/optional/custom frontend types and an
explicit `.var` return type to the original orch_probes/hp_types.py set.
"""

import reflex as rx
from reflex.experimental import hybrid_property
from typing_extensions import reveal_type


class Base(rx.State):
    first: str = "a"
    last: str = "b"
    count: int = 0
    names: list[str] = []

    @hybrid_property
    def full(self) -> str:
        return self.first + self.last

    @hybrid_property
    def doubled(self) -> int:
        return self.count * 2

    @hybrid_property
    def positive(self) -> bool:
        return self.count > 0

    @hybrid_property
    def tags(self) -> list[str]:
        return list(self.names)

    @hybrid_property
    def maybe(self) -> str | None:
        return self.first or None

    @hybrid_property
    def greeting(self) -> str:
        return "hi " + self.first

    @greeting.var
    def _greeting_var(cls) -> rx.Var[str]:
        return rx.Var.create("hi ").to(str) + cls.first


class Child(Base):
    """Inherits every hybrid_property above."""

    extra: str = "x"


reveal_type(Base.full)
reveal_type(Base.doubled)
reveal_type(Base.positive)
reveal_type(Base.tags)
reveal_type(Base.maybe)
reveal_type(Base.greeting)
reveal_type(Child.full)
reveal_type(Child.doubled)
reveal_type(Child.tags)
reveal_type(Child.greeting)
reveal_type(Base().full)
reveal_type(Base().doubled)
reveal_type(Base().tags)
reveal_type(Child().full)
