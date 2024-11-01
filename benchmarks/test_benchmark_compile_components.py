"""Benchmark tests for apps with varying component numbers."""

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


def render_component(num: int):
    """Generate a number of components based on num.

    Args:
        num: number of components to produce.

    Returns:
        The rendered number of components.
    """
    import reflex as rx

    return [
        rx.fragment(
            rx.box(
                rx.accordion.root(
                    rx.accordion.item(
                        header="Full Ingredients",  # type: ignore
                        content="Yes. It's built with accessibility in mind.",  # type: ignore
                        font_size="3em",
                    ),
                    rx.accordion.item(
                        header="Applications",  # type: ignore
                        content="Yes. It's unstyled by default, giving you freedom over the look and feel.",  # type: ignore
                    ),
                    collapsible=True,
                    variant="ghost",
                    width="25rem",
                ),
                padding_top="20px",
            ),
            rx.box(
                rx.drawer.root(
                    rx.drawer.trigger(
                        rx.button("Open Drawer with snap points"), as_child=True
                    ),
                    rx.drawer.overlay(),
                    rx.drawer.portal(
                        rx.drawer.content(
                            rx.flex(
                                rx.drawer.title("Drawer Content"),
                                rx.drawer.description("Drawer description"),
                                rx.drawer.close(
                                    rx.button("Close Button"),
                                    as_child=True,
                                ),
                                direction="column",
                                margin="5em",
                                align_items="center",
                            ),
                            top="auto",
                            height="100%",
                            flex_direction="column",
                            background_color="var(--green-3)",
                        ),
                    ),
                    snap_points=["148px", "355px", 1],
                ),
            ),
            rx.box(
                rx.callout(
                    "You will need admin privileges to install and access this application.",
                    icon="info",
                    size="3",
                ),
            ),
            rx.box(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Full name"),
                            rx.table.column_header_cell("Email"),
                            rx.table.column_header_cell("Group"),
                        ),
                    ),
                    rx.table.body(
                        rx.table.row(
                            rx.table.row_header_cell("Danilo Sousa"),
                            rx.table.cell("danilo@example.com"),
                            rx.table.cell("Developer"),
                        ),
                        rx.table.row(
                            rx.table.row_header_cell("Zahra Ambessa"),
                            rx.table.cell("zahra@example.com"),
                            rx.table.cell("Admin"),
                        ),
                        rx.table.row(
                            rx.table.row_header_cell("Jasper Eriksson"),
                            rx.table.cell("jasper@example.com"),
                            rx.table.cell("Developer"),
                        ),
                    ),
                )
            ),
        )
    ] * num


def AppWithTenComponentsOnePage():
    """A reflex app with roughly 10 components on one page."""
    import reflex as rx

    def index() -> rx.Component:
        return rx.center(rx.vstack(*render_component(1)))

    app = rx.App(state=rx.State)
    app.add_page(index)


def AppWithHundredComponentOnePage():
    """A reflex app with roughly 100 components on one page."""
    import reflex as rx

    def index() -> rx.Component:
        return rx.center(rx.vstack(*render_component(100)))

    app = rx.App(state=rx.State)
    app.add_page(index)


def AppWithThousandComponentsOnePage():
    """A reflex app with roughly 1000 components on one page."""
    import reflex as rx

    def index() -> rx.Component:
        return rx.center(rx.vstack(*render_component(1000)))

    app = rx.App(state=rx.State)
    app.add_page(index)


@pytest.fixture(scope="session")
def app_with_10_components(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start Blank Template app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    root = tmp_path_factory.mktemp("app10components")

    yield AppHarness.create(
        root=root,
        app_source=functools.partial(
            AppWithTenComponentsOnePage,
            render_component=render_component,  # type: ignore
        ),
    )  # type: ignore


@pytest.fixture(scope="session")
def app_with_100_components(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start Blank Template app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    root = tmp_path_factory.mktemp("app100components")

    yield AppHarness.create(
        root=root,
        app_source=functools.partial(
            AppWithHundredComponentOnePage,
            render_component=render_component,  # type: ignore
        ),
    )  # type: ignore


@pytest.fixture(scope="session")
def app_with_1000_components(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Create an app with 1000 components at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        an AppHarness instance
    """
    root = tmp_path_factory.mktemp("app1000components")

    yield AppHarness.create(
        root=root,
        app_source=functools.partial(
            AppWithThousandComponentsOnePage,
            render_component=render_component,  # type: ignore
        ),
    )  # type: ignore


@pytest.mark.skipif(constants.IS_WINDOWS, reason=WINDOWS_SKIP_REASON)
@pytest.mark.benchmark(
    group="Compile time of varying component numbers",
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_10_compile_time_cold(benchmark, app_with_10_components):
    """Test the compile time on a cold start for an app with roughly 10 components.

    Args:
        benchmark: The benchmark fixture.
        app_with_10_components: The app harness.
    """

    def setup():
        with chdir(app_with_10_components.app_path):
            utils.empty_dir(web_pages, ["_app.js"])
            app_with_10_components._initialize_app()
            build.setup_frontend(app_with_10_components.app_path)

    def benchmark_fn():
        with chdir(app_with_10_components.app_path):
            app_with_10_components.app_instance._compile()

    benchmark.pedantic(benchmark_fn, setup=setup, rounds=10)


@pytest.mark.benchmark(
    group="Compile time of varying component numbers",
    min_rounds=5,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_10_compile_time_warm(benchmark, app_with_10_components):
    """Test the compile time on a warm start for an app with roughly 10 components.

    Args:
        benchmark: The benchmark fixture.
        app_with_10_components: The app harness.
    """
    with chdir(app_with_10_components.app_path):
        app_with_10_components._initialize_app()
        build.setup_frontend(app_with_10_components.app_path)

    def benchmark_fn():
        with chdir(app_with_10_components.app_path):
            app_with_10_components.app_instance._compile()

    benchmark(benchmark_fn)


@pytest.mark.skipif(constants.IS_WINDOWS, reason=WINDOWS_SKIP_REASON)
@pytest.mark.benchmark(
    group="Compile time of varying component numbers",
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_100_compile_time_cold(benchmark, app_with_100_components):
    """Test the compile time on a cold start for an app with roughly 100 components.

    Args:
        benchmark: The benchmark fixture.
        app_with_100_components: The app harness.
    """

    def setup():
        with chdir(app_with_100_components.app_path):
            utils.empty_dir(web_pages, ["_app.js"])
            app_with_100_components._initialize_app()
            build.setup_frontend(app_with_100_components.app_path)

    def benchmark_fn():
        with chdir(app_with_100_components.app_path):
            app_with_100_components.app_instance._compile()

    benchmark.pedantic(benchmark_fn, setup=setup, rounds=5)


@pytest.mark.benchmark(
    group="Compile time of varying component numbers",
    min_rounds=5,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_100_compile_time_warm(benchmark, app_with_100_components):
    """Test the compile time on a warm start for an app with roughly 100 components.

    Args:
        benchmark: The benchmark fixture.
        app_with_100_components: The app harness.
    """
    with chdir(app_with_100_components.app_path):
        app_with_100_components._initialize_app()
        build.setup_frontend(app_with_100_components.app_path)

    def benchmark_fn():
        with chdir(app_with_100_components.app_path):
            app_with_100_components.app_instance._compile()

    benchmark(benchmark_fn)


@pytest.mark.skipif(constants.IS_WINDOWS, reason=WINDOWS_SKIP_REASON)
@pytest.mark.benchmark(
    group="Compile time of varying component numbers",
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_1000_compile_time_cold(benchmark, app_with_1000_components):
    """Test the compile time on a cold start for an app with roughly 1000 components.

    Args:
        benchmark: The benchmark fixture.
        app_with_1000_components: The app harness.
    """

    def setup():
        with chdir(app_with_1000_components.app_path):
            utils.empty_dir(web_pages, keep_files=["_app.js"])
            app_with_1000_components._initialize_app()
            build.setup_frontend(app_with_1000_components.app_path)

    def benchmark_fn():
        with chdir(app_with_1000_components.app_path):
            app_with_1000_components.app_instance._compile()

    benchmark.pedantic(benchmark_fn, setup=setup, rounds=5)


@pytest.mark.benchmark(
    group="Compile time of varying component numbers",
    min_rounds=5,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_1000_compile_time_warm(benchmark, app_with_1000_components):
    """Test the compile time on a warm start for an app with roughly 1000 components.

    Args:
        benchmark: The benchmark fixture.
        app_with_1000_components: The app harness.
    """
    with chdir(app_with_1000_components.app_path):
        app_with_1000_components._initialize_app()
        build.setup_frontend(app_with_1000_components.app_path)

    def benchmark_fn():
        with chdir(app_with_1000_components.app_path):
            app_with_1000_components.app_instance._compile()

    benchmark(benchmark_fn)
