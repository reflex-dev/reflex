"""Tests for the bounded Community grid adapter."""

from reflex_components_internal.components.base.community_grid import CommunityGrid


def test_dependency_boundary():
    """The adapter must not install the enterprise wrapper or modules."""
    assert CommunityGrid.lib_dependencies == [
        "ag-grid-community@34.3.1",
        "ag-grid-react@34.3.1",
    ]


def test_shared_asset_and_default_size(tmp_path, monkeypatch):
    """The renderer is linked at creation with a usable virtualized viewport."""
    monkeypatch.chdir(tmp_path)
    grid = CommunityGrid.create(row_data=[], column_defs=[])
    assert grid.library.endswith("/community_grid/CommunityGrid.js")
    assert grid.style["height"]._var_value == "420px"
    assert grid.style["width"]._var_value == "100%"
    assert next((tmp_path / "assets/external").rglob("CommunityGrid.js")).is_symlink()


def test_browser_only_import():
    """The browser renderer is dynamically imported without server rendering."""
    grid = CommunityGrid.create(library="$/custom.js")
    assert "ClientSide(() => import" in grid._get_dynamic_imports()
