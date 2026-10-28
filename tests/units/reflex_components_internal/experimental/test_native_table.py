"""Native table wrapper import and boundary tests."""

from reflex_components_internal.experimental.native_table import (
    NativeTable,
    native_table,
)


def test_native_table_uses_own_renderer_without_grid_dependencies():
    """Keep the original prototype independent of grid packages."""
    component = native_table(
        rows=[{"id": "a", "name": "First"}],
        columns=[{"key": "name", "label": "Name"}],
    )
    assert component.tag == "NativeTable"
    assert component.library is not None
    assert "NativeTable.js" in component.library
    assert component.lib_dependencies == []


def test_native_table_has_bounded_data_api():
    """Keep prototype properties explicit rather than forwarding grid options."""
    props = set(NativeTable.get_props())
    assert {"rows", "columns", "row_id_key", "page_size", "loading", "error"} <= props
    assert "grid_options" not in props
