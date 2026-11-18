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

To connect chart selections to other charts and a table, see the XY-based [linked charts and cross-filtering tutorial](/docs/getting-started/linked-charts-tutorial/). It demonstrates shared state, stable record IDs, empty results, and reset behavior. The example's selection handler is specific to XY; Plotly selection payloads require a different handler.

Let's create a line graph of life expectancy in Canada.

```python demo exec defer
import plotly.express as px

df = px.data.gapminder().query("country=='Canada'")
fig = px.line(df, x="year", y="lifeExp", title="Life expectancy in Canada")


def line_chart():
    return rx.center(
        rx.plotly(width="100%", data=fig),
    )
```

```python test
def test_line_chart_shows_title_and_axes(demo):
    expect(demo.locator(".gtitle")).to_have_text("Life expectancy in Canada")
    expect(demo.locator(".g-xtitle")).to_have_text("year")
    expect(demo.locator(".g-ytitle")).to_have_text("lifeExp")
    expect(demo.locator(".scatterlayer .trace")).to_have_count(1)
```

## Plotly Express Chart Types

[Plotly Express](https://plotly.com/python/plotly-express/) (`plotly.express`, imported as `px`) builds common chart types in a single line of Python, and every figure renders in Reflex with `rx.plotly`.

### Bar Chart

Create a Plotly Express bar chart with `px.bar`:

```python demo exec defer
oceania = px.data.gapminder().query("continent == 'Oceania'")
bar_fig = px.bar(
    oceania, x="year", y="pop", color="country", title="Population of Oceania"
)


def plotly_bar_chart():
    return rx.center(rx.plotly(width="100%", data=bar_fig))
```

```python test
def test_bar_chart_has_a_legend_per_country(demo):
    expect(demo.locator(".gtitle")).to_have_text("Population of Oceania")
    expect(demo.locator(".legendtext")).to_have_text(["Australia", "New Zealand"])
```

### Scatter Plot

Create a Plotly scatter plot with `px.scatter`:

```python demo exec defer
iris = px.data.iris()
scatter_fig = px.scatter(
    iris,
    x="sepal_width",
    y="sepal_length",
    color="species",
    title="Iris sepal dimensions",
)


def plotly_scatter_plot():
    return rx.center(rx.plotly(width="100%", data=scatter_fig))
```

```python test
def test_scatter_plot_colors_by_species(demo):
    expect(demo.locator(".gtitle")).to_have_text("Iris sepal dimensions")
    expect(demo.locator(".legendtext")).to_have_text([
        "setosa",
        "versicolor",
        "virginica",
    ])
    expect(demo.locator(".scatterlayer .point")).to_have_count(150)
```

### Pie Chart

Create a Plotly pie chart with `px.pie`:

```python demo exec defer
tips = px.data.tips()
pie_fig = px.pie(tips, values="tip", names="day", title="Tips by day")


def plotly_pie_chart():
    return rx.center(rx.plotly(width="100%", data=pie_fig))
```

```python test
def test_pie_chart_has_a_slice_per_day(demo):
    expect(demo.locator(".gtitle")).to_have_text("Tips by day")
    expect(demo.locator(".slice")).to_have_count(4)
    expect(demo.locator(".legendtext")).to_have_text([
        "Sat",
        "Sun",
        "Thur",  # codespell:ignore
        "Fri",
    ])
```

### Heatmap

Create a Plotly heatmap with `px.density_heatmap`:

```python demo exec defer
tips_data = px.data.tips()
heatmap_fig = px.density_heatmap(
    tips_data, x="total_bill", y="tip", title="Bill vs tip density heatmap"
)


def plotly_heatmap():
    return rx.center(rx.plotly(width="100%", data=heatmap_fig))
```

```python test
def test_heatmap_renders(demo):
    expect(demo.locator(".gtitle")).to_have_text("Bill vs tip density heatmap")
    expect(demo.locator(".heatmaplayer image")).to_have_count(1)
    expect(demo.locator(".g-xtitle")).to_have_text("total_bill")
```

### Histogram

Create a Plotly histogram with `px.histogram`:

```python demo exec defer
hist_data = px.data.tips()
histogram_fig = px.histogram(
    hist_data, x="total_bill", nbins=20, title="Distribution of total bills"
)


def plotly_histogram():
    return rx.center(rx.plotly(width="100%", data=histogram_fig))
```

```python test
def test_histogram_renders(demo):
    expect(demo.locator(".gtitle")).to_have_text("Distribution of total bills")
    expect(demo.locator(".barlayer .trace")).to_have_count(1)
    expect(demo.locator(".g-ytitle")).to_have_text("count")
```

### Box Plot

Create a Plotly box plot with `px.box`:

```python demo exec defer
box_data = px.data.tips()
box_fig = px.box(box_data, x="day", y="total_bill", title="Total bill by day")


def plotly_box_plot():
    return rx.center(rx.plotly(width="100%", data=box_fig))
```

```python test
def test_box_plot_has_a_box_per_day(demo):
    expect(demo.locator(".gtitle")).to_have_text("Total bill by day")
    expect(demo.locator(".xtick text")).to_have_text([
        "Sun",
        "Sat",
        "Thur",  # codespell:ignore
        "Fri",
    ])
```

### Bubble Chart

A bubble chart is a scatter plot in which a third dimension of the data is shown through the size of the markers. Create one with `px.scatter` by passing a column to the `size` argument:

```python demo exec defer
gapminder = px.data.gapminder()
bubble_fig = px.scatter(
    gapminder.query("year==2007"),
    x="gdpPercap",
    y="lifeExp",
    size="pop",
    color="continent",
    hover_name="country",
    log_x=True,
    size_max=60,
    title="GDP per capita vs life expectancy (2007)",
)


def plotly_bubble_chart():
    return rx.center(rx.plotly(width="100%", data=bubble_fig))
```

```python test
def test_bubble_chart_colors_by_continent(demo):
    expect(demo.locator(".gtitle")).to_have_text(
        "GDP per capita vs life expectancy (2007)"
    )
    expect(demo.locator(".legendtext")).to_have_text([
        "Asia",
        "Europe",
        "Africa",
        "Americas",
        "Oceania",
    ])
```

### Gantt Chart

A Gantt chart is a type of bar chart that illustrates a project schedule: tasks are listed on the vertical axis, time intervals on the horizontal axis, and the width of each bar shows the duration of the activity. Create one with `px.timeline`:

```python demo exec defer
tasks = pd.DataFrame([
    dict(Task="Job A", Start="2009-01-01", Finish="2009-02-28"),
    dict(Task="Job B", Start="2009-03-05", Finish="2009-04-15"),
    dict(Task="Job C", Start="2009-02-20", Finish="2009-05-30"),
])
gantt_fig = px.timeline(tasks, x_start="Start", x_end="Finish", y="Task")
# Reverse the y-axis so tasks are listed top-down instead of bottom-up.
gantt_fig.update_yaxes(autorange="reversed")


def plotly_gantt_chart():
    return rx.center(rx.plotly(width="100%", data=gantt_fig))
```

```python test
def test_gantt_chart_lists_tasks_top_down(demo):
    ticks = demo.locator(".ytick text")
    expect(ticks).to_have_text(["Job C", "Job B", "Job A"])
    expect(demo.locator(".barlayer .point")).to_have_count(3)
    # The reversed axis puts the first task at the top.
    job_a, job_c = ticks.last.bounding_box(), ticks.first.bounding_box()
    assert job_a["y"] < job_c["y"]
```

### Sunburst Chart

Sunburst charts visualize hierarchical data spanning outwards radially from root to leaves: the root sits at the center and children are added to the outer rings. Create one with `px.sunburst`, defining the hierarchy with `names` and `parents`:

```python demo exec defer
family = dict(
    character=["Eve", "Cain", "Seth", "Enos", "Noam", "Abel", "Awan", "Enoch", "Azura"],
    parent=["", "Eve", "Eve", "Seth", "Seth", "Eve", "Eve", "Awan", "Eve"],
    value=[10, 14, 12, 10, 2, 6, 6, 4, 4],
)
sunburst_fig = px.sunburst(family, names="character", parents="parent", values="value")


def plotly_sunburst_chart():
    return rx.center(rx.plotly(width="100%", data=sunburst_fig))
```

```python test
def test_sunburst_has_a_slice_per_character(demo):
    expect(demo.locator(".slice")).to_have_count(9)
    expect(demo.locator(".slicetext").first).to_have_text("Eve")
```

### Funnel Chart

Funnel charts represent data as it moves through the stages of a business process, making them a common Business Intelligence tool for spotting where a process loses volume. Create one with `px.funnel`:

```python demo exec defer
funnel_data = dict(
    number=[39, 27.4, 20.6, 11, 2],
    stage=[
        "Website visit",
        "Downloads",
        "Potential customers",
        "Requested price",
        "Invoice sent",
    ],
)
funnel_fig = px.funnel(funnel_data, x="number", y="stage")


def plotly_funnel_chart():
    return rx.center(rx.plotly(width="100%", data=funnel_fig))
```

```python test
def test_funnel_lists_each_stage(demo):
    expect(demo.locator(".ytick text")).to_have_text([
        "Invoice sent",
        "Requested price",
        "Potential customers",
        "Downloads",
        "Website visit",
    ])
    expect(demo.locator(".funnellayer .point")).to_have_count(5)
```

## Locale Configuration

Use `locale` to localize Plotly number/date formatting and modebar labels:

```python demo exec defer
df = px.data.gapminder().query("country=='Canada'")
fig = px.line(df, x="year", y="lifeExp", title="Life expectancy in Canada")


def localized_line_chart():
    return rx.center(
        rx.plotly(
            width="100%",
            data=fig,
            locale="de",
        ),
    )
```

```python test
def test_locale_translates_the_modebar(demo):
    expect(demo.locator(".gtitle")).to_have_text("Life expectancy in Canada")
    expect(demo.locator(".modebar-btn").first).to_have_attribute(
        "data-title",
        "Graphen als PNG herunterladen",  # codespell:ignore
    )
```

You can still pass `config`; when both are provided, `locale=` is applied as the final locale value.

## 3D graphing example

Let's create a 3D surface plot of Mount Bruno. This is a slightly more complicated example, but it wraps in Reflex using the same method. In fact, you can wrap any figure using the same approach.

```python demo exec defer
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
        rx.plotly(width="100%", data=fig),
    )
```

```python test
def test_surface_plot_renders_in_3d(demo):
    expect(demo.locator(".gl-container canvas")).to_have_count(1)
    expect(demo.locator(".js-plotly-plot")).to_have_count(1)
```

📊 **Dataset source:** [mt_bruno_elevation.csv](https://raw.githubusercontent.com/plotly/datasets/master/api_docs/mt_bruno_elevation.csv)

## Financial Charts

### Candlestick Chart

The candlestick chart is a financial chart describing the open, high, low, and close values for a given x coordinate (most likely time): boxes show the spread between open and close, and lines show the spread between low and high. Create one with `go.Candlestick`:

```python demo exec defer
candles = pd.DataFrame({
    "Date": [
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
        "2024-01-08",
        "2024-01-09",
    ],
    "Open": [187.15, 184.22, 182.15, 181.99, 182.09, 183.92],
    "High": [188.44, 185.88, 183.09, 182.76, 185.60, 185.15],
    "Low": [183.89, 183.43, 180.88, 180.17, 181.50, 182.73],
    "Close": [185.64, 184.25, 181.91, 181.18, 185.56, 185.14],
})
candlestick_fig = go.Figure(
    data=[
        go.Candlestick(
            x=candles["Date"],
            open=candles["Open"],
            high=candles["High"],
            low=candles["Low"],
            close=candles["Close"],
        )
    ]
)
candlestick_fig.update_layout(
    title=dict(text="AAPL Stock Price"),
    yaxis=dict(title=dict(text="AAPL Stock")),
)


def candlestick_chart():
    return rx.center(rx.plotly(width="100%", data=candlestick_fig))
```

```python test
def test_candlestick_chart_shows_stock_prices(demo):
    expect(demo.locator(".gtitle")).to_have_text("AAPL Stock Price")
    expect(demo.locator(".g-ytitle")).to_have_text("AAPL Stock")
    # Rising and falling days are drawn as separate traces.
    expect(demo.locator(".boxlayer .trace")).to_have_count(2)
```

### Waterfall Chart

The waterfall chart visualizes how an initial value is affected by a series of positive and negative changes — for example, a profit and loss statement. Create one with `go.Waterfall`, marking each value as `"relative"` or `"total"` via the `measure` argument:

```python demo exec defer
waterfall_fig = go.Figure(
    go.Waterfall(
        name="20",
        orientation="v",
        measure=["relative", "relative", "total", "relative", "relative", "total"],
        x=[
            "Sales",
            "Consulting",
            "Net revenue",
            "Purchases",
            "Other expenses",
            "Profit before tax",
        ],
        textposition="outside",
        text=["+60", "+80", "", "-40", "-20", "Total"],
        y=[60, 80, 0, -40, -20, 0],
        connector={"line": {"color": "rgb(63, 63, 63)"}},
    )
)
waterfall_fig.update_layout(title="Profit and loss statement 2018", showlegend=True)


def waterfall_chart():
    return rx.center(rx.plotly(width="100%", data=waterfall_fig))
```

```python test
def test_waterfall_labels_each_step(demo):
    expect(demo.locator(".gtitle")).to_have_text("Profit and loss statement 2018")
    expect(demo.locator(".xtick text")).to_have_text([
        "Sales",
        "Consulting",
        "Net revenue",
        "Purchases",
        "Other expenses",
        "Profit before tax",
    ])
    expect(demo.locator(".bartext")).to_have_text(["+60", "+80", "-40", "-20", "Total"])
```

### Bullet Chart

The bullet chart, designed by Stephen Few as a compact replacement for dashboard gauges and meters, combines a quantitative bar, qualitative ranges (steps), and a performance threshold line in one simple layout. Build one with `go.Indicator` using the `"bullet"` gauge shape:

```python demo exec defer
bullet_fig = go.Figure(
    go.Indicator(
        mode="number+gauge+delta",
        value=180,
        delta={"reference": 200},
        domain={"x": [0.25, 1], "y": [0.4, 0.6]},
        title={"text": "Revenue"},
        gauge={
            "shape": "bullet",
            "axis": {"range": [None, 300]},
            "threshold": {
                "line": {"color": "black", "width": 2},
                "thickness": 0.75,
                "value": 170,
            },
            "steps": [
                {"range": [0, 150], "color": "gray"},
                {"range": [150, 250], "color": "lightgray"},
            ],
            "bar": {"color": "black"},
        },
    )
).update_layout(height=250)


def bullet_chart():
    return rx.center(rx.plotly(width="100%", data=bullet_fig))
```

```python test
def test_bullet_gauge_shows_value_and_delta(demo):
    expect(demo.locator(".indicatorlayer .title")).to_have_text("Revenue")
    expect(demo.locator(".indicatorlayer .number")).to_have_text("180")
    expect(demo.locator(".indicatorlayer .delta")).to_have_text("▼−20")
```

## Statistical Charts

### Continuous Error Bands

Continuous error bands represent error or uncertainty as a shaded region around a main trace, rather than as discrete whisker-like error bars. Build one with `go.Scatter` by drawing the main line, then a second trace that walks the upper bound forward and the lower bound in reverse, filled with `fill="toself"`:

```python demo exec defer
band_x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
band_y = [1, 2, 7, 4, 5, 6, 7, 8, 9, 10]
band_y_upper = [2, 3, 8, 5, 6, 7, 8, 9, 10, 11]
band_y_lower = [0, 1, 5, 3, 4, 5, 6, 7, 8, 9]

error_band_fig = go.Figure([
    go.Scatter(
        x=band_x,
        y=band_y,
        line=dict(color="rgb(0,100,80)"),
        mode="lines",
    ),
    go.Scatter(
        x=band_x + band_x[::-1],  # x, then x reversed
        y=band_y_upper + band_y_lower[::-1],  # upper, then lower reversed
        fill="toself",
        fillcolor="rgba(0,100,80,0.2)",
        line=dict(color="rgba(255,255,255,0)"),
        hoverinfo="skip",
        showlegend=False,
    ),
])


def continuous_error_bands_chart():
    return rx.center(rx.plotly(width="100%", data=error_band_fig))
```

```python test
def test_error_band_draws_line_and_band(demo):
    expect(demo.locator(".scatterlayer .trace")).to_have_count(2)
    expect(demo.locator(".scatterlayer .trace .fills path")).to_have_count(1)
```

## Maps

### Geo Map

Geo maps are outline-based maps drawn from geographic features rather than map tiles. Figures created with `px.scatter_geo`, `px.line_geo`, or `px.choropleth` — or containing `go.Scattergeo` or `go.Choropleth` traces — store their map configuration in the figure's `layout.geo` object, which you can adjust with `update_geos`:

```python demo exec defer
geo_fig = go.Figure(go.Scattergeo())
geo_fig.update_geos(
    visible=False,
    resolution=50,
    showlakes=True,
    lakecolor="Blue",
    showrivers=True,
    rivercolor="Blue",
)
geo_fig.update_layout(height=300, margin={"r": 0, "t": 0, "l": 0, "b": 0})


def geo_map_chart():
    return rx.center(rx.plotly(width="100%", data=geo_fig))
```

```python test
def test_geo_map_renders_rivers_and_lakes(demo):
    expect(demo.locator(".geo .layer.lakes path")).to_have_count(1)
    expect(demo.locator(".geo .layer.rivers path")).to_have_count(1)
```

### Scatter Map

Scatter maps plot markers on a tile-based map, sized and colored by your data — useful for visualizing geographic point data like vehicle locations or store sites. Create one with `px.scatter_map` (or a `go.Scattermap` trace for lower-level control):

```python demo exec defer
carshare = px.data.carshare()
map_fig = px.scatter_map(
    carshare,
    lat="centroid_lat",
    lon="centroid_lon",
    color="peak_hour",
    size="car_hours",
    color_continuous_scale=px.colors.cyclical.IceFire,
    size_max=15,
    zoom=10,
)


def scatter_map_chart():
    return rx.center(rx.plotly(width="100%", data=map_fig))
```

```python test
def test_scatter_map_renders_a_map_canvas(demo):
    expect(demo.locator(".maplibregl-canvas")).to_have_count(1)
    expect(demo.locator(".colorbar .cbtitle")).to_have_text("peak_hour")
```

## Tables and Diagrams

### Table

Plotly can also render data as an interactive table. Create one with `go.Table`, passing column headers to `header` and column data to `cells`:

```python demo exec defer
table_fig = go.Figure(
    data=[
        go.Table(
            header=dict(values=["A Scores", "B Scores"]),
            cells=dict(values=[[100, 90, 80, 90], [95, 85, 75, 95]]),
        )
    ]
)


def plotly_table():
    return rx.center(rx.plotly(width="100%", data=table_fig))
```

```python test
def test_table_shows_headers_and_scores(demo):
    expect(demo.locator(".table-control-view")).to_have_count(1)
    expect(demo.locator(".cell-text")).to_have_text([
        "100",
        "90",
        "80",
        "90",
        "A Scores",
        "95",
        "85",
        "75",
        "95",
        "B Scores",
    ])
```

### Sankey Diagram

A Sankey diagram is a flow diagram in which the width of the arrows is proportional to the flow quantity. Create one with `go.Sankey`, defining the nodes and the links between them by index:

```python demo exec defer
sankey_fig = go.Figure(
    data=[
        go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color="black", width=0.5),
                label=["A1", "A2", "B1", "B2", "C1", "C2"],
                color="blue",
            ),
            link=dict(
                # Indices correspond to node labels, e.g. A1, A2, B1, ...
                source=[0, 1, 0, 2, 3, 3],
                target=[2, 3, 3, 4, 4, 5],
                value=[8, 4, 2, 8, 4, 2],
            ),
        )
    ]
)
sankey_fig.update_layout(title_text="Basic Sankey Diagram", font_size=10)


def plotly_sankey_diagram():
    return rx.center(rx.plotly(width="100%", data=sankey_fig))
```

```python test
def test_sankey_diagram_labels_nodes(demo):
    expect(demo.locator(".gtitle")).to_have_text("Basic Sankey Diagram")
    expect(demo.locator(".sankey-node .node-label")).to_have_text([
        "A1",
        "A2",
        "B1",
        "B2",
        "C1",
        "C2",
    ])
    expect(demo.locator(".sankey-link")).to_have_count(6)
```

## 3D Charts

### 3D Scatter Plot

3D scatter plots show the relationship between three variables at once, with an optional fourth encoded as color. Create one with `px.scatter_3d`:

```python demo exec defer
iris_3d = px.data.iris()
scatter_3d_fig = px.scatter_3d(
    iris_3d,
    x="sepal_length",
    y="sepal_width",
    z="petal_width",
    color="species",
)


def scatter_3d_chart():
    return rx.center(rx.plotly(width="100%", data=scatter_3d_fig))
```

```python test
def test_3d_scatter_plot_has_species_legend(demo):
    expect(demo.locator(".gl-container canvas")).to_have_count(1)
    expect(demo.locator(".legendtext")).to_have_text([
        "setosa",
        "versicolor",
        "virginica",
    ])
```

### 3D Axis

3D figures place their traces in a scene, and each scene axis is configured through the figure's `scene` layout — set `nticks`, `range`, or axis titles per axis. This example renders a `go.Mesh3d` cloud with custom tick counts and ranges on all three axes:

```python demo exec defer
import numpy as np

np.random.seed(1)
N = 70

mesh_fig = go.Figure(
    data=[
        go.Mesh3d(
            x=(70 * np.random.randn(N)),
            y=(55 * np.random.randn(N)),
            z=(40 * np.random.randn(N)),
            opacity=0.5,
            color="rgba(244,22,100,0.6)",
        )
    ]
)
mesh_fig.update_layout(
    scene=dict(
        xaxis=dict(nticks=4, range=[-100, 100]),
        yaxis=dict(nticks=4, range=[-50, 100]),
        zaxis=dict(nticks=4, range=[-100, 100]),
    ),
    margin=dict(r=20, l=10, b=10, t=10),
)


def axis_3d_chart():
    return rx.center(rx.plotly(width="100%", data=mesh_fig))
```

```python test
def test_3d_mesh_renders(demo):
    expect(demo.locator(".gl-container canvas")).to_have_count(1)
    expect(demo.locator(".js-plotly-plot")).to_have_count(1)
```

## Plot as State Var

If the figure is set as a state var, it can be updated during run time.

```python demo exec defer
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
            width="100%",
            data=PlotlyState.figure,
            on_mount=PlotlyState.create_figure,
        ),
    )
```

```python test
def test_selecting_a_country_redraws_the_chart(demo, page):
    title = demo.locator(".gtitle")
    expect(title).to_have_text("Life expectancy in Canada")
    demo.get_by_role("combobox").click()
    page.get_by_role("option", name="France").click()
    expect(title).to_have_text("Life expectancy in France")
```

## Adding Styles and Layouts

Use `update_layout()` method to update the layout of your chart. Checkout [Plotly Layouts](https://plotly.com/python/reference/layout/) for all layouts props.

```md alert info
Note that the width and height props are not recommended to ensure the plot remains size responsive to its container. The size of plot will be determined by it's outer container.
```

```python demo exec defer
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
        rx.plotly(width="100%", data=fig_1),
        width="100%",
        height="100%",
    )
```

```python test
def test_styled_chart_uses_custom_background(demo):
    expect(demo.locator(".gtitle")).to_have_text("Life expectancy in Canada")
    expect(demo.locator(".gtitle")).to_have_css("font-size", "25px")
    expect(demo.locator(".plot .bg, .bglayer .bg").first).to_have_css(
        "fill", "rgb(195, 215, 247)"
    )
```
