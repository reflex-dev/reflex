"""Welcome to Reflex! This file outlines the steps to create a basic app."""
from rxconfig import config
import matplotlib.pyplot as plt
import mpld3
import reflex as rx

docs_url = "https://reflex.dev/docs/getting-started/introduction"
filename = f"{config.app_name}/{config.app_name}.py"

import altair as alt
import numpy as np
import pandas as pd

# Compute x^2 + y^2 across a 2D grid
x, y = np.meshgrid(range(-5, 5), range(-5, 5))
z = x ** 2 + y ** 2

# Convert this grid to columnar data expected by Altair
source = pd.DataFrame({'x': x.ravel(),
                     'y': y.ravel(),
                     'z': z.ravel()})

class State(rx.State):
    """The app state."""
    chart: alt.Chart = alt.Chart(source).mark_rect().encode(
        x='x:O',
        y='y:O',
        color='z:Q'
    )

    chart2: alt.Chart = alt.Chart(source).mark_line().transform_calculate(
        sin='sin(datum.x)',
        cos='cos(datum.x)'
    ).transform_fold(
        ['sin', 'cos']
    ).encode(
        x='x:Q',
        y='value:Q',
        color='key:N'
    )

 
def index() -> rx.Component:
    return rx.vstack(
        rx.heading("Welcome to Reflex!"),
        rx.divider(),
        rx.box(
        rx.altair(fig=State.chart2),
        ),
        width="100%",
    )    
 

# Add state and page to the app.
app = rx.App()
app.add_page(index)
app.compile() 
     