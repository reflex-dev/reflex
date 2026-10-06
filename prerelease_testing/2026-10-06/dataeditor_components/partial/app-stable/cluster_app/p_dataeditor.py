"""Data editor pages: all column types, events, images, theme, memo, ComponentState,
client_state filter, foreach, and a 5,000-row grid."""

import json
from typing import Any

import reflex as rx
from reflex_base.vars.base import VarData

from .common import guarded, nav

LOCAL_RED = "/img_red.png"
LOCAL_A = "/img_a.png"
LOCAL_B = "/img_b.png"
LOCAL_C = "/img_c.png"
REMOTE1 = "https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/app/assets/meta/android-chrome-192x192.png"
REMOTE2 = "https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/app/assets/meta/mstile-310x150.png"
XORIGIN = "http://localhost:8438/xo_purple.png"

DE_COLUMNS: list[dict[str, Any]] = [
    {"title": "Name", "type": "str", "id": "name", "width": 90},
    {"title": "Qty", "type": "int", "id": "qty", "width": 60},
    {"title": "Price", "type": "float", "id": "price", "width": 70},
    {"title": "Active", "type": "bool", "id": "active", "width": 60},
    {"title": "Image", "type": "image", "id": "image", "width": 130},
    {"title": "Link", "type": "uri", "id": "link", "width": 80},
    {"title": "Notes", "type": "markdown", "id": "notes", "width": 80},
    {"title": "Tags", "type": "bubble", "id": "tags", "width": 80},
    {"title": "Drill", "type": "drilldown", "id": "drill", "width": 80},
    {"title": "RowID", "type": "row-id", "id": "rowid", "width": 70},
    {"title": "When", "type": "datetime", "id": "when", "width": 90},
    {"title": "RO", "type": "str", "id": "ro", "width": 60, "editable": False},
]


def _rows() -> list[list[Any]]:
    imgs = [
        LOCAL_RED,
        [LOCAL_A, LOCAL_B, LOCAL_C],
        REMOTE1,
        [REMOTE1, REMOTE2],
        XORIGIN,
        "",
        "/does-not-exist.png",
        [LOCAL_A, REMOTE1, XORIGIN],
    ]
    names = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta"]
    return [
        [
            name,
            i + 1,
            round((i + 1) * 1.25, 2),
            i % 2 == 0,
            imgs[i],
            f"https://example.com/{i}",
            f"**md {i}**",
            [f"t{i}", "x"],
            [{"text": f"d{i}"}],
            f"r-{i}",
            f"2026-01-0{i + 1}",
            f"ro{i}",
        ]
        for i, name in enumerate(names)
    ]


DARK_THEME = {
    "accentColor": "#8c96ff",
    "textDark": "#ffffff",
    "textMedium": "#b8b8b8",
    "textLight": "#a0a0a0",
    "bgCell": "#16161b",
    "bgCellMedium": "#202027",
    "bgHeader": "#212121",
    "bgHeaderHasFocus": "#474747",
    "bgHeaderHovered": "#404040",
    "borderColor": "rgba(225,225,225,0.2)",
    "textHeader": "#a1a1a1",
}


class DEState(rx.State):
    """State for the main data editor page."""

    rows: list[list[Any]] = _rows()
    cols: list[dict[str, Any]] = DE_COLUMNS
    theme: dict[str, str] = {}
    log: list[str] = []
    last_click: str = ""
    last_activated: str = ""
    last_edit: str = ""
    edits: int = 0
    header_clicks: int = 0
    sort_desc: bool = False
    resize_log: str = ""
    deleted: str = ""

    def _log(self, msg: str):
        self.log = [*self.log[-14:], msg]

    @rx.event
    def cell_clicked(self, pos: tuple[int, int]):
        self.last_click = f"{pos[0]},{pos[1]}"
        self._log(f"click {pos[0]},{pos[1]}")

    @rx.event
    def cell_activated(self, pos: tuple[int, int]):
        self.last_activated = f"{pos[0]},{pos[1]}"
        self._log(f"activated {pos[0]},{pos[1]}")

    @rx.event
    def cell_edited(self, pos: tuple[int, int], cell: dict[str, Any]):
        col, row = pos
        self.rows[row][col] = cell.get("data")
        self.edits += 1
        self.last_edit = json.dumps({"pos": [col, row], "cell": cell}, sort_keys=True, default=str)
        print("DE_EDIT", self.last_edit, flush=True)
        self._log(f"edit {col},{row}")

    @rx.event
    def header_clicked(self, col: Any):
        self.header_clicks += 1
        idx = col[0] if isinstance(col, (list, tuple)) else col
        self._log(f"header {json.dumps(col, default=str)} type={type(col).__name__}")
        if isinstance(idx, int) and idx < 3:
            self.sort_desc = not self.sort_desc
            self.rows = sorted(self.rows, key=lambda r: r[idx], reverse=self.sort_desc)

    @rx.event
    def column_resized(self, column: dict[str, Any], new_size: int):
        cid = column.get("id")
        self.cols = [{**c, "width": new_size} if c["id"] == cid else c for c in self.cols]
        self.resize_log = f"{cid}={new_size}"
        self._log(f"resize {cid} {new_size}")

    @rx.event
    def on_delete(self, selection: dict[str, Any]):
        self.deleted = json.dumps(selection, sort_keys=True, default=str)[:300]
        self._log("delete")

    @rx.event
    def toggle_theme(self):
        self.theme = {} if self.theme else DARK_THEME

    @rx.event
    def reset_rows(self):
        self.rows = _rows()
        self.cols = DE_COLUMNS
        self.edits = 0


def de_page() -> rx.Component:
    """Main data editor page."""
    return rx.vstack(
        nav(),
        rx.heading("Data editor: all column types"),
        rx.hstack(
            rx.button("Toggle theme", on_click=DEState.toggle_theme, id="toggle-theme"),
            rx.button("Reset", on_click=DEState.reset_rows, id="reset"),
            rx.text("click:", DEState.last_click, id="last-click"),
            rx.text("activated:", DEState.last_activated, id="last-activated"),
            rx.text("edits:", DEState.edits, id="edits"),
            rx.text("headers:", DEState.header_clicks, id="header-clicks"),
            rx.text("resize:", DEState.resize_log, id="resize-log"),
        ),
        rx.text(DEState.last_edit, id="last-edit"),
        rx.text(DEState.deleted, id="deleted"),
        rx.box(
            rx.data_editor(
                columns=DEState.cols,
                data=DEState.rows,
                on_cell_clicked=DEState.cell_clicked,
                on_cell_activated=DEState.cell_activated,
                on_cell_edited=DEState.cell_edited,
                on_header_clicked=DEState.header_clicked,
                on_column_resize=DEState.column_resized,
                on_delete=DEState.on_delete,
                theme=DEState.theme,
                row_height=60,
                row_markers="number",
                id="de-main",
                width="1100px",
                height="560px",
            ),
            id="de-main-box",
            width="1100px",
            height="560px",
        ),
        rx.heading("Static themed editor", size="3"),
        rx.box(
            rx.data_editor(
                columns=[{"title": "Code", "type": "str"}, {"title": "Value", "type": "int"}],
                data=[["A", 1], ["B", 2], ["C", 3]],
                theme=rx.data_editor_theme(**DARK_THEME),
                id="de-static",
                height="160px",
                width="400px",
            ),
            id="de-static-box",
            width="400px",
            height="160px",
        ),
        rx.vstack(rx.foreach(DEState.log, lambda m: rx.text(m, class_name="log-line")), id="log"),
        padding="10px",
    )


class EditorCS(rx.ComponentState):
    """A data editor owned by a ComponentState (two instances on one page)."""

    rows: list[list[Any]] = [["a", 1], ["b", 2], ["c", 3]]
    clicks: int = 0
    edits: int = 0
    last: str = ""

    @rx.event
    def on_click(self, pos: tuple[int, int]):
        self.clicks += 1
        self.last = f"{pos[0]},{pos[1]}"

    @rx.event
    def on_edit(self, pos: tuple[int, int], cell: dict[str, Any]):
        col, row = pos
        self.rows[row][col] = cell.get("data")
        self.edits += 1

    @classmethod
    def get_component(cls, **props) -> rx.Component:
        prefix = props.pop("prefix")
        return rx.vstack(
            rx.text(prefix, " clicks ", cls.clicks, " edits ", cls.edits, " last ", cls.last, id=f"{prefix}-status"),
            rx.text(cls.rows.to_string(), id=f"{prefix}-rows"),
            rx.box(
                rx.data_editor(
                    columns=[{"title": "K", "type": "str"}, {"title": "V", "type": "int"}],
                    data=cls.rows,
                    on_cell_clicked=cls.on_click,
                    on_cell_edited=cls.on_edit,
                    id=f"{prefix}-grid",
                    width="300px",
                    height="150px",
                ),
                id=f"{prefix}-box",
                width="300px",
                height="150px",
            ),
        )


class MemoDEState(rx.State):
    """State feeding the memoized editor."""

    rows: list[list[Any]] = [["m1", 10], ["m2", 20]]
    title: str = "memo editor"

    @rx.event
    def add_row(self):
        self.rows = [*self.rows, [f"m{len(self.rows) + 1}", (len(self.rows) + 1) * 10]]
        self.title = f"memo editor ({len(self.rows)})"


@rx.memo
def memo_editor(rows: rx.Var[list[list[Any]]], title: rx.Var[str]) -> rx.Component:
    """A data editor inside an rx.memo component."""
    return rx.vstack(
        rx.text(title, id="memo-title"),
        rx.box(
            rx.data_editor(
                columns=[{"title": "M", "type": "str"}, {"title": "N", "type": "int"}],
                data=rows,
                width="300px",
                height="160px",
            ),
            width="300px",
            height="160px",
            id="memo-box",
        ),
    )


cs_a = EditorCS.create(prefix="csa")
cs_b = EditorCS.create(prefix="csb")


class DropdownState(rx.State):
    """Dropdown (extended cell types) editor state."""

    rows: list[list[Any]] = [["x", "red"], ["y", "green"]]
    last: str = ""

    @rx.event
    def on_edit(self, pos: tuple[int, int], cell: dict[str, Any]):
        col, row = pos
        self.rows[row][col] = (cell.get("data") or {}).get("value") if isinstance(cell.get("data"), dict) else cell.get("data")
        self.last = json.dumps(cell, sort_keys=True, default=str)


def de_multi_page() -> rx.Component:
    """Editors in ComponentState x2, rx.memo, and extended dropdown cells."""
    return rx.vstack(
        nav(),
        rx.heading("Multiple editors"),
        rx.hstack(cs_a, cs_b),
        rx.button("Add memo row", on_click=MemoDEState.add_row, id="memo-add"),
        memo_editor(rows=MemoDEState.rows, title=MemoDEState.title),
        rx.heading("Dropdown (extended_cell_types)", size="3"),
        rx.text(DropdownState.last, id="dd-last"),
        guarded(
            "dropdown",
            lambda: rx.box(
                rx.data_editor(
                    columns=[
                        {"title": "K", "type": "str"},
                        {"title": "Color", "type": "dropdown", "allowedValues": ["red", "green", "blue"]},
                    ],
                    data=DropdownState.rows,
                    on_cell_edited=DropdownState.on_edit,
                    extended_cell_types=True,
                    id="dd-grid",
                    width="300px",
                    height="130px",
                ),
                width="300px",
                height="130px",
                id="dd-box",
            ),
        ),
        padding="10px",
    )


class FilterState(rx.State):
    """Products filtered on the client via rx._x.client_state."""

    products: list[dict[str, Any]] = [
        {"name": f"P{i:02d}", "cat": ["fruit", "veg", "meat"][i % 3], "qty": i}
        for i in range(30)
    ]
    groups: list[list[list[Any]]] = [[["g0a", 1], ["g0b", 2]], [["g1a", 3]]]

    @rx.event
    def add_product(self):
        n = len(self.products)
        self.products = [*self.products, {"name": f"P{n:02d}", "cat": "fruit", "qty": n}]


de_filter = rx._x.client_state(var_name="de_filter", default="")
MAPPED_ROWS = FilterState.products.map(lambda p: [p["name"], p["cat"], p["qty"]])
FILTERED_ROWS = rx.Var(
    _js_expr=f"({MAPPED_ROWS!s}).filter((r) => String(r[1]).includes({de_filter.value!s}))",
    _var_data=VarData.merge(MAPPED_ROWS._get_all_var_data(), de_filter.value._get_all_var_data()),
).to(list[list[Any]])


def de_filter_page() -> rx.Component:
    """client_state-driven filter, .map()-built rows, editors inside rx.foreach."""
    return rx.vstack(
        nav(),
        de_filter,
        rx.heading("Client-state filtered editor"),
        rx.input(placeholder="category filter", on_change=de_filter.set_value, id="de-filter-input"),
        rx.text("filter=", de_filter.value, id="de-filter-value"),
        rx.text("visible rows: ", FILTERED_ROWS.length(), id="de-filter-count"),
        rx.button("Add product", on_click=FilterState.add_product, id="add-product"),
        rx.box(
            rx.data_editor(
                columns=[{"title": "Name", "type": "str"}, {"title": "Cat", "type": "str"}, {"title": "Qty", "type": "int"}],
                data=FILTERED_ROWS,
                id="de-filter-grid",
                width="400px",
                height="300px",
            ),
            width="400px",
            height="300px",
            id="de-filter-box",
        ),
        rx.heading("Mapped (.map) rows, no filter", size="3"),
        rx.box(
            rx.data_editor(
                columns=[{"title": "Name", "type": "str"}, {"title": "Cat", "type": "str"}, {"title": "Qty", "type": "int"}],
                data=MAPPED_ROWS,
                id="de-mapped-grid",
                width="400px",
                height="200px",
            ),
            width="400px",
            height="200px",
            id="de-mapped-box",
        ),
        padding="10px",
    )


def de_foreach_page() -> rx.Component:
    """Data editors rendered inside rx.foreach (one per group)."""
    return rx.vstack(
        nav(),
        rx.heading("Editors inside rx.foreach", size="3"),
        guarded(
            "de-foreach",
            lambda: rx.hstack(
                rx.foreach(
                    FilterState.groups,
                    lambda g: rx.box(
                        rx.data_editor(
                            columns=[{"title": "G", "type": "str"}, {"title": "N", "type": "int"}],
                            data=g,
                            width="250px",
                            height="120px",
                        ),
                        width="250px",
                        height="120px",
                        class_name="foreach-grid-box",
                    ),
                ),
                id="de-foreach",
            ),
        ),
        padding="10px",
    )


class BigState(rx.State):
    """5,000-row data editor."""

    big: list[list[Any]] = []
    loaded_ms: int = 0
    last_click: str = ""

    @rx.event
    def load(self):
        self.big = [[i, f"name {i}", round(i * 1.5, 1), i % 2 == 0, f"cat{i % 7}"] for i in range(5000)]

    @rx.event
    def click(self, pos: tuple[int, int]):
        self.last_click = f"{pos[0]},{pos[1]}"


def de_big_page() -> rx.Component:
    """Large data editor page."""
    return rx.vstack(
        nav(),
        rx.heading("5,000 rows"),
        rx.text("rows: ", BigState.big.length(), id="big-count"),
        rx.text("click: ", BigState.last_click, id="big-click"),
        rx.box(
            rx.data_editor(
                columns=[
                    {"title": "Idx", "type": "int"},
                    {"title": "Name", "type": "str"},
                    {"title": "Val", "type": "float"},
                    {"title": "Even", "type": "bool"},
                    {"title": "Cat", "type": "str"},
                ],
                data=BigState.big,
                on_cell_clicked=BigState.click,
                row_markers="number",
                smooth_scroll_y=True,
                id="de-big",
                width="700px",
                height="500px",
            ),
            width="700px",
            height="500px",
            id="de-big-box",
        ),
        padding="10px",
    )
