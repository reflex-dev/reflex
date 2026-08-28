"""Mantine Dates Demo"""

import reflex as rx

import reflex_enterprise as rxe

from .common import demo


class DateState(rx.State):
    """State for the Dates demo."""

    # Define any state variables you need here
    date: str = ""


# @rx.memo
def picker_grid():
    return rx.grid(
        rx.card(
            rx.text("Calendar"),
            rxe.mantine.dates.calendar(),
        ),
        rx.card(
            rx.text("DateTimePicker"),
            rxe.mantine.dates.date_time_picker(
                label="Pick a Date",
                placeholder="Pick date",
                on_change=lambda value: rx.toast(f"Date selected: {value}"),
            ),
        ),
        rx.card(
            rx.text("DatePicker"),
            rxe.mantine.dates.date_picker(
                on_change=lambda value: rx.toast(f"Date selected: {value}"),
            ),
        ),
        rx.card(
            rx.text("DatePickerInput"),
            rxe.mantine.dates.date_picker_input(
                label="Pick a Date",
                placeholder="Pick date",
                # value=DateState.date,
                on_change=lambda value: rx.toast(f"Date selected: {value}"),
            ),
        ),
        rx.card(
            rx.text("DateInput"),
            rxe.mantine.dates.date_input(),
        ),
        rx.card(
            rx.text("MonthPicker"),
            rxe.mantine.dates.month_picker(
                on_change=lambda value: rx.toast(f"Month selected: {value}"),
            ),
        ),
        rx.card(
            rx.text("MonthPickerInput"),
            rxe.mantine.dates.month_picker_input(
                on_change=lambda value: rx.toast(f"Month selected: {value}"),
            ),
        ),
        rx.card(
            rx.text("YearPicker"),
            rxe.mantine.dates.year_picker(
                on_change=lambda value: rx.toast(f"Year selected: {value}"),
            ),
        ),
        rx.card(
            rx.text("YearPickerInput"),
            rxe.mantine.dates.year_picker_input(
                on_change=lambda value: rx.toast(f"Year selected: {value}"),
            ),
        ),
        rx.card(
            rx.text("TimeInput"),
            rxe.mantine.dates.time_input(
                on_change=lambda value: rx.toast(f"Time selected: {value}"),
            ),
        ),
        rx.card(
            rx.text("TimePicker"),
            rxe.mantine.dates.time_picker(
                on_change=lambda value: rx.toast(f"Time selected: {value}"),
            ),
        ),
        rx.card(
            rx.text("DatePicker w/ presets"),
            rxe.mantine.dates.date_picker(
                on_change=lambda value: rx.toast(f"Date selected: {value}"),
                presets=[
                    {
                        "value": rx.Var(
                            "dayjs().subtract(1, 'day').format('YYYY-MM-DD')"
                        ),
                        "label": "Yesterday",
                    },
                    {"value": rx.Var("dayjs().format('YYYY-MM-DD')"), "label": "Today"},
                    {
                        "value": rx.Var("dayjs().add(1, 'day').format('YYYY-MM-DD')"),
                        "label": "Tomorrow",
                    },
                    {
                        "value": rx.Var("dayjs().add(1, 'month').format('YYYY-MM-DD')"),
                        "label": "Next month",
                    },
                    {
                        "value": rx.Var("dayjs().add(1, 'year').format('YYYY-MM-DD')"),
                        "label": "Next year",
                    },
                    {
                        "value": rx.Var(
                            "dayjs().subtract(1, 'month').format('YYYY-MM-DD')"
                        ),
                        "label": "Last month",
                    },
                    {
                        "value": rx.Var(
                            "dayjs().subtract(1, 'year').format('YYYY-MM-DD')"
                        ),
                        "label": "Last year",
                    },
                ],
            ),
        ),
        # rx.text("TimeGrid"),
        # rxe.mantine.dates.time_grid(),
        # rx.text("TimeValue"),
        # rxe.mantine.dates.time_value(),
        columns="3",
    )


@demo(
    route="/dates",
    title="Dates",
    description="A collection of examples using Mantine Dates components in Reflex.",
)
def dates_page():
    return picker_grid()
