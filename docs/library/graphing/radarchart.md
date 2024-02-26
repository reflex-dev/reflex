---
components:
    - rx.recharts.RadarChart
---

# Radar Chart

```python exec
import reflex as rx
from pcweb.templates.docpage import docgraphing

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

radar_chart_simple_example = """rx.recharts.radar_chart(
                rx.recharts.radar(
                    data_key="A",
                    stroke="#8884d8",
                    fill="#8884d8",
                    ),
                    rx.recharts.polar_grid(),
                    rx.recharts.polar_angle_axis(data_key="subject"),
                    data=data
                    )"""

radar_chart_complex_example = """rx.recharts.radar_chart(
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
                    rx.recharts.legend(),
                    data=data
                    )"""

```

A radar chart shows multivariate data of three or more quantitative variables mapped onto an axis.

For a radar chart we must define an `rx.recharts.radar()` component for each set of values we wish to plot. Each `rx.recharts.radar()` component has a `data_key` which clearly states which variable in our data we are plotting. In this simple example we plot the `A` column of our data against the `subject` column which we set as the `data_key` in `rx.recharts.polar_angle_axis`.

```python eval
docgraphing(radar_chart_simple_example, comp=eval(radar_chart_simple_example),  data =  "data=" + str(data))
```

We can also add two radars on one chart by using two `rx.recharts.radar` components.

```python eval
docgraphing(radar_chart_complex_example, comp=eval(radar_chart_complex_example),  data =  "data=" + str(data))
```

# Dynamic Data

Chart data tied to a State var causes the chart to automatically update when the
state changes, providing a nice way to visualize data in response to user
interface elements. View the "Data" tab to see the substate driving this
radar chart of character traits.

```python exec
from typing import Any


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

    @rx.cached_var
    def trait_names(self) -> list[str]:
        return [t["trait"] for t in self.traits]

    def set_trait(self, trait: str, value: int):
        for t in self.traits:
            if t["trait"] == trait:
                available_points = self.remaining_points + t["value"]
                value = min(value, available_points)
                t["value"] = value
                break

radar_chart_state_example = """
rx.hstack(
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
                rx.chakra.slider(
                    value=RadarChartState.traits[i]["value"].to(int),
                    on_change=lambda value: RadarChartState.set_trait(trait_name, value),
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
"""
```

```python eval
docgraphing(
    radar_chart_state_example,
    comp=eval(radar_chart_state_example),
    # data=inspect.getsource(RadarChartState),
)
```
