"""FINDING-025 acceptance app: AdminDash plus a normal event/request-context control.

Set ADMIN_API_TRANSFORMER=1 to also wrap the API in a Starlette app, which is the
configuration the review handoff asks to include.
"""

import os

import reflex as rx


class Widget(rx.Model, table=True):
    """A widget row for the admin dashboard."""

    name: str
    qty: int = 0


class State(rx.State):
    """A normal state, to prove the event/request context still works."""

    count: int = 0
    path: str = ""

    @rx.event
    def bump(self):
        """Increment and read the router, which needs the request context."""
        self.count += 1
        self.path = self.router.page.path


def index() -> rx.Component:
    """Index page."""
    return rx.vstack(
        rx.text(State.count, id="count"),
        rx.text(State.path, id="path"),
        rx.button("bump", on_click=State.bump, id="bump"),
        rx.link("admin", href="/admin/", id="adminlink"),
        rx.text("ready", id="ready"),
    )


app_kwargs = {"admin_dash": rx.AdminDash(models=[Widget])}

if os.environ.get("ADMIN_API_TRANSFORMER") == "1":
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def extra(request):
        """An extra route contributed by the transformer."""
        return JSONResponse({"transformer": "ok"})

    app_kwargs["api_transformer"] = Starlette(routes=[Route("/extra", extra)])

app = rx.App(**app_kwargs)
app.add_page(index, route="/")
