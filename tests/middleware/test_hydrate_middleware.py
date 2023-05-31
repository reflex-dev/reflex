from typing import Any, Dict

import pytest

from pynecone.app import App
from pynecone.constants import IS_HYDRATED
from pynecone.middleware.hydrate_middleware import HydrateMiddleware
from pynecone.state import State, StateUpdate


def exp_is_hydrated(state: State) -> Dict[str, Any]:
    """Expected IS_HYDRATED delta that would be emitted by HydrateMiddleware.

    Args:
        state: the State that is hydrated

    Returns:
        dict similar to that returned by `State.get_delta` with IS_HYDRATED: True
    """
    return {state.get_name(): {IS_HYDRATED: "true"}}


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
        return self.change_name

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
    "State, expected, event_fixture",
    [
        (TestState, {"test_state": {"num": 1}}, "event1"),
        (TestState2, {"test_state2": {"num": 1}}, "event2"),
        (TestState3, {"test_state3": {"num": 1}}, "event3"),
    ],
)
async def test_preprocess(State, hydrate_middleware, request, event_fixture, expected):
    """Test that a state hydrate event is processed correctly.

    Args:
        State: state to process event
        hydrate_middleware: instance of HydrateMiddleware
        request: pytest fixture request
        event_fixture: The event fixture(an Event)
        expected: expected delta
    """
    app = App(state=State, load_events={"index": [State.test_handler]})
    state = State()

    update = await hydrate_middleware.preprocess(
        app=app, event=request.getfixturevalue(event_fixture), state=state
    )
    assert isinstance(update, StateUpdate)
    assert update.delta == {state.get_name(): state.dict()}
    events = update.events
    assert len(events) == 2

    # Apply the on_load event.
    update = await state._process(events[0]).__anext__()
    assert update.delta == expected

    # Apply the hydrate event.
    update = await state._process(events[1]).__anext__()
    assert update.delta == exp_is_hydrated(state)


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
    state = TestState()

    update = await hydrate_middleware.preprocess(app=app, event=event1, state=state)
    assert isinstance(update, StateUpdate)
    assert update.delta == {"test_state": state.dict()}
    assert len(update.events) == 3

    # Apply the events.
    events = update.events
    update = await state._process(events[0]).__anext__()
    assert update.delta == {"test_state": {"num": 1}}

    update = await state._process(events[1]).__anext__()
    assert update.delta == {"test_state": {"num": 2}}

    update = await state._process(events[2]).__anext__()
    assert update.delta == exp_is_hydrated(state)


@pytest.mark.asyncio
async def test_preprocess_no_events(hydrate_middleware, event1):
    """Test that app without on_load is processed correctly.

    Args:
        hydrate_middleware: instance of HydrateMiddleware
        event1: an Event.
    """
    state = TestState()
    update = await hydrate_middleware.preprocess(
        app=App(state=TestState),
        event=event1,
        state=state,
    )
    assert isinstance(update, StateUpdate)
    assert update.delta == {"test_state": state.dict()}
    assert len(update.events) == 1
    assert isinstance(update, StateUpdate)

    update = await state._process(update.events[0]).__anext__()
    assert update.delta == exp_is_hydrated(state)
