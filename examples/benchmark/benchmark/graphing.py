import reflex as rx

from .styles import c


def lighthouse_graph(data, State):
    return rx.vstack(
        rx.recharts.area_chart(
            rx.recharts.area(
                data_key="performance_score",
                type_="monotone",
                stroke=c["indigo"][400],
                fill=c["indigo"][200],
            ),
            rx.recharts.x_axis(data_key="time"),
            rx.recharts.y_axis(),
            rx.recharts.legend(),
            rx.recharts.graphing_tooltip(),
            rx.recharts.brush(data_key="time", height=30, stroke="#8884d8"),
            data=data,
            width="100%",
        ),
        rx.recharts.bar_chart(
            rx.recharts.bar(
                data_key="accessibility_score",
                type_="monotone",
                stroke=c["green"][500],
                fill=c["green"][400],
            ),
            rx.recharts.bar(
                data_key="best_practices_score",
                type_="monotone",
                stroke=c["orange"][300],
                fill=c["orange"][200],
            ),
            rx.recharts.bar(
                data_key="seo_score",
                type_="monotone",
                stroke=c["blue"][300],
                fill=c["blue"][200],
            ),
            rx.recharts.bar(
                data_key="pwa_score",
                type_="monotone",
                stroke=c["violet"][400],
                fill=c["violet"][200],
            ),
            rx.recharts.x_axis(data_key="time"),
            rx.recharts.y_axis(),
            rx.recharts.legend(),
            rx.recharts.brush(data_key="time", height=30, stroke="#8884d8"),
            data=data,
            width="100%",
        ),
        width="100%",
        height="40em",
        box_shadow="0px 2px 3px 0px rgba(3, 3, 11, 0.04), 0px 1px 2px 0px rgba(84, 82, 95, 0.12), 0px 0px 0px 1px rgba(84, 82, 95, 0.18), 0px 1px 0px 0px rgba(255, 255, 255, 0.10) inset;",
        padding="1em",
        border_radius="8px",
        align_items="left"
    )


def performance_graph(data):
    return rx.vstack(
        rx.recharts.composed_chart(
            rx.recharts.line(
                data_key="max",
                type_="monotone",
                stroke=c["red"][400],
            ),
            rx.recharts.line(
                data_key="min",
                type_="monotone",
                stroke=c["green"][300],
            ),
            rx.recharts.line(
                data_key="mean",
                type_="monotone",
                stroke=c["blue"][300],
            ),
            rx.recharts.x_axis(data_key="time"),
            rx.recharts.y_axis(),
            rx.recharts.legend(),
            rx.recharts.graphing_tooltip(),
            rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
            rx.recharts.brush(data_key="time", height=30, stroke="#8884d8"),
            data=data,
            width="100%",
        ),
        height="20em",
        box_shadow="0px 2px 3px 0px rgba(3, 3, 11, 0.04), 0px 1px 2px 0px rgba(84, 82, 95, 0.12), 0px 0px 0px 1px rgba(84, 82, 95, 0.18), 0px 1px 0px 0px rgba(255, 255, 255, 0.10) inset;",
        padding="1em",
        border_radius="8px",
    )
