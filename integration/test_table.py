"""Integration tests for table and related components."""
import time
from typing import Generator, List

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from reflex.testing import AppHarness


def Table():
    """App using table component"""

    import reflex as rx
    from typing import List

    class TableState(rx.State):

        @rx.var
        def rows(self) -> List[List[str]]:
            return [
                ["John", "30", "New York"],
                ["Jane", "31", "San Fransisco"],
                ["Joe", "32", "Los Angeles"]
            ]

        @rx.var
        def headers(self) -> List[str]:
            return ["Name", "Age", "Location"]

        @rx.var
        def footers(self) -> List[str]:
            return ["footer1", "footer2", "footer3"]

        @rx.var
        def caption(self) -> str:
            return "random caption"

    app = rx.App(state=TableState)

    @app.add_page
    def index():
        return rx.center(
            rx.table_container(

                rx.table(
                    headers=TableState.headers,
                    rows=TableState.rows,
                    footers=TableState.footers,
                    caption=TableState.caption,
                    variant="striped",
                    color_scheme="blue",
                    width="100%"
                ),

            )
        )

    app.compile()


@pytest.fixture()
def table(tmp_path_factory) -> Generator[AppHarness, None, None]:
    with AppHarness.create(
            root=tmp_path_factory.mktemp("table"),
            app_source=Table,
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
        assert table.poll_for_clients()
        yield driver
    finally:
        driver.quit()


def test_table(driver, table: AppHarness):
    assert table.app_instance is not None, "app is not running"
    # check headers
    assert driver.find_element(By.TAG_NAME, "thead").find_element(By.TAG_NAME, "tr").text == "NAME AGE LOCATION"
    # check first row value
    assert driver.find_element(By.TAG_NAME, "tbody").find_elements(By.TAG_NAME, "tr")[0].text == "John 30 New York"
    # check footer
    assert driver.find_element(By.TAG_NAME, "tfoot").find_element(By.TAG_NAME, "tr").text == "FOOTER1 FOOTER2 FOOTER3"
    # check caption
    assert driver.find_element(By.TAG_NAME, "caption").text == "random caption"