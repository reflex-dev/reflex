"""vauth + client-storage vars on an auth-protected state (#7493 regression hunt).

#7493 makes the boot (`hydrate_and_load`) delta echo the browser's client-storage values through
`get_delta`, i.e. through the enterprise delta filter (`install_delta_filter`), and the browser
persists that delta. This app checks what happens to client-storage vars that live on a state
protected by the AuthPlugin secure default:

  Vault.draft  rx.LocalStorage (sync)   protected (secure default)
  Vault.ck     rx.Cookie                protected (secure default)

Pages: / public (auth=False) showing the protected vars (placeholders for anonymous), /vault
protected (set/add/logout), /pid public.
"""

import os

import reflex as rx
import reflex_enterprise as rxe
from reflex_enterprise.auth import AuthUserState


class Vault(rx.State):
    """App data protected by the AuthPlugin default (auth=True)."""

    clicks: int = 0
    entries: list[str] = []
    draft: str = rx.LocalStorage("", name="vx_draft", sync=True)
    ck: str = rx.Cookie("", name="vx_ck", max_age=3600)

    @rx.event
    async def add_entry(self):
        """Protected event: record which identity the server attributes it to."""
        info = await AuthUserState.current() or {}
        self.clicks += 1
        self.entries.append(f"click{self.clicks}:{info.get('sub', '<anon>')}")

    @rx.event
    async def set_draft(self):
        """Protected event: store a per-user value in browser storage."""
        info = await AuthUserState.current() or {}
        self.draft = f"draft-of-{info.get('sub', '<anon>')}"
        self.ck = f"ck-of-{info.get('sub', '<anon>')}"


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
        rx.text("draft=", rx.text.span(Vault.draft, id="draft")),
        rx.text("ck=", rx.text.span(Vault.ck, id="ck")),
        rx.link("to vault", href="/vault", id="to-vault"),
    )


def vault() -> rx.Component:
    """Protected page."""
    return rx.vstack(
        rx.heading("vault"),
        rx.text("who=", rx.text.span(AuthUserState.sub, id="who")),
        rx.text("clicks=", rx.text.span(Vault.clicks, id="clicks")),
        rx.text("draft=", rx.text.span(Vault.draft, id="draft")),
        rx.text("ck=", rx.text.span(Vault.ck, id="ck")),
        rx.foreach(Vault.entries, lambda e: rx.text(e, class_name="entry")),
        rx.button("add", on_click=Vault.add_entry, id="add"),
        rx.button("set draft", on_click=Vault.set_draft, id="set-draft"),
        rx.button("logout", on_click=AuthUserState.logout, id="logout"),
        rx.link("home", href="/", id="to-home"),
        rx.link("vault2", href="/vault2", id="to-vault2"),
    )


def vault2() -> rx.Component:
    """Second protected page (client-side navigation between protected pages)."""
    return rx.vstack(
        rx.heading("vault2"),
        rx.text("who=", rx.text.span(AuthUserState.sub, id="who")),
        rx.text("draft=", rx.text.span(Vault.draft, id="draft")),
        rx.text("ck=", rx.text.span(Vault.ck, id="ck")),
        rx.link("back to vault", href="/vault", id="to-vault"),
    )


def pid_page() -> rx.Component:
    """Public pid page."""
    return rx.text("pid=", rx.text.span(PidState.pid, id="pid"))


app = rxe.App()
app.add_page(index, route="/", auth=False)
app.add_page(vault, route="/vault")
app.add_page(vault2, route="/vault2")
app.add_page(pid_page, route="/pid", auth=False, on_load=PidState.load_pid)
