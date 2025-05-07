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


class SubState(rx.State):
    @rx.event
    def simple_sub_state(self, last_request_id: str):
        self.last_request_id = last_request_id


def index() -> rx.Component:
    return rx.text(rx.State.router.session.client_token)


app = rx.App()
app.add_page(index)
