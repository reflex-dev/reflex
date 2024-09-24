"""Integration tests for table and related components."""

from typing import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness


def Table():
    """App using table component."""
    import reflex as rx

    app = rx.App(state=rx.State)

    @app.add_page
    def index():
        return rx.center(
            rx.input(
                id="token",
                value=rx.State.router.session.client_token,
                is_read_only=True,
            ),
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
def table(tmp_path_factory) -> Generator[AppHarness, None, None]:
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


@pytest.fixture
def driver(table: AppHarness):
    """GEt an instance of the browser open to the table app.

    Args:
        table: harness for Table app

    Yields:
        WebDriver instance.
    """
    driver = table.frontend()
    try:
        token_input = driver.find_element(By.ID, "token")
        assert token_input
        # wait for the backend connection to send the token
        token = table.poll_for_value(token_input)
        assert token is not None

        yield driver
    finally:
        driver.quit()


def test_table(driver, table: AppHarness):
    """Test that a table component is rendered properly.

    Args:
        driver: Selenium WebDriver open to the app
        table: Harness for Table app
    """
    assert table.app_instance is not None, "app is not running"

    thead = driver.find_element(By.TAG_NAME, "thead")
    # poll till page is fully loaded.
    table.poll_for_content(element=thead)
    # check headers
    assert thead.find_element(By.TAG_NAME, "tr").text == "Name Age Location"
    # check first row value
    assert (
        driver.find_element(By.TAG_NAME, "tbody")
        .find_elements(By.TAG_NAME, "tr")[0]
        .text
        == "John 30 New York"
    )
