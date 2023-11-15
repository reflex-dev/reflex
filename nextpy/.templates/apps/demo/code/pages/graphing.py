"""The dashboard page for the template."""
import nextpy as xt

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


graph_1_code = """xt.recharts.composed_chart(
    xt.recharts.area(
        data_key="uv", stroke="#8884d8", fill="#8884d8"
    ),
    xt.recharts.bar(
        data_key="amt", bar_size=20, fill="#413ea0"
    ),
    xt.recharts.line(
        data_key="pv", type_="monotone", stroke="#ff7300"
    ),
    xt.recharts.x_axis(data_key="name"),
    xt.recharts.y_axis(),
    xt.recharts.cartesian_grid(stroke_dasharray="3 3"),
    xt.recharts.graphing_tooltip(),
    data=data,
)"""


graph_2_code = """xt.recharts.pie_chart(
    xt.recharts.pie(
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
    xt.recharts.graphing_tooltip(),
),
xt.vstack(
    xt.foreach(
        PieChartState.resource_types,
        lambda type_, i: xt.hstack(
            xt.button(
                "-",
                on_click=PieChartState.decrement(type_),
            ),
            xt.text(
                type_,
                PieChartState.resources[i]["count"],
            ),
            xt.button(
                "+",
                on_click=PieChartState.increment(type_),
            ),
        ),
    ),
)"""

graph_2_state = """class PieChartState(xt.State):
    resources: list[dict[str, Any]] = [
        dict(type_="🏆", count=1),
        dict(type_="🪵", count=1),
        dict(type_="🥑", count=1),
        dict(type_="🧱", count=1),
    ]

    @xt.cached_var
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


def graphing_page() -> xt.Component:
    """The UI for the dashboard page.

    Returns:
        xt.Component: The UI for the dashboard page.
    """
    return xt.box(
        xt.vstack(
            xt.heading(
                "Graphing Demo",
                font_size="3em",
            ),
            xt.heading(
                "Composed Chart",
                font_size="2em",
            ),
            xt.stack(
                xt.recharts.composed_chart(
                    xt.recharts.area(data_key="uv", stroke="#8884d8", fill="#8884d8"),
                    xt.recharts.bar(data_key="amt", bar_size=20, fill="#413ea0"),
                    xt.recharts.line(data_key="pv", type_="monotone", stroke="#ff7300"),
                    xt.recharts.x_axis(data_key="name"),
                    xt.recharts.y_axis(),
                    xt.recharts.cartesian_grid(stroke_dasharray="3 3"),
                    xt.recharts.graphing_tooltip(),
                    data=data_1,
                    # height="15em",
                ),
                width="100%",
                height="20em",
            ),
            xt.tabs(
                xt.tab_list(
                    xt.tab("Code", style=tab_style),
                    xt.tab("Data", style=tab_style),
                    padding_x=0,
                ),
                xt.tab_panels(
                    xt.tab_panel(
                        xt.code_block(
                            graph_1_code,
                            language="python",
                            show_line_numbers=True,
                        ),
                        width="100%",
                        padding_x=0,
                        padding_y=".25em",
                    ),
                    xt.tab_panel(
                        xt.code_block(
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
            xt.heading("Interactive Example", font_size="2em"),
            xt.hstack(
                xt.recharts.pie_chart(
                    xt.recharts.pie(
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
                    xt.recharts.graphing_tooltip(),
                ),
                xt.vstack(
                    xt.foreach(
                        PieChartState.resource_types,
                        lambda type_, i: xt.hstack(
                            xt.button(
                                "-",
                                on_click=PieChartState.decrement(type_),
                            ),
                            xt.text(
                                type_,
                                PieChartState.resources[i]["count"],
                            ),
                            xt.button(
                                "+",
                                on_click=PieChartState.increment(type_),
                            ),
                        ),
                    ),
                ),
                width="100%",
                height="15em",
            ),
            xt.tabs(
                xt.tab_list(
                    xt.tab("Code", style=tab_style),
                    xt.tab("State", style=tab_style),
                    padding_x=0,
                ),
                xt.tab_panels(
                    xt.tab_panel(
                        xt.code_block(
                            graph_2_code,
                            language="python",
                            show_line_numbers=True,
                        ),
                        width="100%",
                        padding_x=0,
                        padding_y=".25em",
                    ),
                    xt.tab_panel(
                        xt.code_block(
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
