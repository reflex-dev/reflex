"""Validate pointer drops at the actual Python draft transaction boundary."""

from typing import Any, cast
from unittest.mock import patch

import pytest
from reflex_components_internal.experimental.customization import (
    Draft,
    Item,
    Preferences,
    Registry,
    Widget,
)

from session_demo.model import Session


@pytest.fixture
def session() -> Session:
    """Open an actual draft with the demo widget size limits.

    Returns:
        An independent active server session.
    """
    registry = Registry(
        tuple(
            Widget(
                key, lambda: None, min_width=6, min_height=minimum, max_height=maximum
            )
            for key, minimum, maximum in (
                ("trend", 3, 8),
                ("accounts", 3, 8),
                ("search", 2, 5),
            )
        )
    )
    value = Session(registry)
    value.begin()
    return value


def command(session: Session, op: str, **values: Any) -> dict[str, Any]:
    """Build a pointer command at the current server revision.

    Args:
        session: The active server session.
        op: The requested pointer operation.
        **values: Its operation-specific fields.

    Returns:
        A versioned pointer payload.
    """
    return {"op": op, "revision": session.engine_calls, **values}


def snapshot(session: Session) -> tuple:
    """Capture all mutation-sensitive state for atomic rejection checks.

    Args:
        session: The server session under test.

    Returns:
        Immutable state before a rejected operation.
    """
    return session.current, session.saved, session.engine_calls, session.last_operation


def test_valid_drop_stages_once_and_cancel_restores_saved(session: Session):
    """Stage one real drop and preserve saved preferences until Save."""
    saved = session.saved
    with patch.object(Draft, "stage", autospec=True, side_effect=Draft.stage) as stage:
        assert session.pointer(
            command(session, "move", id="search", before="trend")
        ) == {"id": "search"}
        assert stage.call_count == 1
    assert [item.id for item in session.current.items] == [
        "search",
        "trend",
        "accounts",
    ]
    assert [(item.y, item.height) for item in session.current.items] == [
        (0, 2),
        (2, 4),
        (6, 4),
    ]
    assert session.saved == saved
    session.cancel()
    assert session.current == saved


def test_inserted_widgets_have_stable_unique_ids_and_save_roundtrips(session: Session):
    """Retain inserted IDs and resize geometry through Save and reopen."""
    assert session.pointer(
        command(session, "add", widget="search", before="accounts")
    ) == {"id": "search-1"}
    assert session.pointer(command(session, "add", widget="search", before="")) == {
        "id": "search-2"
    }
    assert [(item.id, item.y) for item in session.current.items] == [
        ("trend", 0),
        ("search-1", 4),
        ("accounts", 6),
        ("search", 10),
        ("search-2", 12),
    ]
    session.pointer(command(session, "resize", id="search-1", width=6, height=5))
    pending = session.current
    session.save()
    session.begin()
    assert session.current == pending
    assert [item.y for item in pending.items] == [0, 4, 9, 13, 15]
    assert pending.items[1].width == 6


def test_move_and_resize_preserve_explicit_gaps_and_options(session: Session):
    """Preserve authored gaps with mixed heights and nondefault navigation."""
    session.cancel()
    session.saved = Preferences(
        (
            Item("trend", "trend", y=1, width=12, height=4),
            Item("accounts", "accounts", y=7, width=6, height=3),
            Item("search", "search", y=13, width=12, height=2),
        ),
        navigation="left",
    )
    session.begin()
    session.pointer(command(session, "move", id="search", before="trend"))
    assert [(item.id, item.y, item.height) for item in session.current.items] == [
        ("search", 1, 2),
        ("trend", 5, 4),
        ("accounts", 12, 3),
    ]
    session.pointer(command(session, "resize", id="trend", width=6, height=8))
    assert [(item.id, item.y, item.height) for item in session.current.items] == [
        ("search", 1, 2),
        ("trend", 5, 8),
        ("accounts", 16, 3),
    ]
    assert session.current.navigation == "left"
    session.pointer(command(session, "resize", id="trend", width=12, height=3))
    assert session.current.items[-1].y == 11


@pytest.mark.parametrize(
    "values",
    [
        {"op": "unknown"},
        {"op": []},
        {"op": "move", "id": "missing", "before": ""},
        {"op": "move", "id": "trend", "before": "missing"},
        {"op": "move", "id": "trend", "before": "trend"},
        {"op": "move", "id": "trend", "before": []},
        {"op": "move", "id": [], "before": ""},
        {"op": "move", "id": "trend"},
        {"op": "move", "id": "trend", "before": "", "presentation": {}},
        {"op": "add", "widget": "unregistered", "before": ""},
        {"op": "add", "widget": [], "before": ""},
        {"op": "add", "widget": "search", "before": "missing"},
        {"op": "resize", "id": "trend", "width": True, "height": 4},
        {"op": "resize", "id": "trend", "width": 7, "height": 4},
        {"op": "resize", "id": "trend", "width": 6, "height": True},
        {"op": "resize", "id": "trend", "width": 6, "height": 2},
        {"op": "resize", "id": "trend", "width": 6, "height": 9},
        {"op": "resize", "id": "search", "width": 6, "height": 6},
    ],
)
def test_invalid_pointer_payload_is_atomic(session: Session, values: dict[str, Any]):
    """Reject malformed or unsupported payloads without mutating the draft."""
    before = snapshot(session)
    with patch.object(Draft, "stage", autospec=True, side_effect=Draft.stage) as stage:
        with pytest.raises(ValueError):
            session.pointer({"revision": session.engine_calls, **values})
        assert stage.call_count == 0
    assert snapshot(session) == before


def test_stale_drop_cannot_overwrite_newer_setting_or_closed_draft(session: Session):
    """Reject stale gestures after intervening edits or closing Customize."""
    stale = command(session, "move", id="accounts", before="trend")
    session.size("trend")
    before = snapshot(session)
    with pytest.raises(ValueError, match="revision"):
        session.pointer(stale)
    assert snapshot(session) == before
    for revision in (True, "2", None):
        with pytest.raises(ValueError, match="revision"):
            session.pointer({**stale, "revision": revision})
        assert snapshot(session) == before
    session.cancel()
    before = snapshot(session)
    with pytest.raises(ValueError, match="Customize"):
        session.pointer(stale)
    assert snapshot(session) == before


def test_missing_command_object_is_rejected_without_staging(session: Session):
    """Reject a missing client payload before touching the draft."""
    before = snapshot(session)
    with pytest.raises(ValueError, match="object"):
        session.pointer(cast(dict, None))
    assert snapshot(session) == before
