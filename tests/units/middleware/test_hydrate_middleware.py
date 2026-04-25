from __future__ import annotations

import pytest
from reflex_base.registry import RegistrationContext

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
async def test_preprocess_no_events(
    hydrate_middleware, event1, clean_registration_context: RegistrationContext
):
    """Test that app without on_load is processed correctly.

    Args:
        hydrate_middleware: Instance of HydrateMiddleware
        event1: An Event.
        clean_registration_context: The registration context fixture, which is cleared before each test.
    """
    clean_registration_context.register_base_state(TestState)
    state = State()
    update = await hydrate_middleware.preprocess(
        app=App(_state=State),
        event=event1,
        state=state,
    )
    assert isinstance(update, StateUpdate)
    assert update.delta == state.dict()
    assert not update.events
