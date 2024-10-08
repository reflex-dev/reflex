"""Benchmark tests for apps with varying page numbers."""

from __future__ import annotations

import functools
import time
from typing import Generator

import pytest

from benchmarks import WINDOWS_SKIP_REASON
from reflex import constants
from reflex.compiler import utils
from reflex.testing import AppHarness, chdir
from reflex.utils import build
from reflex.utils.prerequisites import get_web_dir

web_pages = get_web_dir() / constants.Dirs.PAGES


def render_multiple_pages(app, num: int):
    """Add multiple pages based on num.

    Args:
        app: The App object.
        num: number of pages to render.

    """
    from typing import Tuple

    from rxconfig import config  # type: ignore

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

    for i in range(1, num + 1):
        if i % 2 == 1:
            app.add_page(comp1, route=f"page{i}")
        else:
            app.add_page(comp2, route=f"page{i}")


def AppWithOnePage():
    """A reflex app with one page."""
    from rxconfig import config  # type: ignore

    import reflex as rx

    docs_url = "https://reflex.dev/docs/getting-started/introduction/"
    filename = f"{config.app_name}/{config.app_name}.py"

    class State(rx.State):
        """The app state."""

        pass

    def index() -> rx.Component:
        return rx.center(
            rx.input(
                id="token", value=State.router.session.client_token, is_read_only=True
            ),
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


def AppWithTenPages():
    """A reflex app with 10 pages."""
    import reflex as rx

    app = rx.App(state=rx.State)
    render_multiple_pages(app, 10)


def AppWithHundredPages():
    """A reflex app with 100 pages."""
    import reflex as rx

    app = rx.App(state=rx.State)
    render_multiple_pages(app, 100)


def AppWithThousandPages():
    """A reflex app with Thousand pages."""
    import reflex as rx

    app = rx.App(state=rx.State)
    render_multiple_pages(app, 1000)


def AppWithTenThousandPages():
    """A reflex app with ten thousand pages."""
    import reflex as rx

    app = rx.App(state=rx.State)
    render_multiple_pages(app, 10000)


@pytest.fixture(scope="session")
def app_with_one_page(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Create an app with 10000 pages at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        an AppHarness instance
    """
    root = tmp_path_factory.mktemp(f"app1")

    yield AppHarness.create(root=root, app_source=AppWithOnePage)  # type: ignore


@pytest.fixture(scope="session")
def app_with_ten_pages(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Create an app with 10 pages at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        an AppHarness instance
    """
    root = tmp_path_factory.mktemp(f"app10")
    yield AppHarness.create(
        root=root,
        app_source=functools.partial(
            AppWithTenPages,
            render_comp=render_multiple_pages,  # type: ignore
        ),
    )


@pytest.fixture(scope="session")
def app_with_hundred_pages(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Create an app with 100 pages at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        an AppHarness instance
    """
    root = tmp_path_factory.mktemp(f"app100")

    yield AppHarness.create(
        root=root,
        app_source=functools.partial(
            AppWithHundredPages,
            render_comp=render_multiple_pages,  # type: ignore
        ),
    )  # type: ignore


@pytest.fixture(scope="session")
def app_with_thousand_pages(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Create an app with 1000 pages at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        an AppHarness instance
    """
    root = tmp_path_factory.mktemp(f"app1000")

    yield AppHarness.create(
        root=root,
        app_source=functools.partial(  # type: ignore
            AppWithThousandPages,
            render_comp=render_multiple_pages,  # type: ignore
        ),
    )  # type: ignore


@pytest.fixture(scope="session")
def app_with_ten_thousand_pages(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Create an app with 10000 pages at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    root = tmp_path_factory.mktemp(f"app10000")

    yield AppHarness.create(
        root=root,
        app_source=functools.partial(
            AppWithTenThousandPages,
            render_comp=render_multiple_pages,  # type: ignore
        ),
    )  # type: ignore


@pytest.mark.skipif(constants.IS_WINDOWS, reason=WINDOWS_SKIP_REASON)
@pytest.mark.benchmark(
    group="Compile time of varying page numbers",
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_1_compile_time_cold(benchmark, app_with_one_page):
    """Test the compile time on a cold start for an app with 1 page.

    Args:
        benchmark: The benchmark fixture.
        app_with_one_page: The app harness.
    """

    def setup():
        with chdir(app_with_one_page.app_path):
            utils.empty_dir(web_pages, keep_files=["_app.js"])
            app_with_one_page._initialize_app()
            build.setup_frontend(app_with_one_page.app_path)

    def benchmark_fn():
        with chdir(app_with_one_page.app_path):
            app_with_one_page.app_instance._compile()

    benchmark.pedantic(benchmark_fn, setup=setup, rounds=5)
    app_with_one_page._reload_state_module()


@pytest.mark.benchmark(
    group="Compile time of varying page numbers",
    min_rounds=5,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_1_compile_time_warm(benchmark, app_with_one_page):
    """Test the compile time on a warm start for an app with 1 page.

    Args:
        benchmark: The benchmark fixture.
        app_with_one_page: The app harness.
    """
    with chdir(app_with_one_page.app_path):
        app_with_one_page._initialize_app()
        build.setup_frontend(app_with_one_page.app_path)

    def benchmark_fn():
        with chdir(app_with_one_page.app_path):
            app_with_one_page.app_instance._compile()

    benchmark(benchmark_fn)
    app_with_one_page._reload_state_module()


@pytest.mark.skipif(constants.IS_WINDOWS, reason=WINDOWS_SKIP_REASON)
@pytest.mark.benchmark(
    group="Compile time of varying page numbers",
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_10_compile_time_cold(benchmark, app_with_ten_pages):
    """Test the compile time on a cold start for an app with 10 page.

    Args:
        benchmark: The benchmark fixture.
        app_with_ten_pages: The app harness.
    """

    def setup():
        with chdir(app_with_ten_pages.app_path):
            utils.empty_dir(web_pages, keep_files=["_app.js"])
            app_with_ten_pages._initialize_app()
            build.setup_frontend(app_with_ten_pages.app_path)

    def benchmark_fn():
        with chdir(app_with_ten_pages.app_path):
            app_with_ten_pages.app_instance._compile()

    benchmark.pedantic(benchmark_fn, setup=setup, rounds=5)
    app_with_ten_pages._reload_state_module()


@pytest.mark.benchmark(
    group="Compile time of varying page numbers",
    min_rounds=5,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_10_compile_time_warm(benchmark, app_with_ten_pages):
    """Test the compile time on a warm start for an app with 10 page.

    Args:
        benchmark: The benchmark fixture.
        app_with_ten_pages: The app harness.
    """
    with chdir(app_with_ten_pages.app_path):
        app_with_ten_pages._initialize_app()
        build.setup_frontend(app_with_ten_pages.app_path)

    def benchmark_fn():
        with chdir(app_with_ten_pages.app_path):
            app_with_ten_pages.app_instance._compile()

    benchmark(benchmark_fn)
    app_with_ten_pages._reload_state_module()


@pytest.mark.skipif(constants.IS_WINDOWS, reason=WINDOWS_SKIP_REASON)
@pytest.mark.benchmark(
    group="Compile time of varying page numbers",
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_100_compile_time_cold(benchmark, app_with_hundred_pages):
    """Test the compile time on a cold start for an app with 100 page.

    Args:
        benchmark: The benchmark fixture.
        app_with_hundred_pages: The app harness.
    """

    def setup():
        with chdir(app_with_hundred_pages.app_path):
            utils.empty_dir(web_pages, keep_files=["_app.js"])
            app_with_hundred_pages._initialize_app()
            build.setup_frontend(app_with_hundred_pages.app_path)

    def benchmark_fn():
        with chdir(app_with_hundred_pages.app_path):
            app_with_hundred_pages.app_instance._compile()

    benchmark.pedantic(benchmark_fn, setup=setup, rounds=5)
    app_with_hundred_pages._reload_state_module()


@pytest.mark.benchmark(
    group="Compile time of varying page numbers",
    min_rounds=5,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_100_compile_time_warm(benchmark, app_with_hundred_pages):
    """Test the compile time on a warm start for an app with 100 page.

    Args:
        benchmark: The benchmark fixture.
        app_with_hundred_pages: The app harness.
    """
    with chdir(app_with_hundred_pages.app_path):
        app_with_hundred_pages._initialize_app()
        build.setup_frontend(app_with_hundred_pages.app_path)

    def benchmark_fn():
        with chdir(app_with_hundred_pages.app_path):
            app_with_hundred_pages.app_instance._compile()

    benchmark(benchmark_fn)
    app_with_hundred_pages._reload_state_module()


@pytest.mark.skipif(constants.IS_WINDOWS, reason=WINDOWS_SKIP_REASON)
@pytest.mark.benchmark(
    group="Compile time of varying page numbers",
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_1000_compile_time_cold(benchmark, app_with_thousand_pages):
    """Test the compile time on a cold start for an app with 1000 page.

    Args:
        benchmark: The benchmark fixture.
        app_with_thousand_pages: The app harness.
    """

    def setup():
        with chdir(app_with_thousand_pages.app_path):
            utils.empty_dir(web_pages, keep_files=["_app.js"])
            app_with_thousand_pages._initialize_app()
            build.setup_frontend(app_with_thousand_pages.app_path)

    def benchmark_fn():
        with chdir(app_with_thousand_pages.app_path):
            app_with_thousand_pages.app_instance._compile()

    benchmark.pedantic(benchmark_fn, setup=setup, rounds=5)
    app_with_thousand_pages._reload_state_module()


@pytest.mark.benchmark(
    group="Compile time of varying page numbers",
    min_rounds=5,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_1000_compile_time_warm(benchmark, app_with_thousand_pages):
    """Test the compile time on a warm start for an app with 1000 page.

    Args:
        benchmark: The benchmark fixture.
        app_with_thousand_pages: The app harness.
    """
    with chdir(app_with_thousand_pages.app_path):
        app_with_thousand_pages._initialize_app()
        build.setup_frontend(app_with_thousand_pages.app_path)

    def benchmark_fn():
        with chdir(app_with_thousand_pages.app_path):
            app_with_thousand_pages.app_instance._compile()

    benchmark(benchmark_fn)
    app_with_thousand_pages._reload_state_module()


@pytest.mark.skip
@pytest.mark.benchmark(
    group="Compile time of varying page numbers",
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_10000_compile_time_cold(benchmark, app_with_ten_thousand_pages):
    """Test the compile time on a cold start for an app with 10000 page.

    Args:
        benchmark: The benchmark fixture.
        app_with_ten_thousand_pages: The app harness.
    """

    def setup():
        with chdir(app_with_ten_thousand_pages.app_path):
            utils.empty_dir(web_pages, keep_files=["_app.js"])
            app_with_ten_thousand_pages._initialize_app()
            build.setup_frontend(app_with_ten_thousand_pages.app_path)

    def benchmark_fn():
        with chdir(app_with_ten_thousand_pages.app_path):
            app_with_ten_thousand_pages.app_instance._compile()

    benchmark.pedantic(benchmark_fn, setup=setup, rounds=5)
    app_with_ten_thousand_pages._reload_state_module()


@pytest.mark.skip
@pytest.mark.benchmark(
    group="Compile time of varying page numbers",
    min_rounds=5,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_10000_compile_time_warm(benchmark, app_with_ten_thousand_pages):
    """Test the compile time on a warm start for an app with 10000 page.

    Args:
        benchmark: The benchmark fixture.
        app_with_ten_thousand_pages: The app harness.
    """

    def benchmark_fn():
        with chdir(app_with_ten_thousand_pages.app_path):
            app_with_ten_thousand_pages.app_instance._compile()

    benchmark(benchmark_fn)
    app_with_ten_thousand_pages._reload_state_module()
