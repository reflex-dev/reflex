"""Mixed-sibling-floor probe app: forms (#7386), window_event_listener / clipboard (#7586 hook order), data_editor with
state-backed columns (#7607), lucide icons incl. a dynamic one (#7604), shiki code block with transformers (#7437), moment.
Run under: new (all 0.10.1a1), n001-pip312 (reflex 0.10.1a1 + code/dataeditor 0.10.0, lucide 1.1.0), prev (reflex 0.10.0 +
code/moment 0.10.1a1, lucide 1.1.1a1), pure-prev (0.10.0 train)."""

import datetime
import json
import os

import reflex as rx

_qa_ev = os.environ.get("QA_EXPECT_VENV")
if _qa_ev:  # QA venv guard
    assert f"/envs/{_qa_ev}/" in rx.__file__, rx.__file__

CODE = "def hello(name: str) -> str:\n    return f'hi {name}'  # [!code highlight]\n"


class State(rx.State):
    submitted: str = ""
    submit_count: int = 0
    last_key: str = ""
    key_count: int = 0
    pasted: str = ""
    cell: str = ""
    icon_name: str = "calendar"
    columns: list[dict] = (
        # MIXED_TYPED_COLUMNS=1: every column typed, so that 0.10.0 (bug #7596) renders the page and the other checks
        # can be compared; default: the first column has no type / id (#7607 fills in the defaults on 0.10.1a1).
        [{"title": "Name", "type": "str", "id": "name"}, {"title": "Age", "type": "int", "id": "age"}]
        if os.environ.get("MIXED_TYPED_COLUMNS")
        else [{"title": "Name"}, {"title": "Age", "type": "int", "id": "age"}]
    )
    data: list[list] = [["ada", 36], ["grace", 45], ["linus", 55]]
    now: str = datetime.datetime(2026, 10, 24, 12, 30, tzinfo=datetime.timezone.utc).isoformat()

    @rx.event
    def handle_submit(self, form_data: dict):
        self.submitted = json.dumps(form_data, sort_keys=True)
        self.submit_count += 1

    @rx.event
    def on_key(self, ev):
        self.last_key = str(ev.get("key", ev) if isinstance(ev, dict) else ev)
        self.key_count += 1

    @rx.event
    def on_paste(self, data: list[tuple[str, str]]):
        self.pasted = json.dumps(data)

    @rx.event
    def cell_clicked(self, pos):
        self.cell = json.dumps(pos)

    @rx.event
    def toggle_icon(self):
        self.icon_name = "sun" if self.icon_name == "calendar" else "calendar"

    @rx.event
    def add_row(self):
        self.data.append(["new", len(self.data)])
        self.columns = [*self.columns]


def index():
    return rx.vstack(
        rx.heading("mixed floors probe", id="title"),
        rx.text(rx.State.router.page.path, id="path"),
        rx.form(
            rx.input(name="username", placeholder="username", id="username"),
            rx.input(id="idonly", placeholder="idonly"),
            rx.checkbox("agree", name="agree", id="agree"),
            rx.switch(name="sw", id="sw"),
            rx.input(name="tags", placeholder="tag1", id="tag1"),
            rx.input(name="tags", placeholder="tag2", id="tag2"),
            rx.select(["a", "b"], name="choice", default_value="a", id="choice"),
            rx.button("Submit", type="submit", id="submit"),
            on_submit=State.handle_submit,
            reset_on_submit=False,
            id="form",
        ),
        rx.text(State.submitted, id="submitted"),
        rx.text(State.submit_count, id="submit_count"),
        rx.window_event_listener(on_key_down=State.on_key),
        rx.clipboard(on_paste=State.on_paste),
        rx.text(State.last_key, id="last_key"),
        rx.text(State.key_count, id="key_count"),
        rx.text(State.pasted, id="pasted"),
        rx.hstack(
            rx.icon("calendar", id="icon_static", size=24),
            rx.icon(State.icon_name, id="icon_dynamic", size=24),
            rx.button("toggle icon", on_click=State.toggle_icon, id="toggle_icon"),
            rx.text(State.icon_name, id="icon_name"),
        ),
        rx.box(rx.code_block(CODE, language="python", show_line_numbers=True), id="code_rsh"),
        rx.box(rx._x.code_block(CODE, language="python", theme="github-light", use_transformers=True), id="code_shiki"),
        rx.box(rx.moment(State.now, format="YYYY-MM-DD HH:mm", tz="UTC"), id="moment"),
        rx.box(
            rx.data_editor(
                columns=State.columns,
                data=State.data,
                on_cell_clicked=State.cell_clicked,
                height="200px",
            ),
            id="de_state",
        ),
        rx.box(
            rx.data_editor(columns=[{"title": "Lit"}, {"title": "N", "type": "int"}], data=[["x", 1]], height="120px"),
            id="de_literal",
        ),
        rx.button("add row", on_click=State.add_row, id="add_row"),
        rx.text(State.cell, id="cell"),
        rx.text(State.data.length(), id="nrows"),
        spacing="3",
        padding="1em",
    )


app = rx.App()
app.add_page(index, route="/")
