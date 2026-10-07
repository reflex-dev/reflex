"""Minimal OIDC-protected app for verifying cross-tab logout and cookie sync.

Pages:
  /       public  (auth=False): shows the resolved user sub.
  /vault  protected (AuthPlugin secure default): user sub, a protected counter and
          list, a protected "add" event and a logout button.
  /pid    public: shows the backend worker pid that handled the page's on_load.
"""

import os

import reflex as rx
import reflex_enterprise as rxe
from reflex_enterprise.auth import AuthUserState


class Vault(rx.State):
    """App data protected by the AuthPlugin default (auth=True)."""

    clicks: int = 0
    entries: list[str] = []

    @rx.event
    async def add_entry(self):
        """Protected event: record which identity the server attributes it to."""
        info = await AuthUserState.current() or {}
        self.clicks += 1
        self.entries.append(f"click{self.clicks}:{info.get('sub', '<anon>')}")


class PidState(rx.State):
    """Public diagnostics."""

    pid: str = ""

    @rx.event
    def load_pid(self):
        """Record the backend worker pid."""
        self.pid = str(os.getpid())


def index() -> rx.Component:
    """Public landing page."""
    return rx.vstack(
        rx.heading("public home"),
        rx.text("who=", rx.text.span(AuthUserState.sub, id="who")),
        rx.link("to vault", href="/vault", id="to-vault"),
    )


def vault() -> rx.Component:
    """Protected page."""
    return rx.vstack(
        rx.heading("vault"),
        rx.text("who=", rx.text.span(AuthUserState.sub, id="who")),
        rx.text("clicks=", rx.text.span(Vault.clicks, id="clicks")),
        rx.foreach(Vault.entries, lambda e: rx.text(e, class_name="entry")),
        rx.button("add", on_click=Vault.add_entry, id="add"),
        rx.button("logout", on_click=AuthUserState.logout, id="logout"),
    )


def pid_page() -> rx.Component:
    """Public pid page."""
    return rx.text("pid=", rx.text.span(PidState.pid, id="pid"))


def _pid_header(asgi_app):
    """Wrap the backend ASGI app to tag every HTTP response with the worker pid."""
    async def wrapped(scope, receive, send):
        if scope["type"] != "http":
            return await asgi_app(scope, receive, send)

        async def send_with_pid(message):
            if message["type"] == "http.response.start":
                message = {
                    **message,
                    "headers": [*message.get("headers", []), (b"x-worker-pid", str(os.getpid()).encode())],
                }
            await send(message)

        return await asgi_app(scope, receive, send_with_pid)

    return wrapped


# VAUTH_PID_HEADER=1 adds an x-worker-pid response header (diagnostics for A-2 only).
app = rxe.App(
    api_transformer=_pid_header if os.environ.get("VAUTH_PID_HEADER") == "1" else None
)
app.add_page(index, route="/", auth=False)
app.add_page(vault, route="/vault")
app.add_page(pid_page, route="/pid", auth=False, on_load=PidState.load_pid)
