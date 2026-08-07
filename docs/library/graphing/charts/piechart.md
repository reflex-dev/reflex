---
components:
  - rx.recharts.PieChart
  - rx.recharts.Pie
title: Pie Chart
meta_description: "Build interactive pie and donut charts in Python with Reflex. Create Recharts pie charts with custom colors, labels, legends, and tooltips — all in pure Python, no JavaScript required."
---

# Pie Chart

```python exec
import reflex as rx
```

Pie charts in Reflex are built on [Recharts](https://recharts.org/), a React charting library, and created in pure Python. A pie chart — or a donut chart when the center is hollow — is a circular statistical graphic which is divided into slices to illustrate numerical proportion.

For a pie chart we must define an `rx.recharts.pie()` component for each set of values we wish to plot. Each `rx.recharts.pie()` component has a `data`, a `data_key` and a `name_key` which clearly states which data and which variables in our data we are tracking. In this simple example we plot `value` column as our `data_key` against the `name` column which we set as our `name_key`.
We also use the `fill` prop to set the color of the pie slices.

```python demo graphing
data01 = [
    {"name": "Group A", "value": 400},
    {"name": "Group B", "value": 300, "fill": "#AC0E08FF"},
    {"name": "Group C", "value": 300, "fill": "rgb(80,40, 190)"},
    {"name": "Group D", "value": 200, "fill": rx.color("yellow", 10)},
    {"name": "Group E", "value": 278, "fill": "purple"},
    {"name": "Group F", "value": 189, "fill": "orange"},
]


def pie_simple():
    return rx.recharts.pie_chart(
        rx.recharts.pie(
            data=data01,
            data_key="value",
            name_key="name",
            fill="#8884d8",
            label=True,
        ),
        width="100%",
        height=300,
    )
```

We can also add two pies on one chart by using two `rx.recharts.pie` components.

In this example `inner_radius` and `outer_radius` props are used. They define the doughnut shape of a pie chart: `inner_radius` creates the hollow center (use "0%" for a full pie), while `outer_radius` sets the overall size. The `padding_angle` prop, used on the green pie below, adds space between pie slices, enhancing visibility of individual segments.

```python demo graphing
data01 = [
    {"name": "Group A", "value": 400},
    {"name": "Group B", "value": 300},
    {"name": "Group C", "value": 300},
    {"name": "Group D", "value": 200},
    {"name": "Group E", "value": 278},
    {"name": "Group F", "value": 189},
]
data02 = [
    {"name": "Group A", "value": 2400},
    {"name": "Group B", "value": 4567},
    {"name": "Group C", "value": 1398},
    {"name": "Group D", "value": 9800},
    {"name": "Group E", "value": 3908},
    {"name": "Group F", "value": 4800},
]


def pie_double():
    return rx.recharts.pie_chart(
        rx.recharts.pie(
            data=data01,
            data_key="value",
            name_key="name",
            fill="#82ca9d",
            inner_radius="60%",
            padding_angle=5,
        ),
        rx.recharts.pie(
            data=data02,
            data_key="value",
            name_key="name",
            fill="#8884d8",
            outer_radius="50%",
        ),
        rx.recharts.graphing_tooltip(),
        width="100%",
        height=300,
    )
```

## Coloring Slices Individually

Instead of storing a `fill` color in every data entry, you can pass `rx.recharts.cell` components as children of `rx.recharts.pie` — one cell per slice. Using `rx.foreach` with the index argument lets you cycle through a color palette, so the palette lives in one place and works for any number of slices. This example also combines `inner_radius` and `padding_angle` to render the pie as a donut, and uses `stroke` with `custom_attrs={"strokeWidth": 2}` to draw a separator around each slice. (Passing `stroke_width` directly is not forwarded to the underlying SVG element, so the width goes through `custom_attrs`.)

```python demo graphing
data = [
    {"browser": "Chrome", "visitors": 275},
    {"browser": "Firefox", "visitors": 150},
    {"browser": "Safari", "visitors": 100},
    {"browser": "Opera", "visitors": 130},
    {"browser": "Edge", "visitors": 140},
]

colors = ["#6366F1", "#8B5CF6", "#A855F7", "#D946EF", "#EC4899"]


def pie_cells():
    return rx.recharts.pie_chart(
        rx.recharts.pie(
            rx.foreach(
                data,
                lambda item, index: rx.recharts.cell(
                    fill=rx.Var.create(colors)[index % len(colors)],
                ),
            ),
            data=data,
            data_key="visitors",
            name_key="browser",
            inner_radius="40%",
            outer_radius="80%",
            padding_angle=2,
            stroke="#fff",
            custom_attrs={"strokeWidth": 2},
        ),
        rx.recharts.graphing_tooltip(),
        width="100%",
        height=300,
    )
```

## Gradient Fills

Slices can also be filled with SVG gradients. Define the gradients inside a hidden `rx.el.svg` element, then reference each one from a cell's `fill` prop with `url(#gradient_id)`. A radial gradient works well for pie slices since it follows the circular shape.

```python demo graphing
data = [
    {"name": "Product A", "value": 400},
    {"name": "Product B", "value": 300},
    {"name": "Product C", "value": 300},
    {"name": "Product D", "value": 200},
]

gradients = [
    ("#6366F1", "pie_grad_a"),
    ("#8B5CF6", "pie_grad_b"),
    ("#EC4899", "pie_grad_c"),
    ("#F59E0B", "pie_grad_d"),
]


def create_gradient(color: str, gradient_id: str) -> rx.Component:
    return rx.el.svg.radial_gradient(
        rx.el.svg.stop(offset="10%", stop_color=color, stop_opacity=1),
        rx.el.svg.stop(offset="95%", stop_color=color, stop_opacity=0.6),
        id=gradient_id,
        cx="50%",
        cy="50%",
        r="50%",
        fx="50%",
        fy="50%",
    )


def pie_gradient():
    return rx.box(
        rx.el.svg(
            rx.el.svg.defs(
                *[
                    create_gradient(color, gradient_id)
                    for color, gradient_id in gradients
                ],
            ),
            width=0,
            height=0,
        ),
        rx.recharts.pie_chart(
            rx.recharts.pie(
                *[
                    rx.recharts.cell(fill=f"url(#{gradient_id})")
                    for _, gradient_id in gradients
                ],
                data=data,
                data_key="value",
                name_key="name",
                inner_radius="60%",
                outer_radius="80%",
                padding_angle=5,
                stroke="#fff",
                custom_attrs={"strokeWidth": 2},
            ),
            rx.recharts.graphing_tooltip(),
            width="100%",
            height=300,
        ),
        width="100%",
    )
```

## Dynamic Data

Chart data tied to a State var causes the chart to automatically update when the
state changes, providing a nice way to visualize data in response to user
interface elements. View the "Data" tab to see the substate driving this
half-pie chart.

```python demo exec
from typing import Any


class PieChartState(rx.State):
    resources: list[dict[str, Any]] = [
        dict(type_="🏆", count=1),
        dict(type_="🪵", count=1),
        dict(type_="🥑", count=1),
        dict(type_="🧱", count=1),
    ]

    @rx.var(cache=True)
    def resource_types(self) -> list[str]:
        return [r["type_"] for r in self.resources]

    @rx.event
    def increment(self, type_: str):
        for resource in self.resources:
            if resource["type_"] == type_:
                resource["count"] += 1
                break

    @rx.event
    def decrement(self, type_: str):
        for resource in self.resources:
            if resource["type_"] == type_ and resource["count"] > 0:
                resource["count"] -= 1
                break


def dynamic_pie_example():
    return rx.hstack(
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
        rx.vstack(
            rx.foreach(
                PieChartState.resource_types,
                lambda type_, i: rx.hstack(
                    rx.button("-", on_click=PieChartState.decrement(type_)),
                    rx.text(type_, PieChartState.resources[i]["count"]),
                    rx.button("+", on_click=PieChartState.increment(type_)),
                ),
            ),
        ),
        width="100%",
        height="15em",
    )
```

## Hover Events

Charts can react to the mouse with `on_mouse_enter` and `on_mouse_leave`. Like click events, these are best attached to `rx.recharts.cell` components rendered with `rx.foreach`, so each handler is bound to the index of its data point at render time and the event handler can look up the hovered item in state.

This example shows the hovered slice's name and value in the center of a donut chart, and clears them when the mouse leaves.

```python demo exec
PIE_HOVER_COLORS = ["#2B79D1", "#2469B3", "#1E5AA1", "#3D8EE1", "#61A9E4"]


class PieHoverState(rx.State):
    languages: list[dict[str, str | int]] = [
        {"name": "Python", "value": 35},
        {"name": "JavaScript", "value": 25},
        {"name": "Java", "value": 20},
        {"name": "C++", "value": 15},
        {"name": "Ruby", "value": 5},
    ]

    hovered_name: str = ""
    hovered_value: int = 0

    @rx.event
    def handle_mouse_enter(self, index: int):
        self.hovered_name = str(self.languages[index]["name"])
        self.hovered_value = int(self.languages[index]["value"])

    @rx.event
    def handle_mouse_leave(self):
        self.hovered_name, self.hovered_value = "", 0


def pie_hover():
    return rx.box(
        rx.vstack(
            rx.cond(
                PieHoverState.hovered_name != "",
                rx.fragment(
                    rx.heading(PieHoverState.hovered_value, size="8"),
                    rx.text(PieHoverState.hovered_name, size="2"),
                ),
                rx.text("Hover a slice", size="2", color_scheme="gray"),
            ),
            align="center",
            spacing="1",
            position="absolute",
            top="50%",
            left="50%",
            transform="translate(-50%, -50%)",
        ),
        rx.recharts.pie_chart(
            rx.recharts.pie(
                rx.foreach(
                    PieHoverState.languages,
                    lambda item, index: rx.recharts.cell(
                        fill=rx.Var.create(PIE_HOVER_COLORS)[
                            index % len(PIE_HOVER_COLORS)
                        ],
                        on_mouse_enter=PieHoverState.handle_mouse_enter(index),
                        on_mouse_leave=PieHoverState.handle_mouse_leave,
                    ),
                ),
                data=PieHoverState.languages,
                data_key="value",
                name_key="name",
                inner_radius=90,
                stroke="0",
            ),
            width="100%",
            height=300,
        ),
        position="relative",
        width="100%",
    )
```

## Related Charts

Explore more chart types you can build with Reflex and Recharts in pure Python:

- [Radial Bar Chart](/docs/library/graphing/charts/radialbarchart)
- [Funnel Chart](/docs/library/graphing/charts/funnelchart)
- [Bar Chart](/docs/library/graphing/charts/barchart)
