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
  {
    "name": "Page A",
    "uv": 4000,
    "pv": 2400,
    "amt": 2400
  },
  {
    "name": "Page B",
    "uv": 3000,
    "pv": 1398,
    "amt": 2210
  },
  {
    "name": "Page C",
    "uv": 2000,
    "pv": 5800,
    "amt": 2290
  },
  {
    "name": "Page D",
    "uv": 2780,
    "pv": 3908,
    "amt": 2000
  },
  {
    "name": "Page E",
    "uv": 1890,
    "pv": 4800,
    "amt": 2181
  },
  {
    "name": "Page F",
    "uv": 2390,
    "pv": 3800,
    "amt": 2500
  },
  {
    "name": "Page G",
    "uv": 3490,
    "pv": 4300,
    "amt": 2100
  }
]

def label_simple():
    return rx.recharts.bar_chart(
        rx.recharts.cartesian_grid(
            stroke_dasharray="3 3"
        ),
        rx.recharts.bar(
            rx.recharts.label_list(
                data_key="uv", position="top"
            ),
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

## Label List Example

`rx.recharts.label_list` takes in a `data_key` where we define the data column to plot.

```python demo graphing
data = [
  {
    "name": "Page A",
    "uv": 4000,
    "pv": 2400,
    "amt": 2400
  },
  {
    "name": "Page B",
    "uv": 3000,
    "pv": 1398,
    "amt": 2210
  },
  {
    "name": "Page C",
    "uv": 2000,
    "pv": 5800,
    "amt": 2290
  },
  {
    "name": "Page D",
    "uv": 2780,
    "pv": 3908,
    "amt": 2000
  },
  {
    "name": "Page E",
    "uv": 1890,
    "pv": 4800,
    "amt": 2181
  },
  {
    "name": "Page F",
    "uv": 2390,
    "pv": 3800,
    "amt": 2500
  },
  {
    "name": "Page G",
    "uv": 3490,
    "pv": 4300,
    "amt": 2100
  }
]

def label_list():
  return rx.recharts.bar_chart(
    rx.recharts.bar(
        rx.recharts.label_list(data_key="uv", position="top"),
        data_key="uv",
        stroke="#8884d8",
        fill="#8884d8"
    ), 
    rx.recharts.bar(
        rx.recharts.label_list(data_key="pv", position="top"),
        data_key="pv",
        stroke="#82ca9d",
        fill="#82ca9d" 
    ), 
    rx.recharts.x_axis(
        data_key="name"
    ),
    rx.recharts.y_axis(),
    margin={"left": 10, "right": 0, "top": 20, "bottom": 10},
    data=data,
    width="100%",
    height = 300,
  )
```


