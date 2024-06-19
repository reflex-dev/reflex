"""Unit tests for the included testing tools."""

import pytest

from reflex.constants import IS_WINDOWS
from reflex.testing import AppHarness


@pytest.mark.skip("Slow test that makes network requests.")
def test_app_harness(tmp_path):
    """Ensure that AppHarness can compile and start an app.

    Args:
        tmp_path: pytest tmp_path fixture
    """
    # Skip in Windows CI.
    if IS_WINDOWS:
        return

    def BasicApp():
        import reflex as rx

        class State(rx.State):
            pass

        app = rx.App(state=State)
        app.add_page(lambda: rx.text("Basic App"), route="/", title="index")
        app._compile()

    with AppHarness.create(
        root=tmp_path,
        app_source=BasicApp,  # type: ignore
    ) as harness:
        assert harness.app_instance is not None
        assert harness.backend is not None
        assert harness.frontend_url is not None
        assert harness.frontend_process is not None
        assert harness.frontend_process.poll() is None

    assert harness.frontend_process.poll() is not None
