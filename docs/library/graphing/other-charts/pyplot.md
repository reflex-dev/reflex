---
components:
  - pyplot
title: Pyplot
meta_description: "Render interactive Matplotlib charts in a Python web app with Reflex. The pyplot component embeds any matplotlib.pyplot figure — line, bar, scatter, or contour — directly in the browser, with light and dark mode support and no Flask or HTML boilerplate."
---

```python exec
import reflex as rx
from reflex_pyplot import pyplot
import numpy as np
import random
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from reflex.style import toggle_color_mode
```

# Pyplot: Display Matplotlib Charts in a Python Web App

Pyplot (`reflex-pyplot`) lets you render any [Matplotlib](https://matplotlib.org/) figure inside a Reflex web app. Matplotlib's `pyplot` interface is the most popular way to create plots in Python, but on its own it renders to a static window or an image file. The `pyplot` component takes a `matplotlib.pyplot` figure and displays it directly in the browser — no Flask routes, HTML templating, or manual image encoding required — so you can turn plotting scripts and notebooks into interactive, stateful dashboards in pure Python.

## What is pyplot?

`matplotlib.pyplot` is a collection of functions that make Matplotlib behave like MATLAB: each call (`plt.plot`, `plt.scatter`, `plt.bar`, and so on) builds up a figure by adding lines, bars, labels, or legends. In a normal script you would finish with `plt.show()` to open a window. In a Reflex app you instead pass the `Figure` object to the `pyplot` component, which serves it to the frontend and re-renders it whenever your state changes.

## Installation

Install the `reflex-pyplot` package using pip.

```bash
pip install reflex-pyplot
```

## Basic Example

To display a Matplotlib plot in your app, you can use the `pyplot` component. Pass in the figure you created with Matplotlib to the `pyplot` component as a child.

```python demo exec
import matplotlib.pyplot as plt
import reflex as rx
from reflex_pyplot import pyplot
import numpy as np


def create_contour_plot():
    X, Y = np.meshgrid(np.linspace(-3, 3, 256), np.linspace(-3, 3, 256))
    Z = (1 - X / 2 + X**5 + Y**3) * np.exp(-(X**2) - Y**2)
    levels = np.linspace(Z.min(), Z.max(), 7)

    fig, ax = plt.subplots()
    ax.contourf(X, Y, Z, levels=levels)
    plt.close(fig)
    return fig


def pyplot_simple_example():
    return rx.card(
        pyplot(create_contour_plot(), width="100%", height="400px"),
        bg_color="#ffffff",
        width="100%",
    )
```

```md alert info
# You must close the figure after creating

Not closing the figure could cause memory issues.
```

## Line Plot

A line plot is the most common Matplotlib chart. Build it with `plt.subplots()` and `ax.plot()` exactly as you would in a script, then hand the figure to `pyplot` to show it in the browser.

```python demo exec
import matplotlib.pyplot as plt
import reflex as rx
from reflex_pyplot import pyplot
import numpy as np


def create_line_plot():
    x = np.linspace(0, 10, 100)
    fig, ax = plt.subplots()
    ax.plot(x, np.sin(x), label="sin(x)")
    ax.plot(x, np.cos(x), label="cos(x)")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.legend()
    plt.close(fig)
    return fig


def pyplot_line_example():
    return rx.card(
        pyplot(create_line_plot(), width="100%", height="400px"),
        bg_color="#ffffff",
        width="100%",
    )
```

## Bar Chart

The same pattern works for a Matplotlib bar chart — call `ax.bar()` with your categories and values, then render the figure with `pyplot`.

```python demo exec
import matplotlib.pyplot as plt
import reflex as rx
from reflex_pyplot import pyplot


def create_bar_chart():
    fruits = ["apples", "oranges", "bananas", "pears"]
    counts = [23, 17, 35, 29]
    fig, ax = plt.subplots()
    ax.bar(fruits, counts, color="#4e79a7")
    ax.set_ylabel("count")
    ax.set_title("Fruit inventory")
    plt.close(fig)
    return fig


def pyplot_bar_example():
    return rx.card(
        pyplot(create_bar_chart(), width="100%", height="400px"),
        bg_color="#ffffff",
        width="100%",
    )
```

## Stateful Example

Lets create a scatter plot of random data. We'll also allow the user to randomize the data and change the number of points.

In this example, we'll use a `color_mode_cond` to display the plot in both light and dark mode. We need to do this manually here because the colors are determined by the matplotlib chart and not the theme.

```python demo exec
import random
from typing import Literal
import matplotlib.pyplot as plt
import reflex as rx
from reflex_pyplot import pyplot
import numpy as np


def create_plot(theme: str, plot_data: tuple, scale: list):
    bg_color, text_color = (
        ("#1e1e1e", "white") if theme == "dark" else ("white", "black")
    )
    grid_color = "#555555" if theme == "dark" else "#cccccc"

    fig, ax = plt.subplots(facecolor=bg_color)
    ax.set_facecolor(bg_color)

    for (x, y), color in zip(plot_data, ["#4e79a7", "#f28e2b"]):
        ax.scatter(x, y, c=color, s=scale, label=color, alpha=0.6, edgecolors="none")

    ax.legend(
        loc="upper right", facecolor=bg_color, edgecolor="none", labelcolor=text_color
    )
    ax.grid(True, color=grid_color)
    ax.tick_params(colors=text_color)
    for spine in ax.spines.values():
        spine.set_edgecolor(text_color)

    for item in [ax.xaxis.label, ax.yaxis.label, ax.title]:
        item.set_color(text_color)
    plt.close(fig)

    return fig


class PyplotState(rx.State):
    num_points: int = 25
    plot_data: tuple = tuple(np.random.rand(2, 25) for _ in range(2))
    scale: list = [random.uniform(0, 100) for _ in range(25)]

    @rx.event(temporal=True, throttle=500)
    def randomize(self):
        self.plot_data = tuple(np.random.rand(2, self.num_points) for _ in range(2))
        self.scale = [random.uniform(0, 100) for _ in range(self.num_points)]

    @rx.event(temporal=True, throttle=500)
    def set_num_points(self, num_points: list[int | float]):
        self.num_points = int(num_points[0])
        yield PyplotState.randomize()

    @rx.var
    def fig_light(self) -> Figure:
        fig = create_plot("light", self.plot_data, self.scale)
        return fig

    @rx.var
    def fig_dark(self) -> Figure:
        fig = create_plot("dark", self.plot_data, self.scale)
        return fig


def pyplot_example():
    return rx.vstack(
        rx.card(
            rx.color_mode_cond(
                pyplot(PyplotState.fig_light, width="100%", height="100%"),
                pyplot(PyplotState.fig_dark, width="100%", height="100%"),
            ),
            rx.vstack(
                rx.hstack(
                    rx.button(
                        "Randomize",
                        on_click=PyplotState.randomize,
                    ),
                    rx.text("Number of Points:"),
                    rx.slider(
                        default_value=25,
                        min_=10,
                        max=100,
                        on_value_commit=PyplotState.set_num_points,
                    ),
                    width="100%",
                ),
                width="100%",
            ),
            width="100%",
        ),
        justify_content="center",
        align_items="center",
        height="100%",
        width="100%",
    )
```

## Common Questions

### How do I display a Matplotlib plot in a website?

Create the figure with `matplotlib.pyplot` as usual, then pass the `Figure` object to Reflex's `pyplot` component. Reflex renders it in the browser for you — you don't need Flask, a REST endpoint, or manual base64 image encoding.

### Can I make Matplotlib interactive in Reflex?

Yes. Compute the figure inside an `rx.var` that depends on your state, then update the state from buttons, sliders, or other events. The chart re-renders automatically, as shown in the Stateful Example above.

### Do I need to call `plt.show()`?

No. `plt.show()` opens a desktop window and is not used in a web app. Instead, return the figure to the `pyplot` component and call `plt.close(fig)` after creating it to free memory.
