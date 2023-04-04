from typing import List

import pytest

from pynecone.app import App
from pynecone.middleware.hydrate_middleware import HydrateMiddleware
from pynecone.state import State


class TestState(State):
    """A test state with no return in handler."""

    num: int = 0

    def test_handler(self):
        """Test handler."""
        self.num += 1


class TestState2(State):
    """A test state with return in handler."""

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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state, expected, event_fixture",
    [
        (TestState, {"test_state": {"num": 1}}, "event1"),
        (TestState2, {"test_state2": {"num": 1}}, "event2"),
    ],
)
async def test_preprocess(state, request, event_fixture, expected):
    """Test that a state hydrate event is processed correctly.

    Args:
        state: state to process event
        request: pytest fixture request
        event_fixture: The event fixture(an Event)
        expected: expected delta
    """
    app = App(state=state, load_events={"index": state.test_handler})

    hydrate_middleware = HydrateMiddleware()
    result = await hydrate_middleware.preprocess(
        app=app, event=request.getfixturevalue(event_fixture), state=state()
    )
    assert isinstance(result, List)
    assert result[0].delta == expected


@pytest.mark.asyncio
async def test_preprocess_multiple_load_events(event1):
    """Test that a state hydrate event for multiple on-load events is processed correctly.

    Args:
        event1: an Event.
    """
    app = App(
        state=TestState,
        load_events={"index": [TestState.test_handler, TestState.test_handler]},
    )

    hydrate_middleware = HydrateMiddleware()
    result = await hydrate_middleware.preprocess(
        app=app, event=event1, state=TestState()
    )
    assert isinstance(result, List)
    assert result[0].delta == {"test_state": {"num": 1}}
    assert result[1].delta == {"test_state": {"num": 2}}
