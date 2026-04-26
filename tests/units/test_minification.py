"""Unit tests for state and event handler minification via minify.json."""

from __future__ import annotations

import json

import pytest
from reflex_base.registry import DefaultNameResolver, NameResolver, RegistrationContext

from reflex.environment import MinifyMode, environment
from reflex.minify import (
    MINIFY_JSON,
    SCHEMA_VERSION,
    MinifyConfig,
    MinifyNameResolver,
    clear_config_cache,
    generate_minify_config,
    get_event_id,
    get_state_full_path,
    get_state_id,
    int_to_minified_name,
    is_event_minify_enabled,
    is_minify_enabled,
    is_state_minify_enabled,
    minified_name_to_int,
    save_minify_config,
    sync_minify_config,
    validate_minify_config,
)
from reflex.state import BaseState, State


def _resolved_event_id(state_cls: type[BaseState], handler_name: str) -> str | None:
    """Ask the active resolver for the minified name of a handler.

    Args:
        state_cls: The state class the handler is attached to.
        handler_name: The handler's original (Python) name.

    Returns:
        The minified id, or ``None`` if the resolver doesn't override it.
    """
    return RegistrationContext.get().name_resolver.resolve_handler_name(
        state_cls, handler_name
    )


class TestIntToMinifiedName:
    """Tests for int_to_minified_name function."""

    def test_zero(self):
        """Test that 0 maps to 'a'."""
        assert int_to_minified_name(0) == "a"

    def test_single_char(self):
        """Test single character mappings."""
        assert int_to_minified_name(1) == "b"
        assert int_to_minified_name(25) == "z"
        assert int_to_minified_name(26) == "A"
        assert int_to_minified_name(51) == "Z"
        assert int_to_minified_name(52) == "$"
        assert int_to_minified_name(53) == "_"

    def test_two_chars(self):
        """Test two character mappings (base 54)."""
        # 54 = 1*54 + 0 -> 'ba'
        assert int_to_minified_name(54) == "ba"
        # 55 = 1*54 + 1 -> 'bb'
        assert int_to_minified_name(55) == "bb"

    def test_unique_names(self):
        """Test that a large range of IDs produce unique names."""
        names = set()
        for i in range(10000):
            name = int_to_minified_name(i)
            assert name not in names, f"Duplicate name {name} for id {i}"
            names.add(name)

    def test_negative_raises(self):
        """Test that negative IDs raise ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            int_to_minified_name(-1)


class TestMinifiedNameToInt:
    """Tests for minified_name_to_int reverse conversion."""

    def test_single_char(self):
        """Test single character conversion."""
        assert minified_name_to_int("a") == 0
        assert minified_name_to_int("b") == 1
        assert minified_name_to_int("z") == 25
        assert minified_name_to_int("A") == 26
        assert minified_name_to_int("Z") == 51

    def test_roundtrip(self):
        """Test that int -> minified -> int roundtrip works."""
        for i in range(1000):
            minified = int_to_minified_name(i)
            result = minified_name_to_int(minified)
            assert result == i, f"Roundtrip failed for {i}: {minified} -> {result}"

    def test_invalid_char_raises(self):
        """Test that invalid characters raise ValueError."""
        with pytest.raises(ValueError, match="Invalid character"):
            minified_name_to_int("!")


class TestGetStateFullPath:
    """Tests for get_state_full_path function."""

    def test_root_state_path(self):
        """Test that root State has correct full path."""
        path = get_state_full_path(State)
        assert path == "reflex.state.State"

    def test_substate_path(self):
        """Test that substates have correct full paths."""

        class TestState(BaseState):
            pass

        path = get_state_full_path(TestState)
        assert "TestState" in path
        assert path.startswith("tests.units.test_minification.")


@pytest.fixture
def temp_minify_json(tmp_path, monkeypatch):
    """Run the test against a fresh ``minify.json`` location.

    Teardown undoes monkeypatch *before* clearing the cache so the registry
    is rebuilt under unmodified env/cwd — otherwise other tests would inherit
    minified names.

    Yields:
        The temporary directory path.
    """
    monkeypatch.chdir(tmp_path)
    clear_config_cache()
    yield tmp_path
    monkeypatch.undo()
    clear_config_cache()


class TestMinifyConfig:
    """Tests for minify.json configuration loading and saving."""

    def test_no_config_returns_none(self, temp_minify_json):
        """Test that missing minify.json returns None."""
        assert is_minify_enabled() is False
        assert get_state_id("any.path") is None
        assert get_event_id("any.path", "handler") is None

    def test_save_and_load_config(self, temp_minify_json, monkeypatch):
        """Test saving and loading a config."""
        monkeypatch.setenv(
            environment.REFLEX_MINIFY_STATES.name, MinifyMode.ENABLED.value
        )
        monkeypatch.setenv(
            environment.REFLEX_MINIFY_EVENTS.name, MinifyMode.ENABLED.value
        )
        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {"test.module.MyState": "a"},
            "events": {"test.module.MyState": {"handler": "a"}},
        }
        save_minify_config(config)

        # Clear cache and reload
        clear_config_cache()

        assert is_minify_enabled() is True
        assert get_state_id("test.module.MyState") == "a"
        assert get_event_id("test.module.MyState", "handler") == "a"

    def test_invalid_version_raises(self, temp_minify_json, monkeypatch):
        """Test that invalid version raises ValueError."""
        monkeypatch.setenv(
            environment.REFLEX_MINIFY_STATES.name, MinifyMode.ENABLED.value
        )
        config = {"version": 999, "states": {}, "events": {}}
        path = temp_minify_json / MINIFY_JSON
        with path.open("w") as f:
            json.dump(config, f)

        clear_config_cache()

        with pytest.raises(ValueError, match=r"Unsupported.*version"):
            is_state_minify_enabled()

    def test_missing_states_raises(self, temp_minify_json, monkeypatch):
        """Test that missing 'states' key raises ValueError."""
        monkeypatch.setenv(
            environment.REFLEX_MINIFY_STATES.name, MinifyMode.ENABLED.value
        )
        config = {"version": SCHEMA_VERSION, "events": {}}
        path = temp_minify_json / MINIFY_JSON
        with path.open("w") as f:
            json.dump(config, f)

        clear_config_cache()

        with pytest.raises(ValueError, match="'states' must be"):
            is_state_minify_enabled()


class TestGenerateMinifyConfig:
    """Tests for generate_minify_config function."""

    def test_generate_for_root_state(self):
        """Test generating config for the root State."""
        config = generate_minify_config(State)

        assert config["version"] == SCHEMA_VERSION
        assert "reflex.state.State" in config["states"]
        # State should have event handlers like set_is_hydrated
        state_path = "reflex.state.State"
        assert state_path in config["events"]
        assert "set_is_hydrated" in config["events"][state_path]

    def test_generates_unique_sibling_ids(self):
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

        child_a_id = config["states"].get(child_a_path)
        child_b_id = config["states"].get(child_b_path)

        assert child_a_id is not None
        assert child_b_id is not None
        assert child_a_id != child_b_id


class TestValidateMinifyConfig:
    """Tests for validate_minify_config function."""

    def test_valid_config_no_errors(self):
        """Test that a valid config produces no errors."""
        config = generate_minify_config(State)
        errors, _warnings, missing = validate_minify_config(config, State)

        assert len(errors) == 0
        assert len(missing) == 0

    def test_duplicate_state_ids_detected(self):
        """Test that duplicate state IDs are detected."""
        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {
                "test.Parent": "a",
                "test.Parent.ChildA": "b",
                "test.Parent.ChildB": "b",  # Duplicate!
            },
            "events": {},
        }

        # Create a mock state tree
        class Parent(BaseState):
            pass

        errors, _warnings, _missing = validate_minify_config(config, Parent)

        assert any("Duplicate state_id='b'" in e for e in errors)


class TestSyncMinifyConfig:
    """Tests for sync_minify_config function."""

    def test_sync_adds_new_states(self):
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

        # Should have added the state
        state_path = get_state_full_path(TestState)
        assert state_path in new_config["states"]
        assert state_path in new_config["events"]
        assert "handler" in new_config["events"][state_path]

    def test_sync_preserves_existing_ids(self):
        """Test that sync preserves existing IDs."""

        class TestState(BaseState):
            def handler_a(self):
                pass

            def handler_b(self):
                pass

        state_path = get_state_full_path(TestState)

        # Start with partial config (using string IDs in v2 format)
        existing_config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {state_path: "bU"},  # codespell:ignore
            "events": {state_path: {"handler_a": "k"}},  # Another arbitrary name
        }

        new_config = sync_minify_config(existing_config, TestState)

        # Existing IDs should be preserved
        assert new_config["states"][state_path] == "bU"  # codespell:ignore
        assert new_config["events"][state_path]["handler_a"] == "k"
        # New handler should be added with next ID (k=10, so next is l=11)
        assert "handler_b" in new_config["events"][state_path]
        assert (
            new_config["events"][state_path]["handler_b"] == "l"
        )  # 10 + 1 = 11 -> 'l'

    def test_sync_no_sibling_collision_across_modules(self):
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

        parent_path = get_state_full_path(ParentState)
        child_a_path = get_state_full_path(ChildA)

        # Config already has ParentState and ChildA assigned
        existing_config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {
                parent_path: "a",
                child_a_path: "a",
            },
            "events": {},
        }

        # Sync should assign ChildB a DIFFERENT ID than ChildA
        new_config = sync_minify_config(existing_config, ParentState)

        child_b_path = get_state_full_path(ChildB)
        assert child_b_path in new_config["states"]
        assert (
            new_config["states"][child_a_path] != new_config["states"][child_b_path]
        ), (
            f"Sibling collision: ChildA and ChildB both got "
            f"'{new_config['states'][child_a_path]}'"
        )

    def test_validate_detects_sibling_collision(self):
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
                parent_path: "a",
                child_a_path: "a",
                child_b_path: "a",  # collision!
            },
            "events": {},
        }

        errors, _warnings, _missing = validate_minify_config(bad_config, ParentState)
        assert any("Duplicate" in e and "'a'" in e for e in errors), (
            f"Expected duplicate ID error, got: {errors}"
        )


class TestStateMinification:
    """Tests for state name minification with minify.json."""

    def test_state_uses_full_name_without_config(self, temp_minify_json):
        """Test that states use full names when no minify.json exists."""

        class TestState(BaseState):
            pass

        TestState.get_name.cache_clear()
        name = TestState.get_name()

        # Should be the full name (snake_case module___class)
        assert "test_state" in name.lower()

    def test_state_uses_minified_name_with_config(self, temp_minify_json, monkeypatch):
        """Test that states use minified names when minify.json exists and env var is enabled."""
        monkeypatch.setenv(
            environment.REFLEX_MINIFY_STATES.name, MinifyMode.ENABLED.value
        )

        class TestState(BaseState):
            pass

        state_path = get_state_full_path(TestState)
        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {state_path: "f"},  # Direct minified name
            "events": {},
        }
        save_minify_config(config)
        clear_config_cache()
        TestState.get_name.cache_clear()

        name = TestState.get_name()

        # Should be the minified name directly
        assert name == "f"

    def test_state_uses_full_name_when_env_disabled(
        self, temp_minify_json, monkeypatch
    ):
        """Test that states use full names when env var is disabled even with minify.json."""
        monkeypatch.setenv(
            environment.REFLEX_MINIFY_STATES.name, MinifyMode.DISABLED.value
        )

        class TestState(BaseState):
            pass

        state_path = get_state_full_path(TestState)
        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {state_path: "f"},
            "events": {},
        }
        save_minify_config(config)
        clear_config_cache()
        TestState.get_name.cache_clear()

        name = TestState.get_name()

        # Should be the full name, not minified
        assert name != "f"
        assert "test_state" in name.lower()


class TestEventMinification:
    """Tests for event handler name minification with minify.json."""

    def test_event_uses_full_name_without_config(self, temp_minify_json):
        """Test that event handlers use full names when no minify.json exists."""
        import reflex as rx
        from reflex.utils.format import get_event_handler_parts

        class TestState(BaseState):
            @rx.event
            def my_handler(self):
                pass

        TestState.get_name.cache_clear()
        handler = TestState.event_handlers["my_handler"]
        _, event_name = get_event_handler_parts(handler)

        # Should use full name
        assert event_name == "my_handler"

    def test_event_uses_minified_name_with_config(self, temp_minify_json, monkeypatch):
        """Test that event handlers use minified names when minify.json exists and env var is enabled."""
        import reflex as rx
        from reflex.utils.format import get_event_handler_parts

        monkeypatch.setenv(
            environment.REFLEX_MINIFY_EVENTS.name, MinifyMode.ENABLED.value
        )

        # First, set up the config BEFORE creating the state class
        # The event_id_to_name registry is built during __init_subclass__
        # so the config must exist before the class is defined

        # For this test, we extend State (not BaseState) so that
        # get_event_handler_parts can look up our state in the State tree.
        # We need to include State's full path in our config too.

        # The state path includes the full class hierarchy from State.
        # For a direct subclass of State defined in this test module,
        # get_state_full_path returns: "tests.units.test_minification.State.TestStateWithMinifiedEvent"
        # (module + class hierarchy from root state to leaf)

        expected_module = "tests.units.test_minification"
        expected_state_path = f"{expected_module}.State.TestStateWithMinifiedEvent"

        # Also need to include the base State in the config (v2 format with nested events)
        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {
                "reflex.state.State": "a",  # Base State
                expected_state_path: "b",  # Our test state
            },
            "events": {
                expected_state_path: {"my_handler": "d"},  # Nested under state path
            },
        }
        save_minify_config(config)
        clear_config_cache()
        State.get_name.cache_clear()
        State.get_full_name.cache_clear()
        State.get_class_substate.cache_clear()

        # Now create the state class extending State - it will pick up the config
        class TestStateWithMinifiedEvent(State):
            @rx.event
            def my_handler(self):
                pass

        # Verify the path matches what we expected
        actual_path = get_state_full_path(TestStateWithMinifiedEvent)
        assert actual_path == expected_state_path, (
            f"Expected path {expected_state_path}, got {actual_path}"
        )

        # The active resolver should map this handler to its minified name.
        assert _resolved_event_id(TestStateWithMinifiedEvent, "my_handler") == "d"

        handler = TestStateWithMinifiedEvent.event_handlers["my_handler"]
        _, event_name = get_event_handler_parts(handler)

        # Should be the minified name directly
        assert event_name == "d"

    def test_event_uses_full_name_when_env_disabled(
        self, temp_minify_json, monkeypatch
    ):
        """Test that event handlers use full names when env var is disabled even with minify.json."""
        import reflex as rx
        from reflex.utils.format import get_event_handler_parts

        monkeypatch.setenv(
            environment.REFLEX_MINIFY_EVENTS.name, MinifyMode.DISABLED.value
        )

        expected_module = "tests.units.test_minification"
        expected_state_path = (
            f"{expected_module}.State.TestStateWithMinifiedEventDisabled"
        )

        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {
                "reflex.state.State": "a",
                expected_state_path: "b",
            },
            "events": {
                expected_state_path: {"my_handler": "d"},
            },
        }
        save_minify_config(config)
        clear_config_cache()
        State.get_name.cache_clear()
        State.get_full_name.cache_clear()
        State.get_class_substate.cache_clear()

        class TestStateWithMinifiedEventDisabled(State):
            @rx.event
            def my_handler(self):
                pass

        # When env var is disabled, the resolver yields no minified name.
        assert (
            _resolved_event_id(TestStateWithMinifiedEventDisabled, "my_handler") is None
        )

        handler = TestStateWithMinifiedEventDisabled.event_handlers["my_handler"]
        _, event_name = get_event_handler_parts(handler)

        # Should use full name
        assert event_name == "my_handler"


class TestDynamicHandlerMinification:
    """Tests for dynamic event handler minification (setvar, auto-setters)."""

    def test_setvar_registered_with_config(self, temp_minify_json, monkeypatch):
        """Test that ``setvar`` is resolvable to its minified name."""
        monkeypatch.setenv(
            environment.REFLEX_MINIFY_EVENTS.name, MinifyMode.ENABLED.value
        )
        expected_module = "tests.units.test_minification"
        expected_state_path = f"{expected_module}.State.TestStateWithSetvar"

        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {
                "reflex.state.State": "a",
                expected_state_path: "b",
            },
            "events": {
                expected_state_path: {"setvar": "s"},
            },
        }
        save_minify_config(config)
        clear_config_cache()
        State.get_name.cache_clear()
        State.get_full_name.cache_clear()
        State.get_class_substate.cache_clear()

        class TestStateWithSetvar(State):
            pass

        # The active resolver should report setvar's minified id.
        assert _resolved_event_id(TestStateWithSetvar, "setvar") == "s"

    def test_auto_setter_registered_with_config(self, temp_minify_json, monkeypatch):
        """Test that auto-setters (set_*) are resolvable to their minified name."""
        from reflex_base import config as base_config

        monkeypatch.setenv(
            environment.REFLEX_MINIFY_EVENTS.name, MinifyMode.ENABLED.value
        )
        # state_auto_setters is False by default; force it on so that
        # `_init_var` actually creates the setter we want to verify.
        real_get_config = base_config.get_config

        def _mock_get_config(*args, **kwargs):
            cfg = real_get_config(*args, **kwargs)
            cfg.state_auto_setters = True
            return cfg

        monkeypatch.setattr(base_config, "get_config", _mock_get_config)
        expected_module = "tests.units.test_minification"
        expected_state_path = f"{expected_module}.State.TestStateWithAutoSetter"

        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {
                "reflex.state.State": "a",
                expected_state_path: "b",
            },
            "events": {
                expected_state_path: {"set_count": "c", "setvar": "v"},
            },
        }
        save_minify_config(config)
        clear_config_cache()
        State.get_name.cache_clear()
        State.get_full_name.cache_clear()
        State.get_class_substate.cache_clear()

        class TestStateWithAutoSetter(State):
            count: int = 0

        # The auto-setter should resolve to the minified id from the config.
        assert _resolved_event_id(TestStateWithAutoSetter, "set_count") == "c"

    def test_dynamic_handlers_not_registered_without_config(self, temp_minify_json):
        """Test that dynamic handlers have no resolved minified name without config."""
        # No config saved - temp_minify_json fixture ensures clean state

        class TestStateNoConfig(State):
            count: int = 0

        # Without config, the resolver returns None for every handler.
        for handler_name in TestStateNoConfig.event_handlers:
            assert _resolved_event_id(TestStateNoConfig, handler_name) is None

    def test_add_event_handler_registered_with_config(
        self, temp_minify_json, monkeypatch
    ):
        """Test that dynamically added event handlers via _add_event_handler are registered."""
        import reflex as rx

        monkeypatch.setenv(
            environment.REFLEX_MINIFY_EVENTS.name, MinifyMode.ENABLED.value
        )
        expected_module = "tests.units.test_minification"
        expected_state_path = f"{expected_module}.State.TestStateWithDynamicHandler"

        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {
                "reflex.state.State": "a",
                expected_state_path: "b",
            },
            "events": {
                expected_state_path: {"dynamic_handler": "d", "setvar": "v"},
            },
        }
        save_minify_config(config)
        clear_config_cache()
        State.get_name.cache_clear()
        State.get_full_name.cache_clear()
        State.get_class_substate.cache_clear()

        class TestStateWithDynamicHandler(State):
            pass

        # Dynamically add an event handler after class creation
        @rx.event
        def dynamic_handler(self):
            pass

        TestStateWithDynamicHandler._add_event_handler(
            "dynamic_handler", dynamic_handler
        )

        # Dynamically-added handlers are resolved through the same resolver,
        # so the new name picks up the minified id without re-registering.
        assert _resolved_event_id(TestStateWithDynamicHandler, "dynamic_handler") == "d"

    def test_component_state_picks_up_minified_name(
        self, temp_minify_json, monkeypatch
    ):
        """``ComponentState.create()`` instances are real state classes too.

        They register via ``__init_subclass__`` like any other state, so as
        long as the minify resolver is installed before ``create()`` runs,
        the resulting class gets the minified name from ``minify.json``.
        """
        import reflex as rx

        monkeypatch.setenv(
            environment.REFLEX_MINIFY_STATES.name, MinifyMode.ENABLED.value
        )
        monkeypatch.setenv(
            environment.REFLEX_MINIFY_EVENTS.name, MinifyMode.ENABLED.value
        )

        # ComponentState.create() builds a new class via ``type(...)`` with
        # ``__module__ = "reflex.istate.dynamic"`` and a ``_n<count>`` suffix,
        # so the path under which the resolver will look it up is fully
        # determined ahead of time.
        instance_count = rx.ComponentState._per_component_state_instance_count + 1
        instance_path = (
            f"reflex.istate.dynamic.State.ComponentStateMinifyExample_n{instance_count}"
        )

        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {
                "reflex.state.State": "a",
                instance_path: "z",
            },
            "events": {
                instance_path: {"increment": "i", "setvar": "s"},
            },
        }
        save_minify_config(config)
        clear_config_cache()

        class ComponentStateMinifyExample(rx.ComponentState):
            count: int = 0

            @rx.event
            def increment(self):
                self.count += 1

            @classmethod
            def get_component(cls, **props):
                return rx.fragment()

        ComponentStateMinifyExample.create()
        instance_cls = next(
            cls
            for cls in RegistrationContext.get().base_states.values()
            if cls.__name__ == f"ComponentStateMinifyExample_n{instance_count}"
        )

        assert instance_cls.get_name() == "z"
        assert _resolved_event_id(instance_cls, "increment") == "i"

    def test_state_created_after_resolver_install_uses_minified_name(
        self, temp_minify_json, monkeypatch
    ):
        """A state class created after the resolver is installed gets its
        minified name at registration time — no later refresh needed.

        This is the path exercised by ``ComponentState.create()`` and any
        locally-defined state inside a page function: the class doesn't
        exist when ``minify.json`` is loaded, so the resolver must be
        consulted lazily on first lookup.
        """
        monkeypatch.setenv(
            environment.REFLEX_MINIFY_STATES.name, MinifyMode.ENABLED.value
        )
        late_path = "tests.units.test_minification.State.LateBornState"
        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {late_path: "lb"},
            "events": {},
        }
        save_minify_config(config)
        clear_config_cache()  # installs the MinifyNameResolver

        class LateBornState(State):
            pass

        # Newly-registered class is keyed by its minified name in the registry.
        ctx = RegistrationContext.get()
        assert LateBornState.get_name() == "lb"
        # State stays un-minified, so the parent prefix is its default snake form.
        assert ctx.base_states.get(f"{State.get_full_name()}.lb") is LateBornState


class TestMinifyModeEnvVars:
    """Tests for REFLEX_MINIFY_STATES and REFLEX_MINIFY_EVENTS env vars."""

    def test_state_minify_disabled_by_default(self, temp_minify_json):
        """Test that state minification is disabled by default."""
        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {"test.module.MyState": "a"},
            "events": {},
        }
        save_minify_config(config)
        clear_config_cache()

        assert is_state_minify_enabled() is False

    def test_event_minify_disabled_by_default(self, temp_minify_json):
        """Test that event minification is disabled by default."""
        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {},
            "events": {"test.module.MyState": {"handler": "a"}},
        }
        save_minify_config(config)
        clear_config_cache()

        assert is_event_minify_enabled() is False

    def test_state_minify_enabled_with_env_and_config(
        self, temp_minify_json, monkeypatch
    ):
        """Test that state minification is enabled when env var is enabled and config exists."""
        monkeypatch.setenv(
            environment.REFLEX_MINIFY_STATES.name, MinifyMode.ENABLED.value
        )
        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {"test.module.MyState": "a"},
            "events": {},
        }
        save_minify_config(config)
        clear_config_cache()

        assert is_state_minify_enabled() is True

    def test_event_minify_enabled_with_env_and_config(
        self, temp_minify_json, monkeypatch
    ):
        """Test that event minification is enabled when env var is enabled and config exists."""
        monkeypatch.setenv(
            environment.REFLEX_MINIFY_EVENTS.name, MinifyMode.ENABLED.value
        )
        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {},
            "events": {"test.module.MyState": {"handler": "a"}},
        }
        save_minify_config(config)
        clear_config_cache()

        assert is_event_minify_enabled() is True

    def test_state_minify_disabled_without_config(self, temp_minify_json, monkeypatch):
        """Test that state minification is disabled when env var is enabled but no config exists."""
        monkeypatch.setenv(
            environment.REFLEX_MINIFY_STATES.name, MinifyMode.ENABLED.value
        )
        clear_config_cache()

        assert is_state_minify_enabled() is False

    def test_event_minify_disabled_without_config(self, temp_minify_json, monkeypatch):
        """Test that event minification is disabled when env var is enabled but no config exists."""
        monkeypatch.setenv(
            environment.REFLEX_MINIFY_EVENTS.name, MinifyMode.ENABLED.value
        )
        clear_config_cache()

        assert is_event_minify_enabled() is False

    def test_independent_state_and_event_toggles(self, temp_minify_json, monkeypatch):
        """Test that state and event minification can be toggled independently."""
        monkeypatch.setenv(
            environment.REFLEX_MINIFY_STATES.name, MinifyMode.ENABLED.value
        )
        monkeypatch.setenv(
            environment.REFLEX_MINIFY_EVENTS.name, MinifyMode.DISABLED.value
        )
        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {"test.module.MyState": "a"},
            "events": {"test.module.MyState": {"handler": "a"}},
        }
        save_minify_config(config)
        clear_config_cache()

        assert is_state_minify_enabled() is True
        assert is_event_minify_enabled() is False
        assert is_minify_enabled() is True

    def test_is_minify_enabled_true_when_either_enabled(
        self, temp_minify_json, monkeypatch
    ):
        """Test that is_minify_enabled returns True when either state or event is enabled."""
        monkeypatch.setenv(
            environment.REFLEX_MINIFY_STATES.name, MinifyMode.DISABLED.value
        )
        monkeypatch.setenv(
            environment.REFLEX_MINIFY_EVENTS.name, MinifyMode.ENABLED.value
        )
        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {},
            "events": {"test.module.MyState": {"handler": "a"}},
        }
        save_minify_config(config)
        clear_config_cache()

        assert is_minify_enabled() is True

    def test_is_minify_enabled_false_when_both_disabled(self, temp_minify_json):
        """Test that is_minify_enabled returns False when both are disabled (default)."""
        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {"test.module.MyState": "a"},
            "events": {"test.module.MyState": {"handler": "a"}},
        }
        save_minify_config(config)
        clear_config_cache()

        assert is_minify_enabled() is False


class TestMinifiedNameCollision:
    """Tests for parent-child minified name collision in substate resolution."""

    def test_get_class_substate_with_parent_child_name_collision(
        self, temp_minify_json, monkeypatch
    ):
        """Test that get_class_substate resolves correctly when parent and child
        share the same minified name (IDs are only sibling-unique).
        """
        monkeypatch.setenv(
            environment.REFLEX_MINIFY_STATES.name, MinifyMode.ENABLED.value
        )

        # Build a hierarchy: State -> ParentClassSubstateCollision ->
        # ChildClassSubstateCollision where both children minify to "b".
        # Class names are deliberately unique so ``_handle_local_def`` does
        # not append a numeric suffix when run alongside other tests that
        # might also define a ``ParentState``.
        class ParentClassSubstateCollision(State):
            pass

        class ChildClassSubstateCollision(ParentClassSubstateCollision):
            pass

        parent_path = get_state_full_path(ParentClassSubstateCollision)
        child_path = get_state_full_path(ChildClassSubstateCollision)

        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {
                parent_path: "b",
                child_path: "b",  # Same minified name as parent
            },
            "events": {},
        }
        save_minify_config(config)
        # ``clear_config_cache`` resets the per-class name caches and re-keys
        # the registry under the new minified names.
        clear_config_cache()

        # Verify both get the same minified name
        assert ParentClassSubstateCollision.get_name() == "b"
        assert ChildClassSubstateCollision.get_name() == "b"

        # Full path is ``State.b.b`` (State stays un-minified).
        state_prefix = State.get_full_name()
        assert ChildClassSubstateCollision.get_full_name() == f"{state_prefix}.b.b"

        # get_class_substate should resolve <state>.b.b to the child, not parent.
        resolved = State.get_class_substate(f"{state_prefix}.b.b")
        assert resolved is ChildClassSubstateCollision

    def test_get_substate_with_parent_child_name_collision(
        self, temp_minify_json, monkeypatch
    ):
        """Test that get_substate (instance method) resolves correctly when parent
        and child share the same minified name.
        """
        import reflex as rx

        monkeypatch.setenv(
            environment.REFLEX_MINIFY_STATES.name, MinifyMode.ENABLED.value
        )

        # Class names are deliberately unique so ``_handle_local_def`` does
        # not append a numeric suffix when run alongside other tests that
        # might also define a ``ParentState2``.
        class ParentInstanceSubstateCollision(State):
            pass

        class ChildInstanceSubstateCollision(ParentInstanceSubstateCollision):
            @rx.event
            def my_handler(self):
                pass

        parent_path = get_state_full_path(ParentInstanceSubstateCollision)
        child_path = get_state_full_path(ChildInstanceSubstateCollision)

        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {
                parent_path: "b",
                child_path: "b",  # Same minified name as parent
            },
            "events": {},
        }
        save_minify_config(config)
        # ``clear_config_cache`` resets the per-class name caches and re-keys
        # the registry under the new minified names.
        clear_config_cache()

        # Create a state instance tree
        root = State(_reflex_internal_init=True)  # type: ignore[call-arg]

        # Instance get_substate should resolve <state>.b.b to the collision child.
        resolved = root.get_substate([State.get_name(), "b", "b"])
        assert type(resolved) is ChildInstanceSubstateCollision


class TestMinifyLookupCLI:
    """Tests for the 'reflex minify lookup' CLI command."""

    def test_lookup_resolves_minified_path(self, temp_minify_json, monkeypatch):
        """Test that lookup resolves a minified path to full state info."""
        from unittest import mock

        from click.testing import CliRunner

        from reflex.reflex import cli
        from reflex.utils import prerequisites

        # Create test states
        class AppState(State):
            pass

        class ChildState(AppState):
            pass

        app_state_path = get_state_full_path(AppState)
        child_state_path = get_state_full_path(ChildState)

        # Create minify.json with known mappings
        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {
                "reflex.state.State": "a",
                app_state_path: "b",
                child_state_path: "c",
            },
            "events": {},
        }
        save_minify_config(config)
        clear_config_cache()

        # Stub the compiled-app loader; the test already populates the registry
        app_module_mock = mock.Mock()
        monkeypatch.setattr(
            prerequisites, "get_compiled_app", lambda *a, **kw: app_module_mock
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["minify", "lookup", "a.b.c"])

        assert result.exit_code == 0, result.output
        # Output should include the module and class names
        assert "State" in result.output
        assert "AppState" in result.output
        assert "ChildState" in result.output

    def test_lookup_fails_without_minify_json(self, temp_minify_json, monkeypatch):
        """Test that lookup fails gracefully when minify.json is missing."""
        from unittest import mock

        from click.testing import CliRunner

        from reflex.reflex import cli
        from reflex.utils import prerequisites

        # Stub the compiled-app loader
        app_module_mock = mock.Mock()
        monkeypatch.setattr(
            prerequisites, "get_compiled_app", lambda *a, **kw: app_module_mock
        )

        # Don't create minify.json
        clear_config_cache()

        runner = CliRunner()
        result = runner.invoke(cli, ["minify", "lookup", "a.b"])

        assert result.exit_code == 1
        assert "minify.json not found" in result.output

    def test_lookup_fails_for_invalid_path(self, temp_minify_json, monkeypatch):
        """Test that lookup fails for non-existent minified path."""
        from unittest import mock

        from click.testing import CliRunner

        from reflex.reflex import cli
        from reflex.utils import prerequisites

        # Create minify.json with only root state
        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {
                "reflex.state.State": "a",
            },
            "events": {},
        }
        save_minify_config(config)
        clear_config_cache()

        # Stub the compiled-app loader
        app_module_mock = mock.Mock()
        monkeypatch.setattr(
            prerequisites, "get_compiled_app", lambda *a, **kw: app_module_mock
        )

        runner = CliRunner()
        # Try to lookup a path that doesn't exist
        result = runner.invoke(cli, ["minify", "lookup", "a.xyz"])

        assert result.exit_code == 1
        assert "No state found" in result.output

    def test_lookup_with_json_output(self, temp_minify_json, monkeypatch):
        """Test that lookup with --json flag outputs valid JSON."""
        from unittest import mock

        from click.testing import CliRunner

        from reflex.reflex import cli
        from reflex.utils import prerequisites

        # Create test state
        class JsonTestState(State):
            pass

        state_path = get_state_full_path(JsonTestState)

        # Create minify.json
        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {
                "reflex.state.State": "a",
                state_path: "b",
            },
            "events": {},
        }
        save_minify_config(config)
        clear_config_cache()

        # Stub the compiled-app loader
        app_module_mock = mock.Mock()
        monkeypatch.setattr(
            prerequisites, "get_compiled_app", lambda *a, **kw: app_module_mock
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["minify", "lookup", "--json", "a.b"])

        assert result.exit_code == 0, result.output
        # Parse output as JSON to verify it's valid
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert len(output_data) == 2  # Root state + JsonTestState
        assert output_data[0]["class"] == "State"
        assert output_data[1]["class"] == "JsonTestState"
        assert output_data[1]["state_id"] == "b"


class TestNameResolverProtocol:
    """Tests for the pluggable :class:`NameResolver` protocol.

    These exercise the contract independent of minification: any resolver that
    implements ``resolve_state_name`` / ``resolve_handler_name`` can be slotted
    into the registration context to rewrite names.
    """

    def test_default_resolver_returns_none(self):
        """The default resolver yields no overrides."""
        resolver = DefaultNameResolver()
        assert resolver.resolve_state_name(State) is None
        assert resolver.resolve_handler_name(State, "any_handler") is None

    def test_default_resolver_satisfies_protocol(self):
        """``DefaultNameResolver`` is a structural :class:`NameResolver`."""
        assert isinstance(DefaultNameResolver(), NameResolver)

    def test_minify_resolver_satisfies_protocol(self):
        """``MinifyNameResolver`` is a structural :class:`NameResolver`."""
        resolver = MinifyNameResolver(
            config=None, states_enabled=False, events_enabled=False
        )
        assert isinstance(resolver, NameResolver)

    def test_get_state_name_falls_back_to_default(self):
        """``RegistrationContext.get_state_name`` returns the built-in name when
        the resolver returns None (the default).
        """
        ctx = RegistrationContext.get()
        assert ctx.get_state_name(State) == RegistrationContext.default_state_name(
            State
        )

    def test_get_handler_name_falls_back_to_default(self):
        """``RegistrationContext.get_handler_name`` returns the input name when
        the resolver returns None (the default).
        """
        ctx = RegistrationContext.get()
        assert ctx.get_handler_name(State, "some_handler") == "some_handler"

    def test_set_name_resolver_propagates_through_get_name(self, monkeypatch):
        """Installing a custom resolver swaps ``BaseState.get_name`` output.

        The resolver overrides only ``State`` so other registered classes
        retain their default names — without this scoping, every class would
        collapse to one entry in the registry's name-keyed dicts.
        """

        class FixedStateNameResolver:
            def resolve_state_name(self, state_cls):
                return "fixed_name" if state_cls is State else None

            def resolve_handler_name(self, state_cls, handler_name):
                return None

        ctx = RegistrationContext.get()
        original = ctx.name_resolver
        try:
            ctx.set_name_resolver(FixedStateNameResolver())
            assert State.get_name() == "fixed_name"
        finally:
            ctx.set_name_resolver(original)

    def test_set_name_resolver_propagates_through_format_event_handler(self):
        """Installing a custom resolver swaps the formatted handler name."""
        from reflex.state import OnLoadInternalState
        from reflex.utils.format import format_event_handler

        class HandlerPrefixResolver:
            def resolve_state_name(self, state_cls):
                return None

            def resolve_handler_name(self, state_cls, handler_name):
                return f"px_{handler_name}"

        ctx = RegistrationContext.get()
        original = ctx.name_resolver
        try:
            ctx.set_name_resolver(HandlerPrefixResolver())
            formatted = format_event_handler(OnLoadInternalState.on_load_internal)  # pyright: ignore[reportArgumentType]
            assert formatted.endswith(".px_on_load_internal")
        finally:
            ctx.set_name_resolver(original)

    def test_resolver_swap_clears_lru_caches(self):
        """``set_name_resolver`` invalidates per-class name caches so that
        ``get_full_name`` reflects the new resolver immediately.
        """

        class A:
            def resolve_state_name(self, state_cls):
                return "first" if state_cls is State else None

            def resolve_handler_name(self, state_cls, handler_name):
                return None

        class B:
            def resolve_state_name(self, state_cls):
                return "second" if state_cls is State else None

            def resolve_handler_name(self, state_cls, handler_name):
                return None

        ctx = RegistrationContext.get()
        original = ctx.name_resolver
        try:
            ctx.set_name_resolver(A())
            assert State.get_full_name() == "first"
            ctx.set_name_resolver(B())
            assert State.get_full_name() == "second"
        finally:
            ctx.set_name_resolver(original)

    def test_chain_of_resolvers(self):
        """Resolvers compose with a tiny user-written chain wrapper."""

        class Chain:
            """Returns the first non-None override from the wrapped resolvers."""

            def __init__(self, *resolvers):
                self.resolvers = resolvers

            def resolve_state_name(self, state_cls):
                for r in self.resolvers:
                    v = r.resolve_state_name(state_cls)
                    if v is not None:
                        return v
                return None

            def resolve_handler_name(self, state_cls, handler_name):
                for r in self.resolvers:
                    v = r.resolve_handler_name(state_cls, handler_name)
                    if v is not None:
                        return v
                return None

        class FirstOnly:
            def resolve_state_name(self, state_cls):
                return "from_first" if state_cls is State else None

            def resolve_handler_name(self, state_cls, handler_name):
                return None

        ctx = RegistrationContext.get()
        original = ctx.name_resolver
        try:
            ctx.set_name_resolver(Chain(FirstOnly(), DefaultNameResolver()))
            assert State.get_name() == "from_first"
        finally:
            ctx.set_name_resolver(original)


class TestMinifyNameResolver:
    """Tests for :class:`MinifyNameResolver` itself (config + caching)."""

    def test_disabled_returns_none(self, temp_minify_json):
        """When neither flag is enabled, the resolver returns None for all."""
        resolver = MinifyNameResolver(
            config={"version": SCHEMA_VERSION, "states": {}, "events": {}},
            states_enabled=False,
            events_enabled=False,
        )
        assert resolver.resolve_state_name(State) is None
        assert resolver.resolve_handler_name(State, "any") is None

    def test_no_config_returns_none(self):
        """No config means no overrides even when flags are enabled."""
        resolver = MinifyNameResolver(
            config=None, states_enabled=True, events_enabled=True
        )
        assert resolver.resolve_state_name(State) is None
        assert resolver.resolve_handler_name(State, "any") is None

    def test_state_lookup_caches(self):
        """Resolved state names are memoized after the first lookup."""

        # Non-framework state — see :func:`_is_framework_state`.
        class UserStateResolverCacheTest(State):
            pass

        config: MinifyConfig = {
            "version": SCHEMA_VERSION,
            "states": {get_state_full_path(UserStateResolverCacheTest): "rs"},
            "events": {},
        }
        resolver = MinifyNameResolver(
            config=config, states_enabled=True, events_enabled=False
        )
        assert resolver.resolve_state_name(UserStateResolverCacheTest) == "rs"
        # second call hits the cache
        assert UserStateResolverCacheTest in resolver._state_cache
        assert resolver.resolve_state_name(UserStateResolverCacheTest) == "rs"

    def test_event_lookup_caches(self):
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

    def test_from_disk_handles_malformed_config(self, temp_minify_json):
        """``from_disk`` returns a usable resolver even when minify.json is bad."""
        path = temp_minify_json / MINIFY_JSON
        with path.open("w") as f:
            f.write("{not valid json")
        resolver = MinifyNameResolver.from_disk()
        # config falls back to None — every lookup returns None.
        assert resolver.config is None
        assert resolver.resolve_state_name(State) is None
        assert resolver.resolve_handler_name(State, "any") is None
