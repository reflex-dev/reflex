"""Offline probe: #7648 (@property through a state Var) and #7651 (backend var misuse).
Run: cd probes && $SB/envs/<venv>/bin/python -I var_errors_probe.py <venv>"""
import dataclasses
import functools
import io
import logging
import sys

import pydantic
import reflex as rx
import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column

venv = sys.argv[1]
assert f"/envs/{venv}/" in rx.__file__, rx.__file__


def show(label, fn):
    try:
        r = fn()
        s = str(r) if not isinstance(r, str) else r
        print(f"[ok ] {label}: {type(r).__name__} :: {s[:200]}")
    except Exception as e:  # noqa: BLE001
        print(f"[ERR] {label}: {type(e).__name__}: {str(e)[:520]}")


class PM(pydantic.BaseModel):
    first: str = "a"
    last: str = "b"

    @property
    def full(self) -> str:
        return f"{self.first} {self.last}"

    @pydantic.computed_field
    @property
    def cf(self) -> str:
        return f"{self.first}-{self.last}"

    @functools.cached_property
    def cached(self) -> str:
        return "cached"

    def method(self) -> str:
        return "m"


class PMChild(PM):
    extra: int = 0


class PMDump(pydantic.BaseModel):
    first: str = "a"

    @property
    def full(self) -> str:
        return self.first

    def model_dump(self, **kw):
        d = super().model_dump(**kw)
        d["full"] = self.full
        return d


class PMSer(pydantic.BaseModel):
    first: str = "a"

    @property
    def full(self) -> str:
        return self.first


@rx.serializer
def ser_pmser(v: PMSer) -> dict:
    return {"first": v.first, "full": v.full}


@dataclasses.dataclass
class DC:
    first: str = "a"

    @property
    def full(self) -> str:
        return self.first + "!"


@dataclasses.dataclass
class DCChild(DC):
    n: int = 0


class Base(MappedAsDataclass, DeclarativeBase):
    pass


class SAUser(Base):
    __tablename__ = "sa_user"
    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    first: Mapped[str] = mapped_column(default="a")

    @property
    def full(self) -> str:
        return self.first + "?"


class RxM(rx.Model, table=True):
    first: str = "a"

    @property
    def full(self) -> str:
        return self.first


class S(rx.State):
    pm: PM = PM()
    pmc: PMChild = PMChild()
    pmd: PMDump = PMDump()
    pms: PMSer = PMSer()
    dc: DC = DC()
    dcc: DCChild = DCChild()
    lst: list[PM] = [PM()]
    opt: PM | None = None
    dct: dict[str, DC] = {"k": DC()}
    rxm: RxM = RxM()
    v: str = "front"
    _t: str = "secret"
    _n: int = 1
    _lst: list[str] = ["x"]

    @property
    def plain_prop(self) -> str:
        return "p"

    @rx.event
    def h(self, x: str):
        pass


try:
    class S2(rx.State):
        sa: SAUser = SAUser()
    HAVE_SA = True
except Exception as e:  # noqa: BLE001
    print("SA model as state var not supported here:", type(e).__name__, str(e)[:200])
    HAVE_SA = False

print("=== #7648 @property through a state Var")
show("pydantic .first (field)", lambda: S.pm.first)
show("pydantic @property", lambda: S.pm.full)
show("pydantic @computed_field", lambda: S.pm.cf)
show("pydantic cached_property", lambda: S.pm.cached)
show("pydantic method", lambda: S.pm.method)
show("pydantic inherited @property", lambda: S.pmc.full)
show("pydantic @property + model_dump override", lambda: S.pmd.full)
show("pydantic @property + rx.serializer registered", lambda: S.pms.full)
show("dataclass @property", lambda: S.dc.full)
show("dataclass inherited @property", lambda: S.dcc.full)
show("list[PM][0].full", lambda: S.lst[0].full)
show("foreach(list[PM], p.full)", lambda: rx.foreach(S.lst, lambda p: rx.text(p.full)))
show("Optional[PM].full", lambda: S.opt.full)
show("dict[str, DC]['k'].full", lambda: S.dct["k"].full)
show("rx.Model @property", lambda: S.rxm.full)
if HAVE_SA:
    show("MappedAsDataclass @property", lambda: S2.sa.full)
    show("MappedAsDataclass column", lambda: S2.sa.first)
show("State plain @property on the class", lambda: S.plain_prop)
show("missing attribute", lambda: S.pm.nope)

print("=== #7651 backend var misuse")
show("rx.toast(S._t)", lambda: rx.toast(S._t))
show("rx.toast.info(S._t)", lambda: rx.toast.info(S._t))
show("rx.toast(title, description=S._t)", lambda: rx.toast("t", description=S._t))
show("rx.image(src=S._t)", lambda: rx.image(src=S._t))
show("rx.box(id=S._t)", lambda: rx.box(id=S._t))
show("rx.text(S._t) child", lambda: rx.text(S._t))
show("rx.el.div(title=S._t)", lambda: rx.el.div(title=S._t))
show("rx.link(href=S._t)", lambda: rx.link("x", href=S._t))
show("rx.input(value=S._t)", lambda: rx.input(value=S._t))
show("rx.box(style={'color': S._t})", lambda: rx.box(style={"color": S._t}))
show("rx.box(color=S._t)", lambda: rx.box(color=S._t))
show("rx.box(class_name=S._t)", lambda: rx.box(class_name=S._t))
show("rx.box(class_name=[S._t, 'a'])", lambda: rx.box(class_name=[S._t, "a"]))
show("rx.box(custom_attrs={'data-x': S._t})", lambda: rx.box(custom_attrs={"data-x": S._t}))
show("rx.box(key=S._t)", lambda: rx.box(key=S._t))
show("str(S._t)", lambda: str(S._t))
show("'%s' % S._t", lambda: "%s" % S._t)
show("f'{S._t!s}'", lambda: f"{S._t!s}")
show("f'{S._t}'", lambda: f"{S._t}")
show("f'{S._t!r}'", lambda: f"{S._t!r}")
show("repr(S._t)", lambda: repr(S._t))
show("'{}'.format(S._t)", lambda: "{}".format(S._t))
show("'a' + S._t", lambda: "a" + S._t)
show("S._t + 'a'", lambda: S._t + "a")
show("S._n + 1", lambda: S._n + 1)
show("S._t == 'x'", lambda: S._t == "x")
show("S._t.upper()", lambda: S._t.upper())
show("len(S._lst)", lambda: len(S._lst))
show("rx.Var.create(S._t)", lambda: rx.Var.create(S._t))
show("rx.Var.create([S._t])", lambda: rx.Var.create([S._t]))
show("rx.Var.create({'k': S._t})", lambda: rx.Var.create({"k": S._t}))
show("rx.Var.create((S._t, 1))", lambda: rx.Var.create((S._t, 1)))
show("rx.cond(S._t == 'x', 'a', 'b')  [== on a Field is a plain bool]", lambda: rx.cond(S._t == "x", "a", "b"))
show("rx.text(S.plain_prop)", lambda: rx.text(S.plain_prop))
show("rx.cond(S._t, 'a', 'b')", lambda: rx.cond(S._t, "a", "b"))
show("rx.cond(S.v, S._t, 'b')", lambda: rx.cond(S.v, S._t, "b"))
show("rx.match(S._t, ...)", lambda: rx.match(S._t, ("x", rx.text("x")), rx.text("d")))
show("rx.match(S.v, ('x', S._t), 'd')", lambda: rx.match(S.v, ("x", S._t), "d"))
show("rx.foreach(S._lst, ...)", lambda: rx.foreach(S._lst, lambda x: rx.text(x)))
show("f-string with frontend var + backend", lambda: rx.text(f"{S.v} {S._t}"))
show("on_click=S.h(S._t)", lambda: rx.button(on_click=S.h(S._t)))
show("rx.redirect(S._t)", lambda: rx.redirect(S._t))
show("rx.set_clipboard(S._t)", lambda: rx.set_clipboard(S._t))
show("rx.console_log(S._t)", lambda: rx.console_log(S._t))
show("rx.window_alert(S._t)", lambda: rx.window_alert(S._t))
show("rx.call_script(S._t)", lambda: rx.call_script(S._t))
show("rx.download(url=S._t)", lambda: rx.download(url=S._t))
show("rx.script(S._t)", lambda: rx.script(S._t))
show("rx.html(S._t)", lambda: rx.html(S._t))
show("rx.markdown(S._t)", lambda: rx.markdown(S._t))
show("rx.el.title(S._t)", lambda: rx.el.title(S._t))
show("rx.client_state(S._t)", lambda: getattr(rx, "client_state", rx._x.client_state)(S._t) if hasattr(rx, "client_state") else "n/a")
show("rx.LocalStorage(S._t)", lambda: rx.LocalStorage(S._t))
show("S._t.default_value() [suggested fix]", lambda: S._t.default_value())
print("--- add_page metadata")
APP = rx.App()
for kw in ("title", "description", "image"):
    def ap(kw=kw):
        APP.add_page(lambda: rx.text("x"), route=f"/p-{kw}", **{kw: S._t})
        return "accepted"
    show(f"app.add_page({kw}=S._t)", ap)
def ap_meta():
    APP.add_page(lambda: rx.text("x"), route="/p-meta", meta=[{"name": "x", "content": S._t}])
    return "accepted"
show("app.add_page(meta=[{content: S._t}])", ap_meta)
def ap_route():
    APP.add_page(lambda: rx.text("x"), route=S._t)
    return "accepted"
show("app.add_page(route=S._t)", ap_route)
def ap_onload():
    APP.add_page(lambda: rx.text("x"), route="/p-onload", on_load=S._t)
    return "accepted"
show("app.add_page(on_load=S._t)", ap_onload)
def ap_frontvar():
    APP.add_page(lambda: rx.text("x"), route="/p-front", title=S.v)
    return "accepted"
show("app.add_page(title=S.v) [frontend var, allowed]", ap_frontvar)
def page_deco():
    @rx.page(route="/deco", title=S._t)
    def p():
        return rx.text("x")
    return "accepted (deferred)"
show("@rx.page(title=S._t)", page_deco)

print("--- legitimate server-side uses of the class attribute")
show("S.get_fields()['_t']", lambda: type(S.get_fields()["_t"]).__name__)
show("S.get_fields()['_t'].default", lambda: S.get_fields()["_t"].default)
show("str(S.get_fields()['v'])  [frontend var Field]", lambda: str(S.get_fields()["v"]))
show("rx.text(S.get_fields()['v'])", lambda: rx.text(S.get_fields()["v"]))
show("rx.text(S.get_fields()['_t'])", lambda: rx.text(S.get_fields()["_t"]))
show("rx.text(S.__fields__['v'])", lambda: rx.text(S.__fields__["v"]))
show("S.get_fields()['v'] is S.v", lambda: S.get_fields()["v"] is S.v)
show("print(S._t)", lambda: print(S._t) or "printed")
buf = io.StringIO()
h = logging.StreamHandler(buf)
log = logging.getLogger("probe"); log.addHandler(h); log.setLevel(logging.INFO); log.propagate = False
log.info("backend field is %s", S._t)
out = buf.getvalue()
print("[log] logging.info('%s', S._t) ->", repr(out[:160]) if out else "<nothing logged; logging printed an error to stderr>")
show("vars(S)['_t'] / S.__dict__", lambda: type(S.__dict__.get("_t")).__name__)
show("hasattr(S, '_t')", lambda: hasattr(S, "_t"))
show("isinstance check", lambda: isinstance(S._t, rx.Var))
show("bool(S._t)", lambda: bool(S._t))
show("S._t in ['a']", lambda: S._t in ["a"])
show("json.dumps(S._t)", lambda: __import__("json").dumps(S._t))
show("instance: S(_reflex_internal_init=True)._t", lambda: S(_reflex_internal_init=True)._t)
