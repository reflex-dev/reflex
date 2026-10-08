"""Deep-link / router probe app for reflex#7360 with the enterprise AuthPlugin (secure by default).

Pages:
  /             public (auth=False): who, links to protected pages (client-side nav), the deprecated
                frontend cookie header var and the frontend raw_headers keys.
  /vault        protected: on_load diagnostics (router.url / query / params / session / server-side
                cookie names), protected counter + event, logout.
  /vault2       protected: same diagnostics (second protected page for client nav).
  /item/[item]  protected dynamic route: same diagnostics.
"""

import json
from http.cookies import SimpleCookie

import reflex as rx
import reflex_enterprise as rxe
from reflex_enterprise.auth import AuthUserState


class Vault(rx.State):
    """App data protected by the AuthPlugin default."""

    clicks: int = 0
    entries: list[str] = []

    @rx.event
    async def add_entry(self):
        """Protected event: record which identity and page the server attributes it to."""
        info = await AuthUserState.current() or {}
        self.clicks += 1
        self.entries.append(f"click{self.clicks}:{info.get('sub', '<anon>')}@{self.router.url.path}")


def _cookie_names(raw: str) -> str:
    """Names of the cookies in a Cookie header (never the values)."""
    c = SimpleCookie()
    try:
        c.load(raw or "")
    except Exception:
        return "<unparseable>"
    return ",".join(sorted(c.keys()))


class Diag(rx.State):
    """What the on_load handler sees in self.router (server side)."""

    n_loads: int = 0
    log: list[str] = []
    url: str = ""
    path: str = ""
    query: str = ""
    params: str = ""
    cookie_names: str = ""
    token_ok: str = ""
    session_id_ok: str = ""
    raw_has_cookie: str = ""
    host: str = ""

    @rx.event
    def on_page_load(self):
        """Record the router view of this on_load event."""
        r = self.router
        self.n_loads += 1
        self.url = str(r.url)
        self.path = r.url.path
        self.query = json.dumps(dict(r.url.query_parameters), sort_keys=True)
        self.params = json.dumps(dict(r.page.params), sort_keys=True)
        self.cookie_names = _cookie_names(r.headers.cookie)
        self.raw_has_cookie = str(any(k.lower() == "cookie" for k in r.headers.raw_headers))
        self.token_ok = str(bool(r.session.client_token))
        self.session_id_ok = str(bool(r.session.session_id))
        self.host = r.page.host
        self.log.append(f"{self.n_loads}:{self.path}?{r.url.query}")


class Probe(rx.State):
    """Server-side router view from a click (non-on_load) on the public page."""

    click_cookie_names: str = ""
    click_url: str = ""

    @rx.event
    def probe(self):
        """Record the router view of a click event."""
        self.click_cookie_names = _cookie_names(self.router.headers.cookie)
        self.click_url = str(self.router.url)


def diag_block() -> rx.Component:
    """Render the Diag vars with stable ids."""
    return rx.vstack(
        rx.text("who=", rx.text.span(AuthUserState.sub, id="who")),
        rx.text("n_loads=", rx.text.span(Diag.n_loads, id="n_loads")),
        rx.text("url=", rx.text.span(Diag.url, id="d_url")),
        rx.text("path=", rx.text.span(Diag.path, id="d_path")),
        rx.text("query=", rx.text.span(Diag.query, id="d_query")),
        rx.text("params=", rx.text.span(Diag.params, id="d_params")),
        rx.text("cookie_names=", rx.text.span(Diag.cookie_names, id="d_cookies")),
        rx.text("raw_has_cookie=", rx.text.span(Diag.raw_has_cookie, id="d_rawck")),
        rx.text("token_ok=", rx.text.span(Diag.token_ok, id="d_tok")),
        rx.text("session_id_ok=", rx.text.span(Diag.session_id_ok, id="d_sid")),
        rx.text("host=", rx.text.span(Diag.host, id="d_host")),
        rx.text("log=", rx.text.span(Diag.log.join(" | "), id="d_log")),
        rx.text("clicks=", rx.text.span(Vault.clicks, id="clicks")),
        rx.foreach(Vault.entries, lambda e: rx.text(e, class_name="entry")),
        rx.button("add", on_click=Vault.add_entry, id="add"),
        rx.button("logout", on_click=AuthUserState.logout, id="logout"),
        rx.hstack(
            rx.link("home", href="/", id="nav-home"),
            rx.link("vault?x=nav", href="/vault?x=nav", id="nav-vault"),
            rx.link("vault2?q=5", href="/vault2?q=5&r=a%20b", id="nav-vault2"),
            rx.link("item xyz", href="/item/xyz?k=1", id="nav-item"),
        ),
    )


def index() -> rx.Component:
    """Public landing page."""
    return rx.vstack(
        rx.heading("public home"),
        rx.text("who=", rx.text.span(AuthUserState.sub, id="who")),
        rx.text("fe_cookie=[", rx.text.span(rx.State.router.headers.cookie, id="fe_cookie"), "]"),
        rx.text(
            "fe_raw_keys=",
            rx.text.span(rx.State.router.headers.raw_headers.keys().join(","), id="fe_raw_keys"),
        ),
        rx.text("fe_url=", rx.text.span(rx.State.router.url, id="fe_url")),
        rx.button("probe", on_click=Probe.probe, id="probe"),
        rx.text("click_cookies=", rx.text.span(Probe.click_cookie_names, id="click_cookies")),
        rx.text("click_url=", rx.text.span(Probe.click_url, id="click_url")),
        rx.link("vault?x=nav", href="/vault?x=nav", id="nav-vault"),
        rx.link("vault2?q=5", href="/vault2?q=5&r=a%20b", id="nav-vault2"),
        rx.link("item xyz", href="/item/xyz?k=1", id="nav-item"),
    )


def vault() -> rx.Component:
    """Protected page."""
    return rx.vstack(rx.heading("vault"), diag_block())


def vault2() -> rx.Component:
    """Second protected page."""
    return rx.vstack(rx.heading("vault2"), diag_block())


def item() -> rx.Component:
    """Protected dynamic route."""
    return rx.vstack(rx.heading("item"), diag_block())


app = rxe.App()
app.add_page(index, route="/", auth=False)
app.add_page(vault, route="/vault", on_load=Diag.on_page_load)
app.add_page(vault2, route="/vault2", on_load=Diag.on_page_load)
app.add_page(item, route="/item/[item]", on_load=Diag.on_page_load)
