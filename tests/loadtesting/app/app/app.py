import contextlib
import os

import reflex as rx


class State(rx.State):
    last_request_id: str
    last_ix: int

    @rx.event
    def simple(self, last_request_id: str):
        self.last_request_id = last_request_id

    @rx.event
    async def simple_async(self, last_request_id: str):
        self.last_request_id = last_request_id

    @rx.event
    def multi(self, last_request_id: str, iterations: int):
        for ix in range(iterations):
            self.last_ix = ix
            self.last_request_id = last_request_id
            yield

    @rx.event(background=True)
    async def multi_background(self, last_request_id: str, iterations: int):
        for ix in range(iterations):
            async with self:
                self.last_ix = ix
                self.last_request_id = last_request_id


class SubState(State):
    @rx.event
    def simple_sub_state(self, last_request_id: str):
        self.last_request_id = last_request_id


class OtherState(rx.State):
    last_request_id: str

    @rx.event
    async def update_my_var(self, last_request_id: str):
        self.last_request_id = last_request_id

    @rx.event
    async def update_other_var(self, last_request_id: str):
        s = await self.get_state(State)
        s.last_request_id = last_request_id


class LargeState(rx.State):
    _data: str = "\0" * 1024 * 512
    last_request_id: str

    @rx.event
    async def simple(self, last_request_id: str):
        self.last_request_id = last_request_id


def index() -> rx.Component:
    return rx.text(rx.State.router.session.client_token)


@contextlib.asynccontextmanager
async def profile_lifespan():
    import yappi

    yappi.start()
    try:
        yield
    finally:
        yappi.stop()
        with open(f"app_{os.getpid()}.prof.txt", "w") as f:
            yappi.get_func_stats().print_all(f)


app = rx.App()
app.add_page(index)
