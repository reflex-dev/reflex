import json
import re
import subprocess
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pytest
import reflex_base
from reflex_base.vars.base import LiteralVar, Var
from reflex_base.vars.sequence import ArrayVar
from reflex_components_dataeditor.dataeditor import DataEditor

from reflex.state import BaseState

_TEMPLATE_PATH = (
    Path(reflex_base.__file__).parent / ".templates/web/utils/helpers/dataeditor.js"
)


def _helpers_js() -> str:
    """Load the dataeditor.js helpers with the Glide import replaced by a stub.

    Returns:
        The helper module source.
    """
    return _TEMPLATE_PATH.read_text().replace(
        'import { GridCellKind } from "@glideapps/glide-data-grid";',
        'const GridCellKind = { Image: "image", Loading: "loading", Number: "number", Text: "text" };',
    )


def _run_node(script: str) -> Any:
    """Run a module script under node and parse the JSON it prints.

    Args:
        script: The script source.

    Returns:
        The parsed output.
    """
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _create(**props) -> DataEditor:
    """Create a data editor and return the grid inside its sizing wrapper.

    Args:
        **props: The props of the data editor.

    Returns:
        The grid component.
    """
    return cast(DataEditor, DataEditor.create(**props).children[0])


def _prop(editor: DataEditor, name: str) -> str:
    """Render the grid and read one of its props.

    Args:
        editor: The grid component.
        name: The rendered name of the prop.

    Returns:
        The rendered value of the prop.
    """
    prefix = f"{name}:"
    rendered = next(p for p in editor.render()["props"] if p.startswith(prefix))
    return rendered.removeprefix(prefix)


def _set_prop(editor: DataEditor, name: str) -> Var:
    """Read a prop the grid was created with, without rendering it.

    Args:
        editor: The grid component.
        name: The name of the prop.

    Returns:
        The var assigned to the prop.
    """
    return dict(editor._iter_set_props())[name]


def _hooks(editor: DataEditor) -> list[str]:
    """Collect the hooks the grid renders.

    Args:
        editor: The grid component.

    Returns:
        The hooks, in order.
    """
    return list(editor._get_all_hooks())


def _react_imports(editor: DataEditor) -> set[str]:
    """Collect the names the grid imports from react.

    Args:
        editor: The grid component.

    Returns:
        The imported names.
    """
    return {imp.tag for imp in editor._get_all_imports().get("react", []) if imp.tag}


def _text_cell(value: str) -> dict:
    return {
        "kind": "text",
        "data": value,
        "displayData": value,
        "readonly": False,
        "allowOverlay": True,
    }


def test_dataeditor():
    editor_wrapper = DataEditor.create().render()
    editor = editor_wrapper["children"][0]
    assert editor_wrapper["name"] == '"div"'
    assert editor_wrapper["props"] == [
        'css:({ ["width"] : "100%", ["height"] : "100%" })'
    ]
    assert editor["name"] == "DataEditor"


def test_dataeditor_imports_image_overlay_stylesheet():
    """Include Glide's image-overlay carousel stylesheet."""
    editor = _create()
    imports = editor.add_imports()

    assert imports[""] == [
        "@glideapps/glide-data-grid/dist/index.css",
        "react-responsive-carousel/lib/styles/carousel.min.css",
    ]


def test_dataeditor_template_formats_image_cells():
    """Format image values as Glide image cells."""
    test_script = f"""{_helpers_js()}
console.log(JSON.stringify([
  formatCell("single", {{ type: "image" }}),
  formatCell(["first", "second"], {{ type: "image", editable: false }}),
  formatCell("", {{ type: "image" }}),
  formatCell("marker", {{ type: "str" }}),
]));
"""

    assert _run_node(test_script) == [
        {
            "kind": "image",
            "data": ["single"],
            "allowAdd": False,
            "readonly": False,
            "allowOverlay": True,
        },
        {
            "kind": "image",
            "data": ["first", "second"],
            "allowAdd": False,
            "readonly": True,
            "allowOverlay": True,
        },
        {
            "kind": "image",
            "data": [],
            "allowAdd": False,
            "readonly": False,
            "allowOverlay": True,
        },
        _text_cell("marker"),
    ]


def test_dataeditor_literal_columns_defaults():
    """A literal column gets the default id, type and overlay icon.

    An explicit value wins, and the column dicts passed in are not modified.
    """
    columns = [
        "Name",
        {"title": "Age", "type": "int"},
        {"title": "Birth", "id": "date"},
    ]
    passed = [dict(col) if isinstance(col, dict) else col for col in columns]

    editor = _create(columns=columns)

    assert _prop(editor, "columns") == str(
        LiteralVar.create([
            {"title": "Name", "id": "name", "type": "str"},
            {"id": "age", "type": "int", "overlayIcon": None, "title": "Age"},
            {"id": "date", "type": "str", "overlayIcon": None, "title": "Birth"},
        ])
    )
    assert columns == passed


def test_dataeditor_literal_columns_reject_unknown_type():
    with pytest.raises(ValueError, match="unexpected type"):
        DataEditor.create(columns=cast(Any, [1]))


def test_dataeditor_literal_columns_reject_dataframe():
    """A dataframe already names its columns."""
    data: Any = pd.DataFrame({"Name": ["Alice"]})
    with pytest.raises(ValueError, match="pandas dataframe"):
        DataEditor.create(columns=[{"title": "Name"}], data=data)


def test_dataeditor_get_cell_content_is_not_configurable(caplog):
    editor = _create(get_cell_content="mine")

    assert str(_set_prop(editor, "get_cell_content")) != "mine"
    assert "get_cell_content is not user configurable" in caplog.text


def test_dataeditor_cell_content_callback():
    """The cell callback is a useCallback settled at create time.

    Literal columns and data are constants, so it has no dependencies.
    """
    editor = _create(columns=["Name"], data=[["Alice"]])
    callback = str(_set_prop(editor, "get_cell_content"))

    assert re.fullmatch(r"getData_\w+", callback)
    assert _prop(editor, "getCellContent") == callback
    assert _hooks(editor) == [
        (
            f"const {callback} = useCallback(([col, row]) => formatDataEditorCells("
            f"col, row, {_prop(editor, 'columns')}, {_prop(editor, 'data')}), [])"
        )
    ]
    assert _react_imports(editor) == {"useCallback"}
    helper_imports = editor._get_all_imports()["$/utils/helpers/dataeditor.js"]
    assert [imp.tag for imp in helper_imports] == ["formatDataEditorCells"]


def test_dataeditor_cell_content_callback_depends_on_state_data():
    class DataState(BaseState):
        data: list[list[str]] = [["Alice"]]

    editor = _create(columns=["Name"], data=DataState.data)

    (hook,) = [hook for hook in _hooks(editor) if "useCallback" in hook]
    assert hook.endswith(f", [{DataState.data!s}])")


def test_dataeditor_reactive_columns():
    """State-backed columns get the defaults in a useMemo keyed on them.

    The cell callback then depends on the memoized list, and the columns prop
    still tracks the state field it comes from.
    """

    class GridState(BaseState):
        columns: list[dict[str, str]] = [{"title": "Name"}]
        data: list[list[str]] = [["Alice"]]

    editor = _create(columns=GridState.columns, data=GridState.data)
    columns = _prop(editor, "columns")
    callback = str(_set_prop(editor, "get_cell_content"))

    assert re.fullmatch(r"columns_\w+", columns)
    state_var_data = cast(Var, GridState.columns)._get_all_var_data()
    assert state_var_data is not None
    assert _hooks(editor) == [
        *state_var_data.hooks,
        (
            f"const {columns} = useMemo(() => ({GridState.columns!s}).map("
            '(col) => typeof col === "string" ? { title: col, id: col.toLowerCase(), type: "str" } '
            ': { type: "str", id: (col.title ?? "").toLowerCase(), ...col }), '
            f"[{GridState.columns!s}])"
        ),
        (
            f"const {callback} = useCallback(([col, row]) => formatDataEditorCells("
            f"col, row, {columns}, {GridState.data!s}), [{columns}, {GridState.data!s}])"
        ),
    ]
    columns_var_data = _set_prop(editor, "columns")._get_all_var_data()
    assert columns_var_data is not None
    assert columns_var_data.field_dependencies == state_var_data.field_dependencies
    assert (
        dict(state_var_data.imports).items() <= dict(columns_var_data.imports).items()
    )
    assert _react_imports(editor) == {"useMemo", "useCallback"}


def test_dataeditor_hooks_depend_on_the_vars_behind_derived_props():
    """Derived columns and data render to a fresh value on every evaluation.

    The hooks depend on the state vars they are built from instead, and not on
    the predicate, which is a constant.
    """

    class TableState(BaseState):
        columns: list[dict[str, str]] = [{"title": "rank"}, {"title": "name"}]
        data: list[list[str]] = [["1", "Alice"]]

    editor = _create(
        columns=cast(ArrayVar, TableState.columns).filter(
            lambda col: col["title"].to(str).startswith("r")
        ),
        data=cast(ArrayVar, TableState.data).filter(lambda row: row[0] != "0"),
    )
    columns = _prop(editor, "columns")

    memo_hook, callback_hook = [
        hook for hook in _hooks(editor) if "useMemo" in hook or "useCallback" in hook
    ]
    assert ".filter(" in memo_hook
    assert memo_hook.endswith(f", [{TableState.columns!s}])")
    assert callback_hook.endswith(f", [{columns}, {TableState.data!s}])")


def test_dataeditor_reactive_columns_literal_var_is_constant():
    """A literal var has nothing to memoize on, so the mapping runs once."""
    editor = _create(columns=LiteralVar.create([{"title": "Name"}]))

    (hook,) = [hook for hook in _hooks(editor) if "useMemo" in hook]
    assert hook.endswith(", [])")


def test_dataeditor_reactive_columns_render_cells():
    """Run the generated hooks with the real helper.

    The memoized list carries the defaults: an untyped column renders a text
    cell, the default id finds the value in a dict row, an explicit id or type
    wins, and a column may be just its title.
    """
    editor = _create(
        columns=Var(_js_expr="state.columns"), data=Var(_js_expr="state.data"), rows=2
    )
    columns = _prop(editor, "columns")
    callback = str(_set_prop(editor, "get_cell_content"))
    hooks = "\n".join(_hooks(editor))

    test_script = f"""{_helpers_js()}
const useMemo = (compute) => compute();
const useCallback = (callback) => callback;
const state = {{
  columns: [
    {{ title: "Name" }},
    {{ title: "Age", type: "int" }},
    {{ title: "Birth", id: "date" }},
    "Email",
  ],
  data: [
    {{ name: "Alice", age: 30, date: "1990", email: "alice@example.com" }},
    ["Bob", 25, "1991", "bob@example.com"],
  ],
}};
{hooks}
console.log(JSON.stringify([
  structuredClone({columns}),
  {callback}([0, 0]),
  {callback}([1, 0]),
  {callback}([2, 0]),
  {callback}([3, 0]),
  {callback}([2, 1]),
  {callback}([3, 1]),
  {callback}([0, 2]),
]));
"""

    assert _run_node(test_script) == [
        [
            {"type": "str", "id": "name", "title": "Name"},
            {"type": "int", "id": "age", "title": "Age"},
            {"type": "str", "id": "date", "title": "Birth"},
            {"type": "str", "id": "email", "title": "Email"},
        ],
        _text_cell("Alice"),
        {
            "kind": "number",
            "data": 30,
            "displayData": "30",
            "readonly": False,
            "allowOverlay": True,
        },
        _text_cell("1990"),
        _text_cell("alice@example.com"),
        _text_cell("1991"),
        _text_cell("bob@example.com"),
        {"kind": "loading"},
    ]
