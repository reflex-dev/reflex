"""client_state exploration app for reflex 0.11.0a1 (cluster client_vars)."""
import asyncio
import os
from typing import Any

import reflex as rx
from reflex_base.vars.base import Var
from reflex_base.vars.function import ArgsFunctionOperationBuilder

if os.environ.get("EXPECT_VENV"):
    assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__

from .other_mod import dup2
from .shared import blob, dup, hidden, late, page_local, query


class RenderProbe(rx.Component):
    """Custom component: shows a value and counts its own renders (commits) in window.__rc[name]."""

    library = "$/public/render_probe"
    tag = "RenderProbe"
    name: rx.Var[str]
    value: rx.Var[Any]


def probe(name: str, value, id: str | None = None, **kw) -> rx.Component:
    return RenderProbe.create(name=name, value=value, id=id or name, **kw)


class S(rx.State):
    server_count: int = 0
    retrieved: str = ""
    retrieved_log: list[str] = []
    rows: list[str] = ["a", "b", "c"]
    show_a: bool = True
    bg_status: str = ""

    @rx.event
    def server_incr(self):
        self.server_count += 1

    @rx.event
    def push_query(self):
        return query.push("from-backend")

    @rx.event
    def push_many(self):
        # several pushes in one handler
        yield query.push("p1")
        yield query.push("p2")
        yield blob.push({"n": 7, "items": ["x", "é", "😀"], "nested": {"none": None}})

    @rx.event
    def push_late(self):
        return late.push("pushed-before-mount")

    @rx.event
    def push_hidden(self):
        return hidden.push("secret")

    @rx.event
    def retrieve_query(self):
        return query.retrieve(S.got)

    @rx.event
    def retrieve_hidden(self):
        return hidden.retrieve(S.got)

    @rx.event
    def retrieve_blob(self):
        return blob.retrieve(S.got_any)

    @rx.event
    def retrieve_late(self):
        return late.retrieve(S.got_any)

    @rx.event
    def got(self, value: str):
        self.retrieved = f"{value!r}"
        self.retrieved_log.append(f"{value!r}")

    @rx.event
    def got_any(self, value: dict | str | None):
        self.retrieved = f"{value!r}"
        self.retrieved_log.append(f"{value!r}")

    @rx.event(background=True)
    async def bg_push(self):
        for i in range(3):
            await asyncio.sleep(0.3)
            yield query.push(f"bg-{i}")
        async with self:
            self.bg_status = "bg-push-done"

    @rx.event(background=True)
    async def bg_retrieve(self):
        await asyncio.sleep(0.2)
        yield query.retrieve(S.got)
        async with self:
            self.bg_status = "bg-retrieve-sent"

    @rx.event
    def push_then_retrieve(self):
        # ordering: push then retrieve in one handler
        yield query.push("ordered")
        yield query.retrieve(S.got)

    @rx.event
    def add_row(self):
        self.rows.append(f"r{len(self.rows)}")

    @rx.event
    def del_first_row(self):
        if self.rows:
            self.rows.pop(0)

    @rx.event
    def toggle(self):
        self.show_a = not self.show_a

    @rx.event
    def clear_log(self):
        self.retrieved = ""
        self.retrieved_log = []


def header() -> rx.Component:
    """Layout component used by every page: reads and writes the named var."""
    return rx.hstack(
        rx.text("hdr-query=", probe("hdr_query", query.value, "hdr-query")),
        rx.button("hdr-clear", id="hdr-clear", on_click=query.set("")),
        rx.link("home", href="/", id="nav-home"),
        rx.link("other", href="/other", id="nav-other"),
        rx.link("memo", href="/memo", id="nav-memo"),
        rx.link("backend", href="/backend", id="nav-backend"),
        rx.link("legacy", href="/legacy", id="nav-legacy"),
        rx.text(S.router.session.client_token, id="token", display="none"),
        rx.text(rx.cond(S.is_hydrated, "hydrated", "no"), id="hyd"),
        id="hdr",
    )


def layout(*children) -> rx.Component:
    return rx.vstack(header(), *children)


# index
page_count = rx.client_state(0)
unrelated = rx.client_state("u0")
fv_count = rx.client_state(1)
suffixed = rx.client_state("")


def index() -> rx.Component:
    return layout(
        rx.heading("index"),
        rx.input(value=query.value, on_change=query.set, id="q-input"),
        probe("q_a", query.value, "q-a"),
        rx.el.span(query.value, id="q-b"),
        # unnamed page var, value/lambda/FunctionVar
        probe("pc", page_count.value),
        rx.button("pc+1", id="pc-inc", on_click=page_count.set(lambda v: v + 1)),
        rx.button("pc=5", id="pc-5", on_click=page_count.set(5)),
        probe("fv", fv_count.value),
        rx.button(
            "fv*2",
            id="fv-dbl",
            on_click=fv_count.set(
                ArgsFunctionOperationBuilder.create(args_names=("v",), return_expr=Var("v * 2"))
            ),
        ),
        # a var nobody writes in these tests + static element: render isolation
        probe("unrelated", unrelated.value),
        probe("static", "static"),
        probe("pc2", page_count.value + 0),
        probe("sc", S.server_count),
        # chained: client set + server event (both orders)
        rx.button("chain-cs-first", id="chain1", on_click=[page_count.set(lambda v: v + 10), S.server_incr]),
        rx.button("chain-server-first", id="chain2", on_click=[S.server_incr, page_count.set(lambda v: v + 100)]),
        # trigger arg in compound value
        rx.input(on_change=lambda v: suffixed.set(v.to(str) + "!"), id="suf-input"),
        rx.el.span(suffixed.value, id="suf"),
        # deprecated set_value
        rx.button("sv", id="sv", on_click=page_count.set_value(42)),
        rx.input(on_change=suffixed.set_value(), id="sv-input"),
        # module-level unnamed var used on two pages
        rx.el.span(page_local.value, id="pl"),
        rx.button("pl+1", id="pl-inc", on_click=page_local.set(lambda v: v + 1)),
        # form on_submit writing a named var
        rx.form(
            rx.input(name="field", id="form-field"),
            rx.button("submit", type="submit", id="form-submit"),
            on_submit=lambda data: query.set(data.to(dict[str, str])["field"]),
            reset_on_submit=True,
        ),
        # named var with same name from two modules
        rx.el.span(dup.value, id="dup-a"),
        rx.el.span(dup2.value, id="dup-b"),
        rx.button("dup-set-a", id="dup-set-a", on_click=dup.set("via-a")),
        rx.button("dup-set-b", id="dup-set-b", on_click=dup2.set("via-b")),
    )


# other
other_local = rx.client_state("other-default")


def other() -> rx.Component:
    return layout(
        rx.heading("other"),
        rx.el.span(query.value, id="q-other"),
        rx.input(value=query.value, on_change=query.set, id="q-input-other"),
        rx.el.span(page_local.value, id="pl-other"),
        rx.button("pl+1", id="pl-inc-other", on_click=page_local.set(lambda v: v + 1)),
        rx.el.span(other_local.value, id="ol"),
        rx.button("ol-set", id="ol-set", on_click=other_local.set("changed")),
        rx.el.span(late.value, id="late"),
        rx.el.span(dup.value, id="dup-other"),
    )


# memo / foreach / cond / ComponentState
@rx.memo
def counter(label: rx.Var[str]) -> rx.Component:
    count = rx.client_state(0)
    return rx.hstack(
        rx.button("-", on_click=count.set(lambda v: v - 1), class_name="dec"),
        RenderProbe.create(name="memo_counter", value=count.value, class_name="val"),
        rx.button("+", on_click=count.set(lambda v: v + 1), class_name="inc"),
        rx.el.span(query.value, class_name="q"),
        id=f"counter-{label}",
    )


@rx.memo
def row(item: rx.Var[str]) -> rx.Component:
    expanded = rx.client_state(False)
    return rx.hstack(
        rx.text(item),
        rx.button("toggle", on_click=expanded.set(lambda v: ~v), class_name="tog"),
        rx.el.span(rx.cond(expanded.value, "open", "closed"), class_name="st"),
        class_name="memo-row",
    )


def plain_counter(ident: str) -> rx.Component:
    count = rx.client_state(0, prefix="plain")
    return rx.hstack(
        rx.el.span(count.value, class_name="val"),
        rx.button("+", on_click=count.set(lambda v: v + 1), class_name="inc"),
        id=f"plain-{ident}",
    )


def lambda_row(item: rx.Var[str]) -> rx.Component:
    # unnamed var created inside a plain foreach render function (not a memo)
    flag = rx.client_state(False, prefix="lrow")
    return rx.hstack(
        rx.text(item),
        rx.button("toggle", on_click=flag.set(lambda v: ~v), class_name="tog"),
        rx.el.span(rx.cond(flag.value, "open", "closed"), class_name="st"),
        class_name="lambda-row",
    )


cond_a = rx.client_state("A0")
cond_b = rx.client_state("B0")


class Stepper(rx.ComponentState):
    server_n: int = 0

    @rx.event
    def bump(self):
        self.server_n += 1

    @classmethod
    def get_component(cls, **props):
        local = rx.client_state(0, prefix="stepper")
        return rx.hstack(
            rx.el.span(local.value, class_name="local"),
            rx.el.span(cls.server_n, class_name="server"),
            rx.button("local+1", on_click=local.set(lambda v: v + 1), class_name="linc"),
            rx.button("both", on_click=[local.set(lambda v: v + 1), cls.bump], class_name="both"),
            **props,
        )


def memo_page() -> rx.Component:
    return layout(
        rx.heading("memo"),
        counter(label="one"),
        counter(label="two"),
        counter(label="three"),
        plain_counter("x"),
        plain_counter("y"),
        rx.box(rx.foreach(S.rows, lambda item: row(item=item)), id="memo-rows"),
        rx.box(rx.foreach(S.rows, lambda_row), id="lambda-rows"),
        rx.button("add-row", id="add-row", on_click=S.add_row),
        rx.button("del-first", id="del-first", on_click=S.del_first_row),
        rx.cond(
            S.show_a,
            rx.hstack(
                rx.el.span(cond_a.value, id="cond-a"),
                rx.button("set-a", id="set-cond-a", on_click=cond_a.set("A1")),
                id="branch-a",
            ),
            rx.hstack(
                rx.el.span(cond_b.value, id="cond-b"),
                rx.button("set-b", id="set-cond-b", on_click=cond_b.set("B1")),
                id="branch-b",
            ),
        ),
        rx.button("toggle-branch", id="toggle-branch", on_click=S.toggle),
        Stepper.create(id="step-1"),
        Stepper.create(id="step-2"),
    )


# backend
def backend() -> rx.Component:
    return layout(
        rx.heading("backend"),
        rx.el.span(query.value, id="q-backend"),
        rx.el.span(blob.value.to_string(), id="blob"),
        rx.el.span(S.retrieved, id="retrieved"),
        rx.el.span(S.retrieved_log.join("|"), id="rlog"),
        rx.el.span(S.bg_status, id="bg-status"),
        rx.button("push", id="push", on_click=S.push_query),
        rx.button("push-many", id="push-many", on_click=S.push_many),
        rx.button("push-late", id="push-late", on_click=S.push_late),
        rx.button("push-hidden", id="push-hidden", on_click=S.push_hidden),
        rx.button("retrieve", id="retrieve", on_click=S.retrieve_query),
        rx.button("retrieve-hidden", id="retrieve-hidden", on_click=S.retrieve_hidden),
        rx.button("retrieve-blob", id="retrieve-blob", on_click=S.retrieve_blob),
        rx.button("retrieve-late", id="retrieve-late", on_click=S.retrieve_late),
        rx.button("bg-push", id="bg-push", on_click=S.bg_push),
        rx.button("bg-retrieve", id="bg-retrieve", on_click=S.bg_retrieve),
        rx.button("push-then-retrieve", id="ptr", on_click=S.push_then_retrieve),
        rx.button("clear-log", id="clear-log", on_click=S.clear_log),
        rx.button(
            "script-set",
            id="script-set",
            on_click=rx.call_script('refs["__client_state"].set("query", "from-call-script")'),
        ),
        # client set then server retrieve in one chain
        rx.button("set-then-retrieve", id="str", on_click=[query.set("chained"), S.retrieve_query]),
    )


# legacy (rx._x.client_state, as an app ported from 0.10.1)
legacy_named = rx._x.client_state("legacy_named", default="L0")
legacy_local = rx._x.client_state("legacy_local", default=0, global_ref=False)


class LS(rx.State):
    got: str = ""

    @rx.event
    def push(self):
        return legacy_named.push("L-pushed")

    @rx.event
    def retrieve(self):
        return legacy_named.retrieve(LS.on_got)

    @rx.event
    def on_got(self, v: str):
        self.got = v


def legacy() -> rx.Component:
    return layout(
        rx.heading("legacy"),
        legacy_named,
        legacy_local,
        rx.el.span(legacy_named.value, id="ln"),
        rx.button("ln-set", id="ln-set", on_click=legacy_named.set_value("L1")),
        rx.input(on_change=legacy_named.set, id="ln-input"),
        rx.el.span(legacy_local.value, id="ll"),
        rx.button("ll-inc", id="ll-inc", on_click=legacy_local.set_value(legacy_local.value + 1)),
        rx.button("ln-push", id="ln-push", on_click=LS.push),
        rx.button("ln-retrieve", id="ln-retrieve", on_click=LS.retrieve),
        rx.el.span(LS.got, id="ln-got"),
    )


app = rx.App()
app.add_page(index, route="/")
app.add_page(other, route="/other")
app.add_page(memo_page, route="/memo")
app.add_page(backend, route="/backend")
app.add_page(legacy, route="/legacy")
