"""hnet (enterprise variant): IPState.rec records the router view the handler sees (client_ip + raw headers).

Shape copied from the hydration_net item's hnet app so probes/ws_probe.py (its raw websocket client) works unchanged:
state full name reflex___state____state.hnet___hnet___ip_state, handler rec(tag), `seen` = list of JSON strings.
"""
import json
import os

import reflex as rx
import reflex_enterprise as rxe

HDRS = ("x-forwarded-for", "x-real-ip", "forwarded", "asgi-scope-client", "cookie", "authorization", "x-dup")


def router_snap(router, tag: str) -> str:
    h = router.headers
    raw = dict(h.raw_headers)
    return json.dumps(
        {"tag": tag, "ip": router.session.client_ip, "cookie_attr": h.cookie, "raw_n": len(raw),
         "client_token_len": len(router.session.client_token or ""), "session_id_len": len(router.session.session_id or ""),
         **{k: raw.get(k) for k in HDRS}, "pid": os.getpid()},
        sort_keys=True, ensure_ascii=False,
    )


class IPState(rx.State):
    seen: list[str] = []
    secret_note: str = "SECRETNOTE-ONLY-FOR-THIS-SESSION"

    @rx.event
    def rec(self, tag: str):
        self.seen.append(router_snap(self.router, tag))

    @rx.event
    def clear(self):
        self.seen = []

    @rx.var
    def cv_ip(self) -> str:
        return self.router.session.client_ip


def ip_page():
    return rx.vstack(
        rx.heading("ip", id="title"),
        rx.text(IPState.router.session.client_ip, id="f_ip"),
        rx.text(IPState.cv_ip, id="cv_ip"),
        rx.button("rec", id="rec", on_click=IPState.rec("click")),
        rx.button("clear", id="clear", on_click=IPState.clear),
        rx.text("n:", IPState.seen.length(), id="n"),
        rx.foreach(IPState.seen, lambda line: rx.el.pre(line, class_name="seen")),
        rx.text(IPState.is_hydrated.to_string(), id="hydrated"),
    )


app = rxe.App()
app.add_page(ip_page, route="/ip", on_load=IPState.rec("on_load"))
app.add_page(lambda: rx.vstack(rx.heading("index", id="title"), rx.link("ip", href="/ip")), route="/")
