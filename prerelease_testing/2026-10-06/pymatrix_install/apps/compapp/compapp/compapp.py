"""Component-coverage app: every first-party component package plus a #7227 form probe."""

import plotly.graph_objects as go
from reflex_components_core.el.elements.base import BaseHTML

import reflex as rx


class NativeInput(BaseHTML):
    """A bare <input> that is a form control only by its tag (as in the #7227 test)."""

    tag = "input"


class CompState(rx.State):
    """State backing the component pages."""

    count: int = 0
    uploaded: list[str] = []
    md: str = "# Markdown Title\n\n**bold** and `inline`\n\n- item a\n- item b"
    when: str = "2026-10-06T12:00:00Z"
    grid: list[list[str | int]] = [["alpha", 1], ["beta", 2]]
    edited: str = "none"

    @rx.event
    def incr(self):
        self.count += 1

    @rx.event
    def toast(self):
        return rx.toast.success(f"toast count={self.count}")

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        for f in files:
            data = await f.read()
            self.uploaded.append(f"{f.name}:{len(data)}")

    @rx.event
    def cell_edited(self, pos: tuple[int, int], val: dict):
        col, row = pos
        self.edited = f"{col},{row}={val.get('data')}"

    @rx.var
    def chart_data(self) -> list[dict[str, int | str]]:
        return [{"name": f"p{i}", "v": (i * 7 + self.count) % 10} for i in range(6)]


class FormState(rx.State):
    """Captures whatever the browser submits."""

    form_data: rx.Field[dict] = rx.field(default_factory=dict)
    typed: str = ""

    @rx.event
    def form_submit(self, data: dict):
        self.form_data = data

    @rx.event
    def set_typed(self, value: str):
        self.typed = value


def nav() -> rx.Component:
    return rx.hstack(
        rx.link("home", href="/", id="nav-home"),
        rx.link("charts", href="/charts", id="nav-charts"),
        rx.link("upload", href="/upload", id="nav-upload"),
        rx.link("form", href="/form", id="nav-form"),
    )


def index() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("components", id="page-home"),
        rx.hstack(
            rx.button("incr", on_click=CompState.incr, id="incr"),
            rx.text(CompState.count, id="count"),
            rx.button("toast", on_click=CompState.toast, id="toast"),
        ),
        rx.hstack(rx.icon("star", id="icon-star"), rx.icon(tag="plus", id="icon-plus")),
        rx.moment(CompState.when, format="YYYY-MM-DD", tz="UTC", id="moment"),
        rx.code_block("def hello():\n    return 'world'", language="python", id="code"),
        rx.markdown(CompState.md, id="md"),
    )


def charts() -> rx.Component:
    fig = go.Figure(go.Scatter(x=[1, 2, 3], y=[3, 1, 2], name="s"))
    fig.update_layout(title="plotly title")
    return rx.vstack(
        nav(),
        rx.heading("charts", id="page-charts"),
        rx.plotly(data=fig, id="plotly"),
        rx.recharts.line_chart(
            rx.recharts.line(data_key="v"),
            rx.recharts.x_axis(data_key="name"),
            rx.recharts.y_axis(),
            data=CompState.chart_data,
            width=400,
            height=200,
        ),
        rx.data_editor(
            columns=[{"title": "name", "type": "str"}, {"title": "n", "type": "int"}],
            data=CompState.grid,
            on_cell_edited=CompState.cell_edited,
            width="400px",
            height="150px",
        ),
        rx.text(CompState.edited, id="edited"),
    )


def upload() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("upload", id="page-upload"),
        rx.upload(rx.text("drop files here"), id="up1", border="1px dashed"),
        rx.button(
            "do upload",
            on_click=CompState.handle_upload(rx.upload_files(upload_id="up1")),
            id="do-upload",
        ),
        rx.foreach(CompState.uploaded, lambda u: rx.text(u, class_name="uploaded")),
    )


def form() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("form", id="page-form"),
        rx.form(
            rx.vstack(
                rx.input(id="name_input", default_value="foo"),
                rx.input(id="empty_input"),
                NativeInput.create(id="native_input", custom_attrs={"defaultValue": "native"}),
                rx.input(name="named_input", default_value="named"),
                rx.input(id="memo_input", value=FormState.typed, on_change=FormState.set_typed),
                rx.checkbox(id="bool_input", default_checked=True),
                rx.radio_group(["u1", "u2"], id="radio_unset"),
                rx.box(rx.text("not a control"), id="plain_box"),
                rx.button("Submit", type="submit", id="submit"),
                id="form_content_wrapper",
            ),
            on_submit=FormState.form_submit,
            id="form_id",
        ),
        rx.text(FormState.form_data.to_string(), id="form-data"),
    )


app = rx.App()
app.add_page(index)
app.add_page(charts, route="/charts")
app.add_page(upload, route="/upload")
app.add_page(form, route="/form")
