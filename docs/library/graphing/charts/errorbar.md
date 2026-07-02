---
components:
  - rx.recharts.ErrorBar
title: Error Bar
meta_description: "Add error bars to your charts in Python with Reflex. Use Recharts error bars to visualize uncertainty and variance on scatter and line charts — all in pure Python, no JavaScript."
---

```python exec
import reflex as rx
```

# Error Bar

Error bars in Reflex are built on [Recharts](https://recharts.org/), a React charting library, and created in pure Python. An error bar is a graphical representation of the uncertainty or variability of a data point in a chart, depicted as a line extending from the data point parallel to one of the axes. The `data_key`, `width`, `stroke_width`, `stroke`, and `direction` props can be used to customize the appearance and behavior of the error bars, specifying the data source, dimensions, color, and orientation of the error bars.

```python demo graphing
data = [
    {"x": 45, "y": 100, "z": 150, "errorY": [30, 20], "errorX": 5},
    {"x": 100, "y": 200, "z": 200, "errorY": [20, 30], "errorX": 3},
    {"x": 120, "y": 100, "z": 260, "errorY": 20, "errorX": [5, 3]},
    {"x": 170, "y": 300, "z": 400, "errorY": [15, 18], "errorX": 4},
    {"x": 140, "y": 250, "z": 280, "errorY": 23, "errorX": [6, 7]},
    {"x": 150, "y": 400, "z": 500, "errorY": [21, 10], "errorX": 4},
    {"x": 110, "y": 280, "z": 200, "errorY": 21, "errorX": [5, 6]},
]


def error():
    return rx.recharts.scatter_chart(
        rx.recharts.scatter(
            rx.recharts.error_bar(
                data_key="errorY", direction="y", width=4, stroke_width=2, stroke="red"
            ),
            rx.recharts.error_bar(
                data_key="errorX", direction="x", width=4, stroke_width=2
            ),
            data=data,
            fill="#8884d8",
            name="A",
        ),
        rx.recharts.x_axis(data_key="x", name="x", type_="number"),
        rx.recharts.y_axis(data_key="y", name="y", type_="number"),
        width="100%",
        height=300,
    )
```

## Symmetric and Asymmetric Errors

The `data_key` of an `rx.recharts.error_bar()` points at a field in each data row, and that field controls how far the whisker extends. Use a single number for a **symmetric** error — the same distance above and below the point — or a two-element `[low, high]` list for an **asymmetric** error. In the example above, some rows use `"errorY": 20` (symmetric) while others use `"errorY": [30, 20]` (asymmetric). The `direction` prop (`"x"` or `"y"`) chooses which axis the whisker runs along, so you can show error on one or both axes at once.

## Error Bars on a Line Chart

Error bars aren't limited to scatter charts. Add an `rx.recharts.error_bar()` as a child of an `rx.recharts.line()` to visualize variance or measurement uncertainty on a line chart — useful for time series such as average temperature or benchmark results.

```python demo graphing
data = [
    {"month": "Jan", "temp": 7, "error": [2, 3]},
    {"month": "Feb", "temp": 9, "error": 2},
    {"month": "Mar", "temp": 12, "error": [3, 2]},
    {"month": "Apr", "temp": 16, "error": 3},
    {"month": "May", "temp": 20, "error": [2, 4]},
    {"month": "Jun", "temp": 24, "error": 3},
]


def line_error():
    return rx.recharts.line_chart(
        rx.recharts.line(
            rx.recharts.error_bar(
                data_key="error",
                direction="y",
                width=4,
                stroke_width=2,
                stroke=rx.color("accent", 9),
            ),
            data_key="temp",
            stroke=rx.color("accent", 9),
        ),
        rx.recharts.x_axis(data_key="month"),
        rx.recharts.y_axis(),
        data=data,
        width="100%",
        height=300,
    )
```

## Related Charts

Explore more chart types you can build with Reflex and Recharts in pure Python:

- [Scatter Chart](/docs/library/graphing/charts/scatterchart)
- [Line Chart](/docs/library/graphing/charts/linechart)
- [Bar Chart](/docs/library/graphing/charts/barchart)
