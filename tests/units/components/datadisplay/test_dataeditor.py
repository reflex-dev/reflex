from reflex.components.datadisplay.dataeditor import DataEditor


def test_dataeditor():
    editor_wrapper = DataEditor.create().render()
    editor = editor_wrapper["children"][0]
    assert editor_wrapper["name"] == "div"
    assert editor_wrapper["props"] == [
        'css={({ ["width"] : "100%", ["height"] : "100%" })}'
    ]
    assert editor["name"] == "DataEditor"
