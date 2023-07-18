"""Unit tests for the included testing tools."""
from reflex.state import DefaultState
from reflex.testing import AppHarness


def test_app_harness(mocker, tmp_path):
    """Ensure that AppHarness can compile and start an app.

    Args:
        mocker: Pytest mocker object.
        tmp_path: pytest tmp_path fixture
    """
    mocker.patch("reflex.app.State.__subclasses__", return_value=[DefaultState])
    mocker.patch.object(DefaultState, "__subclasses__", return_value=[])

    def BasicApp():
        import reflex as rx

        app = rx.App()
        app.add_page(lambda: rx.text("Basic App"), route="/", title="index")
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
