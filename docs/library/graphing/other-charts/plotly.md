---
components:
  - rx.plotly
title: Plotly
meta_description: "Use Plotly in Python with Reflex. The rx.plotly component renders interactive Plotly and Plotly Express figures — line charts, scatter plots, heatmaps, and histograms — in your web app, all in pure Python."
---

# Plotly in Python: Interactive Charts with Reflex

```python exec
import reflex as rx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
```

[Plotly](https://plotly.com/graphing-libraries/) is a popular Python graphing library for creating interactive, publication-quality charts. Reflex wraps it with the `rx.plotly` component so you can embed any Plotly or Plotly Express figure — line charts, scatter plots, histograms, heatmaps, or 3D surface plots — directly into a Python web app with no JavaScript. Because Reflex compiles to a full-stack web app, these charts stay interactive in the browser and can update live from your app state.

```md alert info
# When integrating Plotly graphs into your UI code, note that the method for displaying the graph differs from a regular Python script. Instead of using `fig.show()`, use `rx.plotly(data=fig)` within your UI code to ensure the graph is properly rendered and displayed within the user interface
```

## Basic Example

Let's create a line graph of life expectancy in Canada.

```python demo exec
import plotly.express as px

df = px.data.gapminder().query("country=='Canada'")
fig = px.line(df, x="year", y="lifeExp", title="Life expectancy in Canada")


def line_chart():
    return rx.center(
        rx.plotly(data=fig),
    )
```

## Plotly Express Chart Types

[Plotly Express](https://plotly.com/python/plotly-express/) (`plotly.express`, imported as `px`) builds common chart types in a single line of Python, and every figure renders in Reflex with `rx.plotly`.

### Bar Chart

Create a Plotly Express bar chart with `px.bar`:

```python demo exec
oceania = px.data.gapminder().query("continent == 'Oceania'")
bar_fig = px.bar(
    oceania, x="year", y="pop", color="country", title="Population of Oceania"
)


def plotly_bar_chart():
    return rx.center(rx.plotly(data=bar_fig))
```

### Scatter Plot

Create a Plotly scatter plot with `px.scatter`:

```python demo exec
iris = px.data.iris()
scatter_fig = px.scatter(
    iris,
    x="sepal_width",
    y="sepal_length",
    color="species",
    title="Iris sepal dimensions",
)


def plotly_scatter_plot():
    return rx.center(rx.plotly(data=scatter_fig))
```

### Pie Chart

Create a Plotly pie chart with `px.pie`:

```python demo exec
tips = px.data.tips()
pie_fig = px.pie(tips, values="tip", names="day", title="Tips by day")


def plotly_pie_chart():
    return rx.center(rx.plotly(data=pie_fig))
```

### Heatmap

Create a Plotly heatmap with `px.density_heatmap`:

```python demo exec
tips_data = px.data.tips()
heatmap_fig = px.density_heatmap(
    tips_data, x="total_bill", y="tip", title="Bill vs tip density heatmap"
)


def plotly_heatmap():
    return rx.center(rx.plotly(data=heatmap_fig))
```

### Histogram

Create a Plotly histogram with `px.histogram`:

```python demo exec
hist_data = px.data.tips()
histogram_fig = px.histogram(
    hist_data, x="total_bill", nbins=20, title="Distribution of total bills"
)


def plotly_histogram():
    return rx.center(rx.plotly(data=histogram_fig))
```

### Box Plot

Create a Plotly box plot with `px.box`:

```python demo exec
box_data = px.data.tips()
box_fig = px.box(box_data, x="day", y="total_bill", title="Total bill by day")


def plotly_box_plot():
    return rx.center(rx.plotly(data=box_fig))
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

## 3D graphing example

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
