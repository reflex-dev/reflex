import pytest
import time

from typing import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import DEFAULT_TIMEOUT, AppHarness, WebDriver, chdir


def BlankTemplate():
    """Test that background tasks work as expected."""
    from rxconfig import config

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


@pytest.fixture(scope="session")
def blank_template(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start Blank Template app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    root = tmp_path_factory.mktemp(f"blank_template")
    print(f" root dir: {root}")
    with AppHarness.create(
        root=root,
        app_source=BlankTemplate,  # type: ignore
    ) as harness:
        yield harness



@pytest.mark.benchmark(
    group="blank template",
    min_time=0.1,
    max_time=0.5,
    min_rounds=10,
    timer=time.perf_counter,
    disable_gc=True,
    warmup=False
)
def test_blank_template_app_start(benchmark, blank_template, mocker):
    import copy
    assert blank_template.app_instance is not None
    from reflex.constants.base import Dirs
    dirs = copy.deepcopy(Dirs)

    dirs.WEB = str( blank_template.app_path /".web")
    dirs.UTILS = "/".join([str( blank_template.app_path),"utils"])

    mocker.patch("reflex.utils.prerequisites.constants.Dirs", dirs)
    benchmark(blank_template.app_instance.compile_)