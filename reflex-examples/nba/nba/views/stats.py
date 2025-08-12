import reflex as rx
from .table import State
from .table import college


def selection():
    return rx.flex(
        rx.vstack(
            rx.hstack(
                rx.icon("person-standing", size=24),
                rx.select(
                    ["All", "C", "PF", "SF", "PG", "SG"],
                    placeholder="Select a position.",
                    default="All",
                    on_change=State.set_position,
                    size="3",
                    variant="soft",
                ),
                justify="end",
                spacing="2",
                align="center",
                width="100%",
            ),
            rx.vstack(
                rx.slider(
                    default_value=[18, 50],
                    min=18,
                    variant="soft",
                    max=50,
                    on_value_commit=State.set_age,
                ),
                rx.hstack(
                    rx.badge("Min Age: ", State.age[0]),
                    rx.spacer(),
                    rx.badge("Max Age: ", State.age[1]),
                    width="100%",
                ),
                width="100%",
            ),
            width="100%",
            spacing="4",
        ),
        rx.spacer(),
        rx.vstack(
            rx.hstack(
                rx.icon("university", size=24),
                rx.select(
                    college,
                    placeholder="Select a college.",
                    default="All",
                    variant="soft",
                    on_change=State.set_college,
                    size="3",
                ),
                justify="end",
                spacing="2",
                align="center",
                width="100%",
            ),
            rx.vstack(
                rx.slider(
                    default_value=[0, 25000000],
                    min=0,
                    max=25000000,
                    variant="soft",
                    on_value_commit=State.set_salary,
                ),
                rx.hstack(
                    rx.badge("Min Sal: ", State.salary[0] // 1000000, "M"),
                    rx.spacer(),
                    rx.badge("Max Sal: ", State.salary[1] // 1000000, "M"),
                    width="100%",
                ),
                width="100%",
                spacing="4",
            ),
            width="100%",
            spacing="4",
        ),
        flex_direction=["column", "column", "row"],
        spacing="4",
        width="100%",
    )


def stats():
    return rx.vstack(
        selection(),
        rx.divider(),
        rx.box(
            rx.plotly(data=State.scat_fig, width="100%", use_resize_handler=True),
            rx.plotly(data=State.hist_fig, width="100%", use_resize_handler=True),
            width="100%",
        ),
        width=["100%", "100%", "100%", "50%"],
        spacing="4",
    )
