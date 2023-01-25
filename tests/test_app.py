from typing import Type

import pytest

from pynecone.app import App, DefaultState
from pynecone.components import Box
from pynecone.event import Event
from pynecone.middleware import HydrateMiddleware
from pynecone.state import State
from pynecone.style import Style


@pytest.fixture
def app() -> App:
    """A base app.

    Returns:
        The app.
    """
    return App()


@pytest.fixture
def index_page():
    """An index page.

    Returns:
        The index page.
    """

    def index():
        return Box.create("Index")

    return index


@pytest.fixture
def about_page():
    """An about page.

    Returns:
        The about page.
    """

    def about():
        return Box.create("About")

    return about


@pytest.fixture()
def TestState() -> Type[State]:
    """A default state.

    Returns:
        A default state.
    """

    class TestState(State):
        var: int

    return TestState


def test_default_app(app: App):
    """Test creating an app with no args.

    Args:
        app: The app to test.
    """
    assert app.state() == DefaultState()
    assert app.middleware == [HydrateMiddleware()]
    assert app.style == Style()


def test_add_page_default_route(app: App, index_page, about_page):
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


def test_add_page_set_route(app: App, index_page):
    """Test adding a page to an app.

    Args:
        app: The app to test.
        index_page: The index page.
    """
    assert app.pages == {}
    app.add_page(index_page, route="/test")
    assert set(app.pages.keys()) == {"test"}


def test_add_page_set_route_nested(app: App, index_page):
    """Test adding a page to an app.

    Args:
        app: The app to test.
        index_page: The index page.
    """
    assert app.pages == {}
    app.add_page(index_page, route="/test/nested")
    assert set(app.pages.keys()) == {"test/nested"}


def test_initialize_with_state(TestState: Type[State]):
    """Test setting the state of an app.

    Args:
        TestState: The default state.
    """
    app = App(state=TestState)
    assert app.state == TestState

    # Get a state for a given token.
    token = "token"
    state = app.state_manager.get_state(token)
    assert isinstance(state, TestState)
    assert state.var == 0  # type: ignore


def test_set_and_get_state(TestState: Type[State]):
    """Test setting and getting the state of an app with different tokens.

    Args:
        TestState: The default state.
    """
    app = App(state=TestState)

    # Create two tokens.
    token1 = "token1"
    token2 = "token2"

    # Get the default state for each token.
    state1 = app.state_manager.get_state(token1)
    state2 = app.state_manager.get_state(token2)
    assert state1.var == 0  # type: ignore
    assert state2.var == 0  # type: ignore

    # Set the vars to different values.
    state1.var = 1
    state2.var = 2
    app.state_manager.set_state(token1, state1)
    app.state_manager.set_state(token2, state2)

    # Get the states again and check the values.
    state1 = app.state_manager.get_state(token1)
    state2 = app.state_manager.get_state(token2)
    assert state1.var == 1  # type: ignore
    assert state2.var == 2  # type: ignore


@pytest.fixture
def list_mutation_state():
    class AppState(State):
        """The app state."""

        friends = ["Tommy"]

        def make_friend(self):
            self.friends.append("another-fd")

        def change_first_friend(self):
            self.friends[0] = "Jenny"

        def unfriend_all_friends(self):
            self.friends.clear()

        def unfriend_first_friend(self):
            del self.friends[0]

    return AppState()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event_tuples",
    [
        pytest.param(
            [
                ("app_state.make_friend", ["Tommy", "another-fd"]),
                ("app_state.change_first_friend", ["Jenny", "another-fd"]),
            ],
            id="append then __setitem__",
        ),
        pytest.param(
            [
                ("app_state.unfriend_first_friend", []),
                ("app_state.make_friend", ["another-fd"]),
            ],
            id="delitem then append",
        ),
    ],
)
async def test_list_mutation_detection(
    event_tuples: list[tuple[str, list[str]]], list_mutation_state: State
):
    """Test list mutation detection
    when reassignment is not explicitly included in the logic.
    """
    for event_name, expected_friends_in_delta in event_tuples:
        result = await list_mutation_state.process(
            Event(
                token="fake-token",
                name=event_name,
                router_data={"pathname": "/", "query": {}},
                payload={},
            )
        )

        assert result.delta["app_state"]["friends"] == expected_friends_in_delta
