"""a5_hydration_router Part 1: reflex#7360 regression hunt (on_load router_data removal + frontend header filtering).

Every on_load flavour records what it sees in self.router into RS.log (JSON lines, secrets reduced to booleans so the
state itself never carries a secret); /front renders the router vars on the frontend (incl. the deprecated cookie forms).
"""

import asyncio
import json
import os

import reflex as rx
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

assert f"/scratchpad/envs/{os.environ['RVH_VENV']}/" in rx.__file__, (os.environ.get("RVH_VENV"), rx.__file__)

SECRETS = {
    "ck_plain": "PLAINSECRET7a1",
    "ck_httponly": "HTTPONLYSECRET9f3",
    "authorization": "AUTHSECRET41c",
    "proxy-authorization": "PROXYAUTHSECRET5d",
    "cf-access-jwt-assertion": "CFJWTSECRET88b",
    "x-forwarded-access-token": "XFATSECRET2e0",
    "x-auth-request-access-token": "XARATSECRET6b2",
    "x-amzn-oidc-accesstoken": "AMZNSECRET3c9",
    "x-amzn-oidc-data": "AMZNDATASECRET1f",
    "x-goog-iap-jwt-assertion": "IAPSECRET77e",
}


def snap(router, tag: str) -> str:
    """Reduce self.router to a JSON line without secrets."""
    try:
        page = router.page  # deprecated alias, still what many apps use
        page_d = {
            "page_path": page.path,
            "raw_path": page.raw_path,
            "full_path": page.full_path,
            "params": dict(page.params),
            "page_host": page.host,
        }
    except Exception as e:  # noqa: BLE001
        page_d = {"page_err": repr(e)}
    h = router.headers
    raw = dict(h.raw_headers)
    cookie = h.cookie or ""
    d = {
        "tag": tag,
        **page_d,
        "url": str(router.url),
        "url_path": router.url.path,
        "qp": dict(router.url.query_parameters),
        "route_id": router.route_id,
        "host": h.host,
        "origin": h.origin,
        "ua": (h.user_agent or "")[:12],
        "ck_names": sorted(p.split("=", 1)[0].strip() for p in cookie.split(";") if p.strip()),
        "be_ck_plain": SECRETS["ck_plain"] in cookie,
        "be_ck_httponly": SECRETS["ck_httponly"] in cookie,
        "be_raw_cookie": SECRETS["ck_plain"] in raw.get("cookie", ""),
        "be_auth": SECRETS["authorization"] in raw.get("authorization", ""),
        "be_cfjwt": SECRETS["cf-access-jwt-assertion"] in raw.get("cf-access-jwt-assertion", ""),
        "be_xfat": SECRETS["x-forwarded-access-token"] in raw.get("x-forwarded-access-token", ""),
        "raw_n": len(raw),
        "tok": (router.session.client_token or "")[:8],
        "sid": (router.session.session_id or "")[:6],
        "ip": router.session.client_ip,
        "pid": os.getpid(),
    }
    return json.dumps(d, sort_keys=True)


class RS(rx.State):
    log: list[str] = []
    bg_ticks: int = 0
    synced: str = rx.LocalStorage("init", name="rtr_synced", sync=True)
    recv: str = ""

    def _rec(self, tag: str):
        self.log.append(snap(self.router, tag))

    @rx.event
    def clear_log(self):
        self.log = []

    @rx.event
    def probe(self):
        self._rec("probe")

    @rx.event
    def ol_index(self):
        self._rec("ol_index")

    @rx.event
    def ol_a(self):
        self._rec("ol_a")

    @rx.event
    def ol_b(self):
        self._rec("ol_b")

    @rx.event
    def ol_chain_yield(self):
        self._rec("ol_chain_yield")
        yield Other.chained

    @rx.event
    def ol_chain_return(self):
        self._rec("ol_chain_return")
        return RS.returned

    @rx.event
    def returned(self):
        self._rec("returned")

    @rx.event(background=True)
    async def ol_bg(self):
        async with self:
            self._rec("bg_start")
        await asyncio.sleep(0.6)
        async with self:
            self._rec("bg_after")
            self.bg_ticks += 1
        yield rx.console_log("bg-yield-frontend-event")
        yield RS.after_bg

    @rx.event
    def after_bg(self):
        self._rec("after_bg")

    @rx.event
    def ol_redirect(self):
        self._rec("ol_redirect")
        return rx.redirect("/target?from=redir")

    @rx.event
    def ol_redirect2(self):
        self._rec("ol_redirect2")
        return rx.redirect("/redir?hop=1")

    @rx.event
    def ol_target(self):
        self._rec("ol_target")

    @rx.event
    def ol_post(self):
        self._rec("ol_post")

    @rx.event
    def ol_splat(self):
        self._rec("ol_splat")

    @rx.event
    def ol_fe(self):
        self._rec("ol_fe")

    @rx.event
    def cb_script(self, value):
        self._rec(f"cb_script:{value}")

    @rx.event
    def set_synced_to(self, value: str):
        self.synced = value

    @rx.event
    def recv_headers(self, hdrs: dict):
        # what the FRONTEND holds in State.router.headers, passed back as an event arg
        txt = json.dumps(hdrs)
        self.recv = json.dumps({
            "keys": sorted(hdrs.keys()) if isinstance(hdrs, dict) else str(type(hdrs)),
            "raw_keys": sorted((hdrs.get("raw_headers") or {}).keys()) if isinstance(hdrs, dict) else [],
            "has_secret": any(s in txt for s in SECRETS.values()),
        })

    @rx.event
    def recv_cookie(self, ck: str):
        self.recv = json.dumps({"cookie_arg": ck[:40] if ck else ck, "has_secret": any(s in (ck or "") for s in SECRETS.values())})

    @rx.var
    def cv_router(self) -> str:
        return f"{self.router.url.path}|{json.dumps(dict(self.router.url.query_parameters), sort_keys=True)}|{json.dumps(dict(self.router.page.params), sort_keys=True)}"

    @rx.var
    def cv_has_cookie(self) -> bool:
        return SECRETS["ck_plain"] in (self.router.headers.cookie or "")

    @rx.var
    def cv_has_auth(self) -> bool:
        return SECRETS["authorization"] in self.router.headers.raw_headers.get("authorization", "")


class Other(rx.State):
    @rx.event
    async def chained(self):
        rs = await self.get_state(RS)
        rs.log.append(snap(self.router, "other_chained"))

    @rx.event
    async def ol_other(self):
        rs = await self.get_state(RS)
        rs.log.append(snap(self.router, "other_ol"))


PAGES = ["/", "/multi", "/chain", "/bg", "/redir", "/redir-chain", "/target", "/post/hello?x=1", "/post/hello?x=2",
         "/post/other", "/files", "/files/a/b/c", "/fe", "/front", "/sync"]


def nav():
    return rx.hstack(
        *[rx.link(p, href=p, id="nav" + p.replace("/", "_").replace("?", "_q_").replace("=", "_")) for p in PAGES],
        rx.button("probe", id="probe", on_click=RS.probe),
        rx.button("clear", id="clear", on_click=RS.clear_log),
        wrap="wrap",
    )


def logview():
    return rx.box(
        rx.text("ticks:", RS.bg_ticks, id="ticks"),
        rx.text(RS.cv_router, id="cv_router"),
        rx.text(rx.cond(RS.cv_has_cookie, "cv_has_cookie=yes", "cv_has_cookie=no"), id="cv_has_cookie"),
        rx.text(rx.cond(RS.cv_has_auth, "cv_has_auth=yes", "cv_has_auth=no"), id="cv_has_auth"),
        rx.text("loglen:", RS.log.length(), id="loglen"),
        rx.foreach(RS.log, lambda line: rx.el.pre(line, class_name="logline")),
        rx.text(RS.is_hydrated.to_string(), id="hydrated"),
    )


def page_body(title: str):
    def _p():
        return rx.vstack(rx.heading(title, id="title"), nav(), logview())

    return _p


def front():
    r = RS.router
    return rx.vstack(
        rx.heading("front", id="title"),
        nav(),
        rx.text(r.page.path, id="f_page_path"),
        rx.text(r.page.params.to_string(), id="f_params"),
        rx.text(r.url, id="f_url"),
        rx.text(r.url.path, id="f_url_path"),
        rx.text(r.url.query_parameters.to_string(), id="f_qp"),
        rx.text(r.headers.user_agent, id="f_ua"),
        rx.text("[", r.headers.cookie, "]", id="f_cookie"),
        rx.text("[", r.headers["cookie"], "]", id="f_cookie_idx"),
        rx.text(rx.cond(r.headers.cookie.contains("PLAIN"), "contains=yes", "contains=no"), id="f_cookie_contains"),
        rx.text("[", r.headers.raw_headers["cookie"], "]", id="f_raw_cookie_idx"),
        rx.text("[", r.headers.raw_headers.get("cookie", ""), "]", id="f_raw_cookie_get"),
        rx.text("[", r.headers.raw_headers["authorization"], "]", id="f_raw_auth_idx"),
        rx.text(r.headers.raw_headers.to_string(), id="f_raw"),
        rx.box(rx.foreach(r.headers.raw_headers, lambda kv: rx.text(kv[0], "=", kv[1], class_name="rawkv")), id="f_raw_fe"),
        rx.text(r.headers.to_string(), id="f_headers_all"),
        rx.text(r.session.client_ip, id="f_ip"),
        rx.text(r.session.client_token, id="f_tok"),
        rx.text(r.to_string(), id="f_router_all"),
        rx.button("send headers", id="send_headers", on_click=RS.recv_headers(r.headers)),
        rx.button("send cookie", id="send_cookie", on_click=RS.recv_cookie(r.headers.cookie)),
        rx.text(RS.recv, id="recv"),
        logview(),
    )


def sync_page():
    return rx.vstack(
        rx.heading("sync", id="title"),
        nav(),
        rx.text(RS.synced, id="synced"),
        rx.button("s1", id="s1", on_click=RS.set_synced_to("s1")),
        rx.button("s2", id="s2", on_click=RS.set_synced_to("s2")),
        logview(),
    )


async def setck(request):
    resp = PlainTextResponse("cookie set")
    resp.set_cookie("rtr_httponly", SECRETS["ck_httponly"], httponly=True, path="/", samesite="lax")
    return resp


api = Starlette(routes=[Route("/setck", setck)])

BIS = os.environ.get("RTR_BISECT", "")
app = rx.App(api_transformer=api) if "noapi" not in BIS else rx.App()
app.add_page(page_body("index"), route="/", on_load=RS.ol_index)
app.add_page(page_body("multi"), route="/multi", on_load=[RS.ol_a, RS.ol_b, Other.ol_other])
app.add_page(page_body("chain"), route="/chain", on_load=[RS.ol_chain_yield, RS.ol_chain_return])
app.add_page(page_body("bg"), route="/bg", on_load=RS.ol_bg)
app.add_page(page_body("redir"), route="/redir", on_load=RS.ol_redirect)
app.add_page(page_body("redir-chain"), route="/redir-chain", on_load=RS.ol_redirect2)
app.add_page(page_body("target"), route="/target", on_load=RS.ol_target)
if "nodyn" not in BIS:
    app.add_page(page_body("post"), route="/post/[slug]", on_load=RS.ol_post)
    app.add_page(page_body("files"), route="/files/[[...splat]]", on_load=RS.ol_splat)
if "nofe" not in BIS:
  app.add_page(page_body("fe"), route="/fe", on_load=[rx.console_log("fe-onload-frontend-event"),
                                                    rx.call_script("'scriptval'", callback=RS.cb_script), RS.ol_fe])
if "nofront" not in BIS:
    app.add_page(front, route="/front")
if "nosync" not in BIS:
    app.add_page(sync_page, route="/sync")
