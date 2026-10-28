"""Exercise real Reflex pointer event handlers against the Python draft."""

from typing import Any
from unittest.mock import patch

import pytest
from reflex_components_internal.experimental.customization import Draft

from session_demo.session_demo import State


@pytest.fixture
def state() -> State:
    """Start an independent session in Customize mode.

    Returns:
        The actual Reflex state with an active Python draft.
    """
    value = State(_reflex_internal_init=True)
    value.load()
    value.begin()
    return value


def _drop(state: State, op: str, **values: Any) -> None:
    state.pointer_command({
        "op": op,
        "revision": state.engine_calls,
        "request_id": "event-test",
        **values,
    })


def test_pointer_event_stages_once_and_returns_authoritative_instance(state: State):
    """Accept one actual add event and expose the server allocated instance."""
    before = state.engine_calls
    with patch.object(Draft, "stage", autospec=True, side_effect=Draft.stage) as stage:
        _drop(
            state,
            "add",
            widget="search",
            before="accounts",
            presentation={"ignore": True},
        )
        assert stage.call_count == 1
    assert state.pointer_result == {
        "request_id": "event-test",
        "accepted": True,
        "id": "search-1",
        "error": "",
    }
    assert state.engine_calls == before + 1
    assert [card["id"] for card in state.cards] == [
        "trend",
        "search-1",
        "accounts",
        "search",
    ]
    assert "presentation" not in state.preferences_json


@pytest.mark.parametrize(
    "payload",
    [
        {"op": []},
        {"op": "move", "id": "missing", "before": ""},
        {"op": "resize", "id": "trend", "width": 6, "height": 2},
    ],
)
def test_invalid_event_replies_rejected_without_mutation(
    state: State, payload: dict[str, Any]
):
    """Reject invalid event data without staging or stranding the request ID."""
    before, revision = state.preferences_json, state.engine_calls
    with patch.object(Draft, "stage", autospec=True, side_effect=Draft.stage) as stage:
        state.pointer_command({
            "revision": revision,
            "request_id": "rejected",
            **payload,
        })
        assert stage.call_count == 0
    assert state.engine_calls == revision
    assert state.preferences_json == before
    assert state.pointer_result["request_id"] == "rejected"
    assert state.pointer_result["accepted"] is False
    assert state.pointer_result["error"]


def test_stale_pointer_reply_preserves_intervening_settings(state: State):
    """Keep newer server settings when a gesture began at an old revision."""
    revision = state.engine_calls
    state.toggle_setting("trend", "trend")
    before = state.preferences_json
    state.pointer_command({
        "op": "move",
        "id": "accounts",
        "before": "trend",
        "revision": revision,
        "request_id": "stale",
    })
    assert not state.pointer_result["accepted"]
    assert state.preferences_json == before
    assert state.cards[0]["legend_hidden"]


def test_grid_catalog_view_is_copied_to_real_added_instance(state: State):
    """Retain catalog presentation on Add without saving it as layout geometry."""
    view = {
        "filter": {
            "filterModel": {
                "region": {"filterType": "text", "type": "contains", "filter": "North"}
            }
        },
        "sort": {"sortModel": [{"colId": "revenue", "sort": "desc"}]},
    }
    state.grid_presentation("preview-accounts", view)
    revision = state.engine_calls
    _drop(state, "add", widget="accounts", before="")
    added = next(card for card in state.cards if card["id"] == "accounts-1")
    assert added["grid_state"] == view
    assert state.engine_calls == revision + 1
    assert "filterModel" not in state.preferences_json
    state.grid_presentation("preview-accounts", {"sort": {"sortModel": []}})
    state.size("accounts-1")
    assert (
        next(card for card in state.cards if card["id"] == "accounts-1")["grid_state"]
        == view
    )


def test_pointer_geometry_survives_save_and_reset_remains_cancelable(state: State):
    """Persist only this session's accepted draft and cancel a later Reset."""
    _drop(state, "resize", id="trend", width=6, height=6)
    _drop(state, "move", id="accounts", before="trend")
    personal = state.preferences_json
    state.save()
    assert not state.editing
    state.begin()
    assert state.preferences_json == personal
    state.reset_layout()
    assert state.preferences_json != personal
    state.cancel()
    assert state.preferences_json == personal
    state.begin()
    before, calls = state.preferences_json, state.engine_calls
    _drop(state, "resize", id="trend", width=12, height=3)
    assert state.engine_calls == calls + 1
    state.cancel()
    assert state.preferences_json == before
