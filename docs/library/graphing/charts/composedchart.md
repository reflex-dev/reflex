---
components:
  - rx.recharts.ComposedChart
title: Composed Chart
meta_description: "Build composed charts in Python with Reflex. Combine bars, lines, and areas in a single Recharts composed chart with shared axes, tooltips, and legends — all in pure Python."
---

```python exec
import reflex as rx
```

# Composed Chart

Composed charts in Reflex are built on [Recharts](https://recharts.org/), a React charting library, and created in pure Python. A `composed_chart` (also called a combo chart) is a higher-level component chart that is composed of multiple charts, where other charts are the children of the `composed_chart`. The charts are placed on top of each other in the order they are provided in the `composed_chart` function.

```md alert info
# To learn more about individual charts, checkout: **[area_chart](/docs/library/graphing/charts/areachart)**, **[line_chart](/docs/library/graphing/charts/linechart)**, or **[bar_chart](/docs/library/graphing/charts/barchart)**.
```

```python demo graphing
data = [
    {"name": "Page A", "uv": 4000, "pv": 2400, "amt": 2400},
    {"name": "Page B", "uv": 3000, "pv": 1398, "amt": 2210},
    {"name": "Page C", "uv": 2000, "pv": 9800, "amt": 2290},
    {"name": "Page D", "uv": 2780, "pv": 3908, "amt": 2000},
    {"name": "Page E", "uv": 1890, "pv": 4800, "amt": 2181},
    {"name": "Page F", "uv": 2390, "pv": 3800, "amt": 2500},
    {"name": "Page G", "uv": 3490, "pv": 4300, "amt": 2100},
]


def composed():
    return rx.recharts.composed_chart(
        rx.recharts.area(data_key="uv", stroke="#8884d8", fill="#8884d8"),
        rx.recharts.bar(data_key="amt", bar_size=20, fill="#413ea0"),
        rx.recharts.line(data_key="pv", type_="monotone", stroke="#ff7300"),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(),
        rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
        rx.recharts.graphing_tooltip(),
        data=data,
        height=250,
        width="100%",
    )
```

## When to Use a Composed Chart

A composed chart is useful whenever a single chart type can't tell the whole story. Common combinations include overlaying a trend `line` on top of `bar` totals, drawing an `area` for a range with a `line` for the actual value, or comparing a cumulative measure against a per-period one. Because each series — `rx.recharts.bar()`, `rx.recharts.line()`, and `rx.recharts.area()` — is a child of `rx.recharts.composed_chart()`, they all share the same `data`, x-axis, tooltip, and legend. Series are drawn in the order you list them, so later children render on top of earlier ones.

## Composed Chart with a Dual Axis

When two series use very different scales (for example, a count and a dollar amount), a single y-axis makes the smaller series unreadable. Add a second y-axis and point each series at one with the `y_axis_id` prop: here the `orders` bars use the left axis and the `revenue` line uses the right axis.

```python demo graphing
data = [
    {"name": "Mon", "orders": 40, "revenue": 2400},
    {"name": "Tue", "orders": 30, "revenue": 1398},
    {"name": "Wed", "orders": 55, "revenue": 9800},
    {"name": "Thu", "orders": 27, "revenue": 3908},
    {"name": "Fri", "orders": 62, "revenue": 4800},
    {"name": "Sat", "orders": 48, "revenue": 3800},
    {"name": "Sun", "orders": 35, "revenue": 4300},
]


def composed_dual_axis():
    return rx.recharts.composed_chart(
        rx.recharts.bar(
            data_key="orders",
            bar_size=20,
            fill=rx.color("accent", 8),
            y_axis_id="left",
        ),
        rx.recharts.line(
            data_key="revenue",
            type_="monotone",
            stroke=rx.color("green", 9),
            y_axis_id="right",
        ),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(y_axis_id="left"),
        rx.recharts.y_axis(y_axis_id="right", orientation="right"),
        rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
        rx.recharts.graphing_tooltip(),
        rx.recharts.legend(),
        data=data,
        height=300,
        width="100%",
    )
```

## Related Charts

Explore more chart types you can build with Reflex and Recharts in pure Python:

- [Bar Chart](/docs/library/graphing/charts/barchart)
- [Line Chart](/docs/library/graphing/charts/linechart)
- [Area Chart](/docs/library/graphing/charts/areachart)
