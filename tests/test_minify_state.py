from typing import Set

from reflex.state import next_minified_state_name


def test_next_minified_state_name():
    """Test that the next_minified_state_name function returns unique state names."""
    state_names: Set[str] = set()
    gen = 10000
    for _ in range(gen):
        state_name = next_minified_state_name()
        assert state_name not in state_names
        state_names.add(state_name)
    assert len(state_names) == gen
