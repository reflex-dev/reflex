import os
import time
from typing import Generator

import pytest

from reflex import constants
from reflex.testing import AppHarness, chdir
from reflex.utils import build, path_ops


def MediumApp():
    """Test that background tasks work as expected."""
    from rxconfig import config

    import reflex as rx

    docs_url = "https://reflex.dev/docs/getting-started/introduction/"
    filename = f"{config.app_name}/{config.app_name}.py"
    college = [
        "Stanford University",
        "Arizona",
        "Arizona state",
        "Baylor",
        "Boston College",
        "Boston University",
    ]

    class State(rx.State):
        """The app state."""

        position: str
        college: str
        age: tuple[int, int] = (18, 50)
        salary: tuple[int, int] = (0, 25000000)

    comp1 = rx.center(
            rx.theme_panel(),
            rx.vstack(
                rx.heading("Welcome to Reflex!", size="9"),
                rx.text("Get started by editing ", rx.code(filename)),
                rx.button(
                    "Check out our docs!",
                    on_click=lambda: rx.redirect(docs_url),
                    size="4",
                ),
                align="center",
                spacing="7",
                font_size="2em",
            ),
            height="100vh",
        )

    comp2 = rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.select(
                        ["C", "PF", "SF", "PG", "SG"],
                        placeholder="Select a position. (All)",
                        on_change=State.set_position,
                        size="3",
                    ),
                    rx.select(
                        college,
                        placeholder="Select a college. (All)",
                        on_change=State.set_college,
                        size="3",
                    ),
                ),
                rx.vstack(
                    rx.vstack(
                        rx.hstack(
                            rx.badge("Min Age: ", State.age[0]),
                            rx.divider(orientation="vertical"),
                            rx.badge("Max Age: ", State.age[1]),
                        ),
                        rx.slider(
                            default_value=[18, 50],
                            min=18,
                            max=50,
                            on_value_commit=State.set_age,
                        ),
                        align_items="left",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.hstack(
                            rx.badge("Min Sal: ", State.salary[0] // 1000000, "M"),
                            rx.divider(orientation="vertical"),
                            rx.badge("Max Sal: ", State.salary[1] // 1000000, "M"),
                        ),
                        rx.slider(
                            default_value=[0, 25000000],
                            min=0,
                            max=25000000,
                            on_value_commit=State.set_salary,
                        ),
                        align_items="left",
                        width="100%",
                    ),
                ),
                spacing="4",
            ),
            width="100%",
        )

    app = rx.App(state=rx.State)

    for i in range(1, 31):
        if i % 2 == 1:
            app.add_page(comp1, route=f"page{i}")
        else:
            app.add_page(comp2, route=f"page{i}")



@pytest.fixture(scope="session")
def medium_app(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start Blank Template app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    root = tmp_path_factory.mktemp(f"medium_app")

    yield AppHarness.create(root=root, app_source=MediumApp)  # type: ignore



@pytest.mark.benchmark(
    group="Medium sized app", min_rounds=10, timer=time.perf_counter, disable_gc=True, warmup=False
)
def test_medium_app_compile_time_cold(benchmark, medium_app):
    def setup():
        with chdir(medium_app.app_path):
            medium_app._initialize_app()
            build.setup_frontend(medium_app.app_path)

    def benchmark_fn():
        with chdir(medium_app.app_path):
            medium_app.app_instance.compile_()

    benchmark.pedantic(benchmark_fn, setup=setup, rounds=10)



@pytest.mark.benchmark(
    group="Medium sized app", min_rounds=10,timer=time.perf_counter, disable_gc=True, warmup=False
)
def test_medium_app_compile_time_warm(benchmark, medium_app):

    def benchmark_fn():
        with chdir(medium_app.app_path):
            medium_app.app_instance.compile_()

    benchmark(benchmark_fn)



def test_medium_app_hot_reload():
    pass
