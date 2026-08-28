"""Test app for the devtools_perf cluster: React DevTools naming (#6945) and
owner-stack perf (#6905) on reflex 0.9.9a1.

Pages:
  /            index: memo components, custom component classes, nav links
  /charts      plotly (NoSSRComponent -> ClientSide(Plot)) + interactions
  /heavy       ~1500 statically compiled elements, perf-navigation target
  /blog/[slug] dynamic route page (displayName Component(blog/[slug]))
"""

import random

import plotly.graph_objects as go

import reflex as rx


class AppState(rx.State):
    """Root app state."""

    clicks: int = 0
    last_action: str = ""

    @rx.event
    def bump(self):
        """Increment the click counter."""
        self.clicks += 1
        self.last_action = "bump"


class ChartState(AppState):
    """Nested substate carrying plotly data."""

    points: list[float] = [2.0, 4.0, 8.0, 16.0, 10.0, 6.0]

    @rx.event
    def shuffle(self):
        """Randomize the chart data."""
        self.points = [round(random.uniform(1, 20), 1) for _ in range(6)]
        self.last_action = "shuffle"

    @rx.var
    def figure(self) -> go.Figure:
        """Build a bar chart from points.

        Returns:
            The plotly figure.
        """
        fig = go.Figure(data=[go.Bar(x=list("abcdef"), y=self.points)])
        fig.update_layout(
            title="DevTools perf test chart", width=600, height=380, margin=dict(t=40)
        )
        return fig

    @rx.var
    def total(self) -> float:
        """Sum of points.

        Returns:
            The sum.
        """
        return round(sum(self.points), 1)


class BlogState(AppState):
    """Nested substate for the dynamic blog route."""

    view_counts: dict[str, int] = {}

    @rx.event
    def record_view(self):
        """Record a view of the current slug."""
        slug = self.slug
        if slug:
            self.view_counts[slug] = self.view_counts.get(slug, 0) + 1

    @rx.var
    def current_views(self) -> int:
        """Views of the current slug.

        Returns:
            The view count.
        """
        return self.view_counts.get(self.slug, 0)


class OwnerProbe(rx.Component):
    """Local component that records React.captureOwnerStack() during render."""

    library = "$/public/owner_probe"
    tag = "OwnerProbe"

    marker: rx.Var[str]


owner_probe = OwnerProbe.create


class StatCard(rx.el.Div):
    """Custom component class: a titled stat card."""

    @classmethod
    def create(cls, title: str, value, **props) -> rx.Component:
        """Create the stat card.

        Args:
            title: Card title.
            value: Value to display (may be a Var).
            **props: Forwarded div props.

        Returns:
            The component.
        """
        props.setdefault("style", {"border": "1px solid #ccc", "padding": "8px"})
        return super().create(
            rx.el.h3(title),
            rx.el.p(value, class_name="stat-value"),
            **props,
        )


class PulseBadge(rx.el.Span):
    """Custom component class: badge showing the last action."""

    @classmethod
    def create(cls, **props) -> rx.Component:
        """Create the badge.

        Args:
            **props: Forwarded span props.

        Returns:
            The component.
        """
        return super().create(
            "last: ", AppState.last_action, id="pulse-badge", **props
        )


@rx.memo
def counter_panel(label: rx.Var[str], value: rx.Var[int]) -> rx.Component:
    """Memoized counter panel."""
    return rx.el.div(
        rx.el.strong(label),
        rx.el.span(value, class_name="panel-value"),
        class_name="counter-panel",
    )


@rx.memo
def nav_bar() -> rx.Component:
    """Memoized navigation bar."""
    return rx.el.nav(
        rx.link("home", href="/", id="nav-home"),
        " | ",
        rx.link("charts", href="/charts", id="nav-charts"),
        " | ",
        rx.link("heavy", href="/heavy", id="nav-heavy"),
        " | ",
        rx.link("blog", href="/blog/hello-world", id="nav-blog"),
        style={"gap": "8px"},
    )


def index() -> rx.Component:
    """Index page."""
    return rx.el.main(
        owner_probe(marker="index"),
        nav_bar(),
        rx.el.h1("DevTools naming test app"),
        StatCard.create("Clicks", AppState.clicks, id="clicks-card"),
        StatCard.create("Chart total", ChartState.total, id="total-card"),
        PulseBadge.create(),
        counter_panel(label="clicks", value=AppState.clicks),
        rx.el.button("bump", on_click=AppState.bump, id="bump-btn"),
        rx.upload(rx.text("drop files"), id="upload-zone"),
        id="page-root",
    )


def charts() -> rx.Component:
    """Charts page with a NoSSR plotly component."""
    return rx.el.main(
        owner_probe(marker="charts"),
        nav_bar(),
        rx.el.h1("Charts"),
        rx.plotly(data=ChartState.figure, id="the-plot"),
        rx.el.p("total: ", ChartState.total, id="chart-total"),
        rx.el.button("shuffle", on_click=ChartState.shuffle, id="shuffle-btn"),
        counter_panel(label="clicks", value=AppState.clicks),
        id="page-root",
    )


def heavy() -> rx.Component:
    """Statically large page: perf target for dev-mode navigation."""
    sections = [
        rx.el.section(
            rx.el.h2(f"Section {s}"),
            *[
                rx.el.div(
                    rx.el.span(f"item {s}-{i}", class_name="cell-label"),
                    rx.el.small(f"meta {i}"),
                    class_name="cell",
                )
                for i in range(120)
            ],
            class_name="heavy-section",
        )
        for s in range(12)
    ]
    return rx.el.main(
        owner_probe(marker="heavy"),
        nav_bar(),
        rx.el.h1("Heavy page", id="heavy-title"),
        counter_panel(label="clicks", value=AppState.clicks),
        *sections,
        id="page-root",
    )


def blog_post() -> rx.Component:
    """Dynamic blog page."""
    return rx.el.main(
        owner_probe(marker="blog"),
        nav_bar(),
        rx.el.h1("Blog: ", BlogState.slug, id="blog-title"),
        rx.el.p("views this session: ", BlogState.current_views, id="blog-views"),
        counter_panel(label="clicks", value=AppState.clicks),
        rx.el.button("bump", on_click=AppState.bump, id="bump-btn"),
        rx.link("next post", href="/blog/second-post", id="next-post-link"),
        id="page-root",
    )


app = rx.App()
app.add_page(index, route="/", title="devtools index")
app.add_page(charts, route="/charts", title="charts")
app.add_page(heavy, route="/heavy", title="heavy")
app.add_page(
    blog_post,
    route="/blog/[slug]",
    title="blog",
    on_load=BlogState.record_view,
)
