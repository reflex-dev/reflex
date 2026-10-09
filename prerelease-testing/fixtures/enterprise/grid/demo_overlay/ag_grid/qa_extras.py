"""QA extension pages (not part of the upstream demo) for the 0.10.0a1 gap campaign.

Covers: row_id_key callback, pinned rows (new names AND legacy aliases),
suppress_overlays, custom JS cell renderer / select editor / value formatter,
rxe.ag_grid inside @rx.memo, inside rx.ComponentState (two instances), and
column defs generated from State data via ArrayVar.foreach.
"""

from typing import Any

import reflex as rx

import reflex_enterprise as rxe

from .common import demo


class QAGridState(rx.State):
    """State backing the QA grid pages."""

    rows: list[dict[str, Any]] = [
        {"uid": "u-1", "name": "alpha", "qty": 1, "status": "new"},
        {"uid": "u-2", "name": "beta", "qty": 2, "status": "new"},
        {"uid": "u-3", "name": "gamma", "qty": 3, "status": "done"},
    ]
    fields: list[str] = ["name", "qty"]
    edits: list[str] = []
    clicked: str = ""

    @rx.event
    def bump(self):
        """Increment qty of u-2 by replacing the row list (immutable update)."""
        self.rows = [
            {**r, "qty": r["qty"] + 10} if r["uid"] == "u-2" else r for r in self.rows
        ]

    @rx.event
    def prepend(self):
        """Insert a row at the top so positional ids would shift."""
        n = len(self.rows) + 1
        self.rows = [
            {"uid": f"u-{n}", "name": f"new{n}", "qty": n, "status": "new"},
            *self.rows,
        ]

    @rx.event
    def toggle_status_field(self):
        """Add/remove the status column via State-derived column defs."""
        if "status" in self.fields:
            self.fields = [f for f in self.fields if f != "status"]
        else:
            self.fields = [*self.fields, "status"]

    clip_rows: list[dict[str, Any]] = [{"a": 1, "b": 10}, {"a": 2, "b": 20}, {"a": 3, "b": 30}]
    clip_log: list[str] = []

    @rx.event
    def on_edit(self, params: dict[str, Any]):
        """Record a cell edit; node_id is the row id, i.e. data.uid via row_id_key."""
        uid = params.get("node_id")
        field = params.get("field")
        self.edits = [*self.edits, f"{uid}:{field}->{params.get('newValue')}"]
        self.rows = [
            {**r, field: params.get("newValue")} if r["uid"] == uid else r
            for r in self.rows
        ]

    @rx.event
    def on_clip_change(self, params: dict[str, Any]):
        """Record clipboard/paste driven value changes."""
        self.clip_log = [*self.clip_log, f"{params.get('rowIndex')}:{params.get('field')}={params.get('newValue')}"]

    @rx.event
    def on_cell_clicked(self, params: dict[str, Any]):
        """Record which cell was clicked inside the memo grid."""
        self.clicked = f"{params.get('colDef', {}).get('field')}={params.get('value')}"


badge_renderer = rx.vars.function.ArgsFunctionOperation.create(
    args_names=["params"],
    return_expr=rx.Var.create(
        rx.badge(
            "S:",
            rx.Var("params.value"),
            color_scheme="green",
            class_name="qa-status-badge",
        )
    ),
)

base_columns: list[Any] = [
    {"field": "uid"},
    {"field": "name"},
    {
        "field": "qty",
        "value_formatter": "params.value + ' units'",
    },
    rxe.ag_grid.column_def(
        field="status",
        editable=True,
        cell_renderer=badge_renderer,
        cell_editor=rxe.ag_grid.editors.select,
        cell_editor_params={"values": ["new", "doing", "done"]},
    ),
]


@demo(
    route="/qa-grid-props",
    title="QA: row_id_key / pinned / overlays",
    description="QA: row_id_key, pinned rows (new + legacy alias), suppress_overlays, custom renderer/editor.",
)
def qa_grid_props_page():
    """Grids exercising AG Grid 36 wrapper props."""
    return rx.vstack(
        rx.hstack(
            rx.button("Bump u-2", on_click=QAGridState.bump, id="qa-bump"),
            rx.button("Prepend", on_click=QAGridState.prepend, id="qa-prepend"),
            rx.text("edits: ", QAGridState.edits.join(" | "), id="qa-edits"),
        ),
        rx.text("rowid grid (new pinned names)"),
        rxe.ag_grid(
            id="qa_rowid_grid",
            row_id_key="uid",
            column_defs=base_columns,
            row_data=QAGridState.rows,
            pinned_top_row_data=[{"uid": "TOP-NEW", "name": "pinned top new"}],
            pinned_bottom_row_data=[{"uid": "BOT-NEW", "name": "pinned bottom new"}],
            on_cell_value_changed=QAGridState.on_edit,
            width="100%",
            height="260px",
        ),
        rx.text("legacy alias grid"),
        rxe.ag_grid(
            id="qa_alias_grid",
            column_defs=[{"field": "uid"}, {"field": "name"}],
            row_data=QAGridState.rows,
            pinned_row_top_data=[{"uid": "TOP-OLD", "name": "pinned top old"}],
            pinned_row_bottom_data=[{"uid": "BOT-OLD", "name": "pinned bottom old"}],
            width="100%",
            height="260px",
        ),
        rx.text("clipboard grid (copy_headers_to_clipboard=False registers ClipboardModule)"),
        rx.text("clip: ", QAGridState.clip_log.join(" | "), id="qa-clip-log"),
        rxe.ag_grid(
            id="qa_clip_grid",
            column_defs=[{"field": "a", "editable": True}, {"field": "b", "editable": True}],
            row_data=QAGridState.clip_rows,
            cell_selection=True,
            copy_headers_to_clipboard=False,
            on_cell_value_changed=QAGridState.on_clip_change,
            width="400px",
            height="180px",
        ),
        rx.hstack(
            rx.box(
                rx.text("empty, overlays default"),
                rxe.ag_grid(
                    id="qa_empty_default",
                    column_defs=[{"field": "uid"}],
                    row_data=[],
                    width="300px",
                    height="150px",
                ),
                id="qa-empty-default-box",
            ),
            rx.box(
                rx.text("empty, suppress noRows"),
                rxe.ag_grid(
                    id="qa_empty_suppressed",
                    column_defs=[{"field": "uid"}],
                    row_data=[],
                    suppress_overlays=["noRows"],
                    width="300px",
                    height="150px",
                ),
                id="qa-empty-suppressed-box",
            ),
        ),
        width="100%",
    )


@rx.memo
def memo_grid(
    column_defs: rx.Var[list[dict[str, Any]]], row_data: rx.Var[list[dict[str, Any]]]
) -> rx.Component:
    """An AG Grid wrapped in a memo component, props fed from State."""
    return rxe.ag_grid(
        id="qa_memo_grid",
        column_defs=column_defs,
        row_data=row_data,
        on_cell_clicked=QAGridState.on_cell_clicked,
        width="100%",
        height="220px",
    )


class GridCS(rx.ComponentState):
    """ComponentState owning its own grid data."""

    cs_rows: list[dict[str, Any]] = [{"k": 1, "v": "one"}]
    cs_cols: list[str] = ["k", "v"]

    @rx.event
    def add_row(self):
        """Append a row to this instance's data."""
        n = len(self.cs_rows) + 1
        self.cs_rows = [*self.cs_rows, {"k": n, "v": f"row{n}"}]

    @classmethod
    def get_component(cls, grid_id: str, **props) -> rx.Component:
        """Render the per-instance grid."""
        return rx.vstack(
            rx.button(
                "Add row " + grid_id, on_click=cls.add_row, id=f"{grid_id}-add"
            ),
            rx.text("rows: ", cls.cs_rows.length(), id=f"{grid_id}-count"),
            rxe.ag_grid(
                id=grid_id,
                column_defs=cls.cs_cols.foreach(lambda f: {"field": f}),
                row_data=cls.cs_rows,
                width="100%",
                height="200px",
            ),
            width="45%",
        )


@demo(
    route="/qa-grid-memo",
    title="QA: memo / ComponentState grids",
    description="QA: rxe.ag_grid inside @rx.memo and rx.ComponentState, column defs from State via foreach.",
)
def qa_grid_memo_page():
    """Grids inside memo and ComponentState."""
    return rx.vstack(
        rx.hstack(
            rx.button(
                "Toggle status column",
                on_click=QAGridState.toggle_status_field,
                id="qa-toggle-col",
            ),
            rx.text("clicked: ", QAGridState.clicked, id="qa-clicked"),
        ),
        memo_grid(
            column_defs=QAGridState.fields.foreach(lambda f: {"field": f}),
            row_data=QAGridState.rows,
        ),
        rx.hstack(
            GridCS.create(grid_id="qa_cs_a"),
            GridCS.create(grid_id="qa_cs_b"),
            width="100%",
        ),
        width="100%",
    )


from reflex_enterprise.components.ag_grid.datasource import DatasourceParams  # noqa: E402

from .model_wrapper_simple import Friend  # noqa: E402


class FriendWrapperWorkaround(rxe.ModelWrapper[Friend]):
    """rxe.ModelWrapper with the params class re-declared as a plain class attribute.

    On reflex 0.10.0a1 the inherited annotated `__data_source_params_class__`
    becomes a `Field` and the data endpoint 500s; a plain (unannotated)
    override keeps it a class, which lets the rest of the wrapper be exercised.
    """

    __data_source_params_class__ = DatasourceParams


@demo(
    route="/qa-model-workaround",
    title="QA: ModelWrapper (params-class workaround)",
    description="QA: infinite ModelWrapper with multi-row selection; __data_source_params_class__ re-declared unannotated.",
)
def qa_model_workaround_page():
    """Infinite-row model wrapper usable on 0.10.0a1."""
    return rx.box(
        FriendWrapperWorkaround.create(
            model_class=Friend,
            row_selection={"mode": "multiRow", "headerCheckbox": False},
        ),
        width="100%",
        height="71vh",
        padding_bottom="60px",
    )
