from typing import Set

from reflex.state import all_state_names, next_minified_state_name


def test_next_minified_state_name():
    """Test that the next_minified_state_name function returns unique state names."""
    current_state_count = len(all_state_names)
    state_names: Set[str] = set()
    gen: int = 10000
    for _ in range(gen):
        state_name = next_minified_state_name()
        assert state_name not in state_names
        state_names.add(state_name)
    assert len(state_names) == gen

    assert len(all_state_names) == current_state_count + gen
