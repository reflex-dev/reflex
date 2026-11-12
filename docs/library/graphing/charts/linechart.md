---
components:
  - rx.recharts.LineChart
  - rx.recharts.Line
title: Line Chart
meta_description: "Build interactive line charts in pure Python with Reflex. Plot single or multi-line Recharts time series with custom axes, tooltips, legends, and styling — no JavaScript needed."
---

# Line Chart

```python exec
import random
from typing import Any
import reflex as rx
```

Line charts in Reflex are built on [Recharts](https://recharts.org/), a React charting library, and are created in pure Python. A line chart is a type of chart used to show information that changes over time. Line charts are created by plotting a series of several points and connecting them with a straight line.

## Simple Example

For a line chart we must define an `rx.recharts.line()` component for each set of values we wish to plot. Each `rx.recharts.line()` component has a `data_key` which clearly states which variable in our data we are tracking. In this simple example we plot `pv` and `uv` as separate lines against the `name` column which we set as the `data_key` in `rx.recharts.x_axis`. Plotting more than one line like this creates a multi-line chart.

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


def line_simple():
    return rx.recharts.line_chart(
        rx.recharts.line(
            data_key="pv",
        ),
        rx.recharts.line(
            data_key="uv",
        ),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(),
        data=data,
        width="100%",
        height=300,
    )
```

```python test
def test_line_chart_draws_pv_and_uv(demo):
    expect(demo.locator(".recharts-line")).to_have_count(2)
    expect(demo.locator(".recharts-xAxis-tick-labels text")).to_have_text([
        "Page A",
        "Page B",
        "Page C",
        "Page D",
        "Page E",
        "Page F",
        "Page G",
    ])
    expect(demo.locator(".recharts-yAxis-tick-labels text")).to_have_text([
        "0",
        "2500",
        "5000",
        "7500",
        "10000",
    ])
```

## Example with Props

Our second example uses exactly the same data as our first example, except now we add some extra features to our line graphs. We add a `type_` prop to `rx.recharts.line` to style the lines differently. In addition, we add an `rx.recharts.cartesian_grid` to get a grid in the background, an `rx.recharts.legend` to give us a legend for our graphs and an `rx.recharts.graphing_tooltip` to add a box with text that appears when you pause the mouse pointer on an element in the graph.

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


def line_features():
    return rx.recharts.line_chart(
        rx.recharts.line(
            data_key="pv",
            type_="monotone",
            stroke="#8884d8",
        ),
        rx.recharts.line(
            data_key="uv",
            type_="monotone",
            stroke="#82ca9d",
        ),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(),
        rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
        rx.recharts.graphing_tooltip(),
        rx.recharts.legend(),
        data=data,
        width="100%",
        height=300,
    )
```

```python test
def test_line_chart_tooltip_shows_hovered_values(demo):
    expect(demo.locator(".recharts-legend-item-text")).to_have_text(["pv", "uv"])
    demo.locator(".recharts-line-dot").nth(2).hover()
    tooltip = demo.locator(".recharts-default-tooltip")
    expect(tooltip.locator(".recharts-tooltip-label")).to_have_text("Page C")
    expect(tooltip.locator(".recharts-tooltip-item")).to_have_text([
        "pv : 9800",
        "uv : 2000",
    ])
```

## Axis Labels

Nest an `rx.recharts.label` inside `rx.recharts.x_axis` or `rx.recharts.y_axis` to title the axes. Use the `position` prop to place the label, and rotate the y-axis label with `custom_attrs={"angle": 270}`. Give the x-axis some extra `height` and the chart a left `margin` so the labels have room. The axes here also use `axis_line=False` and `tick_line=False` for a cleaner look.

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


def line_axis_labels():
    return rx.recharts.line_chart(
        rx.recharts.line(
            data_key="uv",
            stroke=rx.color("accent", 9),
            stroke_width=2,
            type_="natural",
        ),
        rx.recharts.x_axis(
            rx.recharts.label(value="Page", position="center"),
            data_key="name",
            height=60,
            axis_line=False,
            tick_line=False,
        ),
        rx.recharts.y_axis(
            rx.recharts.label(
                value="Visits",
                position="left",
                custom_attrs={"angle": 270},
            ),
            axis_line=False,
            tick_line=False,
        ),
        rx.recharts.graphing_tooltip(),
        data=data,
        margin={"left": 20, "right": 20, "top": 20},
        width="100%",
        height=300,
    )
```

```python test
def test_line_chart_axes_have_labels(demo):
    expect(demo.locator(".recharts-line")).to_have_count(1)
    expect(demo.locator(".recharts-label")).to_have_text(["Page", "Visits"])
```

## Layout

The `layout` prop allows you to set the orientation of the graph to be vertical or horizontal. The `margin` prop defines the spacing around the graph,

```md alert info
# Include margins around your graph to ensure proper spacing and enhance readability. By default, provide margins on all sides of the chart to create a visually appealing and functional representation of your data.
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


def line_vertical():
    return rx.recharts.line_chart(
        rx.recharts.line(
            data_key="pv",
            stroke=rx.color("accent", 9),
        ),
        rx.recharts.line(
            data_key="uv",
            stroke=rx.color("green", 9),
        ),
        rx.recharts.x_axis(type_="number"),
        rx.recharts.y_axis(data_key="name", type_="category"),
        layout="vertical",
        margin={"top": 20, "right": 20, "left": 20, "bottom": 20},
        data=data,
        height=300,
        width="100%",
    )
```

```python test
def test_vertical_line_chart_lists_pages_on_y_axis(demo):
    expect(demo.locator(".recharts-line")).to_have_count(2)
    expect(demo.locator(".recharts-yAxis-tick-labels text")).to_have_text([
        "Page A",
        "Page B",
        "Page C",
        "Page D",
        "Page E",
        "Page F",
        "Page G",
    ])
```

## Dynamic Data

Chart data can be modified by tying the `data` prop to a State var. Most other
props, such as `type_`, can be controlled dynamically as well. In the following
example the "Munge Data" button can be used to randomly modify the data, and the
two `select` elements change the line `type_`. Since the data and style is saved
in the per-browser-tab State, the changes will not be visible to other visitors.

```python demo exec
initial_data = data


class LineChartState(rx.State):
    data: list[dict[str, Any]] = initial_data
    pv_type: str = "monotone"
    uv_type: str = "monotone"

    @rx.event
    def set_pv_type(self, pv_type: str):
        self.pv_type = pv_type

    @rx.event
    def set_uv_type(self, uv_type: str):
        self.uv_type = uv_type

    @rx.event
    def munge_data(self):
        for row in self.data:
            row["uv"] += random.randint(-500, 500)
            row["pv"] += random.randint(-1000, 1000)


def line_dynamic():
    return rx.vstack(
        rx.recharts.line_chart(
            rx.recharts.line(
                data_key="pv",
                type_=LineChartState.pv_type,
                stroke="#8884d8",
            ),
            rx.recharts.line(
                data_key="uv",
                type_=LineChartState.uv_type,
                stroke="#82ca9d",
            ),
            rx.recharts.x_axis(data_key="name"),
            rx.recharts.y_axis(),
            data=LineChartState.data,
            margin={"top": 20, "right": 20, "left": 20, "bottom": 20},
            width="100%",
            height=300,
        ),
        rx.hstack(
            rx.button("Munge Data", on_click=LineChartState.munge_data),
            rx.select(
                ["monotone", "linear", "step", "stepBefore", "stepAfter"],
                value=LineChartState.pv_type,
                on_change=LineChartState.set_pv_type,
            ),
            rx.select(
                ["monotone", "linear", "step", "stepBefore", "stepAfter"],
                value=LineChartState.uv_type,
                on_change=LineChartState.set_uv_type,
            ),
        ),
        width="100%",
    )
```

```python test
def test_munge_button_and_selects_update_lines(demo, page):
    pv_line = demo.locator(".recharts-line-curve").first
    expect(pv_line).to_have_attribute("d", re.compile(r"\S"))
    original = pv_line.get_attribute("d")
    demo.get_by_role("button", name="Munge Data").click()
    expect(pv_line).not_to_have_attribute("d", original)
    munged = pv_line.get_attribute("d")
    pv_select = demo.get_by_role("combobox").first
    expect(pv_select).to_have_text("monotone")
    pv_select.click()
    page.get_by_role("option", name="step", exact=True).click()
    expect(pv_select).to_have_text("step")
    expect(pv_line).not_to_have_attribute("d", munged)
```

To learn how to use the `sync_id`, `x_axis_id` and `y_axis_id` props check out the of the area chart [documentation](/docs/library/graphing/charts/areachart/), where these props are all described with examples.

## Related Charts

Explore more chart types you can build with Reflex and Recharts in pure Python:

- [Area Chart](/docs/library/graphing/charts/areachart/)
- [Bar Chart](/docs/library/graphing/charts/barchart/)
- [Scatter Chart](/docs/library/graphing/charts/scatterchart/)
