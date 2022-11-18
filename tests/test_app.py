import pytest

from pynecone.base import Base
from pynecone.app import App, DefaultState
from pynecone.middleware import HydrateMiddleware
from pynecone.components import Box


@pytest.fixture
def app() -> App:
    """A base app.

    Returns:
        The app.
    """
    return App()


@pytest.fixture
def index_page():
    """An index page."""

    def index():
        return Box.create("Index")

    return index


@pytest.fixture
def about_page():
    """An index page."""

    def about():
        return Box.create("About")

    return about


def test_default_state(app: App) -> None:
    """Test creating an app with no state.

    Args:
        app: The app to test.
    """
    assert app.state() == DefaultState()


def test_default_middleware(app: App) -> None:
    """Test creating an app with no middleware.

    Args:
        app: The app to test.
    """
    assert app.middleware == [HydrateMiddleware()]


def test_add_page_default_route(app: App, index_page, about_page) -> None:
    """Test adding a page to an app.

    Args:
        app: The app to test.
        index_page: The index page.
        about_page: The about page.
    """
    assert app.pages == {}
    app.add_page(index_page)
    assert set(app.pages.keys()) == {"index"}
    app.add_page(about_page)
    assert set(app.pages.keys()) == {"index", "about"}


def test_add_page_set_route(app: App, index_page) -> None:
    """Test adding a page to an app.

    Args:
        app: The app to test.
        index_page: The index page.
    """
    assert app.pages == {}
    app.add_page(index_page, path="/test")
    assert set(app.pages.keys()) == {"test"}
