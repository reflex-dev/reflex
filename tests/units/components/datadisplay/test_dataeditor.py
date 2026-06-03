from typing import Any, cast

from reflex_base.components.component import Component
from reflex_base.vars.base import Var
from reflex_components_dataeditor.dataeditor import DataEditor

COLUMNS = [{"title": "A", "type": "str"}, {"title": "B", "type": "int"}]


def _grid(wrapper: Component) -> Any:
    """Return the inner DataEditor grid from the Div wrapper that create() returns.

    Args:
        wrapper: The component returned by DataEditor.create().

    Returns:
        The wrapped DataEditor grid component.
    """
    return cast(Any, wrapper.children[0])


def _data_hook(grid: Any) -> str:
    """Return the getData callback hook emitted by a DataEditor grid.

    Args:
        grid: A DataEditor grid component.

    Returns:
        The single hook line that declares the getData callback.
    """
    hooks = [h for h in grid._get_added_hooks() if "formatDataEditorCells" in h]
    assert len(hooks) == 1
    return hooks[0]


def test_dataeditor():
    editor_wrapper = DataEditor.create().render()
    editor = editor_wrapper["children"][0]
    assert editor_wrapper["name"] == '"div"'
    assert editor_wrapper["props"] == [
        'css:({ ["width"] : "100%", ["height"] : "100%" })'
    ]
    assert editor["name"] == "DataEditor"


def test_get_cell_content_prop_matches_emitted_hook():
    """The rendered get_cell_content prop references the function add_hooks declares.

    This is the contract the immutability refactor preserves without mutating the
    frozen component: the callback name is derived at create() time and the hook
    is emitted by add_hooks() under the same name.
    """
    grid = _grid(DataEditor.create(columns=COLUMNS, data=[["a", 1]]))
    callback_name = str(grid.get_cell_content)
    assert callback_name.startswith("getData_")
    assert f"function {callback_name}([col, row]){{" in _data_hook(grid)


def test_identical_editors_share_callback_and_dedupe():
    """Editors with identical columns/data share a name and a byte-identical hook.

    Their hook bodies are equal, so the compiler's hook dedupe collapses them to a
    single function declaration rather than emitting a duplicate.
    """
    g1 = _grid(DataEditor.create(columns=COLUMNS, data=[["a", 1], ["b", 2]]))
    g2 = _grid(DataEditor.create(columns=COLUMNS, data=[["a", 1], ["b", 2]]))
    assert str(g1.get_cell_content) == str(g2.get_cell_content)
    assert _data_hook(g1) == _data_hook(g2)


def test_distinct_editors_get_distinct_callbacks():
    """Editors with different data get distinct callback names and hook bodies."""
    g1 = _grid(DataEditor.create(columns=COLUMNS, data=[["a", 1]]))
    g2 = _grid(DataEditor.create(columns=COLUMNS, data=[["x", 9]]))
    assert str(g1.get_cell_content) != str(g2.get_cell_content)
    assert _data_hook(g1) != _data_hook(g2)


def test_add_hooks_does_not_mutate_frozen_grid():
    """Collecting hooks leaves the frozen grid untouched (no compile-time mutation)."""
    grid = _grid(DataEditor.create(columns=COLUMNS, data=[["a", 1]]))
    before = str(grid.get_cell_content)
    grid._get_added_hooks()
    assert str(grid.get_cell_content) == before


def test_data_callback_name_no_collision_on_separator():
    """Distinct (columns, data) bindings never collapse to the same callback name.

    ``|`` and ``||`` appear in compiled Var expressions, so a naive
    ``f"{columns}|{data}"`` hash input is ambiguous: ``("a", "b|c")`` and
    ``("a|b", "c")`` concatenate to the same string yet have different hook
    bodies. Sharing a name with differing bodies would emit two clashing function
    declarations, so the names must differ.
    """
    callback_name = cast(Any, DataEditor)._data_callback_name
    name_a = callback_name(Var(_js_expr="a"), Var(_js_expr="b|c"))
    name_b = callback_name(Var(_js_expr="a|b"), Var(_js_expr="c"))
    assert name_a != name_b
