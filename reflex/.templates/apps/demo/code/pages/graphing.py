"""The dashboard page for the template."""
import reflex as rx

from ..states.pie_state import PieChartState
from ..styles import *

data_1 = [
    {"name": "Page A", "uv": 4000, "pv": 2400, "amt": 2400},
    {"name": "Page B", "uv": 3000, "pv": 1398, "amt": 2210},
    {"name": "Page C", "uv": 2000, "pv": 9800, "amt": 2290},
    {"name": "Page D", "uv": 2780, "pv": 3908, "amt": 2000},
    {"name": "Page E", "uv": 1890, "pv": 4800, "amt": 2181},
    {"name": "Page F", "uv": 2390, "pv": 3800, "amt": 2500},
    {"name": "Page G", "uv": 3490, "pv": 4300, "amt": 2100},
]
data_1_show = """[
    {"name": "Page A", "uv": 4000, "pv": 2400, "amt": 2400},
    {"name": "Page B", "uv": 3000, "pv": 1398, "amt": 2210},
    {"name": "Page C", "uv": 2000, "pv": 9800, "amt": 2290},
    {"name": "Page D", "uv": 2780, "pv": 3908, "amt": 2000},
    {"name": "Page E", "uv": 1890, "pv": 4800, "amt": 2181},
    {"name": "Page F", "uv": 2390, "pv": 3800, "amt": 2500},
    {"name": "Page G", "uv": 3490, "pv": 4300, "amt": 2100},
]"""


graph_1_code = """rx.recharts.composed_chart(
    rx.recharts.area(
        data_key="uv", stroke="#8884d8", fill="#8884d8"
    ),
    rx.recharts.bar(
        data_key="amt", bar_size=20, fill="#413ea0"
    ),
    rx.recharts.line(
        data_key="pv", type_="monotone", stroke="#ff7300"
    ),
    rx.recharts.x_axis(data_key="name"),
    rx.recharts.y_axis(),
    rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
    rx.recharts.graphing_tooltip(),
    data=data,
)"""


graph_2_code = """rx.recharts.pie_chart(
    rx.recharts.pie(
        data=PieChartState.resources,
        data_key="count",
        name_key="type_",
        cx="50%",
        cy="50%",
        start_angle=180,
        end_angle=0,
        fill="#8884d8",
        label=True,
    ),
    rx.recharts.graphing_tooltip(),
),
rx.chakra.vstack(
    rx.foreach(
        PieChartState.resource_types,
        lambda type_, i: rx.chakra.hstack(
            rx.chakra.button(
                "-",
                on_click=PieChartState.decrement(type_),
            ),
            rx.chakra.text(
                type_,
                PieChartState.resources[i]["count"],
            ),
            rx.chakra.button(
                "+",
                on_click=PieChartState.increment(type_),
            ),
        ),
    ),
)"""

graph_2_state = """class PieChartState(rx.State):
    resources: list[dict[str, Any]] = [
        dict(type_="🏆", count=1),
        dict(type_="🪵", count=1),
        dict(type_="🥑", count=1),
        dict(type_="🧱", count=1),
    ]

    @rx.cached_var
    def resource_types(self) -> list[str]:
        return [r["type_"] for r in self.resources]

    def increment(self, type_: str):
        for resource in self.resources:
            if resource["type_"] == type_:
                resource["count"] += 1
                break

    def decrement(self, type_: str):
        for resource in self.resources:
            if (
                resource["type_"] == type_
                and resource["count"] > 0
            ):
                resource["count"] -= 1
                break
"""


def graphing_page() -> rx.Component:
    """The UI for the dashboard page.

    Returns:
        rx.Component: The UI for the dashboard page.
    """
    return rx.chakra.box(
        rx.chakra.vstack(
            rx.chakra.heading(
                "Graphing Demo",
                font_size="3em",
            ),
            rx.chakra.heading(
                "Composed Chart",
                font_size="2em",
            ),
            rx.chakra.stack(
                rx.recharts.composed_chart(
                    rx.recharts.area(data_key="uv", stroke="#8884d8", fill="#8884d8"),
                    rx.recharts.bar(data_key="amt", bar_size=20, fill="#413ea0"),
                    rx.recharts.line(data_key="pv", type_="monotone", stroke="#ff7300"),
                    rx.recharts.x_axis(data_key="name"),
                    rx.recharts.y_axis(),
                    rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
                    rx.recharts.graphing_tooltip(),
                    data=data_1,
                    # height="15em",
                ),
                width="100%",
                height="20em",
            ),
            rx.chakra.tabs(
                rx.chakra.tab_list(
                    rx.chakra.tab("Code", style=tab_style),
                    rx.chakra.tab("Data", style=tab_style),
                    padding_x=0,
                ),
                rx.chakra.tab_panels(
                    rx.chakra.tab_panel(
                        rx.code_block(
                            graph_1_code,
                            language="python",
                            show_line_numbers=True,
                        ),
                        width="100%",
                        padding_x=0,
                        padding_y=".25em",
                    ),
                    rx.chakra.tab_panel(
                        rx.code_block(
                            data_1_show,
                            language="python",
                            show_line_numbers=True,
                        ),
                        width="100%",
                        padding_x=0,
                        padding_y=".25em",
                    ),
                    width="100%",
                ),
                variant="unstyled",
                color_scheme="purple",
                align="end",
                width="100%",
                padding_top=".5em",
            ),
            rx.chakra.heading("Interactive Example", font_size="2em"),
            rx.chakra.hstack(
                rx.recharts.pie_chart(
                    rx.recharts.pie(
                        data=PieChartState.resources,
                        data_key="count",
                        name_key="type_",
                        cx="50%",
                        cy="50%",
                        start_angle=180,
                        end_angle=0,
                        fill="#8884d8",
                        label=True,
                    ),
                    rx.recharts.graphing_tooltip(),
                ),
                rx.chakra.vstack(
                    rx.foreach(
                        PieChartState.resource_types,
                        lambda type_, i: rx.chakra.hstack(
                            rx.chakra.button(
                                "-",
                                on_click=PieChartState.decrement(type_),
                            ),
                            rx.chakra.text(
                                type_,
                                PieChartState.resources[i]["count"],
                            ),
                            rx.chakra.button(
                                "+",
                                on_click=PieChartState.increment(type_),
                            ),
                        ),
                    ),
                ),
                width="100%",
                height="15em",
            ),
            rx.chakra.tabs(
                rx.chakra.tab_list(
                    rx.chakra.tab("Code", style=tab_style),
                    rx.chakra.tab("State", style=tab_style),
                    padding_x=0,
                ),
                rx.chakra.tab_panels(
                    rx.chakra.tab_panel(
                        rx.code_block(
                            graph_2_code,
                            language="python",
                            show_line_numbers=True,
                        ),
                        width="100%",
                        padding_x=0,
                        padding_y=".25em",
                    ),
                    rx.chakra.tab_panel(
                        rx.code_block(
                            graph_2_state,
                            language="python",
                            show_line_numbers=True,
                        ),
                        width="100%",
                        padding_x=0,
                        padding_y=".25em",
                    ),
                    width="100%",
                ),
                variant="unstyled",
                color_scheme="purple",
                align="end",
                width="100%",
                padding_top=".5em",
            ),
            style=template_content_style,
            min_h="100vh",
        ),
        style=template_page_style,
        min_h="100vh",
    )
