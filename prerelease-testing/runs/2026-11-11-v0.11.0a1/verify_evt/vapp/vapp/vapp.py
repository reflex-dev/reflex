"""Verifier app: issue 3 (await outside modify_state in an API route) and issue 4 (non-event return values)."""
import reflex as rx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


class Main(rx.State):
    total: int = 0
    secret: str = ""
    a: int = 7
    b: int = 0
    last: str = ""

    @rx.event
    def add(self, amount: int) -> int:
        self.total += amount
        return self.total

    @rx.event
    def swap_secret(self, value: str) -> str:
        """Store a caller's value and return the previous caller's."""
        prev, self.secret = self.secret, value
        return prev

    @rx.event
    def whoami(self) -> str:
        return self.router.session.client_token

    @rx.event
    def chained(self):
        self.b += 1

    @rx.event
    def ret_value(self):
        self.last = "ret_value ran"
        return self.a

    @rx.event
    def ret_garbage(self):
        self.last = "ret_garbage ran"
        return rx.redirect

    @rx.event
    def ret_self_handler(self):
        self.last = "ret_self_handler ran"
        return self.chained

    @rx.event
    def ret_class_handler(self):
        self.last = "ret_class_handler ran"
        return Main.chained


def index():
    return rx.vstack(
        rx.text("total=", Main.total, id="total"),
        rx.text("b=", Main.b, id="b"),
        rx.text("last=", Main.last, id="last"),
        rx.button("ret_value", id="ret_value", on_click=Main.ret_value),
        rx.button("ret_garbage", id="ret_garbage", on_click=Main.ret_garbage),
        rx.button("ret_self_handler", id="ret_self_handler", on_click=Main.ret_self_handler),
        rx.button("ret_class_handler", id="ret_class_handler", on_click=Main.ret_class_handler),
    )


async def outside(request: Request):
    """Await handlers in an API route WITHOUT app.modify_state (documented to raise)."""
    out = {}
    try:
        out["add"] = await Main.add(1)
        out["prev_secret"] = await Main.swap_secret(request.path_params["who"])
        out["token_seen_by_handler"] = await Main.whoami()
    except Exception as ex:
        out["error"] = f"{type(ex).__name__}: {ex}"
    return JSONResponse(out)


async def inside(request: Request):
    """Documented usage: await inside app.modify_state for a given client token."""
    token = request.path_params["token"]
    async with app.modify_state(rx.BaseStateToken(ident=token, cls=Main)):
        res = await Main.add(1)
    return JSONResponse({"add": res})


app = rx.App(api_transformer=Starlette(routes=[Route("/outside/{who}", outside), Route("/inside/{token}", inside)]))
app.add_page(index)
