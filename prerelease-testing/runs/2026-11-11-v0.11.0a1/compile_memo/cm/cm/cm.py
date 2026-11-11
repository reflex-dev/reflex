"""compile_memo cluster test app: memo / compiler / foreach hooks / refs / uploads / lazy libs / components."""

import os

import reflex as rx

NEW = hasattr(rx, "client_state")

if os.environ.get("CM_BUNDLE"):
    from reflex.components.dynamic import bundle_library

    bundle_library(rx.icon("banana"))
    bundle_library(rx.icon("info"))
    bundle_library(rx.recharts.bar_chart(rx.recharts.bar(data_key="y")))


# ---------------------------------------------------------------- probes
class RenderProbe(rx.Component):
    """A div that counts how many times React rendered it (window.__renders[probe])."""

    tag = "RenderProbe"
    probe: rx.Var[str]
    label: rx.Var[str]

    def add_custom_code(self) -> list[str]:
        return [
            """
function RenderProbe({ probe, label, children, ...rest }) {
  if (typeof window !== "undefined") {
    window.__renders ??= {};
    window.__renders[probe] = (window.__renders[probe] ?? 0) + 1;
  }
  return jsx("div", { "data-probe": probe, ...rest }, label, children);
}
"""
        ]


class HookItem(rx.el.Span):
    """A span whose own add_hooks reads its `label` prop (a loop var inside foreach)."""

    label: rx.Var[str]

    def add_hooks(self) -> list[str | rx.Var]:
        lbl = self.label
        return [
            rx.Var(
                "useEffect(() => { window.__hooklog ??= []; window.__hooklog.push('hm:' + "
                + str(lbl)
                + "); return () => window.__hooklog.push('hu:' + "
                + str(lbl)
                + "); }, [])",
                _var_data=rx.vars.VarData.merge(
                    lbl._get_all_var_data(),
                    rx.vars.VarData(imports={"react": ["useEffect"]}),
                ),
            )
        ]


# ---------------------------------------------------------------- state
class S(rx.State):
    n: int = 0
    other: int = 0
    text: str = "hello"
    flag: bool = True
    suffix: str = "abc"
    clicks: list[str] = []
    items: list[str] = ["alpha", "beta", "gamma"]
    tags: list[str] = ["x", "y"]
    mapping: dict[str, int] = {"one": 1, "two": 2}
    mounted: list[str] = []
    unmounted: list[str] = []
    branch_log: list[str] = []
    focus_log: str = ""
    upload_log: list[str] = []
    progress_log: list[str] = []
    mw_log: list[str] = []
    cols: list[dict] = [{"title": "A", "type": "str"}, {"title": "B", "type": "int"}]
    rows: list[list] = [["a", 1], ["b", 2]]
    icon_name: str = "grid_2x_2"
    icon_names: list[str] = ["grid_2x_2", "grid_3x_3", "arrow_up_0_1", "a_arrow_down", "grid-2x2", "calendar_1", "no_such_icon_x"]
    callout_kind: str = "info"
    lang: str = "text" if NEW else "python"
    cleared: int = 0

    @rx.event
    def inc(self):
        self.n += 1

    @rx.event
    def bump_other(self):
        self.other += 1

    @rx.event
    def click(self, who: str):
        self.clicks.append(who)

    @rx.event
    def toggle(self):
        self.flag = not self.flag

    @rx.event
    def record_mount(self, name: str):
        self.mounted.append(name)

    @rx.event
    def record_unmount(self, name: str):
        self.unmounted.append(name)

    @rx.event
    def log_branch(self, name: str):
        self.branch_log.append(name)

    @rx.event
    def clear_log(self):
        self.mounted = []
        self.unmounted = []
        self.branch_log = []

    @rx.event
    def add_item(self):
        self.items.append(f"item{len(self.items)}")

    @rx.event
    def remove_first(self):
        self.items.pop(0)

    @rx.event
    def remove_middle(self):
        self.items.pop(len(self.items) // 2)

    @rx.event
    def reverse(self):
        self.items = list(reversed(self.items))

    @rx.event
    def set_focus_log(self, v: str):
        self.focus_log = v

    @rx.event
    def next_icon(self):
        i = self.icon_names.index(self.icon_name)
        self.icon_name = self.icon_names[(i + 1) % len(self.icon_names)]

    @rx.event
    def cycle_callout(self):
        order = ["info", "warn", "error"]
        self.callout_kind = order[(order.index(self.callout_kind) + 1) % 3]

    @rx.event
    def on_clear(self):
        self.cleared += 1

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        for f in files:
            data = await f.read()
            self.upload_log.append(f"{f.name}:{len(data)}")

    @rx.event
    async def save_upload(self, files: list[rx.UploadFile]):
        # docs pattern: write to rx.get_upload_dir() / file.name ; also try the relative path
        updir = rx.get_upload_dir()
        for f in files:
            data = await f.read()
            rel = getattr(f, "path", None) or f.name
            out = (updir / rel)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            self.upload_log.append(f"{f.filename!r}->{out.resolve()}")

    stream_vals: list[str] = []
    stream_last: int = -1

    @rx.event
    async def stream_upload(self, files: list[rx.UploadFile]):
        import asyncio

        for f in files:
            await f.read()
        for i in range(8):
            self.stream_last = i
            self.stream_vals.append(str(i))
            yield
            await asyncio.sleep(0.05 if i % 2 else 0)

    @rx.event
    def on_progress(self, prog: dict):
        self.progress_log.append(str(round(prog.get("progress", 0), 2)))

    @rx.event
    def reset_upload(self):
        self.upload_log = []
        self.progress_log = []

    @rx.event
    def toast_upload(self):
        yield rx.toast(
            "upload?",
            action={"label": "Upload now", "on_click": S.handle_upload(rx.upload_files(upload_id="up1", on_upload_progress=S.on_progress))},
            duration=60000,
        )

    @rx.event
    def script_upload(self):
        yield rx.call_script("1", callback=lambda _: S.handle_upload(rx.upload_files(upload_id="up1")))


class Counter(rx.ComponentState):
    c: int = 0

    @rx.event
    def inc(self):
        self.c += 1

    @classmethod
    def get_component(cls, **props):
        return rx.button("cstate ", cls.c, on_click=cls.inc, **props)


# ---------------------------------------------------------------- memo components
@rx.memo
def action_row(label: rx.Var[str], who: rx.Var[str]) -> rx.Component:
    return rx.hstack(
        RenderProbe.create(probe="memo_" + who, label=label),
        rx.button("go " + who, on_click=S.click(who), class_name="memo-go"),
    )


if NEW:

    @rx.memo
    def cs_counter(label: rx.Var[str]) -> rx.Component:
        cnt = rx.client_state(0)
        return rx.hstack(
            rx.text(label, ": ", cnt.value, class_name="cs-val"),
            rx.button("+", on_click=cnt.set(lambda v: v + 1), class_name="cs-inc"),
        )

    shared_cs = rx.client_state(0, name="shared_counter")

    @rx.memo
    def memo_loop(items: rx.Var[list[str]]) -> rx.Component:
        # documented gap: a loop inside an @rx.memo function
        return rx.vstack(
            rx.foreach(
                items,
                lambda it: rx.text(
                    "ml:",
                    it,
                    on_mount=S.record_mount("ml-" + it),
                    on_unmount=S.record_unmount("ml-" + it),
                    class_name="ml-item",
                ),
            )
        )

else:

    @rx.memo
    def memo_loop(items: rx.Var[list[str]]) -> rx.Component:
        return rx.vstack(
            rx.foreach(
                items,
                lambda it: rx.text(
                    "ml:",
                    it,
                    on_mount=S.record_mount("ml-" + it),
                    on_unmount=S.record_unmount("ml-" + it),
                    class_name="ml-item",
                ),
            )
        )


def nav():
    return rx.hstack(
        *[
            rx.link(p, href=f"/{p}" if p != "home" else "/", id=f"nav-{p}")
            for p in ["home", "loop", "loopmemo", "refs", "upload", "plotly", "recharts", "editor", "dyn", "comps"]
        ],
        spacing="3",
    )


def logs():
    return rx.vstack(
        rx.text("mounted: ", S.mounted.join(","), id="mounted"),
        rx.text("unmounted: ", S.unmounted.join(","), id="unmounted"),
        rx.text("branch: ", S.branch_log.join(","), id="branch"),
        rx.button("clear log", on_click=S.clear_log, id="clear-log"),
    )


# ---------------------------------------------------------------- pages
def index():
    extra = []
    if NEW:
        extra = [
            rx.text("shared: ", shared_cs.value, id="shared-val"),
            rx.button("shared+", on_click=shared_cs.set(lambda v: v + 1), id="shared-inc"),
            cs_counter(label="A"),
            cs_counter(label="B"),
        ]
    return rx.vstack(
        nav(),
        rx.heading("home", id="page-home"),
        rx.text("n=", S.n, id="n"),
        rx.text("other=", S.other, id="other"),
        rx.button("inc", on_click=S.inc, id="inc"),
        rx.button("bump other", on_click=S.bump_other, id="bump-other"),
        RenderProbe.create(probe="n_probe", label=S.n.to_string()),
        RenderProbe.create(probe="static_probe", label="static"),
        action_row(label="first", who="a"),
        action_row(label="second", who="b"),
        action_row(label=S.text, who="c"),
        rx.text("clicks: ", S.clicks.join(","), id="clicks"),
        rx.button("toggle", on_click=S.toggle, id="toggle"),
        rx.cond(
            S.flag,
            rx.text("branch A", id="br-a", on_mount=S.log_branch("mA"), on_unmount=S.log_branch("uA")),
            rx.text("branch B", id="br-b", on_mount=S.log_branch("mB"), on_unmount=S.log_branch("uB")),
        ),
        Counter.create(id="cs1"),
        Counter.create(id="cs2"),
        *extra,
        rx.input(id=f"fin_{S.suffix}", placeholder="fstring id", class_name="fin"),
        rx.button("focus fstring", on_click=rx.set_focus(f"fin_{S.suffix}"), id="focus-f"),
        logs(),
        on_mount=S.log_branch("page"),
    )


def loop_item(item: rx.Var[str], index: rx.Var[int]) -> rx.Component:
    return rx.hstack(
        rx.text(item, on_mount=S.record_mount(item), on_unmount=S.record_unmount(item), class_name="loop-item"),
        HookItem.create(f"[{item}]", label=item, class_name="hook-item"),
        rx.foreach(S.tags, lambda tag: rx.text(tag, on_mount=S.record_mount(item + "-" + tag), class_name="loop-tag")),
        rx.input(id=f"row_{item}", class_name="row-input"),
        rx.button("f", on_click=rx.set_focus(f"row_{item}"), class_name="row-focus"),
        rx.text(index, on_mount=S.record_mount("idx" + index.to_string()), class_name="loop-idx"),
        key=item,
    )


def loop():
    return rx.vstack(
        nav(),
        rx.heading("loop", id="page-loop"),
        rx.hstack(
            rx.button("add", on_click=S.add_item, id="add"),
            rx.button("remove first", on_click=S.remove_first, id="rm-first"),
            rx.button("remove middle", on_click=S.remove_middle, id="rm-mid"),
            rx.button("reverse", on_click=S.reverse, id="reverse"),
        ),
        rx.foreach(S.items, loop_item),
        rx.foreach(S.mapping, lambda kv: rx.text(kv[0], on_mount=S.record_mount("kv-" + kv[0]), class_name="kv")),
        logs(),
    )


def loopmemo():
    return rx.vstack(
        nav(),
        rx.heading("loopmemo", id="page-loopmemo"),
        rx.hstack(
            rx.button("add", on_click=S.add_item, id="add"),
            rx.button("remove first", on_click=S.remove_first, id="rm-first"),
            rx.button("reverse", on_click=S.reverse, id="reverse"),
        ),
        memo_loop(items=S.items),
        logs(),
    )


class RefsProbe(rx.Fragment):
    """User code in the docs' 'wrapping React' style that reaches `refs` from page code."""

    def add_custom_code(self) -> list[str]:
        return [
            "function readRefTag(name) { try { const r = refs[name]; return r && r.current ? r.current.tagName : 'none'; } catch (e) { return 'ERR:' + e.message; } }"
        ]

    def add_hooks(self) -> list[str | rx.Var]:
        return [
            "useEffect(() => { try { window.__refs_hook = Object.keys(refs).filter(k => k.startsWith('ref_')).join(','); } catch (e) { window.__refs_hook = 'ERR:' + e.message; } }, [])",
        ]

    def add_imports(self):
        return {"react": ["useEffect"]}


def refs_page():
    return rx.vstack(
        nav(),
        rx.heading("refs", id="page-refs"),
        rx.input(id="plain_input", placeholder="plain"),
        rx.input(id="other_input", placeholder="other"),
        rx.box("scroll target", id="scroll_target", margin_top="1500px"),
        rx.button("set_focus", on_click=rx.set_focus("plain_input"), id="b-focus"),
        rx.button("set_value", on_click=rx.set_value("plain_input", "from set_value"), id="b-setvalue"),
        rx.button("scroll_to", on_click=rx.scroll_to("scroll_target"), id="b-scroll"),
        rx.button(
            "call_script refs",
            on_click=rx.call_script(
                "refs['ref_other_input'].current.value = 'via call_script'; refs['ref_other_input'].current.value",
                callback=S.set_focus_log,
            ),
            id="b-callscript",
        ),
        rx.button(
            "raw Var refs onClick",
            on_click=rx.Var("() => { refs['ref_plain_input'].current.value = 'raw var' }").to(rx.vars.FunctionVar),
            id="b-rawvar",
        ),
        rx.button(
            "call_function refs",
            on_click=rx.call_function(rx.Var("() => refs['ref_plain_input'].current.value"), callback=S.set_focus_log),
            id="b-callfn",
        ),
        rx.text("raw prop: ", rx.Var("(typeof refs !== 'undefined' ? 'refs-ok' : 'refs-undefined')"), id="raw-prop"),
        RefsProbe.create(),
        rx.text("log: ", S.focus_log, id="focus-log"),
        rx.form(
            rx.input(id="form_ref_input", default_value="formval"),
            rx.button("submit", type="submit", id="form-submit"),
            on_submit=lambda fd: S.set_focus_log(fd.to_string()),
        ),
    )


def upload_page():
    return rx.vstack(
        nav(),
        rx.heading("upload", id="page-upload"),
        rx.upload(rx.text("drop"), id="up1", multiple=True),
        rx.text(rx.selected_files("up1").join(","), id="selected"),
        rx.button(
            "upload direct",
            on_click=S.handle_upload(rx.upload_files(upload_id="up1", on_upload_progress=S.on_progress)),
            id="b-up-direct",
        ),
        rx.button("toast upload", on_click=S.toast_upload, id="b-up-toast"),
        rx.button(
            "call_script upload",
            on_click=rx.call_script("1+1", callback=S.handle_upload(rx.upload_files(upload_id="up1"))),
            id="b-up-cs",
        ),
        rx.button("backend call_script upload", on_click=S.script_upload, id="b-up-bcs"),
        rx.button(
            "frontend toast upload",
            on_click=rx.toast("ftoast", action={"label": "FUpload", "on_click": S.handle_upload(rx.upload_files(upload_id="up1"))}, duration=60000),
            id="b-up-ftoast",
        ),
        rx.button("stream upload", on_click=S.stream_upload(rx.upload_files(upload_id="up1", on_upload_progress=S.on_progress)), id="b-up-stream"),
        rx.text("stream: ", S.stream_last, " / ", S.stream_vals.join(","), id="stream"),
        rx.button("clear sel", on_click=rx.clear_selected_files("up1"), id="b-clear"),
        rx.button("reset", on_click=S.reset_upload, id="b-reset"),
        rx.text("uploaded: ", S.upload_log.join("|"), id="uploaded"),
        rx.text("progress: ", S.progress_log.join(","), id="progress"),
    )


def plotly_page():
    import plotly.graph_objects as go

    fig = go.Figure(data=[go.Bar(x=["a", "b"], y=[1, 2])])
    return rx.vstack(nav(), rx.heading("plotly", id="page-plotly"), rx.plotly(data=fig))


def recharts_page():
    data = [{"x": i, "y": i * i} for i in range(5)]
    return rx.vstack(
        nav(),
        rx.heading("recharts", id="page-recharts"),
        rx.recharts.line_chart(rx.recharts.line(data_key="y"), rx.recharts.x_axis(data_key="x"), data=data, width=400, height=200),
    )


def editor_page():
    return rx.vstack(
        nav(),
        rx.heading("editor", id="page-editor"),
        rx.data_editor(columns=S.cols, data=S.rows, width="400px", height="200px"),
    )


class DynState(rx.State):
    which: str = "none"

    @rx.event
    def set_which(self, w: str):
        self.which = w

    @rx.var
    def comp(self) -> rx.Component:
        if self.which == "icon":
            return rx.icon("banana", id="dyn-icon")
        if self.which == "recharts":
            return rx.recharts.bar_chart(rx.recharts.bar(data_key="y"), data=[{"y": 1}, {"y": 3}], width=200, height=100)
        if self.which == "callout":
            return rx.callout("dyn callout", icon=rx.icon("info") if NEW else "info")
        return rx.text("nothing", id="dyn-none")


def dyn_page():
    return rx.vstack(
        nav(),
        rx.heading("dyn", id="page-dyn"),
        rx.button("icon", on_click=DynState.set_which("icon"), id="dyn-b-icon"),
        rx.button("recharts", on_click=DynState.set_which("recharts"), id="dyn-b-recharts"),
        rx.button("callout", on_click=DynState.set_which("callout"), id="dyn-b-callout"),
        rx.box(DynState.comp, id="dyn-box"),
    )


if NEW:

    @rx.memo
    def callout_from_memo(ic: rx.Var[rx.Component]) -> rx.Component:
        return rx.callout("memo icon", icon=ic, id="co-memo")


def comps_page():
    return rx.vstack(
        nav(),
        rx.heading("comps", id="page-comps"),
        rx.callout("str icon", icon="info", id="co-str"),
        *([
            rx.callout("component icon", icon=rx.icon("triangle_alert", color="red"), id="co-comp"),
            rx.callout(
                "cond icon",
                icon=rx.cond(S.flag, rx.icon("check"), rx.icon("x")),
                id="co-cond",
            ),
            rx.callout(
                "match icon",
                icon=rx.match(S.callout_kind, ("info", rx.icon("info")), ("warn", rx.icon("triangle_alert")), rx.icon("circle_x")),
                id="co-match",
            ),
            callout_from_memo(ic=rx.icon("star")),
        ] if NEW else []),
        rx.callout("var name icon", icon=S.icon_name, id="co-var"),
        rx.button("toggle", on_click=S.toggle, id="toggle"),
        rx.button("cycle callout", on_click=S.cycle_callout, id="cycle-co"),
        rx.code_block("plain text\nline 2", language="text" if NEW else "python", show_line_numbers=True, can_copy=True, id="cb-text"),
        rx.code_block("x = 1", language=S.lang, id="cb-var"),
        rx.hstack(
            rx.foreach(S.icon_names, lambda n: rx.hstack(rx.text(n), rx.icon(n, class_name="dyn-icn"), class_name="icn-row")),
            wrap="wrap",
        ),
        rx.icon(S.icon_name, id="icn-var"),
        rx.icon("grid_2x_2", id="icn-static"),
        rx.button("next icon", on_click=S.next_icon, id="next-icon"),
        rx.text("icon: ", S.icon_name, id="icn-name"),
        rx.input(placeholder="clearable", id="clr-in"),
        rx.text("cleared ", S.cleared, id="cleared"),
    )


if NEW:

    @rx.memo
    def memo_row(item: rx.Var[str]) -> rx.Component:
        # docs pattern (wrapping-react/overview.md): per-row client state via an @rx.memo row inside rx.foreach
        expanded = rx.client_state(False)
        return rx.hstack(
            rx.text(item, on_mount=S.record_mount("row-" + item), on_unmount=S.record_unmount("row-" + item), class_name="mr-name"),
            rx.button("t", on_click=expanded.set(lambda v: ~v), class_name="mr-toggle"),
            rx.cond(expanded.value, rx.text("open-" + item, class_name="mr-open", on_mount=S.record_mount("open-" + item))),
        )

    def rows():
        return rx.vstack(
            nav(),
            rx.heading("rows", id="page-rows"),
            rx.button("add", on_click=S.add_item, id="add"),
            rx.button("remove first", on_click=S.remove_first, id="rm-first"),
            rx.button("reverse", on_click=S.reverse, id="reverse"),
            rx.foreach(S.items, lambda item: memo_row(item=item)),
            logs(),
        )


@rx.memo
def memo_cond(show: rx.Var[bool], label: rx.Var[str]) -> rx.Component:
    return rx.box(
        rx.text("mc-" , label, class_name="mc-label"),
        rx.cond(show, rx.text("shown-", label, class_name="mc-shown", on_mount=S.log_branch("mount-shown-" + label), on_unmount=S.log_branch("unmount-shown-" + label))),
    )


def memocond():
    return rx.vstack(
        nav(),
        rx.heading("memocond", id="page-memocond"),
        rx.text("flag=", S.flag.to_string(), id="flag"),
        rx.button("toggle", on_click=S.toggle, id="toggle"),
        memo_cond(show=S.flag, label="x"),
        memo_cond(show=~S.flag, label="y"),
        logs(),
    )


def loopnokey():
    return rx.vstack(
        nav(),
        rx.heading("loopnokey", id="page-loopnokey"),
        rx.button("remove first", on_click=S.remove_first, id="rm-first"),
        rx.button("reverse", on_click=S.reverse, id="reverse"),
        rx.foreach(S.items, lambda item: rx.text(item, on_mount=S.record_mount(item), on_unmount=S.record_unmount(item), class_name="loop-item")),
        logs(),
    )


class T(rx.State):
    a: str = ""
    b: str = ""
    c: str = ""

    @rx.event
    def set_a(self, v: str):
        self.a = v

    @rx.event
    def set_b(self, v: str):
        self.b = v

    @rx.event
    def set_c(self, v: str):
        self.c = v.upper()


def typing():
    return rx.vstack(
        nav(),
        rx.heading("typing", id="page-typing"),
        rx.input(value=T.a, on_change=T.set_a, id="ta"),
        rx.input(value=T.b, on_change=T.set_b, debounce_timeout=300, id="tb"),
        rx.cond(T.a != "zzz", rx.input(value=T.c, on_change=T.set_c, id="tc")),
        rx.text_area(value=T.b, on_change=T.set_b, id="tarea"),
        rx.text("a=", T.a, " b=", T.b, " c=", T.c, id="tout"),
    )


def rowfocus():
    return rx.vstack(
        nav(),
        rx.heading("rowfocus", id="page-rowfocus"),
        rx.foreach(
            S.items,
            lambda item: rx.hstack(
                rx.input(id=f"rf_{item}", class_name="rf-input"),
                rx.button("f", on_click=rx.set_focus(f"rf_{item}"), class_name="rf-focus"),
                rx.button("v", on_click=rx.set_value(f"rf_{item}", item), class_name="rf-value"),
            ),
        ),
    )


app = rx.App()
app.add_page(rowfocus, route="/rowfocus")
app.add_page(typing, route="/typing")
app.add_page(memocond, route="/memocond")
app.add_page(loopnokey, route="/loopnokey")
if NEW:
    app.add_page(rows, route="/rows")
app.add_page(index, route="/")
app.add_page(loop, route="/loop")
app.add_page(loopmemo, route="/loopmemo")
app.add_page(refs_page, route="/refs")
app.add_page(upload_page, route="/upload")
app.add_page(plotly_page, route="/plotly")
app.add_page(recharts_page, route="/recharts")
app.add_page(editor_page, route="/editor")
app.add_page(dyn_page, route="/dyn")
app.add_page(comps_page, route="/comps")
