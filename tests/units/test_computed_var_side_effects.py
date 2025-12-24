from typing import AsyncIterator, Generator, List

import pytest

import reflex as rx
from reflex.constants.state import FIELD_MARKER
from reflex.state import BaseState, StateUpdate
from reflex.vars.base import computed_var


class SideEffectState(BaseState):
    """State for testing computed var side effects."""
    
    count: int = 0
    triggered: bool = False
    side_effect_value: str = ""

    @computed_var
    def computed_with_side_effect(self) -> int:
        if self.count > 0:
            self.triggered = True
            yield rx.window_alert("Triggered!")
            return self.count * 2
        return 0

    @computed_var
    def computed_modifying_other_var(self) -> str:
        if self.count == 5:
            self.side_effect_value = "Five"
            return "Modified"
        return "Not Modified"


@pytest.mark.asyncio
async def test_computed_var_yields_event():
    """Test that a computed var can yield an event."""
    state = SideEffectState()
    state.count = 1
    
    # This should trigger the computed var
    # In a real app, this happens via get_delta, but we can simulate the process
    # The key is that accessing the var triggers the generator and collection
    
    # Manually trigger calculation as get_delta would
    state._mark_dirty_computed_vars()
    
    # Accessing the property should run the getter
    val = state.computed_with_side_effect
    assert val == 2
    assert state.triggered is True
    
    # Check if event was collected
    assert hasattr(state, "_computed_var_events")
    assert len(state._computed_var_events) > 0
    # window_alert uses run_script which uses call_function which creates an EventHandler with _call_function
    # so checking the handler name is tricky. We check if the event spec is returned.
    event = state._computed_var_events[0]
    assert event.handler.fn.__qualname__ == "_call_function"


@pytest.mark.asyncio
async def test_computed_var_modifies_state():
    """Test that a computed var can modify other state variables."""
    state = SideEffectState()
    state.count = 5
    
    # This call to get_delta mimics the backend processing loop
    delta = state.get_delta()
    
    full_name = state.get_full_name()
    # Check that the computed var was calculated
    assert delta[full_name]["computed_modifying_other_var" + FIELD_MARKER] == "Modified"
    
    # Check that the side effect on 'side_effect_value' was captured in the delta
    # The fix involves iterating in get_delta to capture these changes
    assert delta[full_name]["side_effect_value" + FIELD_MARKER] == "Five"
