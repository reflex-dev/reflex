"""hydration_net probe app for the 0.10.1a1 pass.

Pages:
  /ip      #7614 client_ip + #7588/#7602 headers: handler records router data (IPState.rec), frontend renders client_ip
  /big     #7551/#7605 oversized hydrate: a LocalStorage + a Cookie var the driver fills directly
  /shared  #7545 several sync=True vars sharing one storage name (ComponentState x2 + a plain state)
  /cv      #7568 cached computed vars over storage evaluated once per load (module-level eval counters)
  /typed   #7603 vars annotated Cookie / LocalStorage / SessionStorage / unions / Field + int / bool / dict storage
  /ovr     #7572 get_delta override that assigns a storage var; cached dependents must follow
  /cs      #7407 global rx._x.client_state: reader behind rx.cond, backend push before any reader mounts
  /gate    #7407 reader only rendered once is_hydrated
"""

import json
import os

import reflex as rx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

assert f"/envs/{os.environ['RVH_VENV']}/" in rx.__file__, (os.environ.get("RVH_VENV"), rx.__file__)

HDRS = ("x-forwarded-for", "x-real-ip", "forwarded", "asgi-scope-client", "x-dup", "x-bad", "x-name", "cookie")


def router_snap(router, tag: str) -> str:
    h = router.headers
    raw = dict(h.raw_headers)
    return json.dumps(
        {
            "tag": tag,
            "ip": router.session.client_ip,
            "cookie_attr": h.cookie,
            "raw_n": len(raw),
            **{k: raw.get(k) for k in HDRS},
            "pid": os.getpid(),
        },
        sort_keys=True,
        ensure_ascii=False,
    )


class IPState(rx.State):
    seen: list[str] = []

    @rx.event
    def rec(self, tag: str):
        self.seen.append(router_snap(self.router, tag))

    @rx.event
    def clear(self):
        self.seen = []

    @rx.event
    async def up(self, files: list[rx.UploadFile]):
        # the upload handler runs with the websocket session's router data
        self.seen.append(router_snap(self.router, f"upload:{len(files)}"))

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
        rx.upload(rx.text("drop"), id="upl", multiple=False),
        rx.button("upload", id="do-upload", on_click=IPState.up(rx.upload_files(upload_id="upl"))),
        rx.text("n:", IPState.seen.length(), id="n"),
        rx.foreach(IPState.seen, lambda line: rx.el.pre(line, class_name="seen")),
        rx.text(IPState.is_hydrated.to_string(), id="hydrated"),
    )


class Big(rx.State):
    big: str = rx.LocalStorage("", name="hnet_big")
    bigck: str = rx.Cookie("", name="hnet_bigck", max_age=3600)
    clicks: int = 0

    @rx.var
    def big_len(self) -> int:
        return len(self.big)

    @rx.event
    def set_big(self, n: int):
        self.big = "x" * int(n)

    @rx.event
    def click(self):
        self.clicks += 1


def big_page():
    return rx.vstack(
        rx.heading("big", id="title"),
        rx.text("len:", Big.big_len, id="big-len"),
        rx.text("ck:", Big.bigck.length(), id="ck-len"),
        rx.text("clicks:", Big.clicks, id="clicks"),
        rx.button("click", id="click", on_click=Big.click),
        rx.button("clear big", id="clear-big", on_click=Big.set_big(0)),
        rx.button("big 300k", id="big-300k", on_click=Big.set_big(300_000)),
        rx.text(Big.is_hydrated.to_string(), id="hydrated"),
    )


class Pref(rx.ComponentState):
    """ComponentState with a named sync=True LocalStorage var; used twice on /shared (#7506 shape)."""

    val: str = rx.LocalStorage("pref-default", name="hnet_shared", sync=True)

    @rx.event
    def set_it(self, v: str):
        self.val = v

    @classmethod
    def get_component(cls, tag: str, **props):
        return rx.vstack(
            rx.text(cls.val, id=f"v-{tag}"),
            rx.input(id=f"in-{tag}", on_blur=cls.set_it, placeholder=tag),
            rx.button(f"set {tag}", id=f"set-{tag}", on_click=cls.set_it(f"from-{tag}")),
        )


class Plain(rx.State):
    shared: str = rx.LocalStorage("plain-default", name="hnet_shared", sync=True)
    other: str = rx.LocalStorage("other-default", name="hnet_other", sync=True)

    @rx.event
    def set_shared(self, v: str):
        self.shared = v

    @rx.event
    def set_other(self, v: str):
        self.other = v


def shared_page():
    return rx.vstack(
        rx.heading("shared", id="title"),
        Pref.create("a"),
        Pref.create("b"),
        rx.text(Plain.shared, id="v-plain"),
        rx.button("set plain", id="set-plain", on_click=Plain.set_shared("from-plain")),
        rx.text(Plain.other, id="v-other"),
        rx.button("set other", id="set-other", on_click=Plain.set_other("from-other")),
        rx.text(Plain.is_hydrated.to_string(), id="hydrated"),
    )


EVALS = {"tok_len": 0, "sib_len": 0, "uncached": 0}


class Store(rx.State):
    tok: str = rx.LocalStorage("", name="hnet_tok")
    ck: str = rx.Cookie("", name="hnet_cv_ck")
    evals: str = ""

    @rx.var(cache=True)
    def tok_len(self) -> int:
        EVALS["tok_len"] += 1
        return len(self.tok) + len(self.ck)

    @rx.var(cache=False)
    def tok_uncached(self) -> int:
        EVALS["uncached"] += 1
        return len(self.tok)

    @rx.event
    def snap(self):
        self.evals = json.dumps(EVALS, sort_keys=True)

    @rx.event
    def reset_evals(self):
        for k in EVALS:
            EVALS[k] = 0
        self.evals = json.dumps(EVALS, sort_keys=True)

    @rx.event
    def set_tok(self, v: str):
        self.tok = v


class Sib(rx.State):
    @rx.var(cache=True)
    async def sib_len(self) -> int:
        EVALS["sib_len"] += 1
        st = await self.get_state(Store)
        return len(st.tok)


def cv_page():
    return rx.vstack(
        rx.heading("cv", id="title"),
        rx.text("tok_len:", Store.tok_len, id="tok-len"),
        rx.text("sib_len:", Sib.sib_len, id="sib-len"),
        rx.text("unc:", Store.tok_uncached, id="unc"),
        rx.text(Store.evals, id="evals"),
        rx.button("snap", id="snap", on_click=Store.snap),
        rx.button("reset", id="reset", on_click=Store.reset_evals),
        rx.button("set tok", id="set-tok", on_click=Store.set_tok("abcdef")),
        rx.text(Store.is_hydrated.to_string(), id="hydrated"),
    )


class Typed(rx.State):
    ann_ls: rx.LocalStorage = rx.LocalStorage("ls-d", name="hnet_ann_ls")
    ann_ck: rx.Cookie = rx.Cookie("ck-d", name="hnet_ann_ck", max_age=3600)
    ann_ss: rx.SessionStorage = rx.SessionStorage("ss-d", name="hnet_ann_ss")
    ann_opt: rx.LocalStorage | None = rx.LocalStorage("opt-d", name="hnet_ann_opt")
    ann_fld: rx.Field[rx.LocalStorage] = rx.field(rx.LocalStorage("fld-d", name="hnet_ann_fld"))
    n_int: int = rx.LocalStorage("3", name="hnet_int")
    n_bool: bool = rx.Cookie("true", name="hnet_bool", max_age=3600)
    j_dict: dict = rx.LocalStorage('{"a": 1}', name="hnet_json")

    @rx.var
    def summary(self) -> str:
        return json.dumps(
            {
                "ann_ls": [self.ann_ls, type(self.ann_ls).__name__],
                "ann_ck": [self.ann_ck, type(self.ann_ck).__name__],
                "ann_ss": [self.ann_ss, type(self.ann_ss).__name__],
                "ann_opt": [self.ann_opt, type(self.ann_opt).__name__],
                "ann_fld": [self.ann_fld, type(self.ann_fld).__name__],
                "n_int": [self.n_int, type(self.n_int).__name__],
                "n_bool": [self.n_bool, type(self.n_bool).__name__],
                "j_dict": [self.j_dict, type(self.j_dict).__name__],
            },
            default=str,
        )

    @rx.event
    def write_all(self, suffix: str):
        self.ann_ls = f"ls-{suffix}"
        self.ann_ck = f"ck-{suffix}"
        self.ann_ss = f"ss-{suffix}"
        self.ann_opt = f"opt-{suffix}"
        self.ann_fld = f"fld-{suffix}"
        self.n_int = len(suffix)
        self.n_bool = suffix == "w1"
        self.j_dict = {"s": suffix}

    @rx.event
    def set_opt_none(self):
        self.ann_opt = None


def typed_page():
    return rx.vstack(
        rx.heading("typed", id="title"),
        rx.text(Typed.summary, id="summary"),
        rx.text(Typed.ann_ls, id="ann-ls"),
        rx.text(Typed.n_int, id="n-int"),
        rx.text(Typed.n_bool.to_string(), id="n-bool"),
        rx.text(Typed.j_dict.to_string(), id="j-dict"),
        rx.button("w1", id="w1", on_click=Typed.write_all("w1")),
        rx.button("w2", id="w2", on_click=Typed.write_all("w2")),
        rx.button("none", id="opt-none", on_click=Typed.set_opt_none),
        rx.text(Typed.is_hydrated.to_string(), id="hydrated"),
    )


OVR = {"calls": 0, "dep_evals": 0}


class Ovr(rx.State):
    tok: str = rx.LocalStorage("", name="hnet_ovr")
    plain: str = "p"
    calls: str = ""

    @rx.var(cache=True)
    def tok_ok(self) -> str:
        OVR["dep_evals"] += 1
        return f"ok:{self.tok.startswith('good-')}:{self.tok}"

    @rx.var(cache=True)
    def plain_dep(self) -> str:
        return f"plain:{self.plain}"

    @rx.state._override_base_method
    def get_delta(self):
        OVR["calls"] += 1
        # sanitise BEFORE super(): anything not good- is wiped (issue #7571 shape: assignment inside the override)
        if self.tok and not self.tok.startswith("good-"):
            self.tok = ""
            self.plain = "sanitised"
        return super().get_delta()

    @rx.event
    def set_tok(self, v: str):
        self.tok = v

    @rx.event
    def snap(self):
        self.calls = json.dumps(OVR, sort_keys=True)


def ovr_page():
    return rx.vstack(
        rx.heading("ovr", id="title"),
        rx.text(Ovr.tok_ok, id="tok-ok"),
        rx.text(Ovr.plain_dep, id="plain-dep"),
        rx.text("[", Ovr.tok, "]", id="tok"),
        rx.text(Ovr.calls, id="calls"),
        rx.button("snap", id="snap", on_click=Ovr.snap),
        rx.button("good", id="set-good", on_click=Ovr.set_tok("good-1")),
        rx.button("bad", id="set-bad", on_click=Ovr.set_tok("bad-1")),
        rx.text(Ovr.is_hydrated.to_string(), id="hydrated"),
    )


flag = rx._x.client_state(var_name="flag", default="initial", global_ref=True)
count = rx._x.client_state(var_name="count", default=0, global_ref=True)


class CS(rx.State):
    show: bool = False
    log: list[str] = []

    @rx.event
    def toggle(self):
        self.show = not self.show

    @rx.event
    def push_on_load(self):
        # backend push before any reader mounted (fresh load: reader is behind cond / gate)
        self.log.append("push_on_load")
        return [flag.push("pushed-on-load"), count.push(5)]

    @rx.event
    def push_value(self, v: str):
        return flag.push(v)

    @rx.event
    def push_none(self):
        return flag.push(None)


def flag_reader():
    return rx.vstack(
        rx.text("flag=[", flag.value, "]", id="flag-reader"),
        rx.text("count=", count.value, id="count-reader"),
    )


def cs_page():
    return rx.vstack(
        rx.heading("cs", id="title"),
        rx.button("toggle", id="toggle", on_click=CS.toggle),
        rx.button("set clicked", id="set-clicked", on_click=flag.set_value("clicked")),
        rx.button("set default", id="set-default", on_click=flag.set_value("initial")),
        rx.button("push backend", id="push-backend", on_click=CS.push_value("from-backend")),
        rx.button("push none", id="push-none", on_click=CS.push_none),
        rx.button("count+", id="count-inc", on_click=count.set_value(count.value + 1)),
        rx.cond(CS.show, flag_reader(), rx.text("hidden", id="hidden")),
        rx.text(CS.log.join(","), id="log"),
        rx.text(CS.is_hydrated.to_string(), id="hydrated"),
    )


def gate_page():
    return rx.vstack(
        rx.heading("gate", id="title"),
        rx.cond(CS.is_hydrated, flag_reader(), rx.text("waiting", id="waiting")),
        rx.button("set clicked", id="set-clicked", on_click=flag.set_value("clicked")),
        rx.button("set default", id="set-default", on_click=flag.set_value("initial")),
        rx.text(CS.log.join(","), id="log"),
        rx.text(CS.is_hydrated.to_string(), id="hydrated"),
    )


async def whoami(request: Request):
    return JSONResponse(
        {
            "client": list(request.client) if request.client else None,
            "xff": request.headers.get("x-forwarded-for"),
            "all_xff": request.headers.getlist("x-forwarded-for"),
        }
    )


api = Starlette(routes=[Route("/whoami", whoami)])
app = rx.App(api_transformer=api)
app.add_page(ip_page, route="/ip", on_load=IPState.rec("on_load"))
app.add_page(big_page, route="/big")
app.add_page(shared_page, route="/shared")
app.add_page(cv_page, route="/cv")
app.add_page(typed_page, route="/typed")
app.add_page(ovr_page, route="/ovr")
app.add_page(cs_page, route="/cs", on_load=CS.push_on_load)
app.add_page(gate_page, route="/gate", on_load=CS.push_on_load)
app.add_page(lambda: rx.vstack(rx.heading("index", id="title"), rx.link("ip", href="/ip")), route="/")
