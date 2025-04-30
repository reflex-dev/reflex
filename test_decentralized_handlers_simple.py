"""Simple test for decentralized event handlers."""

import reflex as rx


class TestState(rx.State):
    """Test state class for decentralized event handlers."""

    count: int = 0


@rx.event
def reset_count(state: TestState):
    """Reset the count to zero.

    Args:
        state: The test state to modify.
    """
    state.count = 0


@rx.event
def set_count(state: TestState, value: str):
    """Set the count to a specific value.

    Args:
        state: The test state to modify.
        value: The value to set as count.
    """
    state.count = int(value)


def test_is_decentralized():
    """Test if functions are correctly identified as decentralized event handlers."""
    from reflex.event import is_decentralized_event_handler, wrap_decentralized_handler

    assert is_decentralized_event_handler(reset_count)

    wrapped = wrap_decentralized_handler(reset_count)
    assert is_decentralized_event_handler(wrapped)

    assert is_decentralized_event_handler(set_count)
    wrapped_with_params = wrap_decentralized_handler(set_count)
    assert is_decentralized_event_handler(wrapped_with_params)


if __name__ == "__main__":
    test_is_decentralized()
