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


def test_dataeditor_template_supports_image_cells():
    """The data editor helper maps image columns to native Glide image cells."""
    template_path = (
        Path(reflex_base.__file__).parent / ".templates/web/utils/helpers/dataeditor.js"
    )
    template = template_path.read_text()

    assert 'case "image"' in template
    assert "kind: GridCellKind.Image" in template
