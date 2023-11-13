"""Welcome to Reflex! This file outlines the steps to create a basic app."""
import reflex as rx
from datetime import datetime
from sqlalchemy import Column, JSON, func
from sqlmodel import Field
from .graphing import lighthouse_graph, performance_graph
from .styles import BASE_STYLE, c

# Define the model reflecting your schema
class Benchmarks(rx.Model, table=True):
    commit_sha: str
    lighthouse: dict = Field(default={}, sa_column=Column(JSON))
    performance: dict = Field(default={}, sa_column=Column(JSON))
    time: datetime
    pr_title: str


class State(rx.State):
    search_term: str  # This will be used to filter results based on user input
    chart_data: list[dict]  # This will store the transformed data for the chart
    pr_titles: list[str]  # This will store the unique pr_titles
    url: str = ""
    test: str = "test_mean_import_time"
    results: list[Benchmarks]

    lighthouse = []
    performance = []

    lighthouse_graph_state = False
    performance_graph_state = False

    average_performance_score = 0
    average_accessibility_score = 0
    average_best_practices_score = 0
    average_seo_score = 0
    average_pwa_score = 0

    def search_performance_data(self):
        with rx.session() as session:
            self.results = results = (
                session.query(Benchmarks)
                .filter(Benchmarks.pr_title.contains(self.search_term))
                .all()
            )

            self.pr_titles = set(
                [
                    benchmark.pr_title
                    for benchmark in results
                    if benchmark.pr_title.strip()
                ]
            )

        yield State.get_performance_data(self.test)
        yield State.get_light_house_data(self.url)

    def get_light_house_data(self, url: str):
        lighthouse = []
        if url == "/":
            url = ""
        for benchmark in self.results:
            for key, value in benchmark:
                if key == "lighthouse":
                    for page in value:
                        if page == url:
                            value[page]["time"] = benchmark.time
                            lighthouse.append(value[page])
        self.lighthouse = lighthouse
        self.lighthouse_graph_state = True

        # Get the average performance score
        self.average_performance_score = round(
            sum([page["performance_score"] for page in lighthouse]) / len(lighthouse), 2
        )
        self.average_accessibility_score = round(
            sum([page["accessibility_score"] for page in lighthouse]) / len(lighthouse),
            2,
        )
        self.average_best_practices_score = round(
            sum([page["best_practices_score"] for page in lighthouse])
            / len(lighthouse),
            2,
        )
        self.average_seo_score = round(
            sum([page["seo_score"] for page in lighthouse]) / len(lighthouse), 2
        )
        self.average_pwa_score = round(
            sum([page["pwa_score"] for page in lighthouse]) / len(lighthouse), 2
        )

    def get_performance_data(self, test: str):
        performance = []
        for benchmark in self.results:
            for key, value in benchmark:
                if key == "performance":
                    for v in value:
                        if v["test_name"] == test:
                            v["time"] = benchmark.time
                            performance.append(v)

        self.performance = performance
        self.performance_graph_state = True


def display_pr_titles(pr_title: str) -> rx.Component:
    return rx.text(
        pr_title,
        color=c["green"][800],
        bg=c["green"][400],
        font_size=".75em",
        padding_x=".5em",
        padding_y=".25em",
        border_radius="4px",
    )


options: list[str] = [
    "/",
    "blog/2023-08-02-seed-annoucement/",
    "docs/getting-started/introduction/",
]
tests: list[str] = [
    "test_mean_import_time",
    "test_mean_add_small_page_time",
    "test_mean_add_large_page_time",
]


def performance_data():
    return rx.vstack(
        rx.heading("Performance Data"),
        rx.heading(State.url),
        rx.select(
            tests,
            placeholder="test_mean_import_time",
            on_change=lambda test: State.get_performance_data(test),
            color_schemes="twitter",
        ),
        rx.cond(State.performance_graph_state, performance_graph(State.performance)),
        width="100%",
        align_items="left",
        padding_top="2em",
    )


def light_house_data():
    return rx.vstack(
        rx.heading("Lighthouse Data"),
        rx.select(
            options,
            placeholder="Page to Profile",
            on_change=lambda url: State.get_light_house_data(url),
            color_schemes="twitter",
        ),
        rx.cond(
            State.lighthouse_graph_state,
            rx.hstack(
                rx.badge(
                    f"Average Performance Score: {State.average_performance_score}",
                    bg=c["indigo"][400],
                    color="white",
                ),
                rx.badge(
                    f"Average Accessibility Score: {State.average_accessibility_score}",
                    bg=c["green"][500],
                    color="white",
                ),
                rx.badge(
                    f"Average Best Practices Score: {State.average_best_practices_score}",
                    bg=c["orange"][300],
                    color="white",
                ),
                rx.badge(
                    f"Average SEO Score: {State.average_seo_score}",
                    bg=c["blue"][300],
                    color="white",
                ),
                rx.badge(
                    f"Average PWA Score: {State.average_pwa_score}",
                    bg=c["violet"][400],
                    color="white",
                ),
                padding_top="1em",
            ),
        ),
        rx.cond(
            State.lighthouse_graph_state, lighthouse_graph(State.lighthouse, State)
        ),
        width="100%",
        align_items="left",
        padding_top="2em",
    )


def index() -> rx.Component:
    return rx.vstack(
        rx.heading("Reflex Benchmarking"),
        rx.divider(),
        rx.input(
            placeholder="Search PRs by title",
            on_blur=State.set_search_term,
        ),
        rx.button(
            "Search",
            on_click=State.search_performance_data,
            width="100%",
        ),
        rx.divider(),
        rx.hstack(
            rx.text("PRs:"),
            rx.foreach(State.pr_titles, display_pr_titles),
            align_items="left",
        ),
        rx.divider(),
        light_house_data(),
        performance_data(),
        padding="5em",
        width="100%",
        align_items="left",
        height="100%",
    )


# Add state and page to the app.
app = rx.App(style=BASE_STYLE)
app.add_page(index)
app.compile()
