"""rx.recharts exercised against recharts 3.10.1."""

import random

import reflex as rx


def _row(i: int) -> dict:
    return {
        "name": f"p{i}",
        "uv": random.randint(100, 900),
        "pv": random.randint(100, 900),
        "amt": random.randint(100, 900),
    }


class ChartState(rx.State):
    """State for the recharts page."""

    data: list[dict] = [
        {"name": "p0", "uv": 400, "pv": 240, "amt": 240},
        {"name": "p1", "uv": 300, "pv": 139, "amt": 221},
        {"name": "p2", "uv": 200, "pv": 980, "amt": 229},
        {"name": "p3", "uv": 278, "pv": 390, "amt": 200},
        {"name": "p4", "uv": 189, "pv": 480, "amt": 218},
    ]
    pie_data: list[dict] = [
        {"name": "alpha", "value": 400, "fill": "#8884d8"},
        {"name": "beta", "value": 300, "fill": "#82ca9d"},
        {"name": "gamma", "value": 300, "fill": "#ffc658"},
    ]
    counter: int = 0

    @rx.event
    def randomize(self):
        """Replace the dataset with new random values."""
        random.seed(self.counter)
        self.counter += 1
        self.data = [_row(i) for i in range(5)]

    @rx.event
    def add_point(self):
        """Append a point to the dataset."""
        self.data = [*self.data, _row(len(self.data))]

    @rx.event
    def bump_pie(self):
        """Change the pie slice values."""
        self.pie_data = [
            {**d, "value": d["value"] + 50 * (i + 1)} for i, d in enumerate(self.pie_data)
        ]


def recharts_page() -> rx.Component:
    """The recharts page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.heading("recharts 3.10.1", size="4"),
        rx.link("home", href="/"),
        rx.hstack(
            rx.button("randomize", on_click=ChartState.randomize, id="rc-random"),
            rx.button("add point", on_click=ChartState.add_point, id="rc-add"),
            rx.button("bump pie", on_click=ChartState.bump_pie, id="rc-pie-bump"),
        ),
        rx.text("line chart (responsive container, tooltip, legend, animation)"),
        rx.box(
            rx.recharts.line_chart(
                rx.recharts.line(data_key="uv", stroke="#8884d8", type_="monotone"),
                rx.recharts.line(data_key="pv", stroke="#82ca9d", type_="monotone"),
                rx.recharts.x_axis(data_key="name"),
                rx.recharts.y_axis(unit="u", tick_count=4),
                rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
                rx.recharts.graphing_tooltip(),
                rx.recharts.legend(),
                data=ChartState.data,
                width="100%",
                height=220,
            ),
            width="600px",
            id="rc-line",
        ),
        rx.text("bar chart"),
        rx.box(
            rx.recharts.bar_chart(
                rx.recharts.bar(data_key="uv", fill="#8884d8"),
                rx.recharts.bar(data_key="pv", fill="#82ca9d"),
                rx.recharts.x_axis(data_key="name"),
                rx.recharts.y_axis(
                    custom_attrs={"tickFormatter": rx.Var("((v) => `${v}k`)")},
                ),
                rx.recharts.graphing_tooltip(),
                rx.recharts.legend(),
                data=ChartState.data,
                width="100%",
                height=220,
            ),
            width="600px",
            id="rc-bar",
        ),
        rx.text("area chart"),
        rx.box(
            rx.recharts.area_chart(
                rx.recharts.area(
                    data_key="uv", stroke="#8884d8", fill="#8884d8", is_animation_active=False
                ),
                rx.recharts.x_axis(data_key="name"),
                rx.recharts.y_axis(),
                rx.recharts.graphing_tooltip(),
                data=ChartState.data,
                width="100%",
                height=200,
            ),
            width="600px",
            id="rc-area",
        ),
        rx.text("pie chart"),
        rx.box(
            rx.recharts.pie_chart(
                rx.recharts.pie(
                    data=ChartState.pie_data,
                    data_key="value",
                    name_key="name",
                    cx="50%",
                    cy="50%",
                    outer_radius=70,
                    label=True,
                ),
                rx.recharts.graphing_tooltip(),
                rx.recharts.legend(),
                width="100%",
                height=240,
            ),
            width="500px",
            id="rc-pie",
        ),
        rx.text("composed chart"),
        rx.box(
            rx.recharts.composed_chart(
                rx.recharts.area(data_key="uv", stroke="#8884d8", fill="#8884d8"),
                rx.recharts.bar(data_key="amt", bar_size=20, fill="#413ea0"),
                rx.recharts.line(data_key="pv", type_="monotone", stroke="#ff7300"),
                rx.recharts.x_axis(data_key="name"),
                rx.recharts.y_axis(),
                rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
                rx.recharts.graphing_tooltip(),
                rx.recharts.legend(),
                data=ChartState.data,
                width="100%",
                height=240,
            ),
            width="600px",
            id="rc-composed",
        ),
        spacing="2",
        padding="1em",
        align="start",
    )
