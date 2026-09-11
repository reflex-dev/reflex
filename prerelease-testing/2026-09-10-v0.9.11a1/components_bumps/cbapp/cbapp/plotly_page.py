"""rx.plotly exercised against react-plotly.js 4.1.0."""

import plotly.graph_objects as go

import reflex as rx


def make_fig(n: int) -> go.Figure:
    """Build a scatter figure with n points.

    Args:
        n: Number of points.

    Returns:
        The figure.
    """
    xs = list(range(n))
    ys = [x * x % 17 for x in xs]
    fig = go.Figure(data=[go.Scatter(x=xs, y=ys, mode="lines+markers", name="series")])
    fig.update_layout(title=f"points={n}", height=300)
    return fig


def make_select_fig() -> go.Figure:
    """Build a figure whose default drag mode is box select.

    Returns:
        The figure.
    """
    fig = go.Figure(data=[go.Scatter(x=[1, 2, 3, 4, 5], y=[2, 4, 3, 5, 1], mode="markers")])
    fig.update_layout(dragmode="select", height=280, title="select me")
    return fig


class PlotState(rx.State):
    """State for the plotly page."""

    n: int = 10
    fig: go.Figure = make_fig(10)
    layout: dict = {"title": "layout-from-state", "height": 300}
    events: list[str] = []
    last_click: str = ""
    last_hover: str = ""
    last_select: str = ""
    deselects: int = 0

    @rx.event
    def more_points(self):
        """Regenerate the figure with more points."""
        self.n += 5
        self.fig = make_fig(self.n)

    @rx.event
    def change_layout(self):
        """Change the layout dict of the second plot."""
        self.layout = {
            "title": f"layout v{self.n}",
            "height": 300,
            "paper_bgcolor": "#eef" if self.n % 10 == 0 else "#fee",
        }
        self.n += 1

    @rx.event
    def on_click(self, points):
        """Record an on_click payload.

        Args:
            points: The extracted points.
        """
        self.last_click = str(points)
        self.events.append(f"click:{points}")

    @rx.event
    def on_hover(self, points):
        """Record an on_hover payload.

        Args:
            points: The extracted points.
        """
        self.last_hover = str(points)

    @rx.event
    def on_deselect(self):
        """Record a deselect event."""
        self.deselects += 1

    @rx.event
    def on_selected(self, points):
        """Record an on_selected payload.

        Args:
            points: The extracted points.
        """
        self.last_select = str(points)


SELECT_FIG = make_select_fig()

BAR_FIG = go.Figure(data=[go.Bar(x=["a", "b", "c"], y=[3, 1, 2])])
BAR_FIG.update_layout(height=250, title="static bar")


def plotly_page() -> rx.Component:
    """The plotly page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.heading("plotly (react-plotly.js 4.1.0)", size="4"),
        rx.link("home", href="/"),
        rx.hstack(
            rx.button("more points", on_click=PlotState.more_points, id="pl-more"),
            rx.button("change layout", on_click=PlotState.change_layout, id="pl-layout"),
        ),
        rx.text("state figure + events + id/config"),
        rx.box(
            rx.plotly(
                data=PlotState.fig,
                id="pl-main",
                config={"displayModeBar": True, "staticPlot": False, "displaylogo": False},
                on_click=PlotState.on_click,
                on_hover=PlotState.on_hover,
                on_selected=PlotState.on_selected,
                use_resize_handler=True,
                width="100%",
            ),
            width="60%",
            id="pl-main-box",
        ),
        rx.text("last click: ", rx.text.strong(PlotState.last_click, id="pl-last-click")),
        rx.text("last hover: ", rx.text.strong(PlotState.last_hover, id="pl-last-hover")),
        rx.text("last select: ", rx.text.strong(PlotState.last_select, id="pl-last-select")),
        rx.text("state layout override"),
        rx.box(
            rx.plotly(data=PlotState.fig, layout=PlotState.layout, id="pl-layout-plot", width="500px"),
            id="pl-layout-box",
        ),
        rx.text("dragmode=select plot for on_selected"),
        rx.box(
            rx.plotly(
                data=SELECT_FIG,
                on_selected=PlotState.on_selected,
                on_deselect=PlotState.on_deselect,
                width="500px",
            ),
            id="pl-select-box",
        ),
        rx.text("deselects: ", rx.text.strong(PlotState.deselects, id="pl-deselects")),
        rx.text("static second plot (multiple plots on a page)"),
        rx.box(
            rx.plotly(data=BAR_FIG, id="pl-bar", use_resize_handler=False, width="400px"),
            id="pl-bar-box",
        ),
        spacing="2",
        padding="1em",
        align="start",
    )
