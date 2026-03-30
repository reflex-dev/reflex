---
components:
  - rx.plotly
---

# Plotly

```python exec
import reflex as rx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
```

Plotly is a graphing library that can be used to create interactive graphs. Use the rx.plotly component to wrap Plotly as a component for use in your web page. Checkout [Plotly](https://plotly.com/graphing-libraries/) for more information.

```md alert info
# When integrating Plotly graphs into your UI code, note that the method for displaying the graph differs from a regular Python script. Instead of using `fig.show()`, use `rx.plotly(data=fig)` within your UI code to ensure the graph is properly rendered and displayed within the user interface
```

## Basic Example

Let's create a line graph of life expectancy in Canada.

```python demo exec
import plotly.express as px

df = px.data.gapminder().query("country=='Canada'")
fig = px.line(df, x="year", y="lifeExp", title='Life expectancy in Canada')

def line_chart():
    return rx.center(
        rx.plotly(data=fig),
    )
```

## 3D graphing example

Let's create a 3D surface plot of Mount Bruno. This is a slightly more complicated example, but it wraps in Reflex using the same method. In fact, you can wrap any figure using the same approach.

```python demo exec
import plotly.graph_objects as go
import pandas as pd

# Read data from a csv
z_data = pd.read_csv('data/mt_bruno_elevation.csv')

fig = go.Figure(data=[go.Surface(z=z_data.values)])
fig.update_traces(contours_z=dict(show=True, usecolormap=True,
                                  highlightcolor="limegreen", project_z=True))
fig.update_layout(
    scene_camera_eye=dict(x=1.87, y=0.88, z=-0.64),
    margin=dict(l=65, r=50, b=65, t=90)
)

def mountain_surface():
    return rx.center(
        rx.plotly(data=fig),
    )
```

📊 **Dataset source:** [mt_bruno_elevation.csv](https://raw.githubusercontent.com/plotly/datasets/master/api_docs/mt_bruno_elevation.csv)

## Plot as State Var

If the figure is set as a state var, it can be updated during run time.

```python demo exec
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

class PlotlyState(rx.State):
    df: pd.DataFrame
    figure: go.Figure = px.line()

    @rx.event
    def create_figure(self):
        self.df = px.data.gapminder().query("country=='Canada'")
        self.figure = px.line(
            self.df,
            x="year",
            y="lifeExp",
            title="Life expectancy in Canada",
        )

    @rx.event
    def set_selected_country(self, country):
        self.df = px.data.gapminder().query(f"country=='{country}'")
        self.figure = px.line(
            self.df,
            x="year",
            y="lifeExp",
            title=f"Life expectancy in {country}",
        )



def line_chart_with_state():
    return rx.vstack(
        rx.select(
            ['China', 'France', 'United Kingdom', 'United States', 'Canada'],
            default_value="Canada",
            on_change=PlotlyState.set_selected_country,
        ),
        rx.plotly(
            data=PlotlyState.figure,
            on_mount=PlotlyState.create_figure,
        ),
    )
```

## Adding Styles and Layouts

Use `update_layout()` method to update the layout of your chart. Checkout [Plotly Layouts](https://plotly.com/python/reference/layout/) for all layouts props.

```md alert info
Note that the width and height props are not recommended to ensure the plot remains size responsive to its container. The size of plot will be determined by it's outer container.
```

```python demo exec
df = px.data.gapminder().query("country=='Canada'")
fig_1 = px.line(
    df,
    x="year",
    y="lifeExp",
    title="Life expectancy in Canada",
)
fig_1.update_layout(
    title_x=0.5,
    plot_bgcolor="#c3d7f7",
    paper_bgcolor="rgba(128, 128, 128, 0.1)",
    showlegend=True,
    title_font_family="Open Sans",
    title_font_size=25,
)

def add_styles():
    return rx.center(
        rx.plotly(data=fig_1),
        width="100%",
        height="100%",
    )
```
