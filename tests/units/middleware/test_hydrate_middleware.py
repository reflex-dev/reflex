from __future__ import annotations

import pytest

from reflex.app import App
from reflex.middleware.hydrate_middleware import HydrateMiddleware
from reflex.state import State, StateUpdate


class TestState(State):
    """A test state with no return in handler."""

    __test__ = False

    num: int = 0

    def test_handler(self):
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
async def test_preprocess_no_events(hydrate_middleware, event1, mocker):
    """Test that app without on_load is processed correctly.

    Args:
        hydrate_middleware: Instance of HydrateMiddleware
        event1: An Event.
        mocker: pytest mock object.
    """
    mocker.patch("reflex.state.State.class_subclasses", {TestState})
    state = State()
    update = await hydrate_middleware.preprocess(
        app=App(state=State),
        event=event1,
        state=state,
    )
    assert isinstance(update, StateUpdate)
    assert update.delta == state.dict()
    assert not update.events
