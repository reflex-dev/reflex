"""Exercise the actual server session and Reflex event handlers."""

from dataclasses import replace
from unittest.mock import Mock, patch

import pytest
from reflex_components_internal.experimental.customization import Draft, Item

from session_demo.model import DEFAULTS, Session
from session_demo.session_demo import REGISTRY, State


def test_reflex_events_call_actual_python_engine():
    state = State(_reflex_internal_init=True)
    state.load()
    with patch.object(Draft, "stage", autospec=True, side_effect=Draft.stage) as stage:
        state.begin()
        state.move("accounts", -1)
        assert stage.call_count == 1
    assert state.operation == "Draft.stage"
    assert [card["id"] for card in state.cards] == ["accounts", "trend", "search"]
    state.cancel()
    assert [card["id"] for card in state.cards] == ["trend", "accounts", "search"]
    assert not state.editing


def test_invalid_layout_is_rejected_atomically_by_real_engine():
    session = Session(REGISTRY)
    session.begin()
    before = session.current
    with pytest.raises(ValueError, match="overlap"):
        session.stage(
            replace(before, items=(*before.items, Item("bad", "trend", y=0, width=6)))
        )
    assert session.current == before
    with pytest.raises(ValueError, match="Unsupported widget option"):
        session.option("trend", "business_write", True)
    assert session.current == before


def test_failed_save_retains_draft_for_retry():
    session = Session(REGISTRY)
    session.begin()
    session.navigation("left")
    failure = Mock(side_effect=OSError("test-only offline"))
    with pytest.raises(OSError, match="offline"):
        session.save(failure)
    assert session.draft is not None
    assert session.current.navigation == "left"
    assert session.saved == DEFAULTS
    session.save()
    assert session.draft is None
    assert session.saved.navigation == "left"


def test_reset_remains_cancelable_and_sessions_are_independent():
    first, second = Session(REGISTRY), Session(REGISTRY)
    first.begin()
    first.size("trend")
    first.save()
    personal = first.saved
    first.begin()
    first.reset()
    assert first.current == DEFAULTS
    first.cancel()
    assert first.saved == personal
    assert second.saved == DEFAULTS


def test_catalog_visibility_and_search_never_stage_geometry():
    state = State(_reflex_internal_init=True)
    state.load()
    state.begin()
    before = state.preferences_json
    calls = state.engine_calls
    state.toggle_catalog()
    state.set_query("North")
    state.toggle_catalog()
    assert state.preferences_json == before
    assert state.engine_calls == calls
    assert state.query == "North"


def test_add_move_size_and_settings_preserve_explicit_order():
    session = Session(REGISTRY)
    session.begin()
    session.add("search")
    session.move("search-1", -1)
    session.size("trend")
    session.option("accounts", "page_size", 25)
    assert [item.id for item in session.current.items] == [
        "trend",
        "accounts",
        "search-1",
        "search",
    ]
    assert session.current.items[0].width == 6
    assert dict(session.current.items[1].options) == {"page_size": 25}
    assert session.current.items[-1].y == 10


def test_mixed_height_adjacent_moves_preserve_extent_and_neighbors():
    session = Session(REGISTRY)
    session.begin()
    session.add("search")
    original = session.current
    session.move("accounts", 1)
    assert [(item.id, item.y, item.height) for item in session.current.items] == [
        ("trend", 0, 4),
        ("search", 4, 2),
        ("accounts", 6, 4),
        ("search-1", 10, 2),
    ]
    session.move("accounts", -1)
    assert session.current == original
