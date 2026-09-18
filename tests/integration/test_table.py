"""Integration tests for table and related components."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness

expected_col_headers = ["Name", "Age", "Location"]
expected_row_headers = ["John", "Jane", "Joe"]
expected_cells_data = [
    ["30", "New York"],
    ["31", "San Francisco"],
    ["32", "Los Angeles"],
]


def Table():
    """App using table component."""
    import reflex as rx

    app = rx.App()

    @app.add_page
    def index():
        return rx.center(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Name"),
                        rx.table.column_header_cell("Age"),
                        rx.table.column_header_cell("Location"),
                    ),
                ),
                rx.table.body(
                    rx.table.row(
                        rx.table.row_header_cell("John"),
                        rx.table.cell(30),
                        rx.table.cell("New York"),
                    ),
                    rx.table.row(
                        rx.table.row_header_cell("Jane"),
                        rx.table.cell(31),
                        rx.table.cell("San Francisco"),
                    ),
                    rx.table.row(
                        rx.table.row_header_cell("Joe"),
                        rx.table.cell(32),
                        rx.table.cell("Los Angeles"),
                    ),
                ),
                width="100%",
            ),
        )


@pytest.fixture
def table_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start Table app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance

    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("table"),
        app_source=Table,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_table(page: Page, table_app: AppHarness):
    """Test that a table component is rendered properly.

    Args:
        table_app: Harness for Table app
        page: Playwright page instance
    """
    assert table_app.frontend_url is not None, "frontend url is not available"

    page.goto(table_app.frontend_url)
    table = page.get_by_role("table")

    # Check column headers
    expect(table.get_by_role("columnheader")).to_have_count(3)
    headers = table.get_by_role("columnheader")
    for header, exp_value in zip(headers.all(), expected_col_headers, strict=True):
        expect(header).to_have_text(exp_value)

    # Check rows headers
    rows = table.get_by_role("rowheader")
    for row, expected_row in zip(rows.all(), expected_row_headers, strict=True):
        expect(row).to_have_text(expected_row)

    # Check cells
    rows = table.get_by_role("cell").all_inner_texts()
    for i, expected_row in enumerate(expected_cells_data):
        idx = i * 2
        assert [rows[idx], rows[idx + 1]] == expected_row
