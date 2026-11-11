"""client_state edge cases, one per page so a broken page only breaks its own route in dev (cluster client_vars)."""
import os

import reflex as rx

if os.environ.get("EXPECT_VENV"):
    assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__

PAGES = os.environ.get("CS_PAGES", "all").split(",")


def want(name: str) -> bool:
    return "all" in PAGES or name in PAGES


class S(rx.State):
    v: int = 3
    rows: list[str] = ["a", "b", "c"]
    stored: str = rx.LocalStorage("ls-default", name="pref")

    @rx.event
    def bump(self):
        self.v += 1

    @rx.event
    def del_first(self):
        if self.rows:
            self.rows.pop(0)

    @rx.event
    def set_stored(self, v: str):
        self.stored = v


def hyd() -> rx.Component:
    return rx.text(rx.cond(S.is_hydrated, "hydrated", "no"), id="hyd")


app = rx.App()

# two named vars, one name, different defaults, read by ONE component
if want("dupsame"):
    d1 = rx.client_state("first", name="shared_name")
    d2 = rx.client_state("second", name="shared_name")

    def dupsame():
        return rx.vstack(hyd(), rx.text(d1.value, "|", d2.value, id="both"))

    app.add_page(dupsame, route="/dupsame")

    # the same two vars used by one element (one generated memo component holds both hooks)
    def dupsame2():
        return rx.vstack(hyd(), rx.el.span(d2.value, title=d1.value, id="both"))

    app.add_page(dupsame2, route="/dupsame2")

# names differing only in the case of the first letter share a setter identifier
if want("casing"):
    lower = rx.client_state("lower", name="item")
    upper = rx.client_state("upper", name="Item")

    def casing():
        return rx.vstack(
            hyd(),
            rx.text(lower.value, "|", upper.value, id="both"),
            rx.button("set-lower", id="set-lower", on_click=lower.set("L")),
            rx.button("set-upper", id="set-upper", on_click=upper.set("U")),
        )

    app.add_page(casing, route="/casing")

    # both setters attached to one element: breaks the shared generated-memo module, so only on request (CS_PAGES=casing,casing2)
    def casing2():
        return rx.vstack(
            hyd(),
            rx.text(lower.value, "|", upper.value, id="both"),
            rx.button("set-both", id="set-both", on_click=[lower.set("L"), upper.set("U")]),
        )

    if "casing2" in PAGES:
        app.add_page(casing2, route="/casing2")

# memo rows in foreach, with an explicit key
if want("keyed"):

    @rx.memo
    def krow(item: rx.Var[str], rest: rx.RestProp) -> rx.Component:
        expanded = rx.client_state(False)
        return rx.hstack(
            rx.text(item, class_name="item"),
            rx.button("toggle", on_click=expanded.set(lambda v: ~v), class_name="tog"),
            rx.el.span(rx.cond(expanded.value, "open", "closed"), class_name="st"),
            rest,
            class_name="krow",
        )

    def keyed():
        return rx.vstack(
            hyd(),
            rx.box(rx.foreach(S.rows, lambda item: krow(item=item, key=item)), id="rows"),
            rx.button("del-first", id="del-first", on_click=S.del_first),
        )

    app.add_page(keyed, route="/keyed")

# documented consequence: a page-level read of a module-level var collapses per-memo state into one
if want("collapse"):
    lifted = rx.client_state(0)
    not_lifted = rx.client_state(0)

    @rx.memo
    def lifted_card() -> rx.Component:
        return rx.hstack(
            rx.el.span(lifted.value, class_name="lv"),
            rx.button("+", on_click=lifted.set(lambda v: v + 1), class_name="linc"),
            rx.el.span(not_lifted.value, class_name="nv"),
            rx.button("+", on_click=not_lifted.set(lambda v: v + 1), class_name="ninc"),
            class_name="card",
        )

    def collapse():
        return rx.vstack(hyd(), lifted_card(), lifted_card(), rx.el.span(lifted.value, id="page-lifted"))

    app.add_page(collapse, route="/collapse")

# client value in cond / match / style / foreach / computed expressions
if want("condmatch"):
    mode = rx.client_state("a")
    items = rx.client_state(["x", "y"])
    n = rx.client_state(2)

    def condmatch():
        return rx.vstack(
            hyd(),
            rx.cond(mode.value == "a", rx.text("is-a", id="cond"), rx.text("not-a", id="cond")),
            rx.match(mode.value, ("a", rx.text("match-a", id="match")), ("b", rx.text("match-b", id="match")), rx.text("match-default", id="match")),
            rx.box("styled", id="styled", width=rx.cond(mode.value == "a", "100px", "200px")),
            rx.box(rx.foreach(items.value, lambda it, i: rx.el.span(it, class_name="it")), id="items"),
            rx.el.span(items.value.length(), id="len"),
            rx.el.span(n.value * S.v, id="mul"),
            rx.el.span(f"{n.value}-{mode.value}-{S.v}", id="fmt"),
            rx.button("mode-b", id="mode-b", on_click=mode.set("b")),
            rx.button("mode-c", id="mode-c", on_click=mode.set("c")),
            rx.button("push-item", id="push-item", on_click=items.set(lambda v: rx.Var(f"[...{v!s}, 'z']").to(list[str]))),
            rx.button("n+1", id="n-inc", on_click=n.set(lambda v: v + 1)),
            rx.button("bump", id="bump", on_click=S.bump),
        )

    app.add_page(condmatch, route="/condmatch")

# unnamed var created inside rx.foreach inside an @rx.memo
if want("memoforeach"):

    @rx.memo
    def mlist(items: rx.Var[list[str]]) -> rx.Component:
        def render(item: rx.Var[str]) -> rx.Component:
            flag = rx.client_state(False, prefix="mf")
            return rx.hstack(
                rx.text(item),
                rx.button("toggle", on_click=flag.set(lambda v: ~v), class_name="tog"),
                rx.el.span(rx.cond(flag.value, "open", "closed"), class_name="st"),
                class_name="mrow",
            )

        return rx.box(rx.foreach(items, render), class_name="mlist")

    def memoforeach():
        return rx.vstack(hyd(), rx.box(mlist(items=S.rows), id="l1"), rx.box(mlist(items=S.rows), id="l2"))

    app.add_page(memoforeach, route="/memoforeach")

# default taken from a state var
if want("statedefault"):
    from_state = rx.client_state(S.v)

    def statedefault():
        return rx.vstack(
            hyd(),
            rx.el.span(from_state.value, id="fs"),
            rx.el.span(S.v, id="sv"),
            rx.button("bump", id="bump", on_click=S.bump),
            rx.button("fs+10", id="fs-inc", on_click=from_state.set(lambda v: v + 10)),
        )

    app.add_page(statedefault, route="/statedefault")

# on_mount setter, global_set, global_value
if want("mount"):
    mounted = rx.client_state("initial", name="mounted_flag")
    from reflex_base.vars.function import ArgsFunctionOperationBuilder, FunctionVar

    def mount():
        return rx.vstack(
            hyd(),
            rx.el.span(mounted.value, id="m"),
            rx.box(on_mount=mounted.set("set-on-mount"), id="mounter"),
            rx.button(
                "global-set",
                id="gs",
                on_click=rx.call_function(
                    ArgsFunctionOperationBuilder.create(args_names=(), return_expr=mounted.global_set.to(FunctionVar).call("from-global-set"))
                ),
            ),
            rx.button("log-global-value", id="gv", on_click=rx.console_log(mounted.global_value)),
        )

    app.add_page(mount, route="/mount")

# a named client state var whose name equals a LocalStorage key
if want("storagecollide"):
    pref = rx.client_state("cs-default", name="pref")

    def storagecollide():
        return rx.vstack(
            hyd(),
            rx.el.span(pref.value, id="cs"),
            rx.el.span(S.stored, id="ls"),
            rx.button("set-cs", id="set-cs", on_click=pref.set("cs-new")),
            rx.button("set-ls", id="set-ls", on_click=S.set_stored("ls-new")),
        )

    app.add_page(storagecollide, route="/storagecollide")

# a set held in client state
if want("setcs"):
    tags = rx.client_state({"a", "b"})

    def setcs():
        return rx.vstack(
            hyd(),
            rx.el.span(tags.value.to_string(), id="tags"),
            rx.el.span(tags.value.contains("c").to_string(), id="has-c"),
            rx.el.span(tags.value.length(), id="len"),
            rx.box(rx.foreach(tags.value, lambda t: rx.el.span(t, class_name="t")), id="each"),
            rx.button("add-c", id="add-c", on_click=tags.set(lambda v: v.union({"c"}))),
            rx.button("add-a", id="add-a", on_click=tags.set(lambda v: v.union({"a"}))),
        )

    app.add_page(setcs, route="/setcs")


def index():
    return rx.vstack(hyd(), rx.text("csedge index"))


app.add_page(index, route="/")
