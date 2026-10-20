import json
import subprocess
from pathlib import Path
from typing import cast

import reflex_base
from reflex_components_dataeditor.dataeditor import DataEditor


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
