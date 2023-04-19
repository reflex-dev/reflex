from typing import Any, Dict, List

import pytest

from pynecone.app import App
from pynecone.middleware.hydrate_middleware import IS_HYDRATED, HydrateMiddleware
from pynecone.state import State


def exp_is_hydrated(state: State) -> Dict[str, Any]:
    """Expected IS_HYDRATED delta that would be emitted by HydrateMiddleware.

    Args:
        state: the State that is hydrated

    Returns:
        dict similar to that returned by `State.get_delta` with IS_HYDRATED: True
    """
    return {state.get_name(): {IS_HYDRATED: True}}


class TestState(State):
    """A test state with no return in handler."""

    __test__ = False

    num: int = 0

    def test_handler(self):
        """Test handler."""
        self.num += 1


class TestState2(State):
    """A test state with return in handler."""

    __test__ = False

    num: int = 0
    name: str

    def test_handler(self):
        """Test handler that calls another handler.

        Returns:
            Chain of EventHandlers
        """
        self.num += 1
        return [self.change_name()]

    def change_name(self):
        """Test handler to change name."""
        self.name = "random"


class TestState3(State):
    """A test state with async handler."""

    __test__ = False

    num: int = 0

    async def test_handler(self):
        """Test handler."""
        self.num += 1


@pytest.fixture
def hydrate_middleware() -> HydrateMiddleware:
    """Fixture creates an instance of HydrateMiddleware per test case.

    Returns:
        instance of HydrateMiddleware
    """
    return HydrateMiddleware()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state, expected, event_fixture",
    [
        (TestState, {"test_state": {"num": 1}}, "event1"),
        (TestState2, {"test_state2": {"num": 1}}, "event2"),
        (TestState3, {"test_state3": {"num": 1}}, "event3"),
    ],
)
async def test_preprocess(state, hydrate_middleware, request, event_fixture, expected):
    """Test that a state hydrate event is processed correctly.

    Args:
        state: state to process event
        hydrate_middleware: instance of HydrateMiddleware
        request: pytest fixture request
        event_fixture: The event fixture(an Event)
        expected: expected delta
    """
    app = App(state=state, load_events={"index": state.test_handler})

    result = await hydrate_middleware.preprocess(
        app=app, event=request.getfixturevalue(event_fixture), state=state()
    )
    assert isinstance(result, List)
    assert len(result) == 3
    assert result[0].delta == {state().get_name(): state().dict()}
    assert result[1].delta == expected
    assert result[2].delta == exp_is_hydrated(state())


@pytest.mark.asyncio
async def test_preprocess_multiple_load_events(hydrate_middleware, event1):
    """Test that a state hydrate event for multiple on-load events is processed correctly.

    Args:
        hydrate_middleware: instance of HydrateMiddleware
        event1: an Event.
    """
    app = App(
        state=TestState,
        load_events={"index": [TestState.test_handler, TestState.test_handler]},
    )

    result = await hydrate_middleware.preprocess(
        app=app, event=event1, state=TestState()
    )
    assert isinstance(result, List)
    assert len(result) == 4
    assert result[0].delta == {"test_state": TestState().dict()}
    assert result[1].delta == {"test_state": {"num": 1}}
    assert result[2].delta == {"test_state": {"num": 2}}
    assert result[3].delta == exp_is_hydrated(TestState())


@pytest.mark.asyncio
async def test_preprocess_no_events(hydrate_middleware, event1):
    """Test that app without on_load is processed correctly.

    Args:
        hydrate_middleware: instance of HydrateMiddleware
        event1: an Event.
    """
    result = await hydrate_middleware.preprocess(
        app=App(state=TestState),
        event=event1,
        state=TestState(),
    )
    assert isinstance(result, List)
    assert len(result) == 2
    assert result[0].delta == {"test_state": TestState().dict()}
    assert result[1].delta == exp_is_hydrated(TestState())
