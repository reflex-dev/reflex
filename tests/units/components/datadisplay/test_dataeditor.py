import json
import re
import subprocess
from pathlib import Path
from typing import Any, cast

import reflex_base
from reflex_base.vars import Var
from reflex_components_dataeditor.dataeditor import DataEditor

from reflex.state import BaseState


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
    editor = cast(DataEditor, DataEditor.create().children[0])
    imports = editor.add_imports()

    assert imports[""] == [
        "@glideapps/glide-data-grid/dist/index.css",
        "react-responsive-carousel/lib/styles/carousel.min.css",
    ]


def test_dataeditor_template_formats_image_cells():
    """Format image values as Glide image cells."""
    template_path = (
        Path(reflex_base.__file__).parent / ".templates/web/utils/helpers/dataeditor.js"
    )
    template = template_path.read_text()

    template = template.replace(
        'import { GridCellKind } from "@glideapps/glide-data-grid";',
        'const GridCellKind = { Image: "image", Text: "text" };',
    )
    test_script = f"""{template}
console.log(JSON.stringify([
  formatCell("single", {{ type: "image" }}),
  formatCell(["first", "second"], {{ type: "image", editable: false }}),
  formatCell("", {{ type: "image" }}),
  formatCell("marker", {{ type: "str" }}),
]));
"""

    result = subprocess.run(
        ["node", "--input-type=module", "--eval", test_script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == [
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
        {
            "kind": "text",
            "data": "marker",
            "displayData": "marker",
            "readonly": False,
            "allowOverlay": True,
        },
    ]


def _columns_prop(editor_render: dict) -> str:
    props = editor_render["children"][0]["props"]
    return next(p for p in props if p.startswith("columns:"))


_REACTIVE_EXPR = (
    "(state.columns).map((col) => "
    '({ type: "str", id: (col.title ?? "").toLowerCase(), ...col }))'
)


def test_dataeditor_literal_columns_default_type():
    editor = DataEditor.create(
        columns=[{"title": "Name"}, {"title": "Age", "type": "int"}]
    ).render()
    prop = _columns_prop(editor)
    assert '["type"] : "str"' in prop, prop
    assert '["id"] : "name"' in prop, prop
    # An explicit type is kept.
    assert '["type"] : "int"' in prop, prop


def test_dataeditor_reactive_columns_default_type():
    # Reactive (Var) columns skip literal formatting, so the documented
    # defaults are applied in JS at render time. See issue #7596.
    wrapper = DataEditor.create(columns=Var(_js_expr="state.columns"))
    editor = cast(DataEditor, wrapper.children[0])
    # The grid prop references the hoisted const declared in the hook.
    prop = _columns_prop(wrapper.render())
    assert re.fullmatch(r"columns:columns_\w+", prop), prop
    name = prop.removeprefix("columns:")
    code = "\n".join(editor.add_hooks())
    assert f"const {name} = {_REACTIVE_EXPR};" in code, code


def test_dataeditor_reactive_columns_preserve_var_data():
    class EditorState(BaseState):
        columns: list[dict[str, str]] = [{"title": "Name"}]

    wrapper = DataEditor.create(columns=cast(Any, EditorState.columns))
    editor = cast(DataEditor, wrapper.children[0])
    # The wrapped expression must keep the original var's data (state dep).
    columns_var = cast(Var, cast(Any, editor).columns)
    assert columns_var._var_data == cast(Var, EditorState.columns)._var_data
    # The grid prop references the hoisted const declared in the hook.
    prop = _columns_prop(wrapper.render())
    assert re.fullmatch(r"columns:columns_\w+", prop), prop


def test_dataeditor_add_hooks_evaluates_columns_once_per_render():
    # Glide calls the getData callback per visible cell per draw, so the
    # columns expression (the .map() wrapper for reactive columns) is
    # declared once in the hook and reused by both the grid prop and the
    # per-cell callback (#7597).
    wrapper = DataEditor.create(columns=Var(_js_expr="state.columns"))
    editor = cast(DataEditor, wrapper.children[0])
    code = "\n".join(editor.add_hooks())
    assert code.count(".map(") == 1, code
    match = re.search(r"const (columns_\w+) = ", code)
    assert match is not None, code
    assert f"formatDataEditorCells(col, row, {match.group(1)}," in code, code
    assert _columns_prop(wrapper.render()) == f"columns:{match.group(1)}"


def test_dataeditor_reactive_columns_generated_expr_js_semantics():
    # Evaluate the expression the component actually generates, not a copy:
    # default type, default id, an explicit override, and the dict-row lookup
    # the id default exists for (#7596).
    editor = cast(
        DataEditor, DataEditor.create(columns=Var(_js_expr="state.columns")).children[0]
    )
    code = "\n".join(editor.add_hooks())
    match = re.search(r"const columns_\w+ = (\(.*\));", code)
    assert match is not None, code
    generated_expr = match.group(1)
    assert generated_expr == _REACTIVE_EXPR

    test_script = f"""
const state = {{ columns: [{{ title: "Name" }}, {{ title: "Age", type: "int" }}] }};
const cols = {generated_expr};
const row = {{ name: "Alice" }};
console.log(JSON.stringify([cols, row[cols[0].id]]));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", test_script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == [
        [
            {"type": "str", "id": "name", "title": "Name"},
            {"type": "int", "id": "age", "title": "Age"},
        ],
        "Alice",
    ]
