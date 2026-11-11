"""reveal_type probes: what do the checkers infer for handlers and awaited handlers?"""

import dataclasses

import reflex as rx
from reflex.event import EventCallback, EventHandler


class S(rx.State):
    count: int = 0

    @rx.event
    def no_args(self) -> None: ...

    @rx.event
    def add(self, amount: int) -> int:
        return amount

    @rx.event
    async def aadd(self, amount: int) -> int:
        return amount

    @rx.event(background=True)
    async def bg(self, n: int) -> str:
        return ""

    @rx.event(throttle=100)
    def throttled(self, v: str) -> None: ...

    @rx.event
    async def caller(self) -> None:
        reveal_type(type(self).add)
        reveal_type(S.add)
        reveal_type(S.add(1))
        reveal_type(await S.add(1))
        reveal_type(await S.aadd(1))
        reveal_type(await S.no_args)
        reveal_type(self.add)
        reveal_type(self.add(1))
        reveal_type(self.aadd(1))
        reveal_type(S.bg)
        reveal_type(S.throttled)
        reveal_type(S.no_args)


@dataclasses.dataclass
class Holder:
    on_submit: EventHandler
    on_text: EventCallback[str] | None = None


def f(h: Holder) -> None:
    reveal_type(h.on_submit)
    reveal_type(h.on_text)
