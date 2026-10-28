"""Headless personalization contract tests."""

from dataclasses import FrozenInstanceError, replace
from unittest.mock import Mock

import pytest
from reflex_components_internal.experimental.customization import (
    Draft,
    Item,
    Option,
    Preferences,
    Registry,
    Widget,
)


@pytest.fixture
def registry():
    """Provide a builder-owned page with one explicitly editable option.

    Returns:
        A page registry.
    """
    return Registry((
        Widget("chart", Mock(), (Option("legend", ("auto", "hidden"), "auto"),)),
    ))


@pytest.fixture
def saved():
    """Provide two adjacent real-content widget placements.

    Returns:
        The saved personal layout.
    """
    return Preferences((Item("one", "chart"), Item("two", "chart", x=4)))


def test_cancel_restores_saved_after_reset_and_navigation_change(registry, saved):
    defaults = Preferences((Item("one", "chart", width=8),), "left")
    draft = Draft(registry, saved, defaults)
    draft.reset()
    assert draft.dirty
    assert draft.current == defaults
    assert draft.cancel() == saved
    assert draft.current == saved
    assert not draft.dirty
    registry.widget("chart").render.assert_not_called()


def test_failed_personal_save_keeps_draft_for_retry(registry, saved):
    draft = Draft(registry, saved, saved)
    changed = replace(saved, navigation="left")
    draft.stage(changed)
    snapshot = draft.save()
    storage = Mock(side_effect=OSError("offline"))
    with pytest.raises(OSError, match="offline"):
        storage(snapshot)
    assert draft.current == changed
    assert draft.dirty
    assert draft.save() == snapshot
    draft.confirm_save(snapshot)
    assert not draft.dirty
    with pytest.raises(RuntimeError, match="closed"):
        draft.stage(saved)


def test_stale_save_completion_does_not_close_newer_draft(registry, saved):
    draft = Draft(registry, saved, saved)
    snapshot = draft.save()
    draft.stage(replace(saved, navigation="left"))
    with pytest.raises(ValueError, match="changed while saving"):
        draft.confirm_save(snapshot)
    assert draft.dirty
    assert draft.cancel() == saved


@pytest.mark.parametrize("operation", ["save", "reset", "cancel"])
def test_closed_draft_rejects_commands(registry, saved, operation):
    draft = Draft(registry, saved, saved)
    draft.cancel()
    with pytest.raises(RuntimeError, match="closed"):
        getattr(draft, operation)()


@pytest.mark.parametrize(
    "item",
    [
        Item("one", "unregistered"),
        Item("one", "chart", x=-1),
        Item("one", "chart", x=10),
        Item("one", "chart", y=-1),
        Item("one", "chart", width=0),
        Item("one", "chart", height=25),
        Item("one", "chart", x=True),
        Item("one", "chart", options=(("business_write", True),)),
        Item("one", "chart", options=(("legend", "bad"),)),
        Item("one", "chart", options=(("legend", "auto"), ("legend", "hidden"))),
    ],
)
def test_invalid_candidate_is_atomic(registry, saved, item):
    draft = Draft(registry, saved, saved)
    with pytest.raises(ValueError):
        draft.stage(Preferences((item,)))
    assert draft.current == saved
    assert not draft.dirty
    registry.widget("chart").render.assert_not_called()


def test_overlapping_widgets_and_duplicate_ids_are_rejected(registry, saved):
    for second in (Item("two", "chart", x=3), Item("one", "chart", x=4)):
        with pytest.raises(ValueError):
            registry.validate(Preferences((saved.items[0], second)))


def test_adjacency_order_and_gaps_are_preserved(registry, saved):
    draft = Draft(registry, saved, saved)
    changed = replace(saved, items=(saved.items[1], replace(saved.items[0], y=8)))
    draft.stage(changed)
    assert draft.save().items == changed.items
    assert draft.save().items[1].y == 8


def test_option_value_types_do_not_confuse_true_with_one():
    option = Option("density", (1, 2), 1)
    assert not option.accepts(True)
    with pytest.raises(ValueError):
        Option("density", (1, 2), True)


def test_input_collections_cannot_mutate_preferences():
    options = [["legend", "auto"]]
    item = Item("one", "chart", options=options)
    items = [item]
    preferences = Preferences(items)
    options[0][1] = "hidden"
    items.clear()
    assert preferences.items == (item,)
    assert item.options == (("legend", "auto"),)
    with pytest.raises(FrozenInstanceError):
        item.x = 4


def test_builder_contract_rejects_duplicate_registration_and_bad_bounds(
    registry, saved
):
    widget = registry.widget("chart")
    with pytest.raises(ValueError, match="unique"):
        Registry((widget, widget))
    with pytest.raises(ValueError, match="positive"):
        Widget("broken", Mock(), min_width=0)
    with pytest.raises(ValueError, match="unique"):
        Widget("broken", Mock(), options=(widget.options[0], widget.options[0]))
    with pytest.raises(ValueError, match="Navigation"):
        registry.validate(replace(saved, navigation="bottom"))


def test_preview_and_normal_content_share_builder_renderer(registry):
    renderer = registry.widget("chart").render
    assert registry.widget("chart").render is renderer
    renderer.assert_not_called()


def test_registration_detaches_mutable_builder_input():
    choices = ["auto", "hidden"]
    option = Option("legend", choices, "auto")
    options = [option]
    widget = Widget("chart", Mock(), options)
    choices.clear()
    options.clear()
    assert widget.options == (option,)
    assert option.choices == ("auto", "hidden")
    assert option.accepts("auto")
    with pytest.raises(ValueError, match="immutable"):
        Option("bad", ([1],), [1])
