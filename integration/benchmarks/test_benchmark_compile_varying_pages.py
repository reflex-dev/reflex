"""Benchmark tests for medium sized apps."""

from __future__ import annotations

import time
from typing import Generator

import pytest

from reflex.testing import AppHarness, chdir
from reflex.utils import build
from reflex.utils import path_ops
from reflex import constants
from reflex.compiler import utils


def AppWithOnePage():
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
            rx.chakra.input(
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
    """Test that background tasks work as expected."""

    def register_pages(num):
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

        app = rx.App(state=rx.State)

        for i in range(1, num + 1):
            if i % 2 == 1:
                app.add_page(comp1, route=f"page{i}")
            else:
                app.add_page(comp2, route=f"page{i}")
        return app

    app = register_pages(10)


def AppWithHundredPages():
    def register_pages(num):
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

        app = rx.App(state=rx.State)

        for i in range(1, num + 1):
            if i % 2 == 1:
                app.add_page(comp1, route=f"page{i}")
            else:
                app.add_page(comp2, route=f"page{i}")
        return app

    app = register_pages(100)


def AppWithThousandPages():
    def register_pages(num):
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

        app = rx.App(state=rx.State)

        for i in range(1, num + 1):
            if i % 2 == 1:
                app.add_page(comp1, route=f"page{i}")
            else:
                app.add_page(comp2, route=f"page{i}")
        return app

    app = register_pages(1000)


def AppWithTenThousandPages():
    def register_pages(num):
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

        app = rx.App(state=rx.State)

        for i in range(1, num + 1):
            if i % 2 == 1:
                app.add_page(comp1, route=f"page{i}")
            else:
                app.add_page(comp2, route=f"page{i}")
        return app

    app = register_pages(10000)


@pytest.fixture(scope="session")
def app_with_one_page(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start Blank Template app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    root = tmp_path_factory.mktemp(f"app1")

    yield AppHarness.create(root=root, app_source=AppWithOnePage)  # type: ignore


@pytest.fixture(scope="session")
def app_with_ten_pages(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start Blank Template app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    root = tmp_path_factory.mktemp(f"app10")

    yield AppHarness.create(root=root, app_source=AppWithTenPages)  # type: ignore


@pytest.fixture(scope="session")
def app_with_hundred_pages(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start Blank Template app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    root = tmp_path_factory.mktemp(f"app100")

    yield AppHarness.create(root=root, app_source=AppWithHundredPages)  # type: ignore


@pytest.fixture(scope="session")
def app_with_thousand_pages(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start Blank Template app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    root = tmp_path_factory.mktemp(f"app1000")

    yield AppHarness.create(root=root, app_source=AppWithThousandPages)  # type: ignore


@pytest.fixture(scope="session")
def app_with_ten_thousand_pages(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start Blank Template app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    root = tmp_path_factory.mktemp(f"app10000")

    yield AppHarness.create(root=root, app_source=AppWithTenThousandPages)  # type: ignore


@pytest.mark.benchmark(
    group="Compile time of varying page numbers",
    min_rounds=10,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_1_compile_time_cold(benchmark, app_with_one_page):
    def setup():
        with chdir(app_with_one_page.app_path):
            utils.empty_dir(constants.Dirs.WEB_PAGES, keep_files=["_app.js"])
            app_with_one_page._initialize_app()
            build.setup_frontend(app_with_one_page.app_path)

    def benchmark_fn():
        with chdir(app_with_one_page.app_path):
            app_with_one_page.app_instance.compile_()

    benchmark.pedantic(benchmark_fn, setup=setup, rounds=10)


@pytest.mark.benchmark(
    group="Compile time of varying page numbers",
    min_rounds=10,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_1_compile_time_warm(benchmark, app_with_one_page):
    def benchmark_fn():
        with chdir(app_with_one_page.app_path):
            app_with_one_page.app_instance.compile_()

    benchmark(benchmark_fn)


@pytest.mark.benchmark(
    group="Compile time of varying page numbers",
    min_rounds=10,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_10_compile_time_cold(benchmark, app_with_ten_pages):
    def setup():
        with chdir(app_with_ten_pages.app_path):
            utils.empty_dir(constants.Dirs.WEB_PAGES, keep_files=["_app.js"])
            app_with_ten_pages._initialize_app()
            build.setup_frontend(app_with_ten_pages.app_path)

    def benchmark_fn():
        with chdir(app_with_ten_pages.app_path):
            app_with_ten_pages.app_instance.compile_()

    benchmark.pedantic(benchmark_fn, setup=setup, rounds=10)


@pytest.mark.benchmark(
    group="Compile time of varying page numbers",
    min_rounds=10,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_10_compile_time_warm(benchmark, app_with_ten_pages):
    def benchmark_fn():
        with chdir(app_with_ten_pages.app_path):
            app_with_ten_pages.app_instance.compile_()

    benchmark(benchmark_fn)


@pytest.mark.benchmark(
    group="Compile time of varying page numbers",
    min_rounds=10,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_100_compile_time_cold(benchmark, app_with_hundred_pages):
    def setup():
        with chdir(app_with_hundred_pages.app_path):
            utils.empty_dir(constants.Dirs.WEB_PAGES, keep_files=["_app.js"])
            app_with_hundred_pages._initialize_app()
            build.setup_frontend(app_with_hundred_pages.app_path)

    def benchmark_fn():
        with chdir(app_with_hundred_pages.app_path):
            app_with_hundred_pages.app_instance.compile_()

    benchmark.pedantic(benchmark_fn, setup=setup, rounds=10)


@pytest.mark.benchmark(
    group="Compile time of varying page numbers",
    min_rounds=10,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_100_compile_time_warm(benchmark, app_with_hundred_pages):
    def benchmark_fn():
        with chdir(app_with_hundred_pages.app_path):
            app_with_hundred_pages.app_instance.compile_()

    benchmark(benchmark_fn)


@pytest.mark.benchmark(
    group="Compile time of varying page numbers",
    min_rounds=10,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_1000_compile_time_cold(benchmark, app_with_thousand_pages):
    def setup():
        with chdir(app_with_thousand_pages.app_path):
            utils.empty_dir(constants.Dirs.WEB_PAGES, keep_files=["_app.js"])
            app_with_thousand_pages._initialize_app()
            build.setup_frontend(app_with_thousand_pages.app_path)

    def benchmark_fn():
        with chdir(app_with_thousand_pages.app_path):
            app_with_thousand_pages.app_instance.compile_()

    benchmark.pedantic(benchmark_fn, setup=setup, rounds=10)


@pytest.mark.benchmark(
    group="Compile time of varying page numbers",
    min_rounds=10,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_1000_compile_time_warm(benchmark, app_with_thousand_pages):
    def benchmark_fn():
        with chdir(app_with_thousand_pages.app_path):
            app_with_thousand_pages.app_instance.compile_()

    benchmark(benchmark_fn)


@pytest.mark.benchmark(
    group="Compile time of varying page numbers",
    min_rounds=10,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_10000_compile_time_cold(benchmark, app_with_ten_thousand_pages):
    def setup():
        with chdir(app_with_ten_thousand_pages.app_path):
            utils.empty_dir(constants.Dirs.WEB_PAGES, keep_files=["_app.js"])
            app_with_ten_thousand_pages._initialize_app()
            build.setup_frontend(app_with_ten_thousand_pages.app_path)

    def benchmark_fn():
        with chdir(app_with_ten_thousand_pages.app_path):
            app_with_ten_thousand_pages.app_instance.compile_()

    benchmark.pedantic(benchmark_fn, setup=setup, rounds=10)


@pytest.mark.benchmark(
    group="Compile time of varying page numbers",
    min_rounds=10,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False,
)
def test_app_10000_compile_time_warm(benchmark, app_with_ten_thousand_pages):
    def benchmark_fn():
        with chdir(app_with_ten_thousand_pages.app_path):
            app_with_ten_thousand_pages.app_instance.compile_()

    benchmark(benchmark_fn)
