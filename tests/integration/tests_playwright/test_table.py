"""Integration tests for table and related components."""

from typing import Generator

import pytest
from playwright.sync_api import Page

from reflex.testing import AppHarness


def Table():
    """App using table component."""
    import reflex as rx

    app = rx.App(state=rx.State)

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
                        rx.table.cell("San Fransisco"),
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


@pytest.fixture()
def table_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start Table app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance

    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("table"),
        app_source=Table,  # type: ignore
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_table(page: Page, table_app: AppHarness):
    """Test that a table component is rendered properly.

    Args:
        table_app: Harness for Table app
        page: Playwright page instance
    """
    assert table_app.app_instance is not None, "app is not running"
    assert table_app.frontend_url is not None, "frontend url is not available"

    page.goto(table_app.frontend_url)
    table = page.get_by_role("table")

    headers = table.get_by_role("columnheader").all_inner_texts()
    assert headers == ["Name", "Age", "Location"]

    rows = [
        row.split("\t")
        for row in table.locator("tbody").all_inner_texts()[0].splitlines()
    ]

    assert rows[0] == ["John", "30", "New York"]
    assert rows[1] == ["Jane", "31", "San Fransisco"]
    assert rows[2] == ["Joe", "32", "Los Angeles"]
