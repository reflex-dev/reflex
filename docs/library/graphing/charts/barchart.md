---
components:
  - rx.recharts.BarChart
  - rx.recharts.Bar
title: Bar Chart
meta_description: "Create interactive bar charts in Python with Reflex. Build grouped, stacked, and horizontal Recharts bar charts with custom colors, axes, tooltips, and legends — all in pure Python, no JavaScript."
---

# Bar Chart

```python exec
import reflex as rx
import random
```

Bar charts in Reflex are built on [Recharts](https://recharts.org/), a React charting library, and let you visualize categorical data in pure Python. A bar chart presents categorical data with rectangular bars whose heights or lengths are proportional to the values that they represent.

For a bar chart we must define an `rx.recharts.bar()` component for each set of values we wish to plot. Each `rx.recharts.bar()` component has a `data_key` which clearly states which variable in our data we are tracking. In this simple example we plot `uv` as a bar against the `name` column which we set as the `data_key` in `rx.recharts.x_axis`.

## Simple Example

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


def bar_simple():
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            data_key="uv",
            stroke=rx.color("accent", 9),
            fill=rx.color("accent", 8),
        ),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(),
        data=data,
        width="100%",
        height=250,
    )
```

## Multiple Bars

Multiple bars can be placed on the same `bar_chart`, using multiple `rx.recharts.bar()` components. Drawn side by side like this, they form a grouped (or clustered) bar chart.

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


def bar_double():
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            data_key="uv",
            stroke=rx.color("accent", 9),
            fill=rx.color("accent", 8),
        ),
        rx.recharts.bar(
            data_key="pv",
            stroke=rx.color("green", 9),
            fill=rx.color("green", 8),
        ),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(),
        data=data,
        width="100%",
        height=250,
    )
```

## Stacked Bar Chart

To build a stacked bar chart, give each `rx.recharts.bar()` the same `stack_id`. Instead of being drawn side by side, the bars are stacked on top of one another, which is ideal for showing part-to-whole composition (also called a segmented bar chart). Set `stack_offset="expand"` on the `bar_chart` to turn it into a 100% stacked bar chart.

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


def bar_stacked():
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            data_key="uv",
            stack_id="1",
            fill=rx.color("accent", 8),
        ),
        rx.recharts.bar(
            data_key="pv",
            stack_id="1",
            fill=rx.color("green", 8),
        ),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(),
        rx.recharts.legend(),
        data=data,
        width="100%",
        height=300,
    )
```

## Ranged Charts

You can also assign a range in the bar by assigning the data_key in the `rx.recharts.bar` to a list with two elements, i.e. here a range of two temperatures for each date.

```python demo graphing
range_data = [
    {"day": "05-01", "temperature": [-1, 10]},
    {"day": "05-02", "temperature": [2, 15]},
    {"day": "05-03", "temperature": [3, 12]},
    {"day": "05-04", "temperature": [4, 12]},
    {"day": "05-05", "temperature": [12, 16]},
    {"day": "05-06", "temperature": [5, 16]},
    {"day": "05-07", "temperature": [3, 12]},
    {"day": "05-08", "temperature": [0, 8]},
    {"day": "05-09", "temperature": [-3, 5]},
]


def bar_range():
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            data_key="temperature",
            stroke=rx.color("accent", 9),
            fill=rx.color("accent", 8),
        ),
        rx.recharts.x_axis(data_key="day"),
        rx.recharts.y_axis(),
        data=range_data,
        width="100%",
        height=250,
    )
```

## Stateful Charts

Here is an example of a bar graph with a `State`. Here we have defined a function `randomize_data`, which randomly changes the data for both graphs when the first defined `bar` is clicked on using `on_click=BarState.randomize_data`.

```python demo exec
class BarState(rx.State):
    data = data

    @rx.event
    def randomize_data(self):
        for i in range(len(self.data)):
            self.data[i]["uv"] = random.randint(0, 10000)
            self.data[i]["pv"] = random.randint(0, 10000)
            self.data[i]["amt"] = random.randint(0, 10000)


def bar_with_state():
    return rx.recharts.bar_chart(
        rx.recharts.cartesian_grid(
            stroke_dasharray="3 3",
        ),
        rx.recharts.bar(
            data_key="uv",
            stroke=rx.color("accent", 9),
            fill=rx.color("accent", 8),
        ),
        rx.recharts.bar(
            data_key="pv",
            stroke=rx.color("green", 9),
            fill=rx.color("green", 8),
        ),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(),
        rx.recharts.legend(),
        on_click=BarState.randomize_data,
        data=BarState.data,
        width="100%",
        height=300,
    )
```

## Click Events and Drill-Down

The `on_click` event on `rx.recharts.bar` provides no arguments, so it cannot tell you which bar was clicked. To handle clicks with data — for example, to drill down into a category — render an `rx.recharts.cell` for each data point with `rx.foreach`, so each cell binds its click data at render time from the loop variable.

In this example, clicking a bar filters the chart to that category (zoom in), and clicking the same bar again clears the filter (zoom out). An `rx.cond` on the cell's `fill` highlights the selected bar.

```python demo exec
drilldown_data = [
    {"name": "Fiction", "count": 42},
    {"name": "History", "count": 28},
    {"name": "Science", "count": 35},
    {"name": "Biography", "count": 17},
    {"name": "Fantasy", "count": 24},
]

DRILLDOWN_COLORS = ["#6366F1", "#8B5CF6", "#A855F7", "#D946EF", "#EC4899"]


class BarDrilldownState(rx.State):
    drilled_genre: str = ""

    @rx.var
    def genre_data(self) -> list[dict[str, str | int]]:
        if self.drilled_genre:
            return [d for d in drilldown_data if d["name"] == self.drilled_genre]
        return drilldown_data

    @rx.event
    def toggle_genre(self, genre_name: str):
        """Click the same bar again to zoom back out."""
        if self.drilled_genre == genre_name:
            self.drilled_genre = ""
        else:
            self.drilled_genre = genre_name


def _drilldown_cell(item: rx.Var, index: rx.Var) -> rx.Component:
    """Each bar gets its own cell with on_click bound to the item name."""
    return rx.recharts.cell(
        on_click=BarDrilldownState.toggle_genre(item["name"].to(str)),
        cursor="pointer",
        fill=rx.cond(
            BarDrilldownState.drilled_genre == item["name"],
            "#1D4ED8",
            rx.Var.create(DRILLDOWN_COLORS)[index % len(DRILLDOWN_COLORS)],
        ),
    )


def bar_drilldown():
    return rx.recharts.bar_chart(
        rx.recharts.cartesian_grid(stroke_dasharray="3 3", vertical=False),
        rx.recharts.x_axis(data_key="name", tick_line=False, axis_line=False),
        rx.recharts.y_axis(allow_decimals=False, axis_line=False, tick_line=False),
        rx.recharts.bar(
            rx.foreach(BarDrilldownState.genre_data, _drilldown_cell),
            data_key="count",
            radius=[4, 4, 0, 0],
        ),
        rx.recharts.graphing_tooltip(),
        data=BarDrilldownState.genre_data,
        width="100%",
        height=300,
    )
```

The key points of the pattern:

1. Define a helper function that takes `(item, index)` from `rx.foreach` and returns an `rx.recharts.cell`.
2. Bind the click with `on_click=State.handler(item["name"])` — the handler receives a plain value because it is bound at render time, not extracted from the click event.
3. Use `rx.cond` to highlight the selected item with a different `fill`.
4. Apply the drill filter to the chart's own data, so only the clicked item remains visible; clearing the filter restores all items.

The same pattern works for pie charts: place the `rx.foreach` of cells inside `rx.recharts.pie`.

## Example with Props

Here's an example demonstrates how to customize the appearance and layout of bars using the `bar_category_gap`, `bar_gap`, `bar_size`, and `max_bar_size` props. These props accept values in pixels to control the spacing and size of the bars.

```python demo graphing
data = [
    {"name": "Page A", "value": 2400},
    {"name": "Page B", "value": 1398},
    {"name": "Page C", "value": 9800},
    {"name": "Page D", "value": 3908},
    {"name": "Page E", "value": 4800},
    {"name": "Page F", "value": 3800},
]


def bar_features():
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            data_key="value",
            fill=rx.color("accent", 8),
        ),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(),
        data=data,
        bar_category_gap="15%",
        bar_gap=6,
        bar_size=100,
        max_bar_size=40,
        width="100%",
        height=300,
    )
```

## Rounded Bars

The `radius` prop on `rx.recharts.bar` rounds the corners of each bar. Pass a single number to round all four corners, or a list of four values in the order `[top-left, top-right, bottom-right, bottom-left]` — for example `[8, 8, 0, 0]` rounds only the top corners.

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


def bar_rounded():
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            data_key="uv",
            fill=rx.color("accent", 8),
            radius=[8, 8, 0, 0],
        ),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(),
        data=data,
        width="100%",
        height=250,
    )
```

## Gradient Fill

Bars can be styled with SVG linear gradients. Define one gradient per series inside an `rx.el.svg.defs` block as the first child of the chart, then reference each gradient from the bar's `fill` prop with `"url(#gradient-id)"`.

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


def create_bar_gradient(color: str, id: str) -> rx.Component:
    return rx.el.svg.linear_gradient(
        rx.el.svg.stop(offset="5%", stop_color=color, stop_opacity=0.8),
        rx.el.svg.stop(offset="95%", stop_color=color, stop_opacity=0.2),
        id=id,
        x1=0,
        y1=0,
        x2=0,
        y2=1,
    )


def bar_gradient():
    return rx.recharts.bar_chart(
        rx.el.svg.defs(
            create_bar_gradient("#8884d8", "bar_gradient_uv"),
            create_bar_gradient("#82ca9d", "bar_gradient_pv"),
        ),
        rx.recharts.bar(
            data_key="uv",
            fill="url(#bar_gradient_uv)",
            radius=[4, 4, 0, 0],
        ),
        rx.recharts.bar(
            data_key="pv",
            fill="url(#bar_gradient_pv)",
            radius=[4, 4, 0, 0],
        ),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(),
        rx.recharts.graphing_tooltip(),
        rx.recharts.legend(),
        data=data,
        width="100%",
        height=300,
    )
```

## Vertical Example

The `layout` prop allows you to set the orientation of the graph to be vertical or horizontal, it is set horizontally by default. Setting `layout="vertical"` makes the bars run left-to-right, which is how you create a horizontal bar chart in Reflex.

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


def bar_vertical():
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            data_key="uv",
            stroke=rx.color("accent", 8),
            fill=rx.color("accent", 3),
        ),
        rx.recharts.x_axis(type_="number"),
        rx.recharts.y_axis(data_key="name", type_="category"),
        data=data,
        layout="vertical",
        margin={"top": 20, "right": 20, "left": 20, "bottom": 20},
        width="100%",
        height=300,
    )
```

To learn how to use the `sync_id`, `stack_id`,`x_axis_id` and `y_axis_id` props check out the of the area chart [documentation](/docs/library/graphing/charts/areachart), where these props are all described with examples.

## Related Charts

Explore more chart types you can build with Reflex and Recharts in pure Python:

- [Line Chart](/docs/library/graphing/charts/linechart)
- [Area Chart](/docs/library/graphing/charts/areachart)
- [Composed Chart](/docs/library/graphing/charts/composedchart)
