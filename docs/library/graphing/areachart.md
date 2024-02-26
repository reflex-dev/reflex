---
components:
    - rx.recharts.AreaChart
    - rx.recharts.Area
---

# Area Chart

```python exec
import reflex as rx
from pcweb.templates.docpage import docdemo, docgraphing
import random

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
    "pv": 9800,
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

range_data = [
  {
    "day": "05-01",
    "temperature": [
      -1,
      10
    ]
  },
  {
    "day": "05-02",
    "temperature": [
      2,
      15
    ]
  },
  {
    "day": "05-03",
    "temperature": [
      3,
      12
    ]
  },
  {
    "day": "05-04",
    "temperature": [
      4,
      12
    ]
  },
  {
    "day": "05-05",
    "temperature": [
      12,
      16
    ]
  },
  {
    "day": "05-06",
    "temperature": [
      5,
      16
    ]
  },
  {
    "day": "05-07",
    "temperature": [
      3,
      12
    ]
  },
  {
    "day": "05-08",
    "temperature": [
      0,
      8
    ]
  },
  {
    "day": "05-09",
    "temperature": [
      -3,
      5
    ]
  }
]


area_chart_state = """class AreaState(rx.State):
    data=data

    def randomize_data(self):
        for i in range(len(self.data)):
            self.data[i]["uv"] = random.randint(0, 10000)
            self.data[i]["pv"] = random.randint(0, 10000)
            self.data[i]["amt"] = random.randint(0, 10000)


"""
exec(area_chart_state)


area_chart_example = """rx.recharts.area_chart(
                rx.recharts.area(
                    data_key="uv",
                    stroke="#8884d8",
                    fill="#8884d8"
                ), 
                rx.recharts.x_axis(data_key="name"), 
                rx.recharts.y_axis(),
                data=data)"""

area_chart_example_2 = """rx.recharts.area_chart(
                rx.recharts.area(
                    data_key="uv",
                    stroke="#8884d8",
                    fill="#8884d8"
                ), 
                rx.recharts.area(
                    data_key="pv",
                    stroke="#82ca9d",
                    fill="#82ca9d"
                ), 
                rx.recharts.x_axis(data_key="name"), 
                rx.recharts.y_axis(),
                data=data)"""


range_area_chart = """rx.recharts.area_chart(
                rx.recharts.area(
                    data_key="temperature",
                    stroke="#8884d8",
                    fill="#8884d8"
                ), 
                rx.recharts.x_axis(data_key="day"), 
                rx.recharts.y_axis(),
                data=range_data)"""


area_chart_example_with_state = """rx.recharts.area_chart(
            rx.recharts.area(
                data_key="uv",
                stroke="#8884d8",
                fill="#8884d8",
                type_="natural",
                on_click=AreaState.randomize_data,

            ),
            rx.recharts.area(
                data_key="pv",
                stroke="#82ca9d", 
                fill="#82ca9d",
                type_="natural",
            ),
            rx.recharts.x_axis(
                data_key="name",
            ),
            rx.recharts.y_axis(), 
            rx.recharts.legend(),
            rx.recharts.cartesian_grid(
                stroke_dasharray="3 3",
            ),
            data=AreaState.data,
            width="100%",
            height=400,
        ) 
"""
```

An area chart combines the line chart and bar chart to show how one or more groups’ numeric values change over the progression of a second variable, typically that of time. An area chart is distinguished from a line chart by the addition of shading between lines and a baseline, like in a bar chart.

For an area chart we must define an `rx.recharts.area()` component that has a `data_key` which clearly states which variable in our data we are tracking. In this simple example we track `uv` against `name` and therefore set the `rx.recharts.x_axis` to equal `name`.

```python eval
docgraphing(
  area_chart_example, 
  comp = eval(area_chart_example),
  data =  "data=" + str(data)
)
```

Multiple areas can be placed on the same `area_chart`.

```python eval
docgraphing(
  area_chart_example_2, 
  comp = eval(area_chart_example_2),
  data =  "data=" + str(data)
)
```

You can also assign a range in the area by assiging the data_key in the `rx.recharts.area` to a list with two elements, i.e. here a range of two temperatures for each date.

```python eval
docgraphing(
  area_chart_example_2, 
  comp = eval(range_area_chart),
  data =  "data=" + str(range_data)
)
```

Here is an example of an area graph with a `State`. Here we have defined a function `randomize_data`, which randomly changes the data for both graphs when the first defined `area` is clicked on using `on_click=AreaState.randomize_data`.

```python eval
docdemo(area_chart_example_with_state,
        state=area_chart_state,
        comp=eval(area_chart_example_with_state),
        context=True,
)
```
