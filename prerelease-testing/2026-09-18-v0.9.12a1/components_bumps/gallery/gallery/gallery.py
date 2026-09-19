"""Component gallery exercising the 0.9.12a1 component-library alphas."""

import random
from typing import Any

import plotly.graph_objects as go
import reflex as rx
from reflex_components_core.core.sticky import sticky

assert "/envs/cb/" in rx.__file__, rx.__file__


# ---------------------------------------------------------------- sankey page


SANKEY_STATIC = {
    "nodes": [
        {"name": "Website"},
        {"name": "Landing Page"},
        {"name": "Product Page"},
        {"name": "Checkout"},
        {"name": "Purchase"},
    ],
    "links": [
        {"source": 0, "target": 1, "value": 1200},
        {"source": 1, "target": 2, "value": 900},
        {"source": 2, "target": 3, "value": 420},
        {"source": 3, "target": 4, "value": 260},
    ],
}

STYLED_DATA = {
    "nodes": [
        {"name": "Sources", "type": "source", "fill": "#3b82f6"},
        {"name": "Direct", "type": "channel", "fill": "#22c55e"},
        {"name": "Search", "type": "channel", "fill": "#84cc16"},
        {"name": "Paid", "type": "channel", "fill": "#f59e0b"},
        {"name": "Revenue", "type": "outcome", "fill": "#a855f7"},
    ],
    "links": [
        {"source": 0, "target": 1, "value": 350},
        {"source": 0, "target": 2, "value": 500},
        {"source": 0, "target": 3, "value": 220},
        {"source": 1, "target": 4, "value": 190},
        {"source": 2, "target": 4, "value": 260},
        {"source": 3, "target": 4, "value": 150},
    ],
}


class SankeyState(rx.State):
    """Sankey data driven by State."""

    data: dict[str, Any] = {
        "nodes": [
            {"name": "Marketing"},
            {"name": "Trial"},
            {"name": "Sales"},
            {"name": "Support"},
            {"name": "Retained"},
        ],
        "links": [
            {"source": 0, "target": 1, "value": 600},
            {"source": 1, "target": 2, "value": 320},
            {"source": 2, "target": 4, "value": 210},
            {"source": 1, "target": 3, "value": 180},
            {"source": 3, "target": 4, "value": 130},
        ],
    }
    seed: int = 0
    multi: list[str] = ["alpha", "beta"]

    @rx.event
    def randomize(self):
        self.seed += 1
        rnd = random.Random(self.seed)
        links = [dict(link) for link in self.data["links"]]
        for link in links:
            link["value"] = rnd.randint(80, 700)
        self.data = {"nodes": self.data["nodes"], "links": links}

    @rx.event
    def add_node(self):
        nodes = [*self.data["nodes"], {"name": f"Extra{len(self.data['nodes'])}"}]
        links = [
            *self.data["links"],
            {"source": 4, "target": len(nodes) - 1, "value": 90},
        ]
        self.data = {"nodes": nodes, "links": links}


@rx.recharts.sankey_chart.node
def custom_node(node: rx.Var[rx.recharts.SankeyNodeProps]) -> rx.Component:
    is_out = node.x + node.width + 6 > rx.recharts.use_chart_width()
    return rx.fragment(
        rx.el.svg.text(
            node.payload.name,
            x=rx.cond(is_out, node.x - 6, node.x + node.width + 6).to(int),
            y=(node.y + node.height / 2).to(int),
            text_anchor=rx.cond(is_out, "end", "start"),
            fill="#111827",
            font_size=10,
        ),
        rx.el.svg.rect(
            x=node.x.to(int),
            y=node.y.to(int),
            width=node.width.to(int),
            height=node.height.to(int),
            fill=node.payload.to(dict)["fill"],
            stroke="#111827",
            stroke_width=1,
        ),
    )


@rx.recharts.sankey_chart.link
def custom_link(link: rx.Var[rx.recharts.SankeyLinkProps]) -> rx.Component:
    link_id = rx.vars.use_id()
    source = link.payload.source.to(dict)
    target = link.payload.target.to(dict)
    return rx.fragment(
        rx.el.svg.linear_gradient(
            rx.el.svg.stop(offset="0%", stop_color=source["fill"]),
            rx.el.svg.stop(offset="100%", stop_color=target["fill"]),
            id=link_id,
        ),
        rx.el.svg.path(
            d=(
                f"M{link.sourceX},{link.sourceY} "
                f"C{link.sourceControlX},{link.sourceY} "
                f"{link.targetControlX},{link.targetY} "
                f"{link.targetX},{link.targetY}"
            ),
            fill="none",
            stroke=f"url(#{link_id})",
            stroke_opacity=0.35,
            stroke_width=link.linkWidth,
        ),
        rx.el.svg.text(
            link.payload.value,
            x=((link.sourceX + link.targetX) / 2).to(int),
            y=((link.sourceY + link.targetY) / 2).to(int),
            text_anchor="middle",
            fill="#111827",
            font_size=10,
        ),
    )


@rx.memo
def memo_sankey(label: str) -> rx.Component:
    """Sankey inside an rx.memo, reading chart width from inside the chart."""
    return rx.vstack(
        rx.text(label, id="memo-sankey-label"),
        rx.recharts.sankey_chart(
            data=STYLED_DATA,
            node=custom_node,
            link=custom_link,
            width="100%",
            height=220,
        ),
        width="100%",
    )


def width_probe() -> rx.Component:
    """use_chart_width outside a chart context must be None/undefined."""
    w = rx.recharts.use_chart_width()
    return rx.vstack(
        rx.text("outside-chart width: ", w.to_string(), id="width-outside"),
        rx.cond(
            w,
            rx.text("cond: truthy", id="width-cond"),
            rx.text("cond: falsy(None outside chart)", id="width-cond"),
        ),
    )


def sankey_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("Sankey", size="5"),
        rx.box(
            rx.recharts.sankey_chart(
                rx.recharts.graphing_tooltip(),
                data=SANKEY_STATIC,
                node_padding=24,
                node_width=12,
                link_curvature=0.55,
                width="100%",
                height=260,
            ),
            id="sankey-static",
            width="100%",
        ),
        rx.divider(),
        rx.heading("Stateful", size="4"),
        rx.hstack(
            rx.button("Randomize", on_click=SankeyState.randomize, id="btn-randomize"),
            rx.button("Add node", on_click=SankeyState.add_node, id="btn-addnode"),
            rx.text("seed=", SankeyState.seed.to_string(), id="sankey-seed"),
        ),
        rx.box(
            rx.recharts.sankey_chart(
                rx.recharts.graphing_tooltip(),
                data=SankeyState.data,
                node={"fill": "#7c3aed", "stroke": "#4c1d95", "strokeWidth": 2},
                link={"stroke": "#9ca3af", "strokeOpacity": 0.35},
                node_padding=18,
                node_width=14,
                width="100%",
                height=260,
            ),
            id="sankey-stateful",
            width="100%",
        ),
        rx.divider(),
        rx.heading("Custom node/link renderers", size="4"),
        rx.box(
            rx.recharts.sankey_chart(
                data=STYLED_DATA,
                node=custom_node,
                link=custom_link,
                width="100%",
                height=300,
            ),
            id="sankey-custom",
            width="100%",
        ),
        rx.divider(),
        rx.heading("foreach of memo'd sankeys", size="4"),
        rx.box(
            rx.foreach(SankeyState.multi, lambda name: memo_sankey(label=name)),
            id="sankey-foreach",
            width="100%",
        ),
        rx.divider(),
        width_probe(),
        width="100%",
        padding="1em",
        spacing="3",
    )


# ------------------------------------------------------- recharts props page


class PropsState(rx.State):
    """Data for the cartesian chart."""

    data: list[dict[str, Any]] = [
        {"name": "Jan", "uv": 4000, "pv": 2400},
        {"name": "Feb", "uv": 3000, "pv": 1398},
        {"name": "Mar", "uv": 2000, "pv": 9800},
        {"name": "Apr", "uv": 2780, "pv": 3908},
        {"name": "May", "uv": 1890, "pv": 4800},
    ]
    dash: str = "3 3"

    @rx.event
    def toggle_dash(self):
        self.dash = "8 2" if self.dash == "3 3" else "3 3"


def props_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("Recharts prop routing (#6833)", size="5"),
        rx.button("Toggle dash", on_click=PropsState.toggle_dash, id="btn-dash"),
        rx.text("dash=", PropsState.dash, id="dash-value"),
        rx.box(
            rx.recharts.line_chart(
                rx.recharts.cartesian_grid(stroke_dasharray="4 4"),
                rx.recharts.line(
                    data_key="uv",
                    stroke="#8884d8",
                    stroke_dasharray="5 5",
                    type_="monotone",
                ),
                rx.recharts.line(data_key="pv", stroke="#82ca9d", type_="monotone"),
                rx.recharts.x_axis(
                    data_key="name",
                    tick_formatter="(value) => 'X:' + value",
                ),
                rx.recharts.y_axis(
                    tick_formatter="(value) => (value / 1000) + 'k'",
                ),
                rx.recharts.reference_line(
                    y=3000,
                    stroke="#ff0000",
                    stroke_dasharray=PropsState.dash,
                ),
                rx.recharts.graphing_tooltip(),
                data=PropsState.data,
                width="100%",
                height=300,
            ),
            id="props-chart",
            width="100%",
        ),
        width="100%",
        padding="1em",
        spacing="3",
    )


# ---------------------------------------------------------- data editor page


class EditorState(rx.State):
    """Rows for the data editor, including image cells."""

    columns: list[dict[str, str]] = [
        {"title": "pic", "type": "image", "id": "pic"},
        {"title": "name", "type": "str", "id": "name"},
    ]
    data: list[list[Any]] = [
        [["/red.png", "/green.png"], "Ruby"],
        [["/blue.png"], "Bluey"],
        [["/amber.png", "/red.png", "/green.png"], "Amber"],
    ]
    n_clicks: int = 0
    last_cell: str = ""

    @rx.event
    def add_row(self):
        self.data = [*self.data, [["/green.png"], f"Row{len(self.data)}"]]

    @rx.event
    def on_cell_clicked(self, pos):
        self.n_clicks += 1
        self.last_cell = str(pos)


@rx.memo
def memo_editor() -> rx.Component:
    return rx.data_editor(
        columns=[
            {"title": "pic", "type": "image", "id": "pic"},
            {"title": "name", "type": "str", "id": "name"},
        ],
        data=[[["/blue.png"], "MemoRow"]],
        height="150px",
    )


def editor_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("data_editor image cells (#7081)", size="5"),
        rx.hstack(
            rx.button("Add row", on_click=EditorState.add_row, id="btn-addrow"),
            rx.text("clicks=", EditorState.n_clicks.to_string(), id="editor-clicks"),
            rx.text(EditorState.last_cell, id="editor-lastcell"),
        ),
        rx.box(
            rx.data_editor(
                columns=EditorState.columns,
                data=EditorState.data,
                on_cell_clicked=EditorState.on_cell_clicked,
                height="260px",
            ),
            id="editor-box",
            width="100%",
        ),
        rx.divider(),
        rx.heading("inside rx.memo", size="4"),
        rx.box(memo_editor(), id="editor-memo", width="100%"),
        width="100%",
        padding="1em",
        spacing="3",
    )


# --------------------------------------------------------------- plotly page


def _fig(color: str, n: int) -> go.Figure:
    fig = go.Figure(
        data=[go.Bar(x=["a", "b", "c"], y=[n, n * 2, n * 3], marker_color=color)]
    )
    fig.update_layout(height=220, margin=dict(l=20, r=20, t=20, b=20))
    return fig


class PlotlyState(rx.State):
    """State-var figure."""

    n: int = 1
    ids: list[str] = ["fe-one", "fe-two"]

    @rx.var(cache=True)
    def fig(self) -> go.Figure:
        return _fig("#ef4444", self.n)

    @rx.event
    def bump(self):
        self.n += 1


def plotly_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("plotly divId (#6977)", size="5"),
        rx.button("Bump", on_click=PlotlyState.bump, id="btn-bump"),
        rx.text("n=", PlotlyState.n.to_string(), id="plotly-n"),
        rx.plotly(data=_fig("#3b82f6", 2), id="myplot"),
        rx.divider(),
        rx.plotly(data=PlotlyState.fig, id="stateplot"),
        rx.divider(),
        rx.foreach(
            PlotlyState.ids,
            lambda pid: rx.box(rx.plotly(data=_fig("#22c55e", 3), id=pid)),
        ),
        width="100%",
        padding="1em",
        spacing="3",
    )


# ---------------------------------------------------------------- toast page


class ToastState(rx.State):
    """Counters proving toast action/cancel callbacks fire."""

    action_hits: int = 0
    cancel_hits: int = 0
    log: list[str] = []

    @rx.event
    def hit_action(self, tag: str = "?"):
        self.action_hits += 1
        self.log = [*self.log, f"action:{tag}"]

    @rx.event
    def hit_cancel(self, tag: str = "?"):
        self.cancel_hits += 1
        self.log = [*self.log, f"cancel:{tag}"]

    @rx.event(background=True)
    async def bg_toast(self):
        async with self:
            self.log = [*self.log, "bg:start"]
        yield rx.toast.info(
            "from background task",
            action={
                "label": "BG-ACT",
                "on_click": ToastState.hit_action("bg"),
            },
            duration=20000,
            position="top-center",
            close_button=True,
        )

    @rx.event
    def backend_toast(self):
        yield rx.toast.error(
            "backend toast",
            action={"label": "BE-ACT", "on_click": ToastState.hit_action("backend")},
            cancel={"label": "BE-CAN", "on_click": ToastState.hit_cancel("backend")},
            duration=20000,
        )


@rx.memo
def memo_toast_button() -> rx.Component:
    return rx.button(
        "memo toast",
        id="btn-memo-toast",
        on_click=rx.toast.success(
            "from memo",
            action={"label": "M-ACT", "on_click": ToastState.hit_action("memo")},
            cancel={"label": "M-CAN", "on_click": ToastState.hit_cancel("memo")},
            duration=20000,
        ),
    )


class ToastCS(rx.ComponentState):
    """ComponentState-scoped toast trigger."""

    local: int = 0

    @rx.event
    def bump(self):
        self.local += 1

    @classmethod
    def get_component(cls, **props):
        return rx.hstack(
            rx.button(
                "cs toast",
                on_click=rx.toast.info(
                    "from ComponentState",
                    action={"label": "CS-ACT", "on_click": cls.bump},
                    duration=20000,
                ),
                **props,
            ),
            rx.text("local=", cls.local.to_string(), id="cs-local"),
        )


def toast_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.toast.provider(),
        rx.heading("sonner toast action/cancel (#7157)", size="5"),
        rx.text("action_hits=", ToastState.action_hits.to_string(), id="action-hits"),
        rx.text("cancel_hits=", ToastState.cancel_hits.to_string(), id="cancel-hits"),
        rx.text(ToastState.log.to_string(), id="toast-log"),
        rx.button(
            "frontend toast",
            id="btn-fe-toast",
            on_click=rx.toast.success(
                "frontend trigger",
                action={"label": "FE-ACT", "on_click": ToastState.hit_action("fe")},
                cancel={"label": "FE-CAN", "on_click": ToastState.hit_cancel("fe")},
                duration=20000,
                position="bottom-right",
                close_button=True,
            ),
        ),
        memo_toast_button(),
        ToastCS.create(id="btn-cs-toast"),
        rx.button("backend toast", id="btn-be-toast", on_click=ToastState.backend_toast),
        rx.button("bg toast", id="btn-bg-toast", on_click=ToastState.bg_toast),
        rx.foreach(
            ToastState.log,
            lambda item, i: rx.button(
                "fe-item ",
                item,
                id=f"btn-item-{i}",
                on_click=rx.toast.info(
                    "foreach toast",
                    action={
                        "label": "FEACH-ACT",
                        "on_click": ToastState.hit_action("foreach"),
                    },
                    duration=20000,
                ),
            ),
        ),
        rx.button("dismiss all", id="btn-dismiss", on_click=rx.toast.dismiss()),
        width="100%",
        padding="1em",
        spacing="3",
    )


# ----------------------------------------------------------------- code page

SAMPLE = """def greet(name: str) -> str:
    return f"hello {name}"
"""


class CodeState(rx.State):
    """Form submit counter + code block controls."""

    submits: int = 0
    language: str = "python"
    dark: bool = False

    @rx.event
    def on_submit(self, form_data: dict):
        self.submits += 1

    @rx.event
    def toggle_lang(self):
        self.language = "javascript" if self.language == "python" else "python"

    @rx.event
    def toggle_theme(self):
        self.dark = ~self.dark


def code_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("code_block copy button (#7078)", size="5"),
        rx.text("submits=", CodeState.submits.to_string(), id="submit-count"),
        rx.form(
            rx.vstack(
                rx.input(name="who", default_value="x", id="form-input"),
                rx.box(
                    rx.code_block(SAMPLE, language="python", can_copy=True),
                    id="code-in-form",
                ),
                rx.button("Submit", type="submit", id="btn-submit"),
            ),
            on_submit=CodeState.on_submit,
            id="the-form",
        ),
        rx.divider(),
        rx.hstack(
            rx.button("lang", on_click=CodeState.toggle_lang, id="btn-lang"),
            rx.button("theme", on_click=CodeState.toggle_theme, id="btn-theme"),
            rx.text(CodeState.language, id="cur-lang"),
        ),
        rx.box(
            rx.code_block(
                SAMPLE,
                language=CodeState.language,
                theme=rx.cond(
                    CodeState.dark,
                    rx.code_block.themes.one_dark,
                    rx.code_block.themes.one_light,
                ),
                can_copy=True,
            ),
            id="code-dynamic",
        ),
        rx.box(height="1500px"),
        rx.box(
            rx.code_block(
                "print('below the fold')\nprint('second line')",
                language="python",
                can_copy=True,
            ),
            id="code-belowfold",
        ),
        width="100%",
        padding="1em",
        spacing="3",
    )


# ----------------------------------------------------------------- misc page

MD = """# Markdown

Some **bold** and a [link](/sankey).

| a | b |
|---|---|
| 1 | 2 |

```python
x = 1
```

Inline math $x^2$ and block:

$$\\int_0^1 x dx$$
"""


class MiscState(rx.State):
    """Table data + segmented control binding."""

    rows: list[list[str]] = [
        ["Avery", "35", "Engineer"],
        ["Blake", "28", "Designer"],
        ["Casey", "42", "PM"],
        ["Drew", "31", "Engineer"],
    ]
    choice: str = "one"
    items: list[str] = ["ia", "ib", "ic"]

    @rx.event
    def set_choice(self, value: str | list[str]):
        self.choice = value if isinstance(value, str) else ",".join(value)

    @rx.event
    def add_row(self):
        self.rows = [*self.rows, [f"New{len(self.rows)}", "20", "Intern"]]


@rx.memo
def hook_probe(label: str) -> rx.Component:
    """use_hook_var / use_id inside a memo."""
    ident = rx.vars.use_id()
    return rx.vstack(
        rx.el.label("memo label", html_for=ident),
        rx.el.input(id=ident, default_value=label, class_name="memo-hook-input"),
        rx.text("memo id: ", ident, class_name="memo-hook-id"),
    )


def id_row(item: str) -> rx.Component:
    ident = rx.vars.use_id()
    return rx.hstack(
        rx.el.label(item, html_for=ident, class_name="foreach-label"),
        rx.el.input(id=ident, default_value=item, class_name="foreach-input"),
        rx.text(ident, class_name="foreach-id"),
    )


def misc_page() -> rx.Component:
    # use_hook_var against a real no-arg React hook
    transition = rx.vars.use_hook_var("react", "useId", str)
    return rx.vstack(
        nav(),
        rx.heading("misc", size="5"),
        rx.box(rx.markdown(MD), id="md-box"),
        rx.divider(),
        rx.heading("data_table (gridjs)", size="4"),
        rx.button("add row", on_click=MiscState.add_row, id="btn-tablerow"),
        rx.box(
            rx.data_table(
                data=MiscState.rows,
                columns=["name", "age", "role"],
                search=True,
                sort=True,
                pagination=True,
            ),
            id="table-box",
            width="100%",
        ),
        rx.divider(),
        rx.heading("segmented control (#7198)", size="4"),
        rx.segmented_control.root(
            rx.segmented_control.item("One", value="one"),
            rx.segmented_control.item("Two", value="two"),
            rx.segmented_control.item("Three", value="three"),
            value=MiscState.choice,
            on_change=MiscState.set_choice,
            id="segctl",
        ),
        rx.text("choice=", MiscState.choice, id="seg-value"),
        rx.divider(),
        rx.heading("use_id in foreach", size="4"),
        rx.box(rx.foreach(MiscState.items, id_row), id="ids-box"),
        hook_probe(label="memoized"),
        rx.text("page-level use_hook_var(react,useId): ", transition, id="hookvar-text"),
        rx.cond(
            transition,
            rx.text("hookvar truthy", id="hookvar-cond"),
            rx.text("hookvar falsy", id="hookvar-cond"),
        ),
        rx.divider(),
        rx.logo(),
        sticky(),
        width="100%",
        padding="1em",
        spacing="3",
    )


# ------------------------------------------------------------------- upload


class UploadState(rx.State):
    """Upload sink."""

    files: list[str] = []

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        for f in files:
            self.files = [*self.files, f.name or "?"]


def upload_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("upload", size="5"),
        rx.upload(
            rx.text("drop here"),
            id="up1",
            on_drop=UploadState.handle_upload(rx.upload_files(upload_id="up1")),
        ),
        rx.text(UploadState.files.to_string(), id="upload-files"),
        width="100%",
        padding="1em",
    )


def nav() -> rx.Component:
    return rx.hstack(
        *[
            rx.link(name, href=href, id=f"nav-{name}")
            for name, href in [
                ("home", "/"),
                ("sankey", "/sankey"),
                ("props", "/props"),
                ("editor", "/editor"),
                ("plotly", "/plotly"),
                ("toast", "/toast"),
                ("code", "/code"),
                ("misc", "/misc"),
                ("upload", "/upload"),
            ]
        ],
        spacing="3",
        wrap="wrap",
    )


def index() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("0.9.12a1 component gallery", size="6"),
        rx.text("ok", id="home-ok"),
        padding="1em",
    )


app = rx.App()
app.add_page(index, route="/")
app.add_page(sankey_page, route="/sankey")
app.add_page(props_page, route="/props")
app.add_page(editor_page, route="/editor")
app.add_page(plotly_page, route="/plotly")
app.add_page(toast_page, route="/toast")
app.add_page(code_page, route="/code")
app.add_page(misc_page, route="/misc")
app.add_page(upload_page, route="/upload")
