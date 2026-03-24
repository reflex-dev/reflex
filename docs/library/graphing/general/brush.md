---
components:
    - rx.recharts.Brush
---

# Brush

```python exec
import reflex as rx
```
## Simple Example

The brush component allows us to view charts that have a large number of data points. To view and analyze them efficiently, the brush provides a slider with two handles that helps the viewer to select some range of data points to be displayed.

```python demo graphing
data = [
  { "name": '1', "uv": 300, "pv": 456 },
  { "name": '2', "uv": -145, "pv": 230 },
  { "name": '3', "uv": -100, "pv": 345 },
  { "name": '4', "uv": -8, "pv": 450 },
  { "name": '5', "uv": 100, "pv": 321 },
  { "name": '6', "uv": 9, "pv": 235 },
  { "name": '7', "uv": 53, "pv": 267 },
  { "name": '8', "uv": 252, "pv": -378 },
  { "name": '9', "uv": 79, "pv": -210 },
  { "name": '10', "uv": 294, "pv": -23 },
  { "name": '12', "uv": 43, "pv": 45 },
  { "name": '13', "uv": -74, "pv": 90 },
  { "name": '14', "uv": -71, "pv": 130 },
  { "name": '15', "uv": -117, "pv": 11 },
  { "name": '16', "uv": -186, "pv": 107 },
  { "name": '17', "uv": -16, "pv": 926 },
  { "name": '18', "uv": -125, "pv": 653 },
  { "name": '19', "uv": 222, "pv": 366 },
  { "name": '20', "uv": 372, "pv": 486 },
  { "name": '21', "uv": 182, "pv": 512 },
  { "name": '22', "uv": 164, "pv": 302 },
  { "name": '23', "uv": 316, "pv": 425 },
  { "name": '24', "uv": 131, "pv": 467 },
  { "name": '25', "uv": 291, "pv": -190 },
  { "name": '26', "uv": -47, "pv": 194 },
  { "name": '27', "uv": -415, "pv": 371 },
  { "name": '28', "uv": -182, "pv": 376 },
  { "name": '29', "uv": -93, "pv": 295 },
  { "name": '30', "uv": -99, "pv": 322 },
  { "name": '31', "uv": -52, "pv": 246 },
  { "name": '32', "uv": 154, "pv": 33 },
  { "name": '33', "uv": 205, "pv": 354 },
  { "name": '34', "uv": 70, "pv": 258 },
  { "name": '35', "uv": -25, "pv": 359 },
  { "name": '36', "uv": -59, "pv": 192 },
  { "name": '37', "uv": -63, "pv": 464 },
  { "name": '38', "uv": -91, "pv": -2 },
  { "name": '39', "uv": -66, "pv": 154 },
  { "name": '40', "uv": -50, "pv": 186 },
]

def brush_simple():
  return rx.recharts.bar_chart(
    rx.recharts.bar(
        data_key="uv",
        stroke="#8884d8",
        fill="#8884d8"
    ),
    rx.recharts.bar(
        data_key="pv",
        stroke="#82ca9d",
        fill="#82ca9d"
    ),
    rx.recharts.brush(data_key="name", height=30, stroke="#8884d8"),
    rx.recharts.x_axis(data_key="name"),
    rx.recharts.y_axis(),
    data=data,
    width="100%",
    height=300,
  )
```

## Position, Size, and Range

This example showcases ways to set the Position, Size, and Range. The `gap` prop provides the spacing between stops on the brush when the graph will refresh. The `start_index` and `end_index` props defines the default range of the brush. `traveller_width` prop specifies the width of each handle ("traveller" in recharts lingo).

```python demo graphing
data = [
  { "name": '1', "uv": 300, "pv": 456 },
  { "name": '2', "uv": -145, "pv": 230 },
  { "name": '3', "uv": -100, "pv": 345 },
  { "name": '4', "uv": -8, "pv": 450 },
  { "name": '5', "uv": 100, "pv": 321 },
  { "name": '6', "uv": 9, "pv": 235 },
  { "name": '7', "uv": 53, "pv": 267 },
  { "name": '8', "uv": 252, "pv": -378 },
  { "name": '9', "uv": 79, "pv": -210 },
  { "name": '10', "uv": 294, "pv": -23 },
  { "name": '12', "uv": 43, "pv": 45 },
  { "name": '13', "uv": -74, "pv": 90 },
  { "name": '14', "uv": -71, "pv": 130 },
  { "name": '15', "uv": -117, "pv": 11 },
  { "name": '16', "uv": -186, "pv": 107 },
  { "name": '17', "uv": -16, "pv": 926 },
  { "name": '18', "uv": -125, "pv": 653 },
  { "name": '19', "uv": 222, "pv": 366 },
  { "name": '20', "uv": 372, "pv": 486 },
  { "name": '21', "uv": 182, "pv": 512 },
  { "name": '22', "uv": 164, "pv": 302 },
  { "name": '23', "uv": 316, "pv": 425 },
  { "name": '24', "uv": 131, "pv": 467 },
  { "name": '25', "uv": 291, "pv": -190 },
  { "name": '26', "uv": -47, "pv": 194 },
  { "name": '27', "uv": -415, "pv": 371 },
  { "name": '28', "uv": -182, "pv": 376 },
  { "name": '29', "uv": -93, "pv": 295 },
  { "name": '30', "uv": -99, "pv": 322 },
  { "name": '31', "uv": -52, "pv": 246 },
  { "name": '32', "uv": 154, "pv": 33 },
  { "name": '33', "uv": 205, "pv": 354 },
  { "name": '34', "uv": 70, "pv": 258 },
  { "name": '35', "uv": -25, "pv": 359 },
  { "name": '36', "uv": -59, "pv": 192 },
  { "name": '37', "uv": -63, "pv": 464 },
  { "name": '38', "uv": -91, "pv": -2 },
  { "name": '39', "uv": -66, "pv": 154 },
  { "name": '40', "uv": -50, "pv": 186 },
]

def brush_pos_size_range():
    return rx.recharts.area_chart(
        rx.recharts.area(
            data_key="uv",
            stroke="#8884d8",
            fill="#8884d8",
        ),
        rx.recharts.area(
            data_key="pv",
            stroke="#82ca9d",
            fill="#82ca9d",
        ),
        rx.recharts.brush(
            data_key="name",
            traveller_width=15,
            start_index=3,
            end_index=10,
            stroke=rx.color("mauve", 10),
            fill=rx.color("mauve", 3),
        ),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(),
        data=data,
        width="100%",
        height=200,
    )

```
