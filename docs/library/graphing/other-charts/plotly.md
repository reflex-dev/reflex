---
description: Build interactive Plotly charts in pure Python with Reflex. Render line, scatter, histogram, and 3D surface plots as live web components, no JavaScript required.
components:
  - rx.plotly
---

# Plotly in Python: Interactive Charts with Reflex

```python exec
import reflex as rx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
```

[Plotly](https://plotly.com/graphing-libraries/) is a popular Python graphing library for creating interactive, publication-quality charts. Reflex wraps it with the `rx.plotly` component so you can embed any Plotly figure — line charts, scatter plots, histograms, or 3D surface plots — directly into a Python web app with no JavaScript. Because Reflex compiles to a full-stack web app, these charts stay interactive in the browser and can update live from your app state.

```md alert info
# When integrating Plotly graphs into your UI code, note that the method for displaying the graph differs from a regular Python script. Instead of using `fig.show()`, use `rx.plotly(data=fig)` within your UI code to ensure the graph is properly rendered and displayed within the user interface
```

## Line Chart

Let's start with a basic Plotly line chart of life expectancy in Canada.

```python demo exec
import plotly.express as px

df = px.data.gapminder().query("country=='Canada'")
fig = px.line(df, x="year", y="lifeExp", title="Life expectancy in Canada")


def line_chart():
    return rx.center(
        rx.plotly(data=fig),
    )
```

## Scatter Plot

Scatter plots are useful for showing the relationship between two variables. Here we plot the Iris dataset, coloring each point by species.

```python demo exec
def scatter_plot():
    df = px.data.iris()
    fig = px.scatter(
        df,
        x="sepal_width",
        y="sepal_length",
        color="species",
        title="Iris sepal dimensions",
    )
    return rx.center(
        rx.plotly(data=fig),
    )
```

## Histogram

Histograms show the distribution of a single variable. This example plots the distribution of restaurant bill totals.

```python demo exec
def histogram():
    df = px.data.tips()
    fig = px.histogram(
        df,
        x="total_bill",
        nbins=30,
        title="Distribution of restaurant bills",
    )
    return rx.center(
        rx.plotly(data=fig),
    )
```

## Locale Configuration

Use `locale` to localize Plotly number/date formatting and modebar labels:

```python demo exec
df = px.data.gapminder().query("country=='Canada'")
fig = px.line(df, x="year", y="lifeExp", title="Life expectancy in Canada")


def localized_line_chart():
    return rx.center(
        rx.plotly(
            data=fig,
            locale="de",
        ),
    )
```

You can still pass `config`; when both are provided, `locale=` is applied as the final locale value.

## 3D Surface Plot

Let's create a 3D surface plot of Mount Bruno. This is a slightly more complicated example, but it wraps in Reflex using the same method. In fact, you can wrap any figure using the same approach.

```python demo exec
import plotly.graph_objects as go
import pandas as pd

# Read data from a csv
z_data = pd.read_csv("data/mt_bruno_elevation.csv")

fig = go.Figure(data=[go.Surface(z=z_data.values)])
fig.update_traces(
    contours_z=dict(
        show=True, usecolormap=True, highlightcolor="limegreen", project_z=True
    )
)
fig.update_layout(
    scene_camera_eye=dict(x=1.87, y=0.88, z=-0.64), margin=dict(l=65, r=50, b=65, t=90)
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
            ["China", "France", "United Kingdom", "United States", "Canada"],
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
