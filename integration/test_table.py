"""Integration tests for table and related components."""
from typing import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness


def Table():
    """App using table component."""
    from typing import List

    import reflex as rx

    class TableState(rx.State):
        rows: List[List[str]] = [
            ["John", "30", "New York"],
            ["Jane", "31", "San Fransisco"],
            ["Joe", "32", "Los Angeles"],
        ]

        headers: List[str] = ["Name", "Age", "Location"]

        footers: List[str] = ["footer1", "footer2", "footer3"]

        caption: str = "random caption"

    app = rx.App(state=rx.State)

    @app.add_page
    def index():
        return rx.center(
            rx.input(
                id="token",
                value=TableState.router.session.client_token,
                is_read_only=True,
            ),
            rx.table_container(
                rx.table(
                    headers=TableState.headers,
                    rows=TableState.rows,
                    footers=TableState.footers,
                    caption=TableState.caption,
                    variant="striped",
                    color_scheme="blue",
                    width="100%",
                ),
            ),
        )

    @app.add_page
    def another():
        return rx.center(
            rx.table_container(
                rx.table(  # type: ignore
                    rx.thead(  # type: ignore
                        rx.tr(  # type: ignore
                            rx.th("Name"),
                            rx.th("Age"),
                            rx.th("Location"),
                        )
                    ),
                    rx.tbody(  # type: ignore
                        rx.tr(  # type: ignore
                            rx.td("John"),
                            rx.td(30),
                            rx.td("New York"),
                        ),
                        rx.tr(  # type: ignore
                            rx.td("Jane"),
                            rx.td(31),
                            rx.td("San Francisco"),
                        ),
                        rx.tr(  # type: ignore
                            rx.td("Joe"),
                            rx.td(32),
                            rx.td("Los Angeles"),
                        ),
                    ),
                    rx.tfoot(  # type: ignore
                        rx.tr(rx.td("footer1"), rx.td("footer2"), rx.td("footer3"))  # type: ignore
                    ),
                    rx.table_caption("random caption"),
                    variant="striped",
                    color_scheme="teal",
                )
            )
        )

    app.compile()


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


@pytest.mark.parametrize("route", ["", "/another"])
def test_table(driver, table: AppHarness, route):
    """Test that a table component is rendered properly.

    Args:
        driver: Selenium WebDriver open to the app
        table: Harness for Table app
        route: Page route or path.
    """
    driver.get(f"{table.frontend_url}/{route}")
    assert table.app_instance is not None, "app is not running"

    thead = driver.find_element(By.TAG_NAME, "thead")
    # poll till page is fully loaded.
    table.poll_for_content(element=thead)
    # check headers
    assert thead.find_element(By.TAG_NAME, "tr").text == "NAME AGE LOCATION"
    # check first row value
    assert (
        driver.find_element(By.TAG_NAME, "tbody")
        .find_elements(By.TAG_NAME, "tr")[0]
        .text
        == "John 30 New York"
    )
    # check footer
    assert (
        driver.find_element(By.TAG_NAME, "tfoot")
        .find_element(By.TAG_NAME, "tr")
        .text.lower()
        == "footer1 footer2 footer3"
    )
    # check caption
    assert driver.find_element(By.TAG_NAME, "caption").text == "random caption"
