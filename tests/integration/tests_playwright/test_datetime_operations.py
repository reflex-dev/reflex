from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def DatetimeOperationsApp():
    from datetime import datetime

    import reflex as rx

    class DtOperationsState(rx.State):
        date1: datetime = datetime(2021, 1, 1)
        date2: datetime = datetime(2031, 1, 1)
        date3: datetime = datetime(2021, 1, 1)

    app = rx.App(_state=DtOperationsState)

    @app.add_page
    def index():
        return rx.vstack(
            rx.text(DtOperationsState.date1, id="date1"),
            rx.text(DtOperationsState.date2, id="date2"),
            rx.text(DtOperationsState.date3, id="date3"),
            rx.text("Operations between date1 and date2"),
            rx.text(DtOperationsState.date1 == DtOperationsState.date2, id="1_eq_2"),
            rx.text(DtOperationsState.date1 != DtOperationsState.date2, id="1_neq_2"),
            rx.text(DtOperationsState.date1 < DtOperationsState.date2, id="1_lt_2"),
            rx.text(DtOperationsState.date1 <= DtOperationsState.date2, id="1_le_2"),
            rx.text(DtOperationsState.date1 > DtOperationsState.date2, id="1_gt_2"),
            rx.text(DtOperationsState.date1 >= DtOperationsState.date2, id="1_ge_2"),
            rx.text("Operations between date1 and date3"),
            rx.text(DtOperationsState.date1 == DtOperationsState.date3, id="1_eq_3"),
            rx.text(DtOperationsState.date1 != DtOperationsState.date3, id="1_neq_3"),
            rx.text(DtOperationsState.date1 < DtOperationsState.date3, id="1_lt_3"),
            rx.text(DtOperationsState.date1 <= DtOperationsState.date3, id="1_le_3"),
            rx.text(DtOperationsState.date1 > DtOperationsState.date3, id="1_gt_3"),
            rx.text(DtOperationsState.date1 >= DtOperationsState.date3, id="1_ge_3"),
        )


@pytest.fixture
def datetime_operations_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start Table app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance

    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("datetime_operations_app"),
        app_source=DatetimeOperationsApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_datetime_operations(datetime_operations_app: AppHarness, page: Page):
    assert datetime_operations_app.frontend_url is not None

    page.goto(datetime_operations_app.frontend_url)
    expect(page).to_have_url(datetime_operations_app.frontend_url)
    # Check the actual values
    expect(page.locator("id=date1")).to_have_text("2021-01-01 00:00:00")
    expect(page.locator("id=date2")).to_have_text("2031-01-01 00:00:00")
    expect(page.locator("id=date3")).to_have_text("2021-01-01 00:00:00")

    # Check the operations between date1 and date2
    expect(page.locator("id=1_eq_2")).to_have_text("false")
    expect(page.locator("id=1_neq_2")).to_have_text("true")
    expect(page.locator("id=1_lt_2")).to_have_text("true")
    expect(page.locator("id=1_le_2")).to_have_text("true")
    expect(page.locator("id=1_gt_2")).to_have_text("false")
    expect(page.locator("id=1_ge_2")).to_have_text("false")

    # Check the operations between date1 and date3
    expect(page.locator("id=1_eq_3")).to_have_text("true")
    expect(page.locator("id=1_neq_3")).to_have_text("false")
    expect(page.locator("id=1_lt_3")).to_have_text("false")
    expect(page.locator("id=1_le_3")).to_have_text("true")
    expect(page.locator("id=1_gt_3")).to_have_text("false")
    expect(page.locator("id=1_ge_3")).to_have_text("true")
