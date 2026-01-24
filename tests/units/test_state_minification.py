"""Unit tests for state name minification."""

from __future__ import annotations

import pytest

from reflex.environment import StateMinifyMode, environment
from reflex.state import BaseState, _int_to_minified_name, _state_id_registry
from reflex.utils.exceptions import StateValueError


@pytest.fixture(autouse=True)
def reset_state_registry():
    """Reset the state_id registry before and after each test."""
    _state_id_registry.clear()
    yield
    _state_id_registry.clear()


@pytest.fixture
def reset_minify_mode():
    """Reset REFLEX_MINIFY_STATES to DISABLED after each test."""
    original = environment.REFLEX_MINIFY_STATES.get()
    yield
    environment.REFLEX_MINIFY_STATES.set(original)


class TestIntToMinifiedName:
    """Tests for _int_to_minified_name function."""

    def test_zero(self):
        """Test that 0 maps to 'a'."""
        assert _int_to_minified_name(0) == "a"

    def test_single_char(self):
        """Test single character mappings."""
        assert _int_to_minified_name(1) == "b"
        assert _int_to_minified_name(25) == "z"
        assert _int_to_minified_name(26) == "A"
        assert _int_to_minified_name(51) == "Z"
        assert _int_to_minified_name(52) == "$"
        assert _int_to_minified_name(53) == "_"

    def test_two_chars(self):
        """Test two character mappings (base 54)."""
        # 54 = 1*54 + 0 -> 'ba'
        assert _int_to_minified_name(54) == "ba"
        # 55 = 1*54 + 1 -> 'bb'
        assert _int_to_minified_name(55) == "bb"

    def test_unique_names(self):
        """Test that a large range of IDs produce unique names."""
        names = set()
        for i in range(10000):
            name = _int_to_minified_name(i)
            assert name not in names, f"Duplicate name {name} for id {i}"
            names.add(name)


class TestStateIdValidation:
    """Tests for state_id validation in __init_subclass__."""

    def test_state_with_explicit_id(self):
        """Test that a state can be created with an explicit state_id."""

        class TestState(BaseState, state_id=100):
            pass

        assert TestState._state_id == 100
        assert 100 in _state_id_registry
        assert _state_id_registry[100] is TestState

    def test_state_without_id(self):
        """Test that a state can be created without state_id."""

        class TestState(BaseState):
            pass

        assert TestState._state_id is None

    def test_duplicate_state_id_raises(self):
        """Test that duplicate state_id raises StateValueError."""

        class FirstState(BaseState, state_id=200):
            pass

        with pytest.raises(StateValueError, match="Duplicate state_id=200"):

            class SecondState(BaseState, state_id=200):
                pass


class TestGetNameMinification:
    """Tests for get_name with minification modes."""

    def test_disabled_mode_uses_full_name(self, reset_minify_mode):
        """Test DISABLED mode always uses full name even with state_id."""
        environment.REFLEX_MINIFY_STATES.set(StateMinifyMode.DISABLED)

        class TestState(BaseState, state_id=300):
            pass

        # Clear the lru_cache to get fresh result
        TestState.get_name.cache_clear()

        name = TestState.get_name()
        # Should be full name, not minified
        assert "test_state" in name.lower()
        assert name != _int_to_minified_name(300)

    def test_enabled_mode_with_id_uses_minified(self, reset_minify_mode):
        """Test ENABLED mode with state_id uses minified name."""
        environment.REFLEX_MINIFY_STATES.set(StateMinifyMode.ENABLED)

        class TestState(BaseState, state_id=301):
            pass

        # Clear the lru_cache to get fresh result
        TestState.get_name.cache_clear()

        name = TestState.get_name()
        assert name == _int_to_minified_name(301)

    def test_enabled_mode_without_id_uses_full_name(self, reset_minify_mode):
        """Test ENABLED mode without state_id uses full name."""
        environment.REFLEX_MINIFY_STATES.set(StateMinifyMode.ENABLED)

        class TestState(BaseState):
            pass

        # Clear the lru_cache to get fresh result
        TestState.get_name.cache_clear()

        name = TestState.get_name()
        # Should contain the class name
        assert "test_state" in name.lower()

    def test_enforce_mode_without_id_raises(self, reset_minify_mode):
        """Test ENFORCE mode without state_id raises error during class definition."""
        environment.REFLEX_MINIFY_STATES.set(StateMinifyMode.ENFORCE)

        # Error is raised during class definition because get_name() is called
        # during __init_subclass__
        with pytest.raises(StateValueError, match="missing required state_id"):

            class TestState(BaseState):
                pass

    def test_enforce_mode_with_id_uses_minified(self, reset_minify_mode):
        """Test ENFORCE mode with state_id uses minified name."""
        environment.REFLEX_MINIFY_STATES.set(StateMinifyMode.ENFORCE)

        class TestState(BaseState, state_id=302):
            pass

        # Clear the lru_cache to get fresh result
        TestState.get_name.cache_clear()

        name = TestState.get_name()
        assert name == _int_to_minified_name(302)


class TestMixinState:
    """Tests for mixin states."""

    def test_mixin_no_state_id_required(self, reset_minify_mode):
        """Test that mixin states don't require state_id even in ENFORCE mode."""
        environment.REFLEX_MINIFY_STATES.set(StateMinifyMode.ENFORCE)

        class MixinState(BaseState, mixin=True):
            pass

        # Mixin states should not raise even without state_id
        assert MixinState._state_id is None
        # Mixin states have _mixin = True set, so get_name isn't typically called
        # but the class should be created without error

    def test_mixin_with_state_id_raises(self):
        """Test that mixin states cannot have state_id."""
        with pytest.raises(StateValueError, match="cannot have a state_id"):

            class MixinWithId(BaseState, mixin=True, state_id=999):
                pass
