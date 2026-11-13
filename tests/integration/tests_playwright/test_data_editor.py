"""Playwright integration tests for the data editor component."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def DataEditorApp():
    """App with a data editor that binds on_delete and on_cell_edited."""
    import json

    from reflex_components_dataeditor.dataeditor import GridSelection

    import reflex as rx

    class DataEditorState(rx.State):
        data: list[list[str]] = [["Alpha"], ["Beta"], ["Gamma"]]
        deleted: str = ""

        @rx.event
        def on_delete(self, selection: GridSelection):
            self.deleted = str(selection)

        @rx.event
        def on_cell_edited(self, pos: tuple[int, int], cell):
            col, row = pos
            self.data[row][col] = cell["data"]

        @rx.var
        def data_json(self) -> str:
            return json.dumps(self.data, separators=(",", ":"))

    app = rx.App()

    @app.add_page
    def index():
        return rx.vstack(
            rx.el.input(
                id="token",
                value=DataEditorState.router.session.client_token,
                is_read_only=True,
            ),
            rx.data_editor(
                columns=[{"title": "Name", "id": "name", "type": "str"}],
                data=DataEditorState.data,
                on_delete=DataEditorState.on_delete,
                on_cell_edited=DataEditorState.on_cell_edited,
                row_height=34,
                header_height=36,
            ),
            rx.text(DataEditorState.data_json, id="data"),
            rx.text(DataEditorState.deleted, id="deleted"),
        )


@pytest.fixture(scope="module")
def data_editor_app(
    app_harness_env: type[AppHarness], tmp_path_factory: pytest.TempPathFactory
) -> Generator[AppHarness, None, None]:
    """Run the data editor app in dev and prod modes.

    Args:
        app_harness_env: AppHarness class for dev or production mode.
        tmp_path_factory: Pytest fixture for creating temporary directories.

    Yields:
        The running app harness.
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("data_editor"),
        app_source=DataEditorApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_delete_with_on_delete_bound(data_editor_app: AppHarness, page: Page) -> None:
    """Delete notifies the backend and clears the cell without a page error."""
    assert data_editor_app.frontend_url is not None
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    page.goto(data_editor_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")
    data = page.locator("#data")
    expect(data).to_have_text('[["Alpha"],["Beta"],["Gamma"]]')

    # Glide's scroller covers the canvas, so click by page coordinates: the
    # second row is below the 36px header and the first 34px row.
    canvas = page.get_by_test_id("data-grid-canvas")
    box = canvas.bounding_box()
    assert box is not None
    page.mouse.click(box["x"] + 20, box["y"] + 87)
    expect(canvas).to_be_focused()
    page.keyboard.press("Delete")

    expect(page.locator("#deleted")).to_have_text(
        "{'current': {'cell': [0, 1], 'range': {'x': 0, 'y': 1, 'width': 1, "
        "'height': 1}, 'rangeStack': []}, 'columns': {'items': []}, "
        "'rows': {'items': []}}"
    )
    expect(data).to_have_text('[["Alpha"],[""],["Gamma"]]')
    assert errors == []
