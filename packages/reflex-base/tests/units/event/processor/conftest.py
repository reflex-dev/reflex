"""Fixtures for event processor tests."""

import pytest
from reflex_base.event.context import EventContext
from reflex_base.event.processor import EventProcessor


@pytest.fixture
def mock_event_processor_obj() -> EventProcessor:
    """Create an event processor.

    Returns:
        A fresh event processor.
    """

    def handle_backend_exception(ex: Exception) -> None:
        raise ex

    return EventProcessor(
        backend_exception_handler=handle_backend_exception, graceful_shutdown_timeout=1
    )


@pytest.fixture
def mock_event_processor(
    mock_root_event_context: EventContext, mock_event_processor_obj: EventProcessor
) -> EventProcessor:
    """Create an event processor with a mock root context.

    Set the mock context as the task's current context, and set the processor's
    root context to the mock context.

    Events can be queued against the processor via `await
    mock_event_processor.enqueue(token, *events)`.

    The `state_manager` fixture is used by the `mock_root_event_context` so any
    updates will be reflected in the context's state manager, and any deltas or
    frontend events can be checked via the context's `emitted_deltas` and
    `emitted_events` attributes.

    Args:
        mock_root_event_context: The mock event context to use as the root context for the processor.
        mock_event_processor_obj: The mock event processor to use for the processor's enqueue implementation.

    Returns:
        An un-started event processor with a mock root context.
    """
    mock_event_processor_obj._root_context = mock_root_event_context
    return mock_event_processor_obj
