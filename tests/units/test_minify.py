"""Unit tests for reflex/minify.py."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from reflex_base.registry import DefaultNameResolver, RegistrationContext, scheme_digest
from reflex_base.utils.exceptions import ReflexError

import reflex as rx
from reflex.environment import environment
from reflex.minify import (
    MINIFY_JSON,
    SCHEMA_VERSION,
    MinifyConfig,
    MinifyNameResolver,
    StateEntry,
    _find_missing_entries,
    _get_minify_json_path,
    _load_minify_config_uncached,
    clear_config_cache,
    ensure_minify_resolver_for_active_context,
    generate_minify_config,
    get_parent_key,
    get_state_full_path,
    int_to_minified_name,
    minified_name_to_int,
    raise_for_stale_names,
    save_minify_config,
    sync_minify_config,
    validate_minify_config,
    warn_if_config_stale,
)
from reflex.state import BaseState, State
from tests.units.minify_helpers import (
    install_config,
    resolved_event_id,
    run_in_fresh_interpreter,
    set_minify_modes,
)
from tests.units.name_resolvers import stub_resolver, temporary_resolver


def test_zero():
    """Test that 0 maps to 'a'."""
    assert int_to_minified_name(0) == "a"


def test_int_to_minified_name_single_char():
    """Test single character mappings."""
    assert int_to_minified_name(1) == "b"
    assert int_to_minified_name(25) == "z"
    assert int_to_minified_name(26) == "A"
    assert int_to_minified_name(51) == "Z"
    assert int_to_minified_name(52) == "$"
    assert int_to_minified_name(53) == "_"


def test_two_chars():
    """Test two character mappings (base 54)."""
    # 54 = 1*54 + 0 -> 'ba'
    assert int_to_minified_name(54) == "ba"
    # 55 = 1*54 + 1 -> 'bb'
    assert int_to_minified_name(55) == "bb"


def test_unique_names():
    """Test that a large range of IDs produce unique names."""
    names = set()
    for i in range(10000):
        name = int_to_minified_name(i)
        assert name not in names, f"Duplicate name {name} for id {i}"
        names.add(name)


def test_negative_raises():
    """Test that negative IDs raise ValueError."""
    with pytest.raises(ValueError, match="non-negative"):
        int_to_minified_name(-1)


def test_minified_name_to_int_single_char():
    """Test single character conversion."""
    assert minified_name_to_int("a") == 0
    assert minified_name_to_int("b") == 1
    assert minified_name_to_int("z") == 25
    assert minified_name_to_int("A") == 26
    assert minified_name_to_int("Z") == 51


def test_roundtrip():
    """Test that int -> minified -> int roundtrip works."""
    for i in range(1000):
        minified = int_to_minified_name(i)
        result = minified_name_to_int(minified)
        assert result == i, f"Roundtrip failed for {i}: {minified} -> {result}"


def test_invalid_char_raises():
    """Test that invalid characters raise ValueError."""
    with pytest.raises(ValueError, match="Invalid character"):
        minified_name_to_int("!")


def test_root_state_path():
    """Test that root State has correct full path."""
    path = get_state_full_path(State)
    assert path == "reflex.state.State"


def test_substate_path():
    """Test that substates have correct full paths."""

    class TestState(BaseState):
        pass

    path = get_state_full_path(TestState)
    assert "TestState" in path
    assert path.startswith(f"{__name__}.")


def test_no_config_returns_none(temp_minify_json):
    """Test that missing minify.json returns None."""
    assert _load_minify_config_uncached() is None
    assert scheme_digest() == ""


def test_save_and_load_config(temp_minify_json, monkeypatch):
    """Test saving and loading a config."""
    set_minify_modes(monkeypatch, states=True, events=True)
    install_config(
        states={"test.module.MyState": "a"},
        events={"test.module.MyState": {"handler": "a"}},
    )

    assert scheme_digest()
    loaded = _load_minify_config_uncached()
    assert loaded is not None
    assert loaded["states"]["test.module.MyState"] == {"id": "a", "parent": None}
    assert loaded["events"]["test.module.MyState"]["handler"] == "a"


def test_invalid_version_raises(temp_minify_json):
    """Test that invalid version raises ValueError."""
    config = {"version": 999, "states": {}, "events": {}}
    path = temp_minify_json / MINIFY_JSON
    with path.open("w") as f:
        json.dump(config, f)

    with pytest.raises(ValueError, match=r"Unsupported.*version"):
        _load_minify_config_uncached()


def test_missing_states_raises(temp_minify_json):
    """Test that missing 'states' key raises ValueError."""
    config = {"version": SCHEMA_VERSION, "events": {}}
    path = temp_minify_json / MINIFY_JSON
    with path.open("w") as f:
        json.dump(config, f)

    with pytest.raises(ValueError, match="'states' must be"):
        _load_minify_config_uncached()


def test_flat_string_states_raise(temp_minify_json):
    """Test that legacy flat string state values are rejected."""
    config = {
        "version": SCHEMA_VERSION,
        "states": {"test.module.MyState": "a"},
        "events": {},
        "vars": {},
    }
    path = temp_minify_json / MINIFY_JSON
    with path.open("w") as f:
        json.dump(config, f)

    with pytest.raises(ValueError, match="must be an object with a string 'id'"):
        _load_minify_config_uncached()


@pytest.mark.parametrize("payload", ["[1, 2, 3]", '"a string"', "42", "null"])
def test_non_object_json_raises(temp_minify_json: Path, payload: str) -> None:
    """Valid JSON that isn't an object is rejected as a ValueError."""
    (temp_minify_json / MINIFY_JSON).write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="must be a JSON object"):
        _load_minify_config_uncached()


@pytest.mark.parametrize("bad_id", ["", "1bad", "a-b", "a.b", "a b"])
def test_invalid_state_id_raises(temp_minify_json: Path, bad_id: str) -> None:
    """State ids must be non-empty and built only from the minify alphabet."""
    config = {
        "version": SCHEMA_VERSION,
        "states": {"test.module.MyState": {"id": bad_id, "parent": None}},
        "events": {},
        "vars": {},
    }
    (temp_minify_json / MINIFY_JSON).write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid id"):
        _load_minify_config_uncached()


@pytest.mark.parametrize("bad_id", ["", "1bad", "a-b"])
def test_invalid_event_id_raises(temp_minify_json: Path, bad_id: str) -> None:
    """Event ids go through the same alphabet check as state ids."""
    config = {
        "version": SCHEMA_VERSION,
        "states": {},
        "events": {"test.module.MyState": {"handler": bad_id}},
        "vars": {},
    }
    (temp_minify_json / MINIFY_JSON).write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid id"):
        _load_minify_config_uncached()


def test_generate_for_root_state():
    """Test generating config for the root State."""
    config = generate_minify_config(State)

    assert config["version"] == SCHEMA_VERSION
    assert "reflex.state.State" in config["states"]
    assert config["states"]["reflex.state.State"]["parent"] is None
    # State should have event handlers like set_is_hydrated
    state_path = "reflex.state.State"
    assert state_path in config["events"]
    assert "set_is_hydrated" in config["events"][state_path]


def test_generates_unique_sibling_ids():
    """Test that sibling states get unique IDs."""

    class ParentState(BaseState):
        pass

    class ChildA(ParentState):
        pass

    class ChildB(ParentState):
        pass

    config = generate_minify_config(ParentState)

    # Find the IDs for ChildA and ChildB
    child_a_path = get_state_full_path(ChildA)
    child_b_path = get_state_full_path(ChildB)

    child_a_entry = config["states"].get(child_a_path)
    child_b_entry = config["states"].get(child_b_path)

    assert child_a_entry is not None
    assert child_b_entry is not None
    assert child_a_entry["id"] != child_b_entry["id"]
    parent_path = get_state_full_path(ParentState)
    assert child_a_entry["parent"] == parent_path
    assert child_b_entry["parent"] == parent_path


def test_valid_config_no_errors():
    """Test that a valid config produces no errors."""
    config = generate_minify_config(State)
    errors, _warnings, missing = validate_minify_config(config, State)

    assert len(errors) == 0
    assert len(missing) == 0


def test_duplicate_state_ids_detected():
    """Test that duplicate state IDs are detected."""
    config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
            "test.Parent": StateEntry(id="a", parent=None),
            "test.Parent.ChildA": StateEntry(id="b", parent="test.Parent"),
            "test.Parent.ChildB": StateEntry(  # Duplicate!
                id="b", parent="test.Parent"
            ),
        },
        "events": {},
        "vars": {},
    }

    # Create a mock state tree
    class Parent(BaseState):
        pass

    errors, _warnings, _missing = validate_minify_config(config, Parent)

    assert any("Duplicate state_id='b'" in e for e in errors)


def test_validate_detects_orphan_sibling_collision():
    """An orphaned entry sharing an id with a live sibling is an error."""

    class OrphanCollisionParent(BaseState):
        pass

    class OrphanCollisionLiveChild(OrphanCollisionParent):
        pass

    parent_path = get_state_full_path(OrphanCollisionParent)
    live_path = get_state_full_path(OrphanCollisionLiveChild)
    orphan_path = f"{parent_path}.DeadChild"

    config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
            parent_path: StateEntry(id="a", parent=None),
            live_path: StateEntry(id="b", parent=parent_path),
            orphan_path: StateEntry(id="b", parent=parent_path),  # collision!
        },
        "events": {},
        "vars": {},
    }

    errors, _warnings, _missing = validate_minify_config(config, OrphanCollisionParent)

    assert any("Duplicate state_id='b'" in e and "(orphaned)" in e for e in errors), (
        f"Expected orphan collision error, got: {errors}"
    )


def test_validate_no_cross_group_orphan_false_positive():
    """An orphan of a different parent may share an id with a root state."""

    class OrphanNoFalsePositiveRoot(BaseState):
        pass

    root_path = get_state_full_path(OrphanNoFalsePositiveRoot)
    config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
            root_path: StateEntry(id="a", parent=None),
            # Orphan from an unrelated (deleted) parent, same id "a".
            "gone.module.Gone.Child": StateEntry(id="a", parent="gone.module.Gone"),
        },
        "events": {},
        "vars": {},
    }

    errors, warnings, _missing = validate_minify_config(
        config, OrphanNoFalsePositiveRoot
    )

    assert not errors, f"Unexpected errors: {errors}"
    assert any("Orphaned state" in w for w in warnings)


def test_validate_reports_missing_framework_states():
    """Framework states are ordinary states: omitting them is a gap to sync."""

    class UserOnlyState(State):
        def do_thing(self):
            pass

    user_path = get_state_full_path(UserOnlyState)
    # Config omits the framework reflex.state.State entries.
    config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {user_path: StateEntry(id="a", parent="reflex.state.State")},
        "events": {user_path: {"do_thing": "a"}},
        "vars": {},
    }

    _errors, _warnings, missing = validate_minify_config(config, State)

    assert "state:reflex.state.State" in missing
    assert "event:reflex.state.State.hydrate" in missing
    assert f"state:{user_path}" not in missing
    assert f"event:{user_path}.do_thing" not in missing


def test_validate_warns_stale_parent():
    """A live entry whose stored parent disagrees with the code is flagged."""

    class StaleParentParent(BaseState):
        pass

    class StaleParentChild(StaleParentParent):
        pass

    parent_path = get_state_full_path(StaleParentParent)
    child_path = get_state_full_path(StaleParentChild)
    config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
            parent_path: StateEntry(id="a", parent=None),
            child_path: StateEntry(id="b", parent="wrong.Path"),
        },
        "events": {},
        "vars": {},
    }

    errors, warnings, _missing = validate_minify_config(config, StaleParentParent)

    assert not errors, f"Unexpected errors: {errors}"
    assert any("Stale parent" in w and child_path in w for w in warnings)


def test_sync_adds_new_states():
    """Test that sync adds new states."""

    class TestState(BaseState):
        def handler(self):
            pass

    # Start with empty config
    existing_config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {},
        "events": {},
        "vars": {},
    }

    new_config = sync_minify_config(existing_config, TestState)

    # Should have added the state with its parent key recorded
    state_path = get_state_full_path(TestState)
    assert state_path in new_config["states"]
    assert new_config["states"][state_path]["parent"] == get_parent_key(TestState)
    assert state_path in new_config["events"]
    assert "handler" in new_config["events"][state_path]


def test_sync_preserves_existing_ids():
    """Test that sync preserves existing IDs."""

    class TestState(BaseState):
        def handler_a(self):
            pass

        def handler_b(self):
            pass

    state_path = get_state_full_path(TestState)

    # Start with partial config
    existing_config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
            state_path: StateEntry(id="bU", parent=None)  # codespell:ignore
        },
        "events": {state_path: {"handler_a": "k"}},  # Another arbitrary name
        "vars": {},
    }

    new_config = sync_minify_config(existing_config, TestState)

    # Existing IDs should be preserved
    assert new_config["states"][state_path]["id"] == "bU"  # codespell:ignore
    assert new_config["events"][state_path]["handler_a"] == "k"
    # New handler should be added with next ID (k=10, so next is l=11)
    assert "handler_b" in new_config["events"][state_path]
    assert new_config["events"][state_path]["handler_b"] == "l"  # 10 + 1 = 11 -> 'l'


def test_sync_no_sibling_collision_across_modules(temp_minify_json):
    """Test that sync assigns unique IDs to siblings of the same parent.

    When children of the same parent state class are defined in different
    Python modules, their get_state_full_path() produces different string
    prefixes. The sync function must group siblings by the actual parent
    class object, not by string-splitting the path, to avoid ID collisions.
    Runs in a forked context, so the relocated class stays out of later tests.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
    """

    class ParentState(BaseState):
        pass

    class ChildA(ParentState):
        pass

    class ChildB(ParentState):
        pass

    # Simulate ChildB living in another module, the way get_state_full_path
    # sees a state relocated by ``ComponentState.create()``. Its path now
    # diverges from ChildA's in the prefix, not just the trailing class name,
    # so grouping siblings by string-splitting the path would put the two in
    # different buckets and hand both the same id.
    ChildB.__original_module__ = "some.other.module"

    parent_path = get_state_full_path(ParentState)
    child_a_path = get_state_full_path(ChildA)
    assert not get_state_full_path(ChildB).startswith(parent_path)

    # Config already has ParentState and ChildA assigned
    existing_config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
            parent_path: StateEntry(id="a", parent=None),
            child_a_path: StateEntry(id="a", parent=parent_path),
        },
        "events": {},
        "vars": {},
    }

    # Sync should assign ChildB a DIFFERENT ID than ChildA
    new_config = sync_minify_config(existing_config, ParentState)

    child_b_path = get_state_full_path(ChildB)
    assert child_b_path in new_config["states"]
    assert (
        new_config["states"][child_a_path]["id"]
        != new_config["states"][child_b_path]["id"]
    ), (
        f"Sibling collision: ChildA and ChildB both got "
        f"'{new_config['states'][child_a_path]['id']}'"
    )


def test_validate_detects_sibling_collision():
    """Test that validate catches duplicate IDs among siblings of same parent."""

    class ParentState(BaseState):
        pass

    class ChildA(ParentState):
        pass

    class ChildB(ParentState):
        pass

    parent_path = get_state_full_path(ParentState)
    child_a_path = get_state_full_path(ChildA)
    child_b_path = get_state_full_path(ChildB)

    # Manually create a config with colliding sibling IDs
    bad_config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
            parent_path: StateEntry(id="a", parent=None),
            child_a_path: StateEntry(id="a", parent=parent_path),
            child_b_path: StateEntry(id="a", parent=parent_path),  # collision!
        },
        "events": {},
        "vars": {},
    }

    errors, _warnings, _missing = validate_minify_config(bad_config, ParentState)
    assert any("Duplicate" in e and "'a'" in e for e in errors), (
        f"Expected duplicate ID error, got: {errors}"
    )


def test_sync_reserves_orphan_ids():
    """A new sibling must not reuse the id of an orphaned entry."""

    class OrphanReserveParent(BaseState):
        pass

    class OrphanReserveRenamedChild(OrphanReserveParent):
        pass

    parent_path = get_state_full_path(OrphanReserveParent)
    orphan_path = f"{parent_path}.OldChild"

    existing_config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
            parent_path: StateEntry(id="a", parent=None),
            orphan_path: StateEntry(id="a", parent=parent_path),
        },
        "events": {},
        "vars": {},
    }

    new_config = sync_minify_config(existing_config, OrphanReserveParent)

    renamed_path = get_state_full_path(OrphanReserveRenamedChild)
    assert new_config["states"][orphan_path] == StateEntry(id="a", parent=parent_path)
    assert new_config["states"][renamed_path]["id"] != "a"


def test_sync_reassign_deleted_keeps_orphan_ids_reserved():
    """``reassign_deleted`` fills gaps but never reuses retained orphan ids."""

    class OrphanReassignParent(BaseState):
        pass

    class OrphanReassignChild(OrphanReassignParent):
        pass

    parent_path = get_state_full_path(OrphanReassignParent)
    orphan_path = f"{parent_path}.OldChild"

    existing_config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
            parent_path: StateEntry(id="a", parent=None),
            orphan_path: StateEntry(id="a", parent=parent_path),
        },
        "events": {},
        "vars": {},
    }

    new_config = sync_minify_config(
        existing_config, OrphanReassignParent, reassign_deleted=True
    )

    child_path = get_state_full_path(OrphanReassignChild)
    assert new_config["states"][child_path]["id"] != "a"


def test_sync_prune_frees_orphan_ids():
    """``prune`` removes orphans, freeing their ids for reassignment."""

    class OrphanPruneParent(BaseState):
        pass

    class OrphanPruneChild(OrphanPruneParent):
        pass

    parent_path = get_state_full_path(OrphanPruneParent)
    orphan_path = f"{parent_path}.OldChild"

    existing_config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
            parent_path: StateEntry(id="a", parent=None),
            orphan_path: StateEntry(id="b", parent=parent_path),
        },
        "events": {},
        "vars": {},
    }

    new_config = sync_minify_config(
        existing_config, OrphanPruneParent, reassign_deleted=True, prune=True
    )

    child_path = get_state_full_path(OrphanPruneChild)
    assert orphan_path not in new_config["states"]
    assert new_config["states"][child_path]["id"] == "b"


def test_sync_heals_stale_parent():
    """Sync rewrites a live entry's stored parent to the actual value."""

    class HealParentParent(BaseState):
        pass

    class HealParentChild(HealParentParent):
        pass

    parent_path = get_state_full_path(HealParentParent)
    child_path = get_state_full_path(HealParentChild)

    existing_config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
            parent_path: StateEntry(id="a", parent=None),
            child_path: StateEntry(id="b", parent="wrong.Path"),
        },
        "events": {},
        "vars": {},
    }

    new_config = sync_minify_config(existing_config, HealParentParent)

    assert new_config["states"][child_path] == StateEntry(id="b", parent=parent_path)


def test_disabled_by_default(temp_minify_json):
    """Both modes default to disabled even with a config present."""
    install_config(states={"x": "a"}, events={"x": {"h": "a"}})
    assert scheme_digest() == ""


@pytest.mark.parametrize("var", ["REFLEX_MINIFY_STATES", "REFLEX_MINIFY_EVENTS"])
def test_enabled_requires_env_and_config(temp_minify_json, monkeypatch, var):
    """Each mode renames only when its env var is on AND a config exists."""
    monkeypatch.setenv(getattr(environment, var).name, "1")
    clear_config_cache()
    assert scheme_digest() == ""  # env on, no config
    install_config(states={"x": "a"}, events={"x": {"h": "a"}})
    assert scheme_digest()


def test_modes_toggle_independently(temp_minify_json, monkeypatch):
    """States can be on while events stay off (or vice versa)."""

    class ToggledState(State):
        def handle(self):
            pass

    path = get_state_full_path(ToggledState)
    set_minify_modes(monkeypatch, states=True, events=False)
    install_config(
        states={path: StateEntry(id="z", parent="reflex.state.State")},
        events={path: {"handle": "a"}},
    )
    assert ToggledState.get_name() == "z"
    assert resolved_event_id(ToggledState, "handle") is None


def test_disabled_returns_none(temp_minify_json):
    """When neither flag is enabled, the resolver returns None for all."""
    resolver = MinifyNameResolver(
        config={"version": SCHEMA_VERSION, "states": {}, "events": {}, "vars": {}},
        states_enabled=False,
        events_enabled=False,
        vars_enabled=False,
    )
    assert resolver.resolve_state_name(State) is None
    assert resolver.resolve_handler_name(State, "any") is None


def test_resolver_no_config_returns_none():
    """No config means no overrides even when flags are enabled."""
    resolver = MinifyNameResolver(
        config=None, states_enabled=True, events_enabled=True, vars_enabled=False
    )
    assert resolver.resolve_state_name(State) is None
    assert resolver.resolve_handler_name(State, "any") is None


def test_state_lookup():
    """A state with an entry resolves to its id."""

    # Non-framework state — see :func:`_is_framework_state`.
    class UserStateResolverCacheTest(State):
        pass

    config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
            get_state_full_path(UserStateResolverCacheTest): StateEntry(
                id="rs", parent=None
            )
        },
        "events": {},
        "vars": {},
    }
    resolver = MinifyNameResolver(
        config=config, states_enabled=True, events_enabled=False, vars_enabled=False
    )
    assert resolver.resolve_state_name(UserStateResolverCacheTest) == "rs"


def test_event_lookup():
    """Handlers with an entry resolve to their ids, others to ``None``."""

    class UserStateEventCacheTest(State):
        pass

    config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {},
        "events": {
            get_state_full_path(UserStateEventCacheTest): {"foo": "f", "bar": "b"}
        },
        "vars": {},
    }
    resolver = MinifyNameResolver(
        config=config, states_enabled=False, events_enabled=True, vars_enabled=False
    )
    assert resolver.resolve_handler_name(UserStateEventCacheTest, "foo") == "f"
    assert resolver.resolve_handler_name(UserStateEventCacheTest, "bar") == "b"
    assert resolver.resolve_handler_name(UserStateEventCacheTest, "missing") is None


def test_from_disk_handles_malformed_config(temp_minify_json):
    """``from_disk`` returns a usable resolver even when minify.json is bad."""
    path = temp_minify_json / MINIFY_JSON
    with path.open("w") as f:
        f.write("{not valid json")
    resolver = MinifyNameResolver.from_disk()
    # config falls back to None — every lookup returns None.
    assert resolver.config is None
    assert resolver.resolve_state_name(State) is None
    assert resolver.resolve_handler_name(State, "any") is None


def test_root_state_name_follows_config(temp_minify_json, monkeypatch):
    """``reflex.state.State`` is renamed like any other configured state."""
    set_minify_modes(monkeypatch, states=True)
    install_config(states={"reflex.state.State": "a"})

    assert State.get_name() == "a"


def test_hydrate_event_name_resolves_its_handler(temp_minify_json, monkeypatch):
    """The hydrate name resolves its handler, however it is reached.

    The frontend sends whatever this returns, so a literal ``.hydrate``
    suffix here would never reach the minified registry key.
    """
    from reflex_base.event import get_event, get_hydrate_event, get_hydrate_event_name

    set_minify_modes(monkeypatch, states=True, events=True)
    install_config(
        states={"reflex.state.State": "a"},
        events={"reflex.state.State": {"hydrate": "q"}},
    )

    state = State(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]

    assert get_hydrate_event_name() == "a.q"
    assert get_hydrate_event(state) == "a.q"
    assert get_event(state, "hydrate") == "a.q"
    assert "a.q" in RegistrationContext.get().event_handlers


def test_empty_without_minification(temp_minify_json):
    """No config in force means no name is rewritten, so nothing to agree on."""
    assert scheme_digest() == ""


def test_empty_when_config_present_but_modes_off(temp_minify_json, monkeypatch):
    """A config nobody applies leaves the wire names untouched."""
    set_minify_modes(monkeypatch, states=False, events=False)
    install_config(states={"reflex.state.State": "a"})

    assert scheme_digest() == ""


def test_differs_when_a_mode_is_toggled(temp_minify_json, monkeypatch):
    """Turning events on renames handlers, so the schemes must not match."""
    config_states: dict[str, str | StateEntry] = {"reflex.state.State": "a"}
    config_events = {"reflex.state.State": {"hydrate": "q"}}

    set_minify_modes(monkeypatch, states=True, events=False)
    install_config(states=config_states, events=config_events)
    states_only = scheme_digest()

    set_minify_modes(monkeypatch, events=True)
    install_config(states=config_states, events=config_events)
    both = scheme_digest()

    assert states_only
    assert both
    assert states_only != both


def test_same_scheme_digests_identically_across_processes(tmp_path):
    """Both sides compute the digest independently; they must agree.

    Same-process stability is not enough: the frontend digest is baked at
    compile time and the backend recomputes it in another interpreter.
    """
    config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {"reflex.state.State": StateEntry(id="a", parent=None)},
        "events": {"reflex.state.State": {"hydrate": "q"}},
        "vars": {},
    }
    run_in_fresh_interpreter(
        tmp_path,
        config,
        """
            from reflex_base.registry import scheme_digest
            import reflex.state

            first = scheme_digest()
            assert first, "expected a digest with minification enabled"
            assert scheme_digest() == first, "digest is not stable"
            print(first)
        """,
        REFLEX_MINIFY_STATES="1",
        REFLEX_MINIFY_EVENTS="1",
    )


def test_independent_of_which_states_have_registered(temp_minify_json, monkeypatch):
    """The digest hashes the config, not the state tree.

    Both sides read the same ``minify.json`` but register states at
    different moments, so keying on the tree would make agreement depend
    on timing.
    """
    set_minify_modes(monkeypatch, states=True)
    install_config(states={"reflex.state.State": "a"})

    before = scheme_digest()

    class RegisteredAfterwards(State):
        value: str = ""

    assert RegisteredAfterwards.get_full_name()
    assert scheme_digest() == before


def test_differs_when_an_id_changes(temp_minify_json, monkeypatch):
    """Editing minify.json renames states, so the schemes must not match.

    ``_install_config`` reinstalls the resolver, which is the only thing
    that invalidates the digest: a value cached anywhere that outlives the
    resolver would fail here rather than reject every later connection.
    """
    set_minify_modes(monkeypatch, states=True)

    install_config(states={"reflex.state.State": "a"})
    before = scheme_digest()

    install_config(states={"reflex.state.State": "b"})
    after = scheme_digest()

    assert before != after


def test_resolver_active_before_any_state_registers(tmp_path):
    """A fresh interpreter registers user states under their minified name."""
    run_in_fresh_interpreter(
        tmp_path,
        {
            "version": SCHEMA_VERSION,
            "states": {
                "check.State.Foo": StateEntry(id="f", parent="reflex.state.State")
            },
            "events": {},
            "vars": {},
        },
        """
            from reflex_base.registry import RegistrationContext
            import reflex.state
            resolver = RegistrationContext.ensure_context().name_resolver
            assert type(resolver).__name__ == "MinifyNameResolver", resolver
            class Foo(reflex.state.State):
                pass
            assert Foo.get_name() == "f", Foo.get_name()
        """,
        REFLEX_MINIFY_STATES="1",
    )


def test_no_resolver_installed_without_config(temp_minify_json: Path) -> None:
    """Without a ``minify.json`` the zero-cost default resolver stays in place."""
    ctx = RegistrationContext.ensure_context()
    ctx.set_name_resolver(DefaultNameResolver())

    ensure_minify_resolver_for_active_context()

    assert type(ctx.name_resolver) is DefaultNameResolver


def test_resolver_installed_when_config_appears(temp_minify_json: Path) -> None:
    """A ``minify.json`` showing up later still swaps the resolver in."""
    ctx = RegistrationContext.ensure_context()
    ctx.set_name_resolver(DefaultNameResolver())

    install_config(states={"test.module.MyState": "a"})
    ensure_minify_resolver_for_active_context()

    assert isinstance(ctx.name_resolver, MinifyNameResolver)
    assert ctx.name_resolver.config is not None


def test_minify_json_path_defaults_to_the_working_directory(
    temp_minify_json: Path,
) -> None:
    """Without ``REFLEX_MINIFY_CONFIG``, the app's own ``minify.json`` is used."""
    assert _get_minify_json_path() == temp_minify_json / MINIFY_JSON


@pytest.mark.parametrize("absolute", [True, False])
def test_minify_json_path_from_env_var(
    temp_minify_json: Path, monkeypatch: pytest.MonkeyPatch, absolute: bool
) -> None:
    """``REFLEX_MINIFY_CONFIG`` names the file, relative to the working directory.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
        monkeypatch: The pytest monkeypatch fixture.
        absolute: Whether the env var holds an absolute path.
    """
    target = temp_minify_json / "conf" / "names.json"
    monkeypatch.setenv(
        environment.REFLEX_MINIFY_CONFIG.name,
        str(target if absolute else target.relative_to(temp_minify_json)),
    )
    assert _get_minify_json_path() == target


def _install_in(directory: Path, states: dict[str, str]) -> MinifyConfig:
    """Write a ``minify.json`` into ``directory`` without activating it.

    Args:
        directory: Where to write the file.
        states: ``state_path -> minified_id`` map.

    Returns:
        The written config.
    """
    config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
            path: StateEntry(id=state_id, parent=None)
            for path, state_id in states.items()
        },
        "events": {},
        "vars": {},
    }
    directory.mkdir(parents=True, exist_ok=True)
    (directory / MINIFY_JSON).write_text(json.dumps(config))
    return config


def test_resolver_follows_the_app_directory(
    temp_minify_json: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each app is loaded with the names of its own ``minify.json``, or none.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
        monkeypatch: The pytest monkeypatch fixture.
    """

    class FollowState(State):
        pass

    path = get_state_full_path(FollowState)
    set_minify_modes(monkeypatch, states=True)
    _install_in(temp_minify_json, {path: "f"})
    _install_in(temp_minify_json / "other", {path: "g"})
    (temp_minify_json / "plain").mkdir()
    ctx = RegistrationContext.ensure_context()

    ensure_minify_resolver_for_active_context()
    assert FollowState.get_name() == "f"
    resolver = ctx.name_resolver
    ensure_minify_resolver_for_active_context()
    assert ctx.name_resolver is resolver

    monkeypatch.chdir(temp_minify_json / "plain")
    ensure_minify_resolver_for_active_context()
    assert type(ctx.name_resolver) is DefaultNameResolver
    assert FollowState.get_name() == RegistrationContext.default_state_name(FollowState)

    monkeypatch.chdir(temp_minify_json / "other")
    ensure_minify_resolver_for_active_context()
    assert FollowState.get_name() == "g"

    monkeypatch.chdir(temp_minify_json)
    ensure_minify_resolver_for_active_context()
    assert FollowState.get_name() == "f"


def test_resolver_reloads_an_edited_config(
    temp_minify_json: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An edit to ``minify.json`` or a toggled mode applies on the next app load.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
        monkeypatch: The pytest monkeypatch fixture.
    """

    class EditedState(State):
        pass

    path = get_state_full_path(EditedState)
    set_minify_modes(monkeypatch, states=True)
    _install_in(temp_minify_json, {path: "e"})
    ensure_minify_resolver_for_active_context()
    assert EditedState.get_name() == "e"

    # Same size, modification time put back: only the content tells.
    config_file = temp_minify_json / MINIFY_JSON
    stat = config_file.stat()
    _install_in(temp_minify_json, {path: "f"})
    os.utime(config_file, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert config_file.stat().st_size == stat.st_size
    ensure_minify_resolver_for_active_context()
    assert EditedState.get_name() == "f"

    set_minify_modes(monkeypatch, states=False)
    ensure_minify_resolver_for_active_context()
    assert EditedState.get_name() == RegistrationContext.default_state_name(EditedState)


def test_malformed_config_warns_once_until_edited(
    temp_minify_json: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A broken ``minify.json`` is not re-read on every app load.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
        caplog: The pytest log capture fixture.
    """
    (temp_minify_json / MINIFY_JSON).write_text("{not json")
    ensure_minify_resolver_for_active_context()
    ensure_minify_resolver_for_active_context()
    assert caplog.text.count("could not be loaded") == 1

    (temp_minify_json / MINIFY_JSON).write_text("{still not json")
    ensure_minify_resolver_for_active_context()
    assert caplog.text.count("could not be loaded") == 2


def test_env_var_pins_the_config_for_every_directory(
    temp_minify_json: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``REFLEX_MINIFY_CONFIG`` applies whichever directory the app is in.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
        monkeypatch: The pytest monkeypatch fixture.
    """

    class PinnedState(State):
        pass

    path = get_state_full_path(PinnedState)
    set_minify_modes(monkeypatch, states=True)
    _install_in(temp_minify_json / "deploy", {path: "p"})
    _install_in(temp_minify_json / "app", {path: "q"})
    monkeypatch.setenv(
        environment.REFLEX_MINIFY_CONFIG.name,
        str(temp_minify_json / "deploy" / MINIFY_JSON),
    )

    for directory in (temp_minify_json, temp_minify_json / "app"):
        monkeypatch.chdir(directory)
        ensure_minify_resolver_for_active_context()
        assert PinnedState.get_name() == "p"


def test_custom_resolver_is_left_in_place(temp_minify_json: Path) -> None:
    """A resolver the user installed is not replaced by the app's config.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
    """
    install_config(states={"test.module.MyState": "a"})
    custom = stub_resolver(state_name="custom")
    with temporary_resolver(custom) as ctx:
        ensure_minify_resolver_for_active_context()
        assert ctx.name_resolver is custom
        (temp_minify_json / MINIFY_JSON).unlink()
        ensure_minify_resolver_for_active_context()
        assert ctx.name_resolver is custom


def test_framework_names_reach_registered_handlers(temp_minify_json, monkeypatch):
    """The names the context module emits are the keys the backend dispatches on.

    The config is installed after the framework states were created, so this
    also covers renaming states whose Vars already exist.
    """
    from reflex_base.event import get_hydrate_event

    from reflex.compiler.compiler import _internal_names

    set_minify_modes(monkeypatch, states=True, events=True, vars=True)
    install_config(
        states={
            "reflex.state.State": StateEntry(id="a", parent=None),
            "reflex.state.State.FrontendEventExceptionState": StateEntry(
                id="b", parent="reflex.state.State"
            ),
            "reflex.state.State.OnLoadInternalState": StateEntry(
                id="c", parent="reflex.state.State"
            ),
            "reflex.state.State.UpdateVarsInternalState": StateEntry(
                id="d", parent="reflex.state.State"
            ),
        },
        events={
            "reflex.state.State": {"hydrate": "a"},
            "reflex.state.State.FrontendEventExceptionState": {
                "handle_frontend_exception": "a"
            },
            "reflex.state.State.OnLoadInternalState": {"on_load_internal": "a"},
            "reflex.state.State.UpdateVarsInternalState": {"update_vars_internal": "a"},
        },
        vars={"reflex.state.State": {"is_hydrated": "h"}},
    )

    assert State.get_name() == "a"
    names = _internal_names()
    assert names.main_state_name == "a"
    assert names.is_hydrated_key == "h"
    assert names.hydrate == "a.a"

    handlers = RegistrationContext.get().event_handlers
    for wire_name in (
        names.hydrate,
        names.on_load_internal,
        names.update_vars_internal,
        names.handle_frontend_exception,
    ):
        assert wire_name in handlers, (wire_name, sorted(handlers))

    # The middleware compares against this; it must agree with the name the
    # compiler just told the frontend to send.
    root = State(_reflex_internal_init=True, init_substates=False)  # pyright: ignore [reportCallIssue]
    assert get_hydrate_event(root) == names.hydrate

    # The Var the frontend reads names the context and key the compiler emits.
    assert str(State.is_hydrated) == "$rx_a.h"
    assert root.dict()["a"]["h"] is False


def _parent_id_collisions(config: MinifyConfig) -> list[str]:
    """Find entries that share their parent's id.

    Args:
        config: The config to inspect.

    Returns:
        The state paths that reuse their parent's id.
    """
    states = config["states"]
    return [
        path
        for path, entry in states.items()
        if entry["parent"] is not None
        and (parent := states.get(entry["parent"])) is not None
        and parent["id"] == entry["id"]
    ]


def test_generate_reserves_the_parent_id():
    """No generated state shares an id with its parent.

    A shared id makes a leading path segment ambiguous, so ``_skip_self``
    resolves a relative substate path to the parent instead of the child.
    """
    assert _parent_id_collisions(generate_minify_config()) == []


def test_sync_reserves_the_parent_id():
    """Ids assigned by ``sync`` skip the parent's own id too."""

    class SyncReserveParent(BaseState):
        pass

    class SyncReserveChild(SyncReserveParent):
        pass

    parent_path = get_state_full_path(SyncReserveParent)
    existing: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {parent_path: StateEntry(id="a", parent=None)},
        "events": {},
        "vars": {},
    }

    new_config = sync_minify_config(existing, SyncReserveParent)

    child = new_config["states"][get_state_full_path(SyncReserveChild)]
    assert child["id"] != "a"
    assert _parent_id_collisions(new_config) == []


def test_validate_detects_a_child_reusing_its_parent_id():
    """``validate`` reports a hand-edited config that reintroduces the collision."""

    class ValidateReuseParent(BaseState):
        pass

    class ValidateReuseChild(ValidateReuseParent):
        pass

    parent_path = get_state_full_path(ValidateReuseParent)
    config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
            parent_path: StateEntry(id="a", parent=None),
            get_state_full_path(ValidateReuseChild): StateEntry(
                id="a", parent=parent_path
            ),
        },
        "events": {},
        "vars": {},
    }

    errors, _warnings, _missing = validate_minify_config(config, ValidateReuseParent)

    assert any("reuses the id 'a' of its parent" in error for error in errors)


def test_sync_reserves_the_parent_id_through_a_new_subtree():
    """A whole new branch keeps the invariant at every level.

    Each level's id is reserved from its children's pool only once the parent
    has been assigned, so this pins the order ``sync`` walks the buckets in.
    """

    class DeepSyncRoot(BaseState):
        pass

    class DeepSyncA(DeepSyncRoot):
        pass

    class DeepSyncB(DeepSyncA):
        pass

    existing: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {get_state_full_path(DeepSyncRoot): StateEntry(id="a", parent=None)},
        "events": {},
        "vars": {},
    }

    new_config = sync_minify_config(existing, DeepSyncRoot)

    assert _parent_id_collisions(new_config) == []


def test_sync_moves_a_reparented_id_off_its_new_parent():
    """A preserved id that survives a move must not land on the new parent's.

    `sync` heals the stored parent but keeps the id, so without a fix-up it
    writes a config its own `validate` rejects.
    """

    class MoveParent(BaseState):
        pass

    class MovedChild(MoveParent):
        pass

    parent_path = get_state_full_path(MoveParent)
    existing: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
            parent_path: StateEntry(id="a", parent=None),
            get_state_full_path(MovedChild): StateEntry(
                id="a", parent="some.old.Parent"
            ),
        },
        "events": {},
        "vars": {},
    }

    new_config = sync_minify_config(existing, MoveParent)

    assert _parent_id_collisions(new_config) == []
    errors, _warnings, _missing = validate_minify_config(new_config, MoveParent)
    assert not errors, errors


def test_sync_moves_a_preserved_id_off_a_newly_inserted_parent():
    """Inserting a state above a preserved one must not collide either.

    The new parent draws its id from a different sibling pool, so it can land
    on the id the child below it already holds.
    """

    class MidRoot(BaseState):
        pass

    class NewMid(MidRoot):
        pass

    class OldLeaf(NewMid):
        pass

    root_path = get_state_full_path(MidRoot)
    existing: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
            root_path: StateEntry(id="a", parent=None),
            get_state_full_path(OldLeaf): StateEntry(id="b", parent=root_path),
        },
        "events": {},
        "vars": {},
    }

    new_config = sync_minify_config(existing, MidRoot)

    assert _parent_id_collisions(new_config) == []
    errors, _warnings, _missing = validate_minify_config(new_config, MidRoot)
    assert not errors, errors


def test_sync_moves_a_reparented_id_off_an_occupied_sibling_id():
    """Healing a parent must not drop an entry onto a sibling's id.

    The entry keeps its id across the move, so it can collide with a sibling
    already holding it. The entry that moved gives way; the one whose scope
    did not change keeps the id a served frontend may still be using.
    """

    class SiblingRoot(BaseState):
        pass

    class SiblingParent(SiblingRoot):
        pass

    class SiblingMoved(SiblingParent):
        pass

    class SiblingIncumbent(SiblingParent):
        pass

    root_path = get_state_full_path(SiblingRoot)
    parent_path = get_state_full_path(SiblingParent)
    moved_path = get_state_full_path(SiblingMoved)
    incumbent_path = get_state_full_path(SiblingIncumbent)
    existing: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
            root_path: StateEntry(id="a", parent=None),
            parent_path: StateEntry(id="b", parent=root_path),
            # Recorded under the root, but the code says SiblingParent.
            moved_path: StateEntry(id="c", parent=root_path),
            incumbent_path: StateEntry(id="c", parent=parent_path),
        },
        "events": {},
        "vars": {},
    }

    new_config = sync_minify_config(existing, SiblingRoot)

    assert new_config["states"][incumbent_path]["id"] == "c"
    assert new_config["states"][moved_path]["id"] != "c"
    errors, _warnings, _missing = validate_minify_config(new_config, SiblingRoot)
    assert not errors, errors


def test_validate_exempts_an_orphan_holding_its_parent_id():
    """An orphan may keep an id its live parent also holds.

    Its id stays reserved at the value a served frontend may still use, and it
    resolves no name at runtime, so moving it would cost more than it buys.
    ``sync`` must not produce a config ``validate`` then rejects.
    """

    class OrphanHolder(BaseState):
        pass

    parent_path = get_state_full_path(OrphanHolder)
    orphan_path = f"{parent_path}.DeletedChild"
    existing: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
            parent_path: StateEntry(id="a", parent=None),
            orphan_path: StateEntry(id="a", parent=parent_path),
        },
        "events": {},
        "vars": {},
    }

    new_config = sync_minify_config(existing, OrphanHolder)

    assert new_config["states"][orphan_path]["id"] == "a"
    errors, _warnings, _missing = validate_minify_config(new_config, OrphanHolder)
    assert not errors, errors


def test_validate_checks_the_actual_parent_not_the_recorded_one():
    """A stale ``parent`` must not hide a real collision.

    Lookups walk the live tree, so the collision that matters is with the
    actual parent even when the config still records an older one.
    """

    class ActualParentState(BaseState):
        pass

    class ActualChildState(ActualParentState):
        pass

    config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
            get_state_full_path(ActualParentState): StateEntry(id="a", parent=None),
            get_state_full_path(ActualChildState): StateEntry(
                id="a", parent="some.stale.Path"
            ),
        },
        "events": {},
        "vars": {},
    }

    errors, _warnings, _missing = validate_minify_config(config, ActualParentState)

    assert any("reuses the id 'a' of its parent" in error for error in errors)


def test_find_missing_entries_flags_a_state_added_after_the_config():
    """A state the config predates compiles unminified and is reported."""
    config = generate_minify_config()

    class LateAddedState(State):
        @staticmethod
        def ping():
            """A handler the config cannot know about."""

    resolver = MinifyNameResolver(
        config=config, states_enabled=True, events_enabled=True, vars_enabled=False
    )
    with temporary_resolver(resolver):
        missing = _find_missing_entries()

    assert f"state:{get_state_full_path(LateAddedState)}" in missing


def test_find_missing_entries_respects_disabled_modes():
    """A disabled mode emits full names by design, so it reports nothing."""
    config = generate_minify_config()

    class ModeGatedState(State):
        pass

    path = get_state_full_path(ModeGatedState)
    with temporary_resolver(
        MinifyNameResolver(
            config=config, states_enabled=False, events_enabled=True, vars_enabled=False
        )
    ):
        assert f"state:{path}" not in _find_missing_entries()
    with temporary_resolver(
        MinifyNameResolver(
            config=config,
            states_enabled=False,
            events_enabled=False,
            vars_enabled=False,
        )
    ):
        assert _find_missing_entries() == []


def test_find_missing_entries_without_a_minify_resolver():
    """The default resolver rewrites nothing, so nothing is missing."""
    with temporary_resolver(DefaultNameResolver()):
        assert _find_missing_entries() == []


def test_warn_if_config_stale_points_at_sync(caplog):
    """The warning names the command that fixes it.

    Args:
        caplog: The pytest log capture fixture.
    """
    config = generate_minify_config()

    class StaleWarningState(State):
        pass

    resolver = MinifyNameResolver(
        config=config, states_enabled=True, events_enabled=True, vars_enabled=False
    )
    with temporary_resolver(resolver), caplog.at_level("WARNING"):
        warn_if_config_stale()

    assert "reflex minify sync" in caplog.text
    assert get_state_full_path(StaleWarningState) in caplog.text


def test_warn_if_config_stale_is_silent_when_current(caplog):
    """A config that covers every registered name produces no warning.

    Args:
        caplog: The pytest log capture fixture.
    """
    resolver = MinifyNameResolver(
        config=generate_minify_config(),
        states_enabled=True,
        events_enabled=True,
        vars_enabled=False,
    )
    with temporary_resolver(resolver), caplog.at_level("WARNING"):
        warn_if_config_stale()

    assert caplog.text == ""


def _write_config(path: Path, **sections) -> None:
    """Write a ``minify.json`` holding the given sections.

    Args:
        path: The directory to write it to.
        **sections: The sections, by name.
    """
    config = {"version": SCHEMA_VERSION, "states": {}, "events": {}, **sections}
    (path / MINIFY_JSON).write_text(json.dumps(config))


def test_config_without_vars_loads_with_empty_vars(temp_minify_json):
    """Files written before vars were minified still load."""
    _write_config(temp_minify_json)
    loaded = _load_minify_config_uncached()
    assert loaded is not None
    assert loaded["vars"] == {}


@pytest.mark.parametrize(
    ("vars_section", "match"),
    [
        ([], "'vars' must be a dictionary"),
        ({"test.module.MyState": []}, "must be a dictionary"),
        ({"test.module.MyState": {"count": 1}}, "non-string id"),
        ({"test.module.MyState": {"count": "a-b"}}, "invalid id"),
        ({"test.module.MyState": {"count": "constructor"}}, "reserved id"),
        ({"test.module.MyState": {"count": "__proto__"}}, "reserved id"),
        ({"test.module.MyState": {"count": "a_rx_state_"}}, "reserved id"),
    ],
)
def test_config_rejects_malformed_vars(temp_minify_json, vars_section, match):
    """A var id is a key of its state's frontend object, so only safe ones load.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
        vars_section: The malformed ``vars`` section.
        match: Part of the expected error.
    """
    _write_config(temp_minify_json, vars=vars_section)
    with pytest.raises(ValueError, match=match):
        _load_minify_config_uncached()


def test_reserved_ids_are_fine_for_events(temp_minify_json):
    """Only var ids name object keys; an event id may be any identifier."""
    _write_config(
        temp_minify_json, events={"test.module.MyState": {"handler": "constructor"}}
    )
    loaded = _load_minify_config_uncached()
    assert loaded is not None
    assert loaded["events"]["test.module.MyState"]["handler"] == "constructor"


def test_resolve_var_name_follows_its_mode(temp_minify_json):
    """Var ids apply only while ``REFLEX_MINIFY_VARS`` is on.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
    """

    class VarModeState(State):
        count: int = 0

    config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {},
        "events": {},
        "vars": {get_state_full_path(VarModeState): {"count": "c"}},
    }
    on = MinifyNameResolver(
        config=config, states_enabled=False, events_enabled=False, vars_enabled=True
    )
    off = MinifyNameResolver(
        config=config, states_enabled=True, events_enabled=True, vars_enabled=False
    )
    assert on.resolve_var_name(VarModeState, "count") == "c"
    assert on.resolve_var_name(VarModeState, "missing") is None
    assert off.resolve_var_name(VarModeState, "count") is None


def test_digest_covers_vars_only_when_minified(temp_minify_json, monkeypatch):
    """A var id reaches the wire only with ``REFLEX_MINIFY_VARS`` on.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
        monkeypatch: The pytest monkeypatch fixture.
    """
    config_vars = {"reflex.state.State": {"is_hydrated": "h"}}

    set_minify_modes(monkeypatch, states=False, events=False, vars=False)
    install_config(vars=config_vars)
    assert scheme_digest() == ""

    set_minify_modes(monkeypatch, vars=True)
    install_config(vars=config_vars)
    first = scheme_digest()
    assert first

    install_config(vars={"reflex.state.State": {"is_hydrated": "i"}})
    assert scheme_digest() not in ("", first)


def test_generate_numbers_the_frontend_vars_of_each_state(temp_minify_json):
    """Each state numbers the vars it sends to the client, not inherited ones.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
    """

    class GenVarParent(State):
        count: int = 0
        _secret: str = ""

        @rx.var
        def doubled(self) -> int:
            return self.count * 2

        @rx.var(backend=True)
        def hidden(self) -> int:
            return 0

    class GenVarChild(GenVarParent):
        label: str = ""

    config = generate_minify_config(GenVarParent)
    assert config["vars"] == {
        get_state_full_path(GenVarParent): {"count": "a", "doubled": "b"},
        get_state_full_path(GenVarChild): {"label": "a"},
    }


def test_validate_reports_var_problems(temp_minify_json):
    """Duplicate var ids fail validation; missing and orphaned vars are reported.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
    """

    class ValidateVarState(State):
        first: int = 0
        second: int = 0

    path = get_state_full_path(ValidateVarState)
    config = generate_minify_config(ValidateVarState)
    config["vars"][path] = {"first": "a", "second": "a", "gone": "b"}

    errors, warnings, missing = validate_minify_config(config, ValidateVarState)
    assert any(
        f"vars of '{path}' share ids ('a' by first, second)" in error
        for error in errors
    )
    assert f"Orphaned var in config: {path}.gone" in warnings
    assert missing == []

    del config["vars"][path]
    _errors, _warnings, missing = validate_minify_config(config, ValidateVarState)
    assert missing == [f"var:{path}.first", f"var:{path}.second"]


def test_sync_assigns_new_var_ids_and_prunes_old_ones(temp_minify_json):
    """New vars get fresh ids; existing ones keep theirs until pruned.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
    """

    class SyncVarState(State):
        kept: int = 0
        added: int = 0

    path = get_state_full_path(SyncVarState)
    existing = generate_minify_config(SyncVarState)
    existing["vars"][path] = {"kept": "b", "removed": "a"}

    synced = sync_minify_config(existing, SyncVarState)
    assert synced["vars"][path] == {"kept": "b", "removed": "a", "added": "c"}

    pruned = sync_minify_config(existing, SyncVarState, prune=True)
    assert pruned["vars"][path] == {"kept": "b", "added": "c"}


def test_missing_vars_reported_only_when_minified(temp_minify_json, monkeypatch):
    """The stale-config warning covers vars once their mode is on.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
        monkeypatch: The pytest monkeypatch fixture.
    """

    class MissingVarState(State):
        count: int = 0

    label = f"var:{get_state_full_path(MissingVarState)}.count"

    set_minify_modes(monkeypatch, states=False, events=False, vars=False)
    install_config()
    assert label not in _find_missing_entries()

    set_minify_modes(monkeypatch, vars=True)
    install_config()
    assert label in _find_missing_entries()


def _stale_names_error(code: str) -> str:
    """Scan compiled code for stale names and return the error raised, if any.

    Args:
        code: The compiled code.

    Returns:
        The error message, or an empty string when the code is clean.
    """
    try:
        raise_for_stale_names([("page.jsx", code)])
    except ReflexError as e:
        return str(e)
    return ""


def test_stale_names_ignored_without_minification():
    """Nothing is renamed, so the default spellings are the right ones."""
    assert _stale_names_error(f"{State.get_full_name()}.hydrate") == ""


def test_stale_state_names_are_rejected(temp_minify_json, monkeypatch):
    """Code still spelling a renamed state the default way cannot reach it.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
        monkeypatch: The pytest monkeypatch fixture.
    """

    class StaleNameState(State):
        count: int = 0

    default_expr = str(StaleNameState.count)
    default_event = f"{StaleNameState.get_full_name()}.setvar"
    path = get_state_full_path(StaleNameState)

    set_minify_modes(monkeypatch, states=True)
    install_config(states={path: StateEntry(id="z", parent="reflex.state.State")})

    fresh = str(StaleNameState.count)
    assert fresh != default_expr
    assert _stale_names_error(f"const x = {fresh};") == ""
    for stale in (default_expr, f'addEvents([ReflexEvent("{default_event}")])'):
        error = _stale_names_error(stale)
        assert f"state {path}" in error
        assert "page.jsx" in error


def test_stale_event_names_are_rejected_when_only_events_minify(
    temp_minify_json, monkeypatch
):
    """With states unminified, only the handler part of a name goes stale.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
        monkeypatch: The pytest monkeypatch fixture.
    """

    class StaleEventState(State):
        @rx.event
        def ping(self):
            pass

    path = get_state_full_path(StaleEventState)
    full_name = StaleEventState.get_full_name()

    set_minify_modes(monkeypatch, states=False, events=True)
    install_config(events={path: {"ping": "p"}})

    assert _stale_names_error(f'"{full_name}.p"') == ""
    assert f"event handler {path}.ping" in _stale_names_error(f'"{full_name}.ping"')


def test_stale_var_keys_are_rejected_when_only_vars_minify(
    temp_minify_json, monkeypatch
):
    """With states unminified, only the var part of an expression goes stale.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
        monkeypatch: The pytest monkeypatch fixture.
    """

    class StaleVarState(State):
        count: int = 0

    path = get_state_full_path(StaleVarState)
    default_expr = str(StaleVarState.count)

    set_minify_modes(monkeypatch, states=False, vars=True)
    install_config(vars={path: {"count": "c"}})

    assert _stale_names_error(str(StaleVarState.count)) == ""
    assert f"var {path}.count" in _stale_names_error(f"{default_expr}.length")


def test_stale_resolved_state_names_are_rejected(
    temp_minify_json: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Code built under another app's ``minify.json`` cannot reach its states.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
        monkeypatch: The pytest monkeypatch fixture.
    """

    class ResolvedState(State):
        count: int = 0

    set_minify_modes(monkeypatch, states=True)
    install_config(
        states={
            get_state_full_path(ResolvedState): StateEntry(
                id="z", parent="reflex.state.State"
            )
        }
    )
    minified_expr = str(ResolvedState.count)
    assert "$rx_" in minified_expr
    assert _stale_names_error(minified_expr) == ""

    (temp_minify_json / "plain").mkdir()
    monkeypatch.chdir(temp_minify_json / "plain")
    ensure_minify_resolver_for_active_context()

    assert _stale_names_error(str(ResolvedState.count)) == ""
    error = _stale_names_error(f"const x = {minified_expr};")
    assert f"state {get_state_full_path(ResolvedState)}" in error
    assert "page.jsx" in error


@pytest.mark.parametrize("new_vars", [{"count": "d"}, {}], ids=["other", "none"])
def test_stale_var_keys_of_a_state_keeping_its_name_are_rejected(
    temp_minify_json: Path, monkeypatch: pytest.MonkeyPatch, new_vars: dict[str, str]
) -> None:
    """A var key from another ``minify.json`` is caught though its state's id matches.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
        monkeypatch: The pytest monkeypatch fixture.
        new_vars: The var ids of the config the code is compiled under.
    """

    class KeptNameState(State):
        count: int = 0

    path = get_state_full_path(KeptNameState)
    entry = StateEntry(id="z", parent="reflex.state.State")
    set_minify_modes(monkeypatch, states=True, vars=True)
    install_config(states={path: entry}, vars={path: {"count": "c"}})
    old_expr = str(KeptNameState.count)

    install_config(states={path: entry}, vars={path: new_vars})

    assert _stale_names_error(str(KeptNameState.count)) == ""
    error = _stale_names_error(f"{old_expr}.length")
    assert f"var {path}.count, as '{old_expr}'" in error


def test_stale_var_read_is_rejected_when_another_state_takes_its_local(
    temp_minify_json: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A var read off a local now handed to another state is caught by its key.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
        monkeypatch: The pytest monkeypatch fixture.
    """

    class FormerOwnerState(State):
        count: int = 0

    class NewOwnerState(State):
        total: int = 0

    former, new = (
        get_state_full_path(FormerOwnerState),
        get_state_full_path(NewOwnerState),
    )
    set_minify_modes(monkeypatch, states=True, vars=True)
    root = "reflex.state.State"
    install_config(
        states={
            former: StateEntry(id="k", parent=root),
            new: StateEntry(id="m", parent=root),
        },
        vars={former: {"count": "c"}, new: {"total": "t"}},
    )
    old_expr = str(FormerOwnerState.count)

    install_config(
        states={
            former: StateEntry(id="m", parent=root),
            new: StateEntry(id="k", parent=root),
        },
        vars={former: {"count": "c"}, new: {"total": "t"}},
    )

    assert str(NewOwnerState.total).split(".")[0] == old_expr.split(".")[0]
    assert _stale_names_error(str(NewOwnerState.total)) == ""
    assert f"var {former}.count" in _stale_names_error(old_expr)


def test_stale_minified_var_keys_are_rejected_after_unminifying(
    temp_minify_json: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A minified var key is caught once its state's vars are unminified.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
        monkeypatch: The pytest monkeypatch fixture.
    """

    class UnminifiedVarState(State):
        count: int = 0

    path = get_state_full_path(UnminifiedVarState)
    set_minify_modes(monkeypatch, states=False, vars=True)
    install_config(vars={path: {"count": "c"}})
    old_expr = str(UnminifiedVarState.count)

    set_minify_modes(monkeypatch, vars=False)
    install_config(vars={path: {"count": "c"}})

    assert _stale_names_error(str(UnminifiedVarState.count)) == ""
    assert f"var {path}.count" in _stale_names_error(old_expr)


def test_text_resembling_state_reads_is_not_rejected(temp_minify_json: Path) -> None:
    """Only locals and var keys once handed out count, not look-alike page text.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
    """

    class LookAlikeState(State):
        pass

    root = State.get_full_name()
    for code in (
        '"Total: $rx_total"',
        "$rx_never__issued.c",
        f'"{root}.hydrate"',
        f'"{root}.{LookAlikeState.get_name()}.anything"',
        f"{root}.not_a_var",
    ):
        assert _stale_names_error(code) == "", code


@pytest.mark.parametrize("state_id", ["_", "_b", "a_", "a__b"])
def test_state_ids_that_blur_path_segments_are_rejected(temp_minify_json, state_id):
    """A state id must survive its path's dots becoming ``__`` unambiguously.

    ``a`` + ``_b`` and ``a_`` + ``b`` would both read ``a___b``, colliding two
    states' context keys and locals in the compiled frontend.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
        state_id: A state id with an underscore at an edge or doubled.
    """
    (temp_minify_json / MINIFY_JSON).write_text(
        json.dumps({
            "version": SCHEMA_VERSION,
            "states": {"test.module.MyState": {"id": state_id, "parent": None}},
            "events": {},
        })
    )
    with pytest.raises(ValueError, match="__"):
        _load_minify_config_uncached()


def test_generated_state_ids_keep_paths_distinct(temp_minify_json):
    """Numbering past ``$`` skips the ids an underscore would blur.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
    """
    parent = type("ManySiblingsParent", (State,), {"__module__": __name__})
    siblings = [
        type(f"ManySiblings{index:03d}", (parent,), {"__module__": __name__})
        for index in range(120)
    ]
    config = generate_minify_config(parent)
    ids = [config["states"][get_state_full_path(s)]["id"] for s in siblings]
    assert len(set(ids)) == len(ids)
    assert not [i for i in ids if i.startswith("_") or i.endswith("_") or "__" in i]

    # Sync assigns the ids a later sibling needs the same way.
    del config["states"][get_state_full_path(siblings[-1])]
    synced = sync_minify_config(config, parent)
    new_id = synced["states"][get_state_full_path(siblings[-1])]["id"]
    assert not (new_id.startswith("_"))
    assert not (new_id.endswith("_"))
    assert "__" not in new_id


def test_state_entry_without_parent_is_rejected(temp_minify_json):
    """``validate`` and ``sync`` read every entry's parent, so it is required.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
    """
    (temp_minify_json / MINIFY_JSON).write_text(
        json.dumps({
            "version": SCHEMA_VERSION,
            "states": {"test.module.MyState": {"id": "a"}},
            "events": {},
        })
    )
    with pytest.raises(ValueError, match="parent"):
        _load_minify_config_uncached()


def _config_with_ambiguous_ids(parent: type[BaseState]) -> MinifyConfig:
    """A config as generated before ambiguous state ids were skipped.

    Args:
        parent: A state with at least one substate.

    Returns:
        The config, with the first substate on ``_`` and an orphan on ``a_``.
    """
    config = generate_minify_config(parent)
    parent_path = get_state_full_path(parent)
    child_path = next(
        path for path, entry in config["states"].items() if entry["parent"]
    )
    config["states"][child_path]["id"] = "_"
    config["states"][f"{parent_path}.Gone"] = StateEntry(id="a_", parent=parent_path)
    return config


def test_ambiguous_state_ids_are_reported_and_reassigned(temp_minify_json):
    """A config written before the rule loads for the CLI, which repairs it.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
    """
    parent = type("AmbiguousParent", (State,), {"__module__": __name__})
    type("AmbiguousChild", (parent,), {"__module__": __name__})
    config = _config_with_ambiguous_ids(parent)
    (temp_minify_json / MINIFY_JSON).write_text(json.dumps(config))

    # The app refuses it; the CLI loads it to report and repair it.
    with pytest.raises(ValueError, match="reflex minify sync"):
        _load_minify_config_uncached()
    loaded = _load_minify_config_uncached(for_repair=True)
    assert loaded is not None

    errors, _warnings, _missing = validate_minify_config(loaded, parent)
    assert sum("reflex minify sync" in error for error in errors) == 2

    synced = sync_minify_config(loaded, parent)
    ids = {path: entry["id"] for path, entry in synced["states"].items()}
    assert "_" not in ids.values()
    assert "a_" not in ids.values()
    assert len(ids) == len(config["states"])
    save_minify_config(synced)
    assert _load_minify_config_uncached() is not None


def test_duplicate_event_ids_are_rejected_and_reassigned(temp_minify_json):
    """Two handlers of a state on one id would leave one unreachable.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
    """

    class DuplicateEventState(State):
        def first(self):
            pass

        def second(self):
            pass

    path = get_state_full_path(DuplicateEventState)
    config = generate_minify_config(DuplicateEventState)
    config["events"][path] = {"first": "a", "second": "a", "setvar": "c"}
    config["events"]["gone.module.State"] = {"x": "b", "y": "b"}
    (temp_minify_json / MINIFY_JSON).write_text(json.dumps(config))

    with pytest.raises(ValueError, match="reflex minify sync"):
        _load_minify_config_uncached()
    loaded = _load_minify_config_uncached(for_repair=True)
    assert loaded is not None

    synced = sync_minify_config(loaded, DuplicateEventState)
    assert synced["events"][path]["first"] == "a"
    assert synced["events"][path]["second"] not in ("a", "c")
    assert len(set(synced["events"]["gone.module.State"].values())) == 2
    save_minify_config(synced)
    assert _load_minify_config_uncached() is not None


def test_duplicate_var_ids_are_rejected_and_reassigned(temp_minify_json):
    """Two vars of a state on one id would overwrite each other on the wire.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
    """

    class DuplicateVarState(State):
        first: int = 0
        second: int = 0

    path = get_state_full_path(DuplicateVarState)
    config = generate_minify_config(DuplicateVarState)
    config["vars"][path] = {"first": "a", "second": "a"}
    (temp_minify_json / MINIFY_JSON).write_text(json.dumps(config))

    with pytest.raises(ValueError, match="reflex minify sync"):
        _load_minify_config_uncached()
    loaded = _load_minify_config_uncached(for_repair=True)
    assert loaded is not None

    synced = sync_minify_config(loaded, DuplicateVarState)
    assert synced["vars"][path]["first"] == "a"
    assert synced["vars"][path]["second"] != "a"
    save_minify_config(synced)
    assert _load_minify_config_uncached() is not None


def test_duplicate_repair_keeps_the_live_handler_id(temp_minify_json):
    """A deleted handler sharing a live one's id gives way, whatever the order.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
    """

    class LiveHandlerState(State):
        def zed(self):
            pass

    path = get_state_full_path(LiveHandlerState)
    config = generate_minify_config(LiveHandlerState)
    config["events"][path] = {"alpha_gone": "a", "zed": "a", "setvar": "b"}

    synced = sync_minify_config(config, LiveHandlerState)
    assert synced["events"][path]["zed"] == "a"
    assert synced["events"][path]["alpha_gone"] not in ("a", "b")


def test_duplicate_repair_keeps_the_live_var_id(temp_minify_json):
    """A deleted var sharing a live one's id gives way, whatever the order.

    Args:
        temp_minify_json: Temporary ``minify.json`` location.
    """

    class LiveVarState(State):
        zed: int = 0

    path = get_state_full_path(LiveVarState)
    config = generate_minify_config(LiveVarState)
    config["vars"][path] = {"alpha_gone": "a", "zed": "a"}

    synced = sync_minify_config(config, LiveVarState)
    assert synced["vars"][path]["zed"] == "a"
    assert synced["vars"][path]["alpha_gone"] != "a"
