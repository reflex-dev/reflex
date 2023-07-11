"""Unit tests for the included testing tools."""
from reflex.testing import AppHarness


def test_app_harness(tmp_path):
    """Ensure that AppHarness can compile and start an app.

    Args:
        tmp_path: pytest tmp_path fixture
    """

    def BasicApp():
        import reflex as rx

        app = rx.App()
        app.add_page(lambda: rx.text("Basic App"))
        app.compile()

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
