"""pyright probe for hybrid_property class/instance typing (0.9.11a1 claim)."""
import reflex as rx
from reflex.experimental import hybrid_property
from typing_extensions import reveal_type


class State(rx.State):
    first: str = "a"
    last: str = "b"
    count: int = 0
    names: list[str] = []
    ratio: float = 0.5
    meta: dict[str, int] = {}

    @hybrid_property
    def full(self) -> str:
        return f"{self.first} {self.last}"

    @full.setter
    def _set_full(self, value: str) -> None:
        self.first, self.last = value.split(" ", 1)

    @hybrid_property
    def doubled(self) -> int:
        return self.count * 2

    @hybrid_property
    def positive(self) -> bool:
        return self.count > 0

    @hybrid_property
    def upper(self) -> list[str]:
        return [n.upper() for n in self.names]

    @hybrid_property
    def half(self) -> float:
        return self.ratio / 2

    @hybrid_property
    def meta_copy(self) -> dict[str, int]:
        return dict(self.meta)

    @hybrid_property
    def maybe(self) -> int | None:
        return None

    # var fn declaring its own type (classmethod, redeclared name)
    @hybrid_property
    def greeting(self) -> str:  # pyright: ignore[reportRedeclaration]
        return f"hi {self.first}"

    @greeting.var
    @classmethod
    def greeting(cls) -> rx.Var[str]:
        return rx.cond(cls.first, f"hi {cls.first}", "hi")

    # var fn returning None type
    @hybrid_property
    def nothing(self) -> int:  # pyright: ignore[reportRedeclaration]
        return 1

    @nothing.var
    @classmethod
    def nothing(cls) -> None:
        return None

    # var fn under its own name (type on class access falls back to getter-derived)
    @hybrid_property
    def scaled(self) -> int:
        return self.count * 2

    @scaled.var
    def _scaled_var(cls) -> rx.Var[int]:
        return cls.count * 3

    @rx.event
    def rename(self, value: str):
        self.full = value


reveal_type(State.full)
reveal_type(State.doubled)
reveal_type(State.positive)
reveal_type(State.upper)
reveal_type(State.half)
reveal_type(State.meta_copy)
reveal_type(State.maybe)
reveal_type(State.greeting)
reveal_type(State.nothing)
reveal_type(State.scaled)
reveal_type(State().full)
reveal_type(State().doubled)
reveal_type(State().greeting)
reveal_type(State().nothing)
reveal_type(State.full.upper())
reveal_type(State.doubled + 1)
reveal_type(State.upper.length())
reveal_type(State.__dict__["full"])
_c = rx.text(State.full)
_d = rx.cond(State.positive, rx.text("y"), rx.text("n"))
_e = rx.foreach(State.upper, lambda n: rx.text(n))
