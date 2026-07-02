---
title: Charts and Data Visualization
meta_description: "Build interactive charts and data visualizations in Python with Reflex. Explore bar, line, area, pie, scatter, and more Recharts chart types, plus Plotly and Matplotlib — all in pure Python."
---

# Charts and Data Visualization in Reflex

Reflex makes it easy to build interactive charts and data visualizations in pure Python — no JavaScript required. The core charting components are built on [Recharts](https://recharts.org/), a popular React charting library, and Reflex also wraps [Plotly](https://plotly.com/python/) and [Matplotlib](https://matplotlib.org/) for even more chart types. This makes Reflex a natural fit for building data dashboards and analytics apps entirely in Python.

Every chart is a regular Reflex component: pass your data as a list of dictionaries (or bind it to a state var for live updates), and style it with props and `rx.color()` for automatic light/dark mode support.

## Chart Types

Reflex ships a full set of Recharts-based chart components:

- [Bar Chart](/docs/library/graphing/charts/barchart) — grouped, stacked, and horizontal bar charts
- [Line Chart](/docs/library/graphing/charts/linechart) — single and multi-line time series
- [Area Chart](/docs/library/graphing/charts/areachart) — stacked and gradient area charts
- [Pie Chart](/docs/library/graphing/charts/piechart) — pie and donut charts
- [Scatter Chart](/docs/library/graphing/charts/scatterchart) — scatter plots and bubble charts
- [Composed Chart](/docs/library/graphing/charts/composedchart) — combo charts mixing bars, lines, and areas
- [Radar Chart](/docs/library/graphing/charts/radarchart) — radar (spider) charts
- [Radial Bar Chart](/docs/library/graphing/charts/radialbarchart) — radial bar and gauge charts
- [Funnel Chart](/docs/library/graphing/charts/funnelchart) — conversion and flow funnels
- [Treemap](/docs/library/graphing/charts/treemap) — hierarchical, part-to-whole data
- [Error Bar](/docs/library/graphing/charts/errorbar) — uncertainty and variance

## Customizing Your Charts

The general graphing components let you fine-tune any chart:

- [Axis](/docs/library/graphing/general/axis) — configure the x and y axes
- [Legend](/docs/library/graphing/general/legend) — label your data series
- [Tooltip](/docs/library/graphing/general/tooltip) — show values on hover
- [Cartesian Grid](/docs/library/graphing/general/cartesiangrid) — add background gridlines
- [Brush](/docs/library/graphing/general/brush) — zoom and pan across data
- [Label](/docs/library/graphing/general/label) — annotate data points
- [Reference](/docs/library/graphing/general/reference) — draw reference lines and areas

## Other Charting Libraries

Beyond Recharts, Reflex integrates two of the most popular Python plotting libraries:

- [Plotly](/docs/library/graphing/other-charts/plotly) — interactive Plotly and Plotly Express figures
- [Pyplot](/docs/library/graphing/other-charts/pyplot) — render any Matplotlib figure in your app
