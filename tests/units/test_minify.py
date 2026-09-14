"""Unit tests for reflex/minify.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from reflex_base.registry import DefaultNameResolver, RegistrationContext, scheme_digest

from reflex.environment import environment
from reflex.minify import (
    MINIFY_JSON,
    SCHEMA_VERSION,
    MinifyConfig,
    MinifyNameResolver,
    StateEntry,
    _find_missing_entries,
    clear_config_cache,
    ensure_minify_resolver_for_active_context,
    generate_minify_config,
    get_minify_config,
    get_parent_key,
    get_state_full_path,
    int_to_minified_name,
    is_minify_enabled,
    is_mode_enabled,
    minified_name_to_int,
    sync_minify_config,
    validate_minify_config,
    warn_if_config_stale,
)
from reflex.state import BaseState, State
from tests.units.minify_helpers import (
    install_config,
    run_in_fresh_interpreter,
    set_minify_modes,
)
from tests.units.name_resolvers import temporary_resolver


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
    assert is_minify_enabled() is False
    assert get_minify_config() is None


def test_save_and_load_config(temp_minify_json, monkeypatch):
    """Test saving and loading a config."""
    set_minify_modes(monkeypatch, states=True, events=True)
    install_config(
        states={"test.module.MyState": "a"},
        events={"test.module.MyState": {"handler": "a"}},
    )

    assert is_minify_enabled() is True
    loaded = get_minify_config()
    assert loaded is not None
    assert loaded["states"]["test.module.MyState"] == {"id": "a", "parent": None}
    assert loaded["events"]["test.module.MyState"]["handler"] == "a"


def test_invalid_version_raises(temp_minify_json, monkeypatch):
    """Test that invalid version raises ValueError."""
    set_minify_modes(monkeypatch, states=True)
    config = {"version": 999, "states": {}, "events": {}}
    path = temp_minify_json / MINIFY_JSON
    with path.open("w") as f:
        json.dump(config, f)

    clear_config_cache()

    with pytest.raises(ValueError, match=r"Unsupported.*version"):
        is_mode_enabled("REFLEX_MINIFY_STATES")


def test_missing_states_raises(temp_minify_json, monkeypatch):
    """Test that missing 'states' key raises ValueError."""
    set_minify_modes(monkeypatch, states=True)
    config = {"version": SCHEMA_VERSION, "events": {}}
    path = temp_minify_json / MINIFY_JSON
    with path.open("w") as f:
        json.dump(config, f)

    clear_config_cache()

    with pytest.raises(ValueError, match="'states' must be"):
        is_mode_enabled("REFLEX_MINIFY_STATES")


def test_flat_string_states_raise(temp_minify_json, monkeypatch):
    """Test that legacy flat string state values are rejected."""
    set_minify_modes(monkeypatch, states=True)
    config = {
        "version": SCHEMA_VERSION,
        "states": {"test.module.MyState": "a"},
        "events": {},
    }
    path = temp_minify_json / MINIFY_JSON
    with path.open("w") as f:
        json.dump(config, f)

    clear_config_cache()

    with pytest.raises(ValueError, match="must be an object with a string 'id'"):
        is_mode_enabled("REFLEX_MINIFY_STATES")


@pytest.mark.parametrize("payload", ["[1, 2, 3]", '"a string"', "42", "null"])
def test_non_object_json_raises(
    temp_minify_json: Path, monkeypatch: pytest.MonkeyPatch, payload: str
) -> None:
    """Valid JSON that isn't an object is rejected as a ValueError."""
    set_minify_modes(monkeypatch, states=True)
    (temp_minify_json / MINIFY_JSON).write_text(payload, encoding="utf-8")

    clear_config_cache()

    with pytest.raises(ValueError, match="must be a JSON object"):
        is_mode_enabled("REFLEX_MINIFY_STATES")


@pytest.mark.parametrize("bad_id", ["", "1bad", "a-b", "a.b", "a b"])
def test_invalid_state_id_raises(
    temp_minify_json: Path, monkeypatch: pytest.MonkeyPatch, bad_id: str
) -> None:
    """State ids must be non-empty and built only from the minify alphabet."""
    set_minify_modes(monkeypatch, states=True)
    config = {
        "version": SCHEMA_VERSION,
        "states": {"test.module.MyState": {"id": bad_id, "parent": None}},
        "events": {},
    }
    (temp_minify_json / MINIFY_JSON).write_text(json.dumps(config), encoding="utf-8")

    clear_config_cache()

    with pytest.raises(ValueError, match="invalid id"):
        is_mode_enabled("REFLEX_MINIFY_STATES")


@pytest.mark.parametrize("bad_id", ["", "1bad", "a-b"])
def test_invalid_event_id_raises(
    temp_minify_json: Path, monkeypatch: pytest.MonkeyPatch, bad_id: str
) -> None:
    """Event ids go through the same alphabet check as state ids."""
    set_minify_modes(monkeypatch, events=True)
    config = {
        "version": SCHEMA_VERSION,
        "states": {},
        "events": {"test.module.MyState": {"handler": bad_id}},
    }
    (temp_minify_json / MINIFY_JSON).write_text(json.dumps(config), encoding="utf-8")

    clear_config_cache()

    with pytest.raises(ValueError, match="invalid id"):
        is_mode_enabled("REFLEX_MINIFY_EVENTS")


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
    }

    new_config = sync_minify_config(existing_config, TestState)

    # Existing IDs should be preserved
    assert new_config["states"][state_path]["id"] == "bU"  # codespell:ignore
    assert new_config["events"][state_path]["handler_a"] == "k"
    # New handler should be added with next ID (k=10, so next is l=11)
    assert "handler_b" in new_config["events"][state_path]
    assert new_config["events"][state_path]["handler_b"] == "l"  # 10 + 1 = 11 -> 'l'


def test_sync_no_sibling_collision_across_modules():
    """Test that sync assigns unique IDs to siblings of the same parent.

    When children of the same parent state class are defined in different
    Python modules, their get_state_full_path() produces different string
    prefixes. The sync function must group siblings by the actual parent
    class object, not by string-splitting the path, to avoid ID collisions.
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
            child_path: StateEntry(id="a", parent="wrong.Path"),
        },
        "events": {},
    }

    new_config = sync_minify_config(existing_config, HealParentParent)

    assert new_config["states"][child_path] == StateEntry(id="a", parent=parent_path)


@pytest.mark.parametrize("var", ["REFLEX_MINIFY_STATES", "REFLEX_MINIFY_EVENTS"])
def test_disabled_by_default(temp_minify_json, var):
    """Both modes default to disabled even with a config present."""
    install_config(states={"x": "a"}, events={"x": {"h": "a"}})
    assert is_mode_enabled(var) is False


@pytest.mark.parametrize("var", ["REFLEX_MINIFY_STATES", "REFLEX_MINIFY_EVENTS"])
def test_enabled_requires_env_and_config(temp_minify_json, monkeypatch, var):
    """Each mode flips True only when its env var is on AND a config exists."""
    monkeypatch.setenv(getattr(environment, var).name, "1")
    clear_config_cache()
    assert is_mode_enabled(var) is False  # env on, no config
    install_config(states={"x": "a"}, events={"x": {"h": "a"}})
    assert is_mode_enabled(var) is True


def test_modes_toggle_independently(temp_minify_json, monkeypatch):
    """States can be on while events stay off (or vice versa)."""
    set_minify_modes(monkeypatch, states=True, events=False)
    install_config(states={"x": "a"}, events={"x": {"h": "a"}})
    assert is_mode_enabled("REFLEX_MINIFY_STATES") is True
    assert is_mode_enabled("REFLEX_MINIFY_EVENTS") is False
    assert is_minify_enabled() is True


def test_is_minify_enabled_false_when_both_disabled(temp_minify_json):
    """Default (no env) → ``is_minify_enabled`` is False even with config."""
    install_config(states={"x": "a"}, events={"x": {"h": "a"}})
    assert is_minify_enabled() is False


def test_disabled_returns_none(temp_minify_json):
    """When neither flag is enabled, the resolver returns None for all."""
    resolver = MinifyNameResolver(
        config={"version": SCHEMA_VERSION, "states": {}, "events": {}},
        states_enabled=False,
        events_enabled=False,
    )
    assert resolver.resolve_state_name(State) is None
    assert resolver.resolve_handler_name(State, "any") is None


def test_resolver_no_config_returns_none():
    """No config means no overrides even when flags are enabled."""
    resolver = MinifyNameResolver(config=None, states_enabled=True, events_enabled=True)
    assert resolver.resolve_state_name(State) is None
    assert resolver.resolve_handler_name(State, "any") is None


def test_state_lookup_caches():
    """Resolved state names are memoized after the first lookup."""

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
    }
    resolver = MinifyNameResolver(
        config=config, states_enabled=True, events_enabled=False
    )
    assert resolver.resolve_state_name(UserStateResolverCacheTest) == "rs"
    # second call hits the cache
    assert UserStateResolverCacheTest in resolver._state_cache
    assert resolver.resolve_state_name(UserStateResolverCacheTest) == "rs"


def test_event_lookup_caches():
    """Resolved handler names are memoized per state class."""

    class UserStateEventCacheTest(State):
        pass

    config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {},
        "events": {
            get_state_full_path(UserStateEventCacheTest): {"foo": "f", "bar": "b"}
        },
    }
    resolver = MinifyNameResolver(
        config=config, states_enabled=False, events_enabled=True
    )
    assert resolver.resolve_handler_name(UserStateEventCacheTest, "foo") == "f"
    assert resolver.resolve_handler_name(UserStateEventCacheTest, "bar") == "b"
    assert resolver.resolve_handler_name(UserStateEventCacheTest, "missing") is None
    assert UserStateEventCacheTest in resolver._event_cache


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


def test_framework_event_names_reach_registered_handlers(tmp_path):
    """The names the context module emits are the keys the backend dispatches on."""
    config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
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
        "events": {
            "reflex.state.State": {"hydrate": "a"},
            "reflex.state.State.FrontendEventExceptionState": {
                "handle_frontend_exception": "a"
            },
            "reflex.state.State.OnLoadInternalState": {"on_load_internal": "a"},
            "reflex.state.State.UpdateVarsInternalState": {"update_vars_internal": "a"},
        },
    }
    run_in_fresh_interpreter(
        tmp_path,
        config,
        """
            from reflex_base.event import get_hydrate_event
            from reflex_base.registry import RegistrationContext

            from reflex.compiler.compiler import _internal_event_names
            from reflex.state import State

            assert State.get_name() == "a", State.get_name()

            names = _internal_event_names()
            assert names.main_state_name == "a", names
            assert names.hydrate == "a.a", names

            handlers = RegistrationContext.ensure_context().event_handlers
            for wire_name in (
                names.hydrate,
                names.on_load_internal,
                names.update_vars_internal,
                names.handle_frontend_exception,
            ):
                assert wire_name in handlers, (wire_name, sorted(handlers))

            # The middleware compares against this; it must agree with the
            # name the compiler just told the frontend to send.
            root = State(_reflex_internal_init=True)
            assert get_hydrate_event(root) == names.hydrate

            # Nothing was renamed after its Vars captured the old name.
            assert RegistrationContext.ensure_context().find_unbound_states() == []
        """,
        REFLEX_MINIFY_STATES="1",
        REFLEX_MINIFY_EVENTS="1",
    )


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
    }

    new_config = sync_minify_config(existing, SyncReserveParent)

    child = new_config["states"][get_state_full_path(SyncReserveChild)]
    assert child["id"] != "a"
    assert _parent_id_collisions(new_config) == []


def test_validate_detects_a_child_reusing_its_parent_id():
    """``validate`` reports a hand-edited config that reintroduces the collision."""

    class ValidateReuseParent(BaseState):
        pass

    parent_path = get_state_full_path(ValidateReuseParent)
    config: MinifyConfig = {
        "version": SCHEMA_VERSION,
        "states": {
            parent_path: StateEntry(id="a", parent=None),
            f"{parent_path}.Child": StateEntry(id="a", parent=parent_path),
        },
        "events": {},
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
    }

    new_config = sync_minify_config(existing, DeepSyncRoot)

    assert _parent_id_collisions(new_config) == []


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
        config=config, states_enabled=True, events_enabled=True
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
        MinifyNameResolver(config=config, states_enabled=False, events_enabled=True)
    ):
        assert f"state:{path}" not in _find_missing_entries()
    with temporary_resolver(
        MinifyNameResolver(config=config, states_enabled=False, events_enabled=False)
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
        config=config, states_enabled=True, events_enabled=True
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
        config=generate_minify_config(), states_enabled=True, events_enabled=True
    )
    with temporary_resolver(resolver), caplog.at_level("WARNING"):
        warn_if_config_stale()

    assert caplog.text == ""
