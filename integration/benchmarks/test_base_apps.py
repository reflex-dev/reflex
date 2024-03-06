"""Benchmark tests for base apps."""

import os
import time
from typing import Generator

import pytest

from reflex import constants
from reflex.testing import AppHarness, chdir
from reflex.utils import build, path_ops


def BaseApp():
    """Test that background tasks work as expected."""
    from rxconfig import config  # type: ignore

    import reflex as rx

    docs_url = "https://reflex.dev/docs/getting-started/introduction/"
    filename = f"{config.app_name}/{config.app_name}.py"

    class State(rx.State):
        """The app state."""

        pass

    def index() -> rx.Component:
        return rx.center(
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

    app = rx.App(state=rx.State)
    app.add_page(index)


def BaseApp2():
    """Test that background tasks work as expected."""
    from rxconfig import config  # type: ignore
    from typing import Tuple

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
        age: Tuple[int, int] = (18, 50)
        salary: Tuple[int, int] = (0, 25000000)

    def index() -> rx.Component:
        return rx.center(
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

    def selection() -> rx.Component:
        return rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.select(
                        ["C", "PF", "SF", "PG", "SG"],
                        placeholder="Select a position. (All)",
                        on_change=State.set_position,  # type: ignore
                        size="3",
                    ),
                    rx.select(
                        college,
                        placeholder="Select a college. (All)",
                        on_change=State.set_college,  # type: ignore
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
                            on_value_commit=State.set_age,  # type: ignore
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
                            on_value_commit=State.set_salary,  # type: ignore
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
    app.add_page(index)
    app.add_page(selection)


@pytest.fixture(scope="session")
def base_app(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start Base app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    root = tmp_path_factory.mktemp(f"base_app")

    yield AppHarness.create(root=root, app_source=BaseApp)  # type: ignore


@pytest.fixture(scope="session")
def base_app_two_pages(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start Base app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    root = tmp_path_factory.mktemp(f"base_app_two_pages")

    yield AppHarness.create(root=root, app_source=BaseApp2)  # type: ignore


@pytest.mark.benchmark(
    group="blank template", timer=time.perf_counter, disable_gc=True, warmup=False
)
def test_base_app_compile_time_cold(benchmark, base_app):
    def setup():
        with chdir(base_app.app_path):
            base_app._initialize_app()
            build.setup_frontend(base_app.app_path)

    def benchmark_fn():
        with chdir(base_app.app_path):
            base_app.app_instance.compile_()

    benchmark.pedantic(benchmark_fn, setup=setup, rounds=10)


@pytest.mark.benchmark(
    group="blank template", timer=time.perf_counter, disable_gc=True, warmup=False
)
def test_base_app_two_pages_compile_time_cold(benchmark, base_app_two_pages):
    def setup():
        with chdir(base_app_two_pages.app_path):
            base_app_two_pages._initialize_app()
            build.setup_frontend(base_app_two_pages.app_path)

    def benchmark_fn():
        with chdir(base_app_two_pages.app_path):
            base_app_two_pages.app_instance.compile_()
            path_ops.rm(
                os.path.join(
                    constants.Dirs.WEB, "reflex.install_frontend_packages.cached"
                )
            )
            path_ops.rm(os.path.join(constants.Dirs.WEB, "node_modules"))

    benchmark.pedantic(benchmark_fn, setup=setup, rounds=10)


@pytest.mark.benchmark(
    group="blank template",
    min_rounds=10,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_base_app_compile_time_warm(benchmark, base_app):
    def benchmark_fn():
        with chdir(base_app.app_path):
            base_app.app_instance.compile_()

    benchmark.pedantic(benchmark_fn, rounds=10)


@pytest.mark.benchmark(
    group="blank template",
    min_rounds=10,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_base_app_two_pages_compile_time_warm(benchmark, base_app_two_pages):
    def benchmark_fn():
        with chdir(base_app_two_pages.app_path):
            base_app_two_pages.app_instance.compile_()
            path_ops.rm(
                os.path.join(
                    constants.Dirs.WEB, "reflex.install_frontend_packages.cached"
                )
            )
            path_ops.rm(os.path.join(constants.Dirs.WEB, "node_modules"))

    benchmark.pedantic(benchmark_fn)


# TODO:
def test_base_app_hot_reload():
    pass


# TODO:
def test_base_app_two_pages_hot_reload():
    pass
