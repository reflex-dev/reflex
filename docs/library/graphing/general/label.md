---
components:
  - rx.recharts.Label
  - rx.recharts.LabelList
---

# Label

```python exec
import reflex as rx
```

Label is a component used to display a single label at a specific position within a chart or axis, while LabelList is a component that automatically renders a list of labels for each data point in a chart series, providing a convenient way to display multiple labels without manually positioning each one.

## Simple Example

Here's a simple example that demonstrates how you can customize the label of your axis using `rx.recharts.label`. The `value` prop represents the actual text of the label, the `position` prop specifies where the label is positioned within the axis component, and the `offset` prop is used to fine-tune the label's position.

```python demo graphing
data = [
    {"name": "Page A", "uv": 4000, "pv": 2400, "amt": 2400},
    {"name": "Page B", "uv": 3000, "pv": 1398, "amt": 2210},
    {"name": "Page C", "uv": 2000, "pv": 5800, "amt": 2290},
    {"name": "Page D", "uv": 2780, "pv": 3908, "amt": 2000},
    {"name": "Page E", "uv": 1890, "pv": 4800, "amt": 2181},
    {"name": "Page F", "uv": 2390, "pv": 3800, "amt": 2500},
    {"name": "Page G", "uv": 3490, "pv": 4300, "amt": 2100},
]


def label_simple():
    return rx.recharts.bar_chart(
        rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
        rx.recharts.bar(
            rx.recharts.label_list(data_key="uv", position="top"),
            data_key="uv",
            fill=rx.color("accent", 8),
        ),
        rx.recharts.x_axis(
            rx.recharts.label(
                value="center",
                position="center",
                offset=30,
            ),
            rx.recharts.label(
                value="inside left",
                position="insideLeft",
                offset=10,
            ),
            rx.recharts.label(
                value="inside right",
                position="insideRight",
                offset=10,
            ),
            height=50,
        ),
        data=data,
        margin={
            "left": 20,
            "right": 20,
            "top": 20,
            "bottom": 20,
        },
        width="100%",
        height=250,
    )
```

```python test
def test_bar_values_and_axis_labels_are_shown(demo):
    expect(demo.locator(".recharts-label-list text")).to_have_text([
        "4000",
        "3000",
        "2000",
        "2780",
        "1890",
        "2390",
        "3490",
    ])
    surface = demo.locator(".recharts-wrapper > .recharts-surface")
    for text in ["center", "inside left", "inside right"]:
        expect(surface.get_by_text(text, exact=True)).to_be_visible()
```

## Label List Example

`rx.recharts.label_list` takes in a `data_key` where we define the data column to plot.

```python demo graphing
data = [
    {"name": "Page A", "uv": 4000, "pv": 2400, "amt": 2400},
    {"name": "Page B", "uv": 3000, "pv": 1398, "amt": 2210},
    {"name": "Page C", "uv": 2000, "pv": 5800, "amt": 2290},
    {"name": "Page D", "uv": 2780, "pv": 3908, "amt": 2000},
    {"name": "Page E", "uv": 1890, "pv": 4800, "amt": 2181},
    {"name": "Page F", "uv": 2390, "pv": 3800, "amt": 2500},
    {"name": "Page G", "uv": 3490, "pv": 4300, "amt": 2100},
]


def label_list():
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            rx.recharts.label_list(data_key="uv", position="top"),
            data_key="uv",
            stroke="#8884d8",
            fill="#8884d8",
        ),
        rx.recharts.bar(
            rx.recharts.label_list(data_key="pv", position="top"),
            data_key="pv",
            stroke="#82ca9d",
            fill="#82ca9d",
        ),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(),
        margin={"left": 10, "right": 0, "top": 20, "bottom": 10},
        data=data,
        width="100%",
        height=300,
    )
```

```python test
def test_each_bar_series_has_a_label_list(demo):
    label_lists = demo.locator(".recharts-label-list")
    expect(label_lists.first.locator("text")).to_have_text([
        "4000",
        "3000",
        "2000",
        "2780",
        "1890",
        "2390",
        "3490",
    ])
    expect(label_lists.last.locator("text")).to_have_text([
        "2400",
        "1398",
        "5800",
        "3908",
        "4800",
        "3800",
        "4300",
    ])
```

## Styling Labels

Styling that is not exposed as a prop on `rx.recharts.label` can be passed through to the underlying Recharts label with `custom_attrs`. This is useful for setting the font size and weight of an axis label, or rotating a y-axis label with `angle` so it reads vertically along the axis.

```python demo graphing
data = [
    {"name": "Page A", "uv": 4000, "pv": 2400, "amt": 2400},
    {"name": "Page B", "uv": 3000, "pv": 1398, "amt": 2210},
    {"name": "Page C", "uv": 2000, "pv": 5800, "amt": 2290},
    {"name": "Page D", "uv": 2780, "pv": 3908, "amt": 2000},
    {"name": "Page E", "uv": 1890, "pv": 4800, "amt": 2181},
    {"name": "Page F", "uv": 2390, "pv": 3800, "amt": 2500},
    {"name": "Page G", "uv": 3490, "pv": 4300, "amt": 2100},
]


def label_styled():
    return rx.recharts.area_chart(
        rx.recharts.area(
            data_key="uv",
            stroke=rx.color("accent", 9),
            fill=rx.color("accent", 8),
        ),
        rx.recharts.x_axis(
            rx.recharts.label(
                value="Pages",
                position="center",
                custom_attrs={"fontSize": "12px", "fontWeight": "700"},
            ),
            data_key="name",
            height=60,
        ),
        rx.recharts.y_axis(
            rx.recharts.label(
                value="Views",
                position="left",
                custom_attrs={"angle": 270, "fontSize": "12px", "fontWeight": "700"},
            ),
        ),
        data=data,
        margin={"left": 20, "right": 20, "top": 25},
        width="100%",
        height=300,
    )
```

```python test
def test_axis_labels_are_bold(demo):
    labels = demo.locator(".recharts-label")
    expect(labels).to_have_text(["Pages", "Views"])
    expect(labels.first).to_have_attribute("font-weight", "700")
    expect(labels.last).to_have_attribute("font-size", "12px")
```
