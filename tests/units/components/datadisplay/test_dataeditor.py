from pathlib import Path

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


def test_dataeditor_template_supports_image_cells():
    """The data editor helper maps image columns to native Glide image cells."""
    template_path = (
        Path(reflex_base.__file__).parent / ".templates/web/utils/helpers/dataeditor.js"
    )
    template = template_path.read_text()

    assert 'case "image"' in template
    assert "kind: GridCellKind.Image" in template
