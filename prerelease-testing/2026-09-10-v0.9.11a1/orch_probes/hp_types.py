import reflex as rx
from reflex.experimental import hybrid_property
from typing_extensions import reveal_type


class State(rx.State):
    first: str = "a"
    last: str = "b"
    count: int = 0

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
    def greeting(self) -> str:
        return "hi " + self.first

    @greeting.var
    def _greeting_var(cls) -> rx.Var[str]:
        return rx.Var.create("hi ").to(str) + cls.first


reveal_type(State.full)      # promised: a str Var
reveal_type(State.doubled)   # promised: an int Var
reveal_type(State.positive)  # promised: a bool Var
reveal_type(State.greeting)  # explicit var fn type
reveal_type(State().full)    # python-side: str
reveal_type(State().doubled) # python-side: int
