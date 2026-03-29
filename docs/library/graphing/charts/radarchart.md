---
components:
  - rx.recharts.RadarChart
  - rx.recharts.Radar
---

# Radar Chart

```python exec
import reflex as rx
from typing import Any
```

A radar chart shows multivariate data of three or more quantitative variables mapped onto an axis.

## Simple Example

For a radar chart we must define an `rx.recharts.radar()` component for each set of values we wish to plot. Each `rx.recharts.radar()` component has a `data_key` which clearly states which variable in our data we are plotting. In this simple example we plot the `A` column of our data against the `subject` column which we set as the `data_key` in `rx.recharts.polar_angle_axis`.

```python demo graphing
data = [
  {
    "subject": "Math",
    "A": 120,
    "B": 110,
    "fullMark": 150
  },
  {
    "subject": "Chinese",
    "A": 98,
    "B": 130,
    "fullMark": 150
  },
  {
    "subject": "English",
    "A": 86,
    "B": 130,
    "fullMark": 150
  },
  {
    "subject": "Geography",
    "A": 99,
    "B": 100,
    "fullMark": 150
  },
  {
    "subject": "Physics",
    "A": 85,
    "B": 90,
    "fullMark": 150
  },
  {
    "subject": "History",
    "A": 65,
    "B": 85,
    "fullMark": 150
  }
]

def radar_simple():
    return rx.recharts.radar_chart(
        rx.recharts.radar(
            data_key="A",
            stroke="#8884d8",
            fill="#8884d8",
        ),
        rx.recharts.polar_grid(),
        rx.recharts.polar_angle_axis(data_key="subject"),
        rx.recharts.polar_radius_axis(angle=90, domain=[0, 150]),
        data=data,
        width="100%",
        height=300,
    )
```

## Multiple Radars

We can also add two radars on one chart by using two `rx.recharts.radar` components.

In this plot an `inner_radius` and an `outer_radius` are set which determine the chart's size and shape. The `inner_radius` sets the distance from the center to the innermost part of the chart (creating a hollow center if greater than zero), while the `outer_radius` defines the chart's overall size by setting the distance from the center to the outermost edge of the radar plot.

```python demo graphing

data = [
  {
    "subject": "Math",
    "A": 120,
    "B": 110,
    "fullMark": 150
  },
  {
    "subject": "Chinese",
    "A": 98,
    "B": 130,
    "fullMark": 150
  },
  {
    "subject": "English",
    "A": 86,
    "B": 130,
    "fullMark": 150
  },
  {
    "subject": "Geography",
    "A": 99,
    "B": 100,
    "fullMark": 150
  },
  {
    "subject": "Physics",
    "A": 85,
    "B": 90,
    "fullMark": 150
  },
  {
    "subject": "History",
    "A": 65,
    "B": 85,
    "fullMark": 150
  }
]

def radar_multiple():
    return rx.recharts.radar_chart(
        rx.recharts.radar(
            data_key="A",
            stroke="#8884d8",
            fill="#8884d8",
        ),
        rx.recharts.radar(
            data_key="B",
            stroke="#82ca9d",
            fill="#82ca9d",
            fill_opacity=0.6,
        ),
        rx.recharts.polar_grid(),
        rx.recharts.polar_angle_axis(data_key="subject"),
        rx.recharts.polar_radius_axis(angle=90, domain=[0, 150]),
        rx.recharts.legend(),
        data=data,
        inner_radius="15%",
        outer_radius="80%",
        width="100%",
        height=300,
    )

```

## Using More Props

The `dot` prop shows points at each data vertex when true. `legend_type="line"` displays a line in the chart legend. `animation_begin=0` starts the animation immediately, `animation_duration=8000` sets an 8-second animation, and `animation_easing="ease-in"` makes the animation start slowly and speed up. These props control the chart's appearance and animation behavior.

```python demo graphing

data = [
    {
        "subject": "Math",
        "A": 120,
        "B": 110,
        "fullMark": 150
    },
    {
        "subject": "Chinese",
        "A": 98,
        "B": 130,
        "fullMark": 150
    },
    {
        "subject": "English",
        "A": 86,
        "B": 130,
        "fullMark": 150
    },
    {
        "subject": "Geography",
        "A": 99,
        "B": 100,
        "fullMark": 150
    },
    {
        "subject": "Physics",
        "A": 85,
        "B": 90,
        "fullMark": 150
    },
    {
        "subject": "History",
        "A": 65,
        "B": 85,
        "fullMark": 150
    }
    ]


def radar_start_end():
    return rx.recharts.radar_chart(
            rx.recharts.radar(
                data_key="A",
                dot=True,
                stroke="#8884d8",
                fill="#8884d8",
                fill_opacity=0.6,
                legend_type="line",
                animation_begin=0,
                animation_duration=8000,
                animation_easing="ease-in",
            ),
            rx.recharts.polar_grid(),
            rx.recharts.polar_angle_axis(data_key="subject"),
            rx.recharts.polar_radius_axis(angle=90, domain=[0, 150]),
            rx.recharts.legend(),
            data=data,
            width="100%",
            height=300,
        )

```

# Dynamic Data

Chart data tied to a State var causes the chart to automatically update when the
state changes, providing a nice way to visualize data in response to user
interface elements. View the "Data" tab to see the substate driving this
radar chart of character traits.

```python demo exec
class RadarChartState(rx.State):
    total_points: int = 100
    traits: list[dict[str, Any]] = [
        dict(trait="Strength", value=15),
        dict(trait="Dexterity", value=15),
        dict(trait="Constitution", value=15),
        dict(trait="Intelligence", value=15),
        dict(trait="Wisdom", value=15),
        dict(trait="Charisma", value=15),
    ]

    @rx.var
    def remaining_points(self) -> int:
        return self.total_points - sum(t["value"] for t in self.traits)

    @rx.var(cache=True)
    def trait_names(self) -> list[str]:
        return [t["trait"] for t in self.traits]

    @rx.event
    def set_trait(self, trait: str, value: int):
        for t in self.traits:
            if t["trait"] == trait:
                available_points = self.remaining_points + t["value"]
                value = min(value, available_points)
                t["value"] = value
                break

def radar_dynamic():
    return rx.hstack(
        rx.recharts.radar_chart(
            rx.recharts.radar(
                data_key="value",
                stroke="#8884d8",
                fill="#8884d8",
            ),
            rx.recharts.polar_grid(),
            rx.recharts.polar_angle_axis(data_key="trait"),
            data=RadarChartState.traits,
        ),
        rx.vstack(
            rx.foreach(
                RadarChartState.trait_names,
                lambda trait_name, i: rx.hstack(
                    rx.text(trait_name, width="7em"),
                    rx.slider(
                        default_value=RadarChartState.traits[i]["value"].to(int),
                        on_change=lambda value: RadarChartState.set_trait(trait_name, value[0]),
                        width="25vw",
                    ),
                    rx.text(RadarChartState.traits[i]['value']),
                ),
            ),
            rx.text("Remaining points: ", RadarChartState.remaining_points),
        ),
        width="100%",
        height="15em",
    )
```
