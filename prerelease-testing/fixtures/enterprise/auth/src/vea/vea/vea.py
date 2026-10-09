"""verify_ent_auth app: protected client storage under the enterprise delta filter (A3-10)
and the stale-tab boot reconcile (A3-09).

Env switches (read at import, backend side):
  VEA_INSTRUMENT=1  log every filter_protected_delta call that replaces/drops keys, with
                    whether AuthUserState was in the event's tree cache (stdout: VEA_FILTER ...)
  VEA_FIX=1         causality probe: before an update_vars_internal event, resolve the user
                    (loads AuthUserState into the event tree), as the gate does for app events.
"""

import os
import time

import reflex as rx
import reflex_enterprise as rxe
from reflex_enterprise.auth import enforcement as _enf
from reflex_enterprise.auth.user_state import AuthUserState

if os.environ.get("VEA_INSTRUMENT") == "1":
    _orig_filter = _enf.filter_protected_delta

    def _logged_filter(state, delta, *, defer_to_guard=False):
        out = _orig_filter(state, delta, defer_to_guard=defer_to_guard)
        name = state.get_full_name()
        before = delta.get(name) or {}
        after = out.get(name) or {}
        changed = {
            k: (before[k], after.get(k, "<dropped>"))
            for k in before
            if k not in after or after[k] is not before[k]
        }
        if changed:
            try:
                state._get_state_from_cache(AuthUserState)
                au = "loaded"
            except Exception as e:  # noqa: BLE001
                au = f"NOT-LOADED({type(e).__name__})"
            print(
                f"VEA_FILTER t={time.time():.3f} state={name.rpartition('.')[2]} "
                f"auth_user={au} defer={defer_to_guard} changed={changed!r}",
                flush=True,
            )
        return out

    _enf.filter_protected_delta = _logged_filter

if os.environ.get("VEA_FIX") == "1":
    _orig_pre = _enf.AuthMiddleware.preprocess

    async def _pre(self, app, state, event):
        if event.name.endswith("update_vars_internal"):
            ui = await _enf.resolve_userinfo(state)
            print(f"VEA_FIX resolved={bool(ui)} for {event.name}", flush=True)
        return await _orig_pre(self, app, state, event)

    _enf.AuthMiddleware.preprocess = _pre


class Vault(rx.State):
    """Default-protected state (no rxe.field override): every var below is auth=True."""

    secret: str = ""
    draft: str = rx.LocalStorage("", name="vea_draft", sync=True)
    plain: str = rx.LocalStorage("", name="vea_plain")
    ck: str = rx.Cookie("", name="vea_ck", max_age=3600)
    ss: str = rx.SessionStorage("", name="vea_ss")
    echo: str = ""
    clicks: int = 0

    @rx.event
    async def fill(self):
        """Protected event: write per-user values into every storage kind."""
        sub = (await self.get_state(AuthUserState)).sub
        self.secret = f"secret-of-{sub}"
        self.draft = f"draft-of-{sub}"
        self.plain = f"plain-of-{sub}"
        self.ck = f"ck-of-{sub}"
        self.ss = f"ss-of-{sub}"

    @rx.event
    def show_server(self):
        """Protected event: echo what the BACKEND currently holds for the client-storage vars."""
        self.echo = f"draft={self.draft}|plain={self.plain}|ck={self.ck}|ss={self.ss}"
        self.clicks += 1


class Pub(rx.State):
    """Same storage kinds, explicitly public (auth=False) -- control."""

    pdraft: str = rxe.field(rx.LocalStorage("", name="vea_pub_draft", sync=True), auth=False)
    pck: str = rxe.field(rx.Cookie("", name="vea_pub_ck", max_age=3600), auth=False)

    @rxe.event(auth=False)
    def pfill(self):
        """Public event: write public storage."""
        self.pdraft = "pub-draft"
        self.pck = "pub-ck"


def _vals() -> rx.Component:
    return rx.vstack(
        rx.text("who=", rx.el.span(AuthUserState.sub, id="who")),
        rx.text("secret=", rx.el.span(Vault.secret, id="secret")),
        rx.text("draft=", rx.el.span(Vault.draft, id="draft")),
        rx.text("plain=", rx.el.span(Vault.plain, id="plain")),
        rx.text("ck=", rx.el.span(Vault.ck, id="ck")),
        rx.text("ss=", rx.el.span(Vault.ss, id="ss")),
        rx.text("echo=", rx.el.span(Vault.echo, id="echo")),
        rx.text("clicks=", rx.el.span(Vault.clicks, id="clicks")),
        rx.text("pdraft=", rx.el.span(Pub.pdraft, id="pdraft")),
        rx.text("pck=", rx.el.span(Pub.pck, id="pck")),
        rx.text("hydrated=", rx.el.span(rx.cond(rx.State.is_hydrated, "yes", "no"), id="hyd")),
    )


def _nav() -> rx.Component:
    return rx.hstack(
        rx.link("home", href="/", id="to_home"),
        rx.link("vault", href="/vault", id="to_vault"),
        rx.link("vault2", href="/vault2", id="to_vault2"),
        rx.link("logout", href="/logout", id="to_logout"),
    )


def _page(title: str) -> rx.Component:
    return rx.vstack(
        rx.heading(title, id="title"),
        _nav(),
        rx.hstack(
            rx.button("fill", on_click=Vault.fill, id="fill"),
            rx.button("show server", on_click=Vault.show_server, id="show"),
            rx.button("pub fill", on_click=Pub.pfill, id="pfill"),
        ),
        _vals(),
    )


def index() -> rx.Component:
    return _page("home (public)")


def vault() -> rx.Component:
    return _page("vault")


def vault2() -> rx.Component:
    return _page("vault2")


app = rxe.App()
app.add_page(index, route="/", auth=False)
app.add_page(vault, route="/vault")
app.add_page(vault2, route="/vault2")
