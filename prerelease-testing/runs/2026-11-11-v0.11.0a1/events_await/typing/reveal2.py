"""Which spelling of the decorator keeps a handler's argument types under pyright?"""

import reflex as rx
from reflex.event import event as event_a
from reflex_base.event import event as event_b


class S(rx.State):
    @rx.event
    def via_rx(self, amount: int) -> int:
        return amount

    @event_a
    def via_reflex_event(self, amount: int) -> int:
        return amount

    @event_b
    def via_reflex_base(self, amount: int) -> int:
        return amount

    @rx.event()
    def via_rx_call(self, amount: int) -> int:
        return amount

    @rx.event
    def no_args(self) -> None: ...

    @rx.event
    async def via_rx_async(self, amount: int) -> int:
        return amount

    @rx.event
    def via_rx_gen(self, amount: int):
        yield


reveal_type(rx.event)
reveal_type(S.via_rx)
reveal_type(S.via_reflex_event)
reveal_type(S.via_reflex_base)
reveal_type(S.via_rx_call)
reveal_type(S.no_args)
reveal_type(S.via_rx_async)
reveal_type(S.via_rx_gen)
# these must be errors: wrong type, too many arguments
S.via_rx("not an int")
S.via_rx(1, 2, 3)
S.via_reflex_base("not an int")
S.via_rx_call("not an int")
rx.button("x", on_click=S.via_rx("not an int"))
rx.input(on_change=S.via_rx)
