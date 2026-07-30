from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def DatetimeOperationsApp():
    from datetime import date, datetime, timedelta, timezone

    import reflex as rx

    class DtOperationsState(rx.State):
        date1: datetime = datetime(2021, 1, 1)
        date2: datetime = datetime(2031, 1, 1)
        date3: datetime = datetime(2021, 1, 1)
        date4: datetime = datetime(2021, 1, 1, tzinfo=timezone.utc)
        date5: datetime = datetime(2021, 1, 1, 1, tzinfo=timezone(timedelta(hours=1)))
        date6: datetime = datetime(2021, 1, 1, 1, tzinfo=timezone(timedelta(hours=2)))
        date7: datetime = datetime(
            1890,
            1,
            1,
            tzinfo=timezone(timedelta(minutes=9, seconds=21)),
        )
        date8: datetime = datetime(
            1889,
            12,
            31,
            23,
            50,
            39,
            tzinfo=timezone.utc,
        )
        date9: date = date(2021, 1, 1)
        date10: date = date(2031, 1, 1)
        unset1: datetime | None = None
        unset2: datetime | None = None

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
            rx.text("Operations with timezone offsets"),
            rx.text(DtOperationsState.date4 == DtOperationsState.date5, id="4_eq_5"),
            rx.text(DtOperationsState.date4 != DtOperationsState.date5, id="4_neq_5"),
            rx.text(DtOperationsState.date6 < DtOperationsState.date4, id="6_lt_4"),
            rx.text(DtOperationsState.date4 <= DtOperationsState.date5, id="4_le_5"),
            rx.text(DtOperationsState.date4 > DtOperationsState.date6, id="4_gt_6"),
            rx.text(DtOperationsState.date4 >= DtOperationsState.date5, id="4_ge_5"),
            rx.text("Operations with second-level timezone offsets"),
            rx.text(DtOperationsState.date7 == DtOperationsState.date8, id="7_eq_8"),
            rx.text(DtOperationsState.date7 <= DtOperationsState.date8, id="7_le_8"),
            rx.text("Operations mixing naive and timezone-aware datetimes"),
            rx.text(DtOperationsState.date1 == DtOperationsState.date4, id="1_eq_4"),
            rx.text(DtOperationsState.date1 != DtOperationsState.date4, id="1_neq_4"),
            rx.text(DtOperationsState.date1 < DtOperationsState.date4, id="1_lt_4"),
            rx.text(DtOperationsState.date1 <= DtOperationsState.date4, id="1_le_4"),
            rx.text(DtOperationsState.date1 > DtOperationsState.date4, id="1_gt_4"),
            rx.text(DtOperationsState.date1 >= DtOperationsState.date4, id="1_ge_4"),
            rx.text("Operations between dates"),
            rx.text(DtOperationsState.date9 == DtOperationsState.date10, id="9_eq_10"),
            rx.text(DtOperationsState.date9 != DtOperationsState.date10, id="9_neq_10"),
            rx.text(DtOperationsState.date9 < DtOperationsState.date10, id="9_lt_10"),
            rx.text(DtOperationsState.date9 <= DtOperationsState.date10, id="9_le_10"),
            rx.text("Operations mixing dates and naive datetimes"),
            rx.text(DtOperationsState.date9 == DtOperationsState.date1, id="9_eq_1"),
            rx.text(DtOperationsState.date9 != DtOperationsState.date1, id="9_neq_1"),
            rx.text(DtOperationsState.date9 < DtOperationsState.date1, id="9_lt_1"),
            rx.text(DtOperationsState.date9 >= DtOperationsState.date1, id="9_ge_1"),
            rx.text("Operations with unset optional datetimes"),
            rx.text(DtOperationsState.unset1 == DtOperationsState.date1, id="u1_eq_1"),
            rx.text(DtOperationsState.unset1 != DtOperationsState.date1, id="u1_neq_1"),
            rx.text(
                DtOperationsState.unset1 < DtOperationsState.date1,  # pyright: ignore[reportOptionalOperand]
                id="u1_lt_1",
            ),
            rx.text(
                DtOperationsState.unset1 <= DtOperationsState.date1,  # pyright: ignore[reportOptionalOperand]
                id="u1_le_1",
            ),
            rx.text(
                DtOperationsState.unset1 > DtOperationsState.date1,  # pyright: ignore[reportOptionalOperand]
                id="u1_gt_1",
            ),
            rx.text(
                DtOperationsState.unset1 >= DtOperationsState.date1,  # pyright: ignore[reportOptionalOperand]
                id="u1_ge_1",
            ),
            rx.text(
                DtOperationsState.unset1 == DtOperationsState.unset2, id="u1_eq_u2"
            ),
            rx.text(
                DtOperationsState.unset1 != DtOperationsState.unset2, id="u1_neq_u2"
            ),
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

    # Check comparisons normalize timezone offsets
    expect(page.locator("id=4_eq_5")).to_have_text("true")
    expect(page.locator("id=4_neq_5")).to_have_text("false")
    expect(page.locator("id=6_lt_4")).to_have_text("true")
    expect(page.locator("id=4_le_5")).to_have_text("true")
    expect(page.locator("id=4_gt_6")).to_have_text("true")
    expect(page.locator("id=4_ge_5")).to_have_text("true")

    # Check comparisons support valid second-level UTC offsets
    expect(page.locator("id=7_eq_8")).to_have_text("true")
    expect(page.locator("id=7_le_8")).to_have_text("true")

    # Check mixed naive and timezone-aware values are deterministically incomparable
    expect(page.locator("id=1_eq_4")).to_have_text("false")
    expect(page.locator("id=1_neq_4")).to_have_text("true")
    expect(page.locator("id=1_lt_4")).to_have_text("false")
    expect(page.locator("id=1_le_4")).to_have_text("false")
    expect(page.locator("id=1_gt_4")).to_have_text("false")
    expect(page.locator("id=1_ge_4")).to_have_text("false")

    # Check date values compare chronologically
    expect(page.locator("id=9_eq_10")).to_have_text("false")
    expect(page.locator("id=9_neq_10")).to_have_text("true")
    expect(page.locator("id=9_lt_10")).to_have_text("true")
    expect(page.locator("id=9_le_10")).to_have_text("true")

    # Check dates and naive datetimes are deterministically incomparable
    expect(page.locator("id=9_eq_1")).to_have_text("false")
    expect(page.locator("id=9_neq_1")).to_have_text("true")
    expect(page.locator("id=9_lt_1")).to_have_text("false")
    expect(page.locator("id=9_ge_1")).to_have_text("false")

    # Check unset optional datetimes do not crash the render
    expect(page.locator("id=u1_eq_1")).to_have_text("false")
    expect(page.locator("id=u1_neq_1")).to_have_text("true")
    expect(page.locator("id=u1_lt_1")).to_have_text("false")
    expect(page.locator("id=u1_le_1")).to_have_text("false")
    expect(page.locator("id=u1_gt_1")).to_have_text("false")
    expect(page.locator("id=u1_ge_1")).to_have_text("false")
    expect(page.locator("id=u1_eq_u2")).to_have_text("true")
    expect(page.locator("id=u1_neq_u2")).to_have_text("false")
